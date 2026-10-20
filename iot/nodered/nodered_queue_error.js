const reason = msg.error && msg.error.message || 'Unknown ingestion failure';
try {
    const permanent = msg.ingestPermanent === true ||
        /Conflicting immutable|Overlapping capture|Invalid capture|Invalid measurement|violates .*constraint/.test(reason);
    if (msg.queueId) global.get('captureQueue').queue().fail(msg, reason, permanent);
} catch (error) {
    // Log without another Catch loop. Existing disk work remains for recovery.
    node.warn('Could not update queue failure state: ' + error.message);
}
node.warn(reason + (msg.queueId ? '; retained queue ID ' + msg.queueId : '; check server disk/configuration'));
return msg;
