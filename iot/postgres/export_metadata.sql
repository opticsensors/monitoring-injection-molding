-- psql -X -A -t -f export_metadata.sql > server.metadata.json
-- Import in the desktop's Cycle measurements dialog to edit historical cycles.
SELECT jsonb_build_object('schema_version',1,'kind','cycle_metadata_export','source','server','cycles',
    COALESCE(jsonb_agg(jsonb_build_object('capture', capture, 'review', review,
        'effective_settings', capture || (review->'settings'), 'measurements',
        jsonb_build_object('revision', metadata_revision, 'update_id', metadata_update_id,
                          'weight_g', weight_g, 'length_mm', length_mm,
                          'updated_at_ns', metadata_client_updated_at_ns::text),
        'delivery','Imported; server state unconfirmed') ORDER BY first_time_ns), '[]'::jsonb))
FROM monitoring.cycles WHERE capture IS NOT NULL;
