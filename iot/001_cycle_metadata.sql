-- Run in the dedicated injection_monitoring database as its owner.
-- No waveform samples are stored here. Safe to reapply this initial migration.
BEGIN;
CREATE SCHEMA IF NOT EXISTS monitoring;

CREATE TABLE IF NOT EXISTS monitoring.cycles (
    machine_id text NOT NULL CHECK (length(machine_id) BETWEEN 1 AND 128),
    session_id text NOT NULL CHECK (length(session_id) BETWEEN 1 AND 200),
    cycle_id bigint NOT NULL CHECK (cycle_id BETWEEN 0 AND 9007199254740991),
    capture jsonb,
    waveform_hash text,
    waveform_status text NOT NULL DEFAULT 'metadata_only'
        CHECK (waveform_status IN ('metadata_only', 'pending', 'stored', 'legacy')),
    first_time_ns bigint GENERATED ALWAYS AS ((capture->>'first_time_ns')::bigint) STORED,
    last_time_ns bigint GENERATED ALWAYS AS ((capture->>'last_time_ns')::bigint) STORED,
    sample_count integer GENERATED ALWAYS AS ((capture->>'sample_count')::integer) STORED,
    session_cycle bigint GENERATED ALWAYS AS ((capture->>'session_cycle')::bigint) STORED,
    material text GENERATED ALWAYS AS (capture->>'material') STORED,
    mold_temperature_c double precision GENERATED ALWAYS AS ((capture->>'mold_temperature_c')::double precision) STORED,
    pressure_limit_bar double precision GENERATED ALWAYS AS ((capture->'pressure_settings_bar'->>'limit')::double precision) STORED,
    weight_g double precision CHECK (weight_g >= 0 AND weight_g < 'Infinity'::float8),
    length_mm double precision CHECK (length_mm >= 0 AND length_mm < 'Infinity'::float8),
    metadata_revision bigint NOT NULL DEFAULT -1,
    metadata_update_id text,
    metadata_updated_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    waveform_stored_at timestamptz,
    PRIMARY KEY (machine_id, session_id, cycle_id),
    CHECK (mold_temperature_c IS NULL OR (mold_temperature_c >= -273.15 AND mold_temperature_c < 'Infinity'::float8)),
    CHECK (pressure_limit_bar IS NULL OR (pressure_limit_bar >= 0 AND pressure_limit_bar < 'Infinity'::float8)),
    CHECK (material IS NULL OR length(material) <= 200),
    CHECK (capture IS NULL OR (sample_count > 0 AND first_time_ns > 0 AND last_time_ns >= first_time_ns)),
    CHECK (capture IS NULL OR (capture->>'machine_id' = machine_id AND
           capture->>'session_id' = session_id AND (capture->>'cycle_id')::bigint = cycle_id))
);
CREATE INDEX IF NOT EXISTS cycles_machine_time ON monitoring.cycles (machine_id, first_time_ns DESC);
CREATE INDEX IF NOT EXISTS cycles_session ON monitoring.cycles (machine_id, session_id, cycle_id);
CREATE INDEX IF NOT EXISTS cycles_material ON monitoring.cycles (material);

CREATE OR REPLACE FUNCTION monitoring.apply_measurements(machine text, session text, cycle bigint, m jsonb)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, monitoring AS $$
DECLARE existing monitoring.cycles; revision bigint; weight double precision; length double precision;
BEGIN
    IF jsonb_typeof(m) IS DISTINCT FROM 'object' OR
       jsonb_typeof(m->'revision') IS DISTINCT FROM 'number' OR
       (m->>'revision') !~ '^[0-9]+$' OR
       NOT (m ? 'weight_g' AND m ? 'length_mm') OR
       jsonb_typeof(m->'weight_g') NOT IN ('number', 'null') OR
       jsonb_typeof(m->'length_mm') NOT IN ('number', 'null') OR
       COALESCE(length(m->>'update_id'), 0) NOT BETWEEN 1 AND 100 THEN
        RAISE EXCEPTION 'Invalid measurements';
    END IF;
    revision := (m->>'revision')::bigint;
    weight := (m->>'weight_g')::double precision;
    length := (m->>'length_mm')::double precision;
    IF revision > 9007199254740991 OR weight < 0 OR length < 0 OR
       weight >= 'Infinity'::float8 OR length >= 'Infinity'::float8 THEN
        RAISE EXCEPTION 'Invalid measurement values';
    END IF;
    -- An edit can arrive before its capture. Such a row is explicitly metadata_only.
    INSERT INTO monitoring.cycles(machine_id, session_id, cycle_id)
        VALUES (machine, session, cycle) ON CONFLICT DO NOTHING;
    SELECT * INTO STRICT existing FROM monitoring.cycles
        WHERE machine_id=machine AND session_id=session AND cycle_id=cycle FOR UPDATE;
    IF revision = existing.metadata_revision THEN
        IF weight IS DISTINCT FROM existing.weight_g OR length IS DISTINCT FROM existing.length_mm THEN
            RAISE EXCEPTION 'Conflicting values for metadata revision %', revision;
        END IF;
        RETURN false; -- identical replay
    END IF;
    IF revision < existing.metadata_revision THEN RETURN false; END IF;
    UPDATE monitoring.cycles SET weight_g=weight, length_mm=length,
        metadata_revision=revision, metadata_update_id=m->>'update_id', metadata_updated_at=clock_timestamp()
        WHERE machine_id=machine AND session_id=session AND cycle_id=cycle;
    RETURN true;
END $$;

CREATE OR REPLACE FUNCTION monitoring.register_capture(c jsonb, fingerprint text, m jsonb)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, monitoring AS $$
DECLARE existing monitoring.cycles; machine text; session text; cycle bigint;
BEGIN
    IF jsonb_typeof(c) IS DISTINCT FROM 'object' OR
       COALESCE(c->>'status', '') NOT IN ('complete', 'interrupted', 'legacy') OR
       COALESCE(c->>'mode', '') NOT IN ('cycle', 'continuous') OR
       COALESCE((c->>'sample_count')::integer, 0) < 1 OR
       c->>'first_time_ns' IS NULL OR c->>'last_time_ns' IS NULL OR
       fingerprint IS NULL OR length(fingerprint) <> 32 THEN
        RAISE EXCEPTION 'Invalid capture manifest';
    END IF;
    machine := c->>'machine_id'; session := c->>'session_id'; cycle := (c->>'cycle_id')::bigint;
    -- Influx identity is tag set + timestamp, not cycle_id. Serialize session
    -- registration and reject overlapping captures that could overwrite samples.
    PERFORM pg_advisory_xact_lock(hashtextextended(jsonb_build_array(machine,session)::text,0));
    IF EXISTS (SELECT FROM monitoring.cycles WHERE machine_id=machine AND session_id=session
               AND cycle_id<>cycle AND first_time_ns <= (c->>'last_time_ns')::bigint
               AND last_time_ns >= (c->>'first_time_ns')::bigint) THEN
        RAISE EXCEPTION 'Overlapping capture timestamps in the same machine/session';
    END IF;
    PERFORM monitoring.apply_measurements(machine, session, cycle, m);
    SELECT * INTO STRICT existing FROM monitoring.cycles
        WHERE machine_id=machine AND session_id=session AND cycle_id=cycle FOR UPDATE;
    IF existing.capture IS NOT NULL AND
       (existing.capture <> c OR existing.waveform_hash <> fingerprint) THEN
        RAISE EXCEPTION 'Conflicting immutable capture for machine %, session %, cycle %', machine, session, cycle;
    END IF;
    UPDATE monitoring.cycles SET capture=c, waveform_hash=fingerprint,
        waveform_status=CASE WHEN existing.waveform_status IN ('stored','legacy')
                            THEN existing.waveform_status ELSE 'pending' END
        WHERE machine_id=machine AND session_id=session AND cycle_id=cycle;
    RETURN fingerprint;
END $$;

CREATE OR REPLACE FUNCTION monitoring.mark_stored(machine text, session text, cycle bigint, fingerprint text)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, monitoring AS $$
BEGIN
    UPDATE monitoring.cycles SET waveform_status='stored', waveform_stored_at=clock_timestamp()
        WHERE machine_id=machine AND session_id=session AND cycle_id=cycle AND waveform_hash=fingerprint;
    IF NOT FOUND THEN RAISE EXCEPTION 'Unknown capture receipt'; END IF;
    RETURN true;
END $$;

CREATE OR REPLACE FUNCTION monitoring.import_legacy(c jsonb)
RETURNS void LANGUAGE plpgsql SET search_path = pg_catalog, monitoring AS $$
BEGIN
    IF c->>'status' IS DISTINCT FROM 'legacy' THEN RAISE EXCEPTION 'Expected legacy manifest'; END IF;
    PERFORM monitoring.register_capture(c, md5(c::text),
        '{"revision":0,"update_id":"legacy","weight_g":null,"length_mm":null}'::jsonb);
    UPDATE monitoring.cycles SET waveform_status='legacy'
        WHERE machine_id=c->>'machine_id' AND session_id=c->>'session_id' AND cycle_id=(c->>'cycle_id')::bigint;
END $$;

-- Quote literals for InfluxQL, not SQL. Identity and exact bounds stay paired.
CREATE OR REPLACE FUNCTION monitoring.influx_literal(value text)
RETURNS text LANGUAGE sql IMMUTABLE STRICT AS $$
    SELECT chr(39) || replace(replace(value, chr(92), chr(92)||chr(92)),
                             chr(39), chr(92)||chr(39)) || chr(39)
$$;
CREATE OR REPLACE VIEW monitoring.cycle_catalog AS
SELECT machine_id, session_id, cycle_id, session_cycle, material, mold_temperature_c,
       pressure_limit_bar, weight_g, length_mm, metadata_revision, waveform_status,
       first_time_ns, last_time_ns, sample_count,
       capture->>'mode' AS mode, capture->>'status' AS acquisition_status,
       capture->>'reason' AS acquisition_reason,
       to_timestamp(first_time_ns / 1000000000.0) AS observed_start,
       md5(jsonb_build_array(machine_id, session_id, cycle_id)::text) AS cycle_key,
       format('%s / %s / cycle %s', machine_id, session_id, cycle_id) AS cycle_label,
       format('("machine_id" = %s AND "session_id" = %s AND "cycle_num" = %s AND time >= %s AND time <= %s)',
              monitoring.influx_literal(machine_id), monitoring.influx_literal(session_id),
              cycle_id, first_time_ns, last_time_ns) AS influx_predicate
FROM monitoring.cycles WHERE capture IS NOT NULL;

DO $$ BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='monitoring_ingest') THEN
        CREATE ROLE monitoring_ingest LOGIN;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='monitoring_reader') THEN
        CREATE ROLE monitoring_reader LOGIN;
    END IF;
END $$;
REVOKE ALL ON SCHEMA monitoring FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA monitoring FROM PUBLIC;
GRANT USAGE ON SCHEMA monitoring TO monitoring_ingest, monitoring_reader;
GRANT SELECT ON monitoring.cycle_catalog TO monitoring_reader;
GRANT EXECUTE ON FUNCTION monitoring.influx_literal(text) TO monitoring_reader;
GRANT EXECUTE ON FUNCTION monitoring.register_capture(jsonb,text,jsonb),
    monitoring.apply_measurements(text,text,bigint,jsonb),
    monitoring.mark_stored(text,text,bigint,text) TO monitoring_ingest;
COMMIT;
