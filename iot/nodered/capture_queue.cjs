/* Persistent server work queue. Node 20 built-ins only; never uses Node-RED context
 * as durable storage. One Node-RED instance owns a queue directory.
 * MQTT can acknowledge BEFORE enqueue: this is not an end-to-end delivery ACK.
 */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

function syncDirectory(directory) {
    // Windows does not support opening directories this way; production is Linux.
    if (process.platform === 'win32') return;
    const fd = fs.openSync(directory, 'r');
    try { fs.fsyncSync(fd); } finally { fs.closeSync(fd); }
}
function atomicJSON(filename, value) {
    const temporary = filename + '.' + crypto.randomUUID() + '.tmp';
    let fd;
    try {
        fd = fs.openSync(temporary, 'wx', 0o600);
        fs.writeFileSync(fd, JSON.stringify(value));
        fs.fsyncSync(fd);
        fs.closeSync(fd); fd = undefined;
        fs.renameSync(temporary, filename);
        syncDirectory(path.dirname(filename));
    } finally {
        if (fd !== undefined) fs.closeSync(fd);
        if (fs.existsSync(temporary)) fs.unlinkSync(temporary);
    }
}

class CaptureQueue {
    constructor(root, {now = Date.now, leaseMs = 300000} = {}) {
        this.root = path.resolve(root);
        this.now = now;
        this.leaseMs = leaseMs;
        for (const name of ['pending', 'quarantine', 'archive', 'state']) {
            fs.mkdirSync(path.join(this.root, name), {recursive: true, mode: 0o700});
        }
        syncDirectory(this.root);
        syncDirectory(path.dirname(this.root));
    }
    file(folder, id) {
        if (!/^[a-f0-9]{64}$/.test(id)) throw new Error('Invalid queue ID');
        return path.join(this.root, folder, id + '.json');
    }
    readState(id) {
        const file = this.file('state', id);
        return fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, 'utf8')) :
            {id, attempts: 0, receivedAt: fs.statSync(this.file('pending', id)).mtimeMs, nextAttempt: 0};
    }
    saveState(state) { atomicJSON(this.file('state', state.id), state); }
    ids(folder) {
        return fs.readdirSync(path.join(this.root, folder)).filter(f => /^[a-f0-9]{64}\.json$/.test(f))
            .map(f => f.slice(0, -5));
    }
    enqueue(payload, topic = '') {
        const raw = Buffer.isBuffer(payload) ? payload.toString('utf8') :
            typeof payload === 'string' ? payload : JSON.stringify(payload);
        if (typeof raw !== 'string' || !raw.length) throw new Error('Empty MQTT message');
        const id = crypto.createHash('sha256').update(String(topic)).update('\0').update(raw).digest('hex');
        if (['pending', 'quarantine', 'archive'].some(folder => fs.existsSync(this.file(folder, id)))) return id;
        atomicJSON(this.file('pending', id), {version: 1, id, topic: String(topic), raw, receivedAt: this.now()});
        this.saveState({id, attempts: 0, receivedAt: this.now(), nextAttempt: 0});
        return id;
    }
    claim() {
        const states = this.ids('pending').map(id => this.readState(id));
        // Bounded concurrency: one capture/measurement update at a time.
        if (states.some(s => s.leaseUntil > this.now())) return null;
        for (const state of states.sort((a,b) => a.receivedAt - b.receivedAt)) {
            if (state.quarantined) { this.moveToQuarantine(state.id); continue; }
            if (state.nextAttempt > this.now()) continue;
            const envelope = JSON.parse(fs.readFileSync(this.file('pending', state.id), 'utf8'));
            state.attempts += 1;
            state.lease = crypto.randomUUID();
            state.leaseUntil = this.now() + this.leaseMs;
            this.saveState(state);
            return {queueId: state.id, queueLease: state.lease, topic: envelope.topic, payload: envelope.raw};
        }
        return null;
    }
    owned(msg) {
        if (!msg.queueId || !fs.existsSync(this.file('pending', msg.queueId))) return null;
        const state = this.readState(msg.queueId);
        return state.lease === msg.queueLease ? state : null;
    }
    renew(msg) {
        const state = this.owned(msg);
        if (!state || state.quarantined) throw new Error('Queue lease no longer owned');
        state.leaseUntil = this.now() + this.leaseMs;
        this.saveState(state);
    }
    complete(msg) {
        const state = this.owned(msg);
        if (!state) return false; // late result from an expired/replayed attempt
        fs.unlinkSync(this.file('pending', state.id));
        syncDirectory(path.join(this.root, 'pending'));
        fs.unlinkSync(this.file('state', state.id));
        return true;
    }
    moveToQuarantine(id) {
        fs.renameSync(this.file('pending', id), this.file('quarantine', id));
        syncDirectory(path.join(this.root, 'pending'));
        syncDirectory(path.join(this.root, 'quarantine'));
    }
    fail(msg, reason, permanent = false) {
        const state = this.owned(msg);
        if (!state) return false;
        state.lastError = String(reason).slice(0, 2000);
        state.failedAt = this.now();
        state.leaseUntil = 0;
        state.nextAttempt = this.now() + Math.min(300000, 5000 * 2 ** Math.min(state.attempts - 1, 6));
        state.quarantined = permanent;
        this.saveState(state);
        if (permanent) this.moveToQuarantine(state.id);
        return true;
    }
    requeue(id) {
        const source = this.file('quarantine', id);
        if (!fs.existsSync(source)) throw new Error('No quarantined message with that ID');
        const state = this.readState(id);
        Object.assign(state, {quarantined: false, lease: null, leaseUntil: 0, nextAttempt: 0, attempts: 0});
        this.saveState(state);
        fs.renameSync(source, this.file('pending', id));
        syncDirectory(path.join(this.root, 'pending'));
        syncDirectory(path.join(this.root, 'quarantine'));
    }
    archive(id, note) {
        if (!note || !note.trim()) throw new Error('A resolution note is required');
        const source = this.file('quarantine', id);
        if (!fs.existsSync(source)) throw new Error('Only reviewed quarantined work can be archived');
        const state = this.readState(id);
        Object.assign(state, {archivedAt: this.now(), resolution: note, leaseUntil: 0});
        this.saveState(state);
        fs.renameSync(source, this.file('archive', id));
        syncDirectory(path.join(this.root, 'archive'));
        syncDirectory(path.join(this.root, 'quarantine'));
    }
    status() {
        return ['pending', 'quarantine'].flatMap(folder => this.ids(folder).map(id => {
            const s = this.readState(id);
            return {id, folder, attempts: s.attempts, ageSeconds: Math.floor((this.now()-s.receivedAt)/1000),
                lastError: s.lastError || null, leaseUntil: s.leaseUntil || 0};
        }));
    }
}

// Native HTTP chunks keep the whole-capture fingerprint and original timestamps.
function splitLines(lineProtocol, maxPoints = 5000, maxBytes = 4_000_000) {
    if (!Number.isSafeInteger(maxPoints) || maxPoints < 1 || !Number.isSafeInteger(maxBytes) || maxBytes < 1)
        throw new Error('Invalid write batch limits');
    const result = [];
    let chunk = [], bytes = 0;
    for (const line of lineProtocol.split('\n')) {
        const size = Buffer.byteLength(line, 'utf8');
        if (!line || size > maxBytes) throw new Error('Empty or oversized line protocol point');
        if (chunk.length && (chunk.length >= maxPoints || bytes + size + 1 > maxBytes)) {
            result.push(chunk.join('\n')); chunk = []; bytes = 0;
        }
        bytes += size + (chunk.length ? 1 : 0); chunk.push(line);
    }
    if (chunk.length) result.push(chunk.join('\n'));
    return result;
}
let singleton;
function queue() {
    if (!singleton) singleton = new CaptureQueue(process.env.CAPTURE_QUEUE_DIR || '/data/capture-queue');
    return singleton;
}
module.exports = {CaptureQueue, splitLines, queue};

if (require.main === module) {
    try {
        const q = queue();
        const [command = 'status', id, destination] = process.argv.slice(2);
        if (command === 'status' || command === 'health') {
            const status = q.status();
            console.log(JSON.stringify(status, null, 2));
            if (command === 'health' && status.some(s => s.folder === 'quarantine' || s.ageSeconds > 300)) process.exitCode = 1;
        } else if (command === 'requeue') {
            q.requeue(id); console.log('Requeued ' + id);
        } else if (command === 'archive') {
            q.archive(id, destination); console.log('Archived original with resolution note: ' + id);
        } else if (command === 'export' && destination) {
            const file = q.file('quarantine', id);
            const envelope = JSON.parse(fs.readFileSync(file, 'utf8'));
            fs.writeFileSync(destination, envelope.raw, {flag: 'wx', mode: 0o600});
            console.log('Exported original message to ' + destination);
        } else throw new Error('Usage: capture_queue.cjs status|health|requeue ID|archive ID NOTE|export ID NEW_FILE');
    } catch (error) { console.error(error.message); process.exitCode = 1; }
}
