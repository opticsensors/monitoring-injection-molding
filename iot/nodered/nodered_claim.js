try {
    return global.get('captureQueue').queue().claim();
} catch (error) {
    node.error('Capture queue claim failed: ' + error.message, msg);
    return null;
}
