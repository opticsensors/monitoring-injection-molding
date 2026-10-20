// Outputs: register capture (PostgreSQL), measurements (PostgreSQL).
const assert = (condition, message) => { if (!condition) throw new Error(message); };
const finite = value => typeof value === "number" && Number.isFinite(value);
const optional = (value, minimum) => value === null || (finite(value) && value >= minimum);
const integer = value => Number.isSafeInteger(value) && value >= 0;
function text(value, max) {
    return typeof value === "string" && value.length > 0 && value.length <= max && !/[\x00-\x1f]/.test(value);
}
function ns(value) {
    assert(typeof value === "string" && /^[0-9]+$/.test(value), "Expected decimal nanosecond string");
    const n = BigInt(value);
    assert(n > 0n && n <= 9223372036854775806n, "Timestamp out of Influx range");
    return n;
}
function measurements(m) {
    assert(m && integer(m.revision) && text(m.update_id, 100), "Invalid measurement revision/ID");
    assert(optional(m.weight_g, 0) && optional(m.length_mm, 0), "Invalid part measurements");
}
try {
    const data = typeof msg.payload === 'string' ? JSON.parse(msg.payload) : msg.payload;
    if (Array.isArray(data)) {
        throw new Error('Legacy upload retained for reconciliation; drain old desktop spool before cutover');
    }
    assert(data && data.schema_version === 1, "Unsupported metadata schema");
    measurements(data.measurements);
    if (data.kind === "measurements") {
        assert(text(data.machine_id, 128) && text(data.session_id, 200) && integer(data.cycle_id), "Invalid cycle identity");
        msg.query = "SELECT monitoring.receive_measurements($1, $2, $3::bigint, $4::jsonb) AS result";
        msg.params = [data.machine_id, data.session_id, data.cycle_id, JSON.stringify(data.measurements)];
        return [null, msg];
    }
    assert(data.kind === "capture", "Unknown message kind");
    const c = data.capture;
    assert(c && text(c.machine_id, 128) && text(c.session_id, 200) && integer(c.cycle_id), "Invalid capture identity");
    assert(integer(c.session_cycle) && (c.mode === "cycle" || c.mode === "continuous"), "Invalid acquisition mode");
    assert((c.cycle_id === 0) === (c.mode === "continuous"), "Cycle/mode mismatch");
    assert(["complete", "interrupted"].includes(c.status), "Invalid acquisition status");
    assert(c.material === null || text(c.material, 200), "Invalid material");
    assert(optional(c.mold_temperature_c, -273.15), "Invalid mold setpoint");
    assert(c.pressure_settings_bar && typeof c.pressure_settings_bar === "object", "Missing pressure settings");
    for (const [key, value] of Object.entries(c.pressure_settings_bar)) {
        assert(/^[a-z][a-z0-9_]*$/.test(key) && optional(value, 0), "Invalid pressure setting");
    }
    const fields = c.config_snapshot && c.config_snapshot.field_names;
    assert(Array.isArray(fields) && fields.length > 0 && new Set(fields).size === fields.length, "Invalid channel list");
    assert(fields.every(f => /^CH[0-9]+_[A-Za-z0-9_]+$/.test(f)), "Invalid channel field name");
    assert(Array.isArray(data.samples) && data.samples.length > 0 && c.sample_count === data.samples.length, "Sample count mismatch");
    const first = ns(c.first_time_ns), last = ns(c.last_time_ns), base = ns(c.base_time_ns);
    assert(first <= last, "Invalid capture bounds");
    if (c.trigger_start_ns !== null) ns(c.trigger_start_ns);
    if (c.trigger_end_ns !== null) ns(c.trigger_end_ns);
    const tag = value => value.replace(/\\/g, "\\\\").replace(/([ ,=])/g, "\\$1");
    const prefix = `sensor_data,machine_id=${tag(c.machine_id)},session_id=${tag(c.session_id)} `;
    let previous = null;
    const lines = data.samples.map((r, index) => {
        const stamp = ns(r.timestamp_ns);
        assert(previous === null || stamp > previous, "Duplicate/backward sample timestamp");
        previous = stamp;
        assert(stamp >= first && stamp <= last && stamp >= base, "Sample outside capture bounds");
        assert(r.sample_index === index && finite(r.time_s) && r.time_s >= 0, "Invalid sample index/time");
        assert(finite(r.time_s * 1000) && Math.abs(Number(stamp-base)/1e9-r.time_s) <= 0.0000011,
               "Relative time does not match the capture timestamp");
        assert(Object.keys(r).every(k => fields.includes(k) || ["timestamp_ns", "time_s", "sample_index"].includes(k)), "Unexpected sample field");
        // Existing cycle_num and t_ms fields remain floats; only the new sample_index is integer.
        const values = [`cycle_num=${c.cycle_id}`, `t_ms=${r.time_s * 1000}`, `sample_index=${index}i`];
        for (const field of [...fields].sort()) {
            assert(finite(r[field]), `Missing/non-finite channel ${field}`);
            values.push(`${field}=${r[field]}`);
        }
        return prefix + values.join(",") + " " + r.timestamp_ns;
    });
    assert(data.samples[0].timestamp_ns === c.first_time_ns &&
           data.samples[data.samples.length-1].timestamp_ns === c.last_time_ns, "Manifest bounds mismatch");
    msg.capture = c;
    msg.lineProtocol = lines.join("\n");
    msg.query = "SELECT monitoring.register_capture($1::jsonb, md5($2::text), $3::jsonb) AS fingerprint";
    msg.params = [JSON.stringify(c), msg.lineProtocol, JSON.stringify(data.measurements)];
    delete msg.payload;
    return [msg, null];
} catch (error) {
    msg.ingestPermanent = true;
    node.error(error.message, msg);
    return null;
}
