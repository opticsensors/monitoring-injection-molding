// No new client ACK protocol. The server catalog records successful Influx writes.
if (Number(msg.statusCode) !== 204) {
    const status = Number(msg.statusCode);
    msg.ingestPermanent = status >= 400 && status < 500 && status !== 408 && status !== 429;
    node.error(`Influx write failed: HTTP ${msg.statusCode}; ${String(msg.payload).slice(0, 300)}`, msg);
    return null;
}
const store = global.get('captureQueue');
if (msg.queueId) store.queue().renew(msg);
msg.chunkIndex += 1;
if (msg.chunkIndex < msg.writeChunks.length) {
    msg.payload = msg.writeChunks[msg.chunkIndex];
    msg.headers = {"Content-Type": "text/plain; charset=utf-8"};
    delete msg.statusCode;
    return [msg, null];
}
msg.query = "SELECT monitoring.mark_stored($1, $2, $3::bigint, $4) AS stored";
msg.params = [msg.capture.machine_id, msg.capture.session_id, msg.capture.cycle_id, msg.fingerprint];
delete msg.payload;
delete msg.headers;
delete msg.writeChunks;
return [null, msg];
