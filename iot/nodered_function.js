// The DAQ app publishes one batch per cycle (or one per continuous session):
// [{timestamp_ns, time_s, machine_id, session_id, cycle_id,
//   CH0_T_futaba, CH1_T_futaba, CH2_P_kistler, CH3_P_kistler,
//   CH5_P_machine, CH6_S_speed, CH7_S_position}, ...]
// Channel keys are CH<hw-channel>_<sensor_type>, named by the app from its
// channel config, and the values are already converted to physical units
// (degC, bar, mm/s, mm). The channel set is discovered per record, so any
// channel configuration works without touching this function.
const records = msg.payload;

if (!Array.isArray(records) || records.length === 0) {
    node.warn("Expected non-empty array, got: " + typeof records);
    return null;
}

// Payload metadata keys - everything else is a channel field.
const META = ["timestamp_ns", "time_s", "machine_id", "session_id", "cycle_id"];
const t0 = records[0].timestamp_ns;

msg.payload = records.map(r => {
    const fields = {
        // Cycle-relative time [ms]: the app's time_s when present,
        // timestamp delta for old-format batches.
        t_ms: (typeof r.time_s === "number")
            ? r.time_s * 1000.0
            : (r.timestamp_ns - t0) / 1e6,
        cycle_num: Number(r.cycle_id)
    };
    for (const key of Object.keys(r)) {
        if (META.includes(key)) continue;
        const value = Number(r[key]);
        if (Number.isFinite(value)) fields[key] = value;
    }
    return {
        measurement: "sensor_data",
        tags: {
            machine_id: String(r.machine_id),
            cycle_id: String(r.cycle_id),
            session_id: String(r.session_id || "")
        },
        fields: fields,
        timestamp: r.timestamp_ns
    };
});

node.status({
    fill: "green",
    text: `${records.length} pts @ ${new Date().toLocaleTimeString()}`
});

return msg;
