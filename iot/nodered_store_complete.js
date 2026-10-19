// No new client ACK protocol. The server catalog records successful Influx writes.
if (Number(msg.statusCode) !== 204) {
    node.error(`Influx write failed: HTTP ${msg.statusCode}; ${String(msg.payload).slice(0, 300)}`, msg);
    return null;
}
msg.query = "SELECT monitoring.mark_stored($1, $2, $3::bigint, $4) AS stored";
msg.params = [msg.capture.machine_id, msg.capture.session_id, msg.capture.cycle_id, msg.fingerprint];
delete msg.payload;
delete msg.headers;
return msg;
