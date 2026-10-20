// Separate read-only endpoint; never enters the ingestion queue.
try {
    const api = global.get('historyApi');
    const reply = await api.handle({method:msg.req.method, path:msg.req.path,
        query:msg.req.query, authorization:msg.req.headers.authorization});
    msg.statusCode = reply.status;
    msg.headers = reply.headers;
    msg.payload = reply.body;
} catch (error) {
    node.warn('History API unavailable; check history-access.json and the reader connection.');
    msg.statusCode = 503;
    msg.payload = {error:'History API unavailable; server setup is required.'};
}
return msg;
