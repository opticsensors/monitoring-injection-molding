// Continue only after PostgreSQL accepted the immutable manifest and waveform hash.
if (!msg.payload || !msg.payload[0] || !msg.payload[0].fingerprint) {
    node.error("No PostgreSQL capture registration receipt", msg);
    return null;
}
msg.fingerprint = msg.payload[0].fingerprint;
const store = global.get('captureQueue');
if (msg.queueId) store.queue().renew(msg);
msg.writeChunks = store.splitLines(msg.lineProtocol);
msg.chunkIndex = 0;
msg.payload = msg.writeChunks[0];
// Preserve lineProtocol for diagnostics; disk queue holds the original envelope.
delete msg.query;
delete msg.params;
msg.headers = {"Content-Type": "text/plain; charset=utf-8"};
msg.requestTimeout = 30000;
return msg;
