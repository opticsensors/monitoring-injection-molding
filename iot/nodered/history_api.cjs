// Read-only history endpoints. PostgreSQL reader credentials stay on the server.
const fs = require('node:fs');
const http = require('node:http');
const crypto = require('node:crypto');
const {createRequire} = require('node:module');

class RequestError extends Error {
    constructor(status, message) { super(message); this.status = status; }
}
const literal = value => "'" + String(value).replace(/\\/g, '\\\\').replace(/'/g, "\\'") + "'";
const fieldName = name => /^CH\d+_[A-Za-z0-9_]+$/.test(name);
function identity(query) {
    const {machine_id: machine, session_id: session, cycle_id: cycle} = query;
    if (typeof machine !== 'string' || !machine.length || machine.length > 128 ||
        typeof session !== 'string' || !session.length || session.length > 200 ||
        /[\x00-\x1f\x7f]/.test(machine + session) ||
        typeof cycle !== 'string' || !/^[0-9]{1,16}$/.test(cycle) ||
        !Number.isSafeInteger(Number(cycle)) || Number(cycle) < 1) {
        throw new RequestError(400, 'Invalid cycle identity.');
    }
    return [machine, session, cycle];
}
function predicate(c) {
    if (![c.first_time_ns, c.last_time_ns].every(v => typeof v === 'string' && /^[0-9]{1,19}$/.test(v))) {
        throw new RequestError(409, 'Capture has invalid time bounds.');
    }
    return `"machine_id" = ${literal(c.machine_id)} AND "session_id" = ${literal(c.session_id)}` +
        ` AND "cycle_num" = ${Number(c.cycle_id)} AND time >= ${c.first_time_ns} AND time <= ${c.last_time_ns}`;
}
function rows(document) {
    const results = document.results || document;
    if (!Array.isArray(results) || results.some(r => r.error)) throw new Error('Influx query failed');
    return results.flatMap(r => (r.series || []).flatMap(s =>
        (s.values || []).map(values => Object.fromEntries(s.columns.map((name, i) => [name, values[i]])))));
}
function influxQuery(query) {
    return new Promise((resolve, reject) => {
        const url = new URL('http://influxdb:8086/query');
        url.searchParams.set('db', 'sensor_data');
        url.searchParams.set('q', query);
        const request = http.get(url, response => {
            if (response.statusCode !== 200) {
                response.resume();
                reject(new Error('Influx request failed'));
                return;
            }
            const chunks = [];
            let size = 0;
            response.on('data', chunk => {
                size += chunk.length;
                if (size > 60 * 1024 * 1024) request.destroy(new Error('Waveform response too large'));
                else chunks.push(chunk);
            });
            response.on('error', reject);
            response.on('end', () => {
                try { resolve(JSON.parse(Buffer.concat(chunks))); } catch (e) { reject(e); }
            });
        });
        request.setTimeout(25000, () => request.destroy(new Error('Influx timeout')));
        request.on('error', reject);
    });
}

function createApi({config, query, influx = influxQuery}) {
    const summaries = new Map();
    let knownFields = null, fieldsAt = 0;
    async function fields(c) {
        const recorded = c.config_snapshot?.field_names;
        if (Array.isArray(recorded) && recorded.length && recorded.every(fieldName)) return recorded;
        // Legacy points already contain converted values. Infer channel types from field names.
        if (!knownFields || Date.now() - fieldsAt > 300000) {
            knownFields = rows(await influx('SHOW FIELD KEYS FROM "sensor_data"'))
                .map(r => r.fieldKey).filter(fieldName).sort();
            fieldsAt = Date.now();
        }
        if (!knownFields.length) throw new RequestError(404, 'No recorded channels found.');
        return knownFields;
    }
    async function summary(entry) {
        const c = entry.capture;
        if (c.signal_peaks) return {signal_peaks: c.signal_peaks};
        if (!['stored', 'legacy'].includes(entry.waveform_status)) return {};
        const key = JSON.stringify([c.machine_id, c.session_id, c.cycle_id]);
        if (!summaries.has(key)) {
            const names = await fields(c);
            const select = names.map(f => `max("${f}") AS "${f}"`).join(',');
            const result = rows(await influx(`SELECT ${select} FROM "autogen"."sensor_data" WHERE ${predicate(c)}`));
            const peaks = Object.fromEntries(names.map(f => [f, result[0]?.[f] ?? null]));
            summaries.set(key, {signal_peaks: peaks});
            if (summaries.size > 10000) summaries.delete(summaries.keys().next().value);
        }
        return summaries.get(key);
    }
    async function handle(request) {
        const headers = {'Content-Type': 'application/json', 'Cache-Control': 'no-store'};
        try {
            const expected = Buffer.from('Bearer ' + config.token);
            const supplied = Buffer.from(String(request.authorization || ''));
            if (!config.token || expected.length !== supplied.length || !crypto.timingSafeEqual(expected, supplied)) {
                throw new RequestError(401, 'History access denied.');
            }
            if (request.method !== 'GET') throw new RequestError(405, 'Read-only endpoint.');
            const params = request.query || {};
            if (request.path === '/monitoring/history') {
                let cursor = null;
                if (params.cursor) {
                    if (typeof params.cursor !== 'string' || params.cursor.length > 2048) {
                        throw new RequestError(400, 'Invalid history cursor.');
                    }
                    try { cursor = JSON.parse(Buffer.from(params.cursor, 'base64url').toString()); }
                    catch { throw new RequestError(400, 'Invalid history cursor.'); }
                    if (!Array.isArray(cursor) || cursor.length !== 4 || !cursor.every(v => typeof v === 'string') ||
                        !/^\d{1,19}$/.test(cursor[0])) throw new RequestError(400, 'Invalid history cursor.');
                    identity({machine_id:cursor[1], session_id:cursor[2], cycle_id:cursor[3]});
                }
                const response = await query(`SELECT capture,measurements,waveform_status,first_time_ns::text AS stamp
                    FROM monitoring.history_records
                    ${cursor ? 'WHERE (first_time_ns,machine_id,session_id,cycle_id) < ($1::bigint,$2,$3,$4::bigint)' : ''}
                    ORDER BY first_time_ns DESC,machine_id DESC,session_id DESC,cycle_id DESC LIMIT 51`, cursor || []);
                const page = response.rows.slice(0, 50);
                const cycles = [];
                for (const entry of page) {
                    const features = await summary(entry);
                    cycles.push({capture:entry.capture,measurements:entry.measurements,summary:features,
                        waveform_status:entry.waveform_status,delivery:'Server: '+entry.waveform_status});
                }
                const last = page.at(-1);
                const next = response.rows.length > 50 ? Buffer.from(JSON.stringify([
                    last.stamp,last.capture.machine_id,last.capture.session_id,String(last.capture.cycle_id)
                ])).toString('base64url') : null;
                return {status:200,headers,body:{cycles,next_cursor:next}};
            }
            if (request.path === '/monitoring/waveform') {
                const key = identity(params);
                const response = await query(`SELECT capture,waveform_status FROM monitoring.history_records
                    WHERE machine_id=$1 AND session_id=$2 AND cycle_id=$3::bigint`, key);
                const entry = response.rows[0];
                if (!entry || !['stored','legacy'].includes(entry.waveform_status)) {
                    throw new RequestError(404, 'Stored waveform unavailable.');
                }
                const c = entry.capture;
                if (!Number.isSafeInteger(c.sample_count) || c.sample_count < 1 || c.sample_count > 1000000) {
                    throw new RequestError(413, 'Capture exceeds the interactive viewer limit.');
                }
                const names = await fields(c);
                const data = rows(await influx(`SELECT "t_ms",${names.map(f=>`"${f}"`).join(',')}
                    FROM "autogen"."sensor_data" WHERE ${predicate(c)} ORDER BY time ASC LIMIT ${c.sample_count+1}`));
                if (data.length !== c.sample_count || data.some(r => !Number.isFinite(r.t_ms))) {
                    throw new RequestError(409, 'Waveform does not match its catalog count/timing.');
                }
                return {status:200,headers,body:{fields:names,time_s:data.map(r=>r.t_ms/1000),
                    values:Object.fromEntries(names.map(f=>[f,data.map(r=>r[f] ?? null)]))}};
            }
            throw new RequestError(404, 'Unknown history endpoint.');
        } catch (error) {
            return {status:error.status || 503,headers,
                body:{error:error.status ? error.message : 'History service unavailable. Check server logs and database access.'}};
        }
    }
    return {handle};
}

let api;
function runtime() {
    if (!api) {
        const config = JSON.parse(fs.readFileSync(process.env.MONITORING_HISTORY_CONFIG || '/data/history-access.json','utf8'));
        const manifest = require.resolve('node-red-contrib-postgresql/package.json',
            {paths:['/data','/usr/src/node-red']});
        const {Pool} = createRequire(manifest)('pg');
        const pool = new Pool({...config.database,max:2,connectionTimeoutMillis:10000,statement_timeout:15000});
        pool.on('error', () => console.warn('History reader: PostgreSQL connection interrupted.'));
        api = createApi({config,query:(sql,params)=>pool.query(sql,params)});
    }
    return api;
}
module.exports = {createApi, predicate, rows, handle: request => runtime().handle(request)};
