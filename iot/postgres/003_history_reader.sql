-- Additive desktop history access. Waveforms and immutable manifests stay unchanged.
BEGIN;
CREATE OR REPLACE VIEW monitoring.history_records AS
SELECT machine_id, session_id, cycle_id, first_time_ns, capture, waveform_status,
       jsonb_build_object('revision', metadata_revision, 'update_id', metadata_update_id,
           'weight_g', weight_g, 'length_mm', length_mm,
           'updated_at_ns', metadata_client_updated_at_ns::text) AS measurements
FROM monitoring.cycles
WHERE capture IS NOT NULL AND capture->>'mode' = 'cycle';
ALTER VIEW monitoring.history_records OWNER TO monitoring_owner;
GRANT SELECT ON monitoring.history_records TO monitoring_reader;
INSERT INTO monitoring.schema_migrations(version) VALUES (3) ON CONFLICT DO NOTHING;
COMMIT;
