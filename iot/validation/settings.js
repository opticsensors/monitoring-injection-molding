// Test stack only. Production settings must retain their existing credentials/security.
module.exports = {
    uiPort: 1880,
    flowFile: 'flows.json',
    functionGlobalContext: {
        captureQueue: require('/opt/capture_queue.cjs'),
        historyApi: require('/opt/history_api.cjs')
    },
    logging: {console: {level: 'info', metrics: false, audit: false}}
};
