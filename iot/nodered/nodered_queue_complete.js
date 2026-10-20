try {
    const result = msg.payload && msg.payload[0];
    if (!result || (result.stored !== true && !['applied', 'replay', 'stale', 'conflict'].includes(result.result))) {
        throw new Error('Missing database completion receipt');
    }
    const q = global.get('captureQueue').queue();
    if (['stale', 'conflict'].includes(result.result)) {
        q.fail(msg, 'Measurement ' + result.result + '; review monitoring.measurement_conflicts', true);
        node.warn('Measurement requires reconciliation: ' + msg.queueId);
    } else q.complete(msg);
    return {};
} catch (error) {
    node.error(error.message, msg);
    return null;
}
