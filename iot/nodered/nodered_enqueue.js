try {
    const store = global.get('captureQueue');
    if (!store) throw new Error('Configure functionGlobalContext.captureQueue; see SERVER_SETUP.md');
    store.queue().enqueue(msg.payload, msg.topic);
    return {}; // Wake the worker only AFTER the original message is on disk.
} catch (error) {
    node.error('Capture queue write failed: ' + error.message, msg);
    return null;
}
