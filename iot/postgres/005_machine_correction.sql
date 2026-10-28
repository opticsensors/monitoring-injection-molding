-- Correct the displayed machine without changing capture identity or waveform routing.
BEGIN;
CREATE OR REPLACE FUNCTION monitoring.receive_review(machine text, session text, cycle bigint, r jsonb)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, monitoring, pg_temp AS $$
DECLARE existing monitoring.cycles; revision bigint; setting record; number double precision;
BEGIN
    IF length(machine) NOT BETWEEN 1 AND 128 OR length(session) NOT BETWEEN 1 AND 200 OR
       cycle NOT BETWEEN 1 AND 9007199254740991 OR
       jsonb_typeof(r) IS DISTINCT FROM 'object' OR
       jsonb_typeof(r->'revision') IS DISTINCT FROM 'number' OR
       COALESCE(r->>'revision','') !~ '^[0-9]+$' OR
       jsonb_typeof(r->'update_id') IS DISTINCT FROM 'string' OR
       COALESCE(length(r->>'update_id'),0) NOT BETWEEN 1 AND 100 OR
       jsonb_typeof(r->'excluded') IS DISTINCT FROM 'boolean' OR
       jsonb_typeof(r->'settings') IS DISTINCT FROM 'object' OR
       jsonb_typeof(r->'updated_at_ns') IS DISTINCT FROM 'string' OR
       COALESCE(r->>'updated_at_ns','') !~ '^[0-9]{1,19}$' THEN
        RAISE EXCEPTION 'Invalid cycle review';
    END IF;
    revision := (r->>'revision')::bigint;
    IF revision NOT BETWEEN 1 AND 9007199254740991 OR (r->>'updated_at_ns')::bigint <= 0 THEN
        RAISE EXCEPTION 'Invalid review revision/timestamp';
    END IF;
    FOR setting IN SELECT key,value FROM jsonb_each(r->'settings') LOOP
        IF setting.key NOT IN ('machine_id','material','mold_temperature_c','melt_temperature_c','injection_speed_mm_s') THEN
            RAISE EXCEPTION 'Unknown correction field';
        END IF;
        IF setting.key = 'machine_id' THEN
            IF jsonb_typeof(setting.value) IS DISTINCT FROM 'string' OR
               (setting.value #>> '{}') !~ '^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$' THEN
                RAISE EXCEPTION 'Invalid corrected machine';
            END IF;
            CONTINUE;
        END IF;
        IF setting.value = 'null'::jsonb THEN CONTINUE; END IF;
        IF setting.key = 'material' THEN
            IF jsonb_typeof(setting.value) <> 'string' OR length(setting.value #>> '{}') NOT BETWEEN 1 AND 200 OR
               (setting.value #>> '{}') ~ '[[:cntrl:]]' THEN RAISE EXCEPTION 'Invalid material'; END IF;
        ELSE
            IF jsonb_typeof(setting.value) <> 'number' THEN RAISE EXCEPTION 'Invalid setpoint'; END IF;
            number := (setting.value #>> '{}')::double precision;
            IF number >= 'Infinity'::double precision OR
               number < (CASE WHEN setting.key = 'injection_speed_mm_s' THEN 0 ELSE -273.15 END) THEN
                RAISE EXCEPTION 'Invalid setpoint';
            END IF;
        END IF;
    END LOOP;
    -- Support an edit arriving before its capture (e.g. after offline work).
    INSERT INTO monitoring.cycles(machine_id,session_id,cycle_id)
        VALUES (machine,session,cycle) ON CONFLICT DO NOTHING;
    SELECT * INTO STRICT existing FROM monitoring.cycles
        WHERE machine_id=machine AND session_id=session AND cycle_id=cycle FOR UPDATE;
    IF revision <= (existing.review->>'revision')::bigint THEN
        IF r->'settings' = existing.review->'settings' AND r->'excluded' = existing.review->'excluded' THEN
            RETURN 'replay';
        END IF;
        INSERT INTO monitoring.review_conflicts(machine_id,session_id,cycle_id,update_id,proposed,current_values)
            VALUES (machine,session,cycle,r->>'update_id',r,existing.review) ON CONFLICT DO NOTHING;
        RETURN CASE WHEN revision = (existing.review->>'revision')::bigint THEN 'conflict' ELSE 'stale' END;
    END IF;
    UPDATE monitoring.cycles SET review=r WHERE machine_id=machine AND session_id=session AND cycle_id=cycle;
    RETURN 'applied';
END $$;

CREATE OR REPLACE VIEW monitoring.cycle_catalog AS
SELECT machine_id, session_id, cycle_id, session_cycle,
       CASE WHEN review->'settings' ? 'material' THEN review->'settings'->>'material' ELSE material END AS material,
       CASE WHEN review->'settings' ? 'mold_temperature_c' THEN (review->'settings'->>'mold_temperature_c')::double precision
            ELSE mold_temperature_c END AS mold_temperature_c,
       pressure_limit_bar, weight_g, length_mm, metadata_revision, waveform_status,
       first_time_ns, last_time_ns, sample_count,
       capture->>'mode' AS mode, capture->>'status' AS acquisition_status,
       capture->>'reason' AS acquisition_reason,
       to_timestamp(first_time_ns / 1000000000.0) AS observed_start,
       md5(jsonb_build_array(machine_id, session_id, cycle_id)::text) AS cycle_key,
       format('%s / %s / cycle %s', COALESCE(review->'settings'->>'machine_id', machine_id), session_id, cycle_id) AS cycle_label,
       format('("machine_id" = %s AND "session_id" = %s AND "cycle_num" = %s)',
              monitoring.influx_literal(machine_id), monitoring.influx_literal(session_id), cycle_id) AS influx_predicate,
       CASE WHEN review->'settings' ? 'melt_temperature_c' THEN (review->'settings'->>'melt_temperature_c')::double precision
            ELSE melt_temperature_c END AS melt_temperature_c,
       ((capture || (review->'settings'))->>'injection_speed_mm_s')::double precision AS injection_speed_mm_s,
       excluded, (review->>'revision')::bigint AS review_revision,
       COALESCE(review->'settings'->>'machine_id', machine_id) AS effective_machine_id
FROM monitoring.cycles WHERE capture IS NOT NULL;

ALTER FUNCTION monitoring.receive_review(text,text,bigint,jsonb) OWNER TO monitoring_owner;
REVOKE ALL ON FUNCTION monitoring.receive_review(text,text,bigint,jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION monitoring.receive_review(text,text,bigint,jsonb) TO monitoring_ingest;
ALTER VIEW monitoring.cycle_catalog OWNER TO monitoring_owner;
GRANT SELECT ON monitoring.cycle_catalog TO monitoring_reader;
INSERT INTO monitoring.schema_migrations(version) VALUES (5) ON CONFLICT DO NOTHING;
COMMIT;
