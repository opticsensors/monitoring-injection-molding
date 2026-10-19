// Continue only after PostgreSQL accepted the immutable manifest and waveform hash.
if (!msg.payload || !msg.payload[0] || !msg.payload[0].fingerprint) {
    node.error("No PostgreSQL capture registration receipt", msg);
    return null;
}
msg.fingerprint = msg.payload[0].fingerprint;
msg.payload = msg.lineProtocol;
delete msg.lineProtocol;
delete msg.query;
delete msg.params;
msg.headers = {"Content-Type": "text/plain; charset=utf-8"};
return msg;
