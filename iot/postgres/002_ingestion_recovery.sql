-- Apply AFTER 001, including on an existing metadata database. No waveform migration.
BEGIN;
CREATE TABLE IF NOT EXISTS monitoring.schema_migrations (
    version integer PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
INSERT INTO monitoring.schema_migrations(version) VALUES (1) ON CONFLICT DO NOTHING;

ALTER TABLE monitoring.cycles ADD COLUMN IF NOT EXISTS metadata_client_updated_at_ns bigint;
CREATE TABLE IF NOT EXISTS monitoring.measurement_conflicts (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    machine_id text NOT NULL, session_id text NOT NULL, cycle_id bigint NOT NULL,
    update_id text NOT NULL, proposed jsonb NOT NULL, current_values jsonb NOT NULL,
    source text NOT NULL CHECK (source IN ('capture', 'update')),
    reason text NOT NULL CHECK (reason IN ('stale', 'conflict')),
    server_revision bigint NOT NULL, observed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    resolved_at timestamptz,
    UNIQUE (machine_id, session_id, cycle_id, update_id, server_revision, reason)
);

-- Revision ordering remains authoritative. Client time is provenance, not a
-- last-writer-wins clock. Persist rejected proposals instead of aborting captures.
CREATE OR REPLACE FUNCTION monitoring._apply_measurements(
    machine text, session text, cycle bigint, m jsonb, source text)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, monitoring, pg_temp AS $$
DECLARE existing monitoring.cycles; revision bigint; weight double precision;
        length double precision; client_ns bigint; outcome text;
BEGIN
    IF source NOT IN ('capture', 'update') OR jsonb_typeof(m) IS DISTINCT FROM 'object' OR
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
    IF m->>'updated_at_ns' IS NOT NULL THEN
        IF m->>'updated_at_ns' !~ '^[0-9]{1,19}$' THEN
            RAISE EXCEPTION 'Invalid measurement timestamp';
        END IF;
        client_ns := (m->>'updated_at_ns')::bigint;
        IF client_ns <= 0 THEN RAISE EXCEPTION 'Invalid measurement timestamp'; END IF;
    END IF;
    INSERT INTO monitoring.cycles(machine_id, session_id, cycle_id)
        VALUES (machine, session, cycle) ON CONFLICT DO NOTHING;
    SELECT * INTO STRICT existing FROM monitoring.cycles
        WHERE machine_id=machine AND session_id=session AND cycle_id=cycle FOR UPDATE;
    IF revision <= existing.metadata_revision THEN
        IF weight IS NOT DISTINCT FROM existing.weight_g AND
           length IS NOT DISTINCT FROM existing.length_mm THEN RETURN 'replay'; END IF;
        outcome := CASE WHEN revision = existing.metadata_revision THEN 'conflict' ELSE 'stale' END;
        -- Old capture replay normally embeds older measurements. Ignore those;
        -- standalone edits and equal-revision conflicts remain reviewable.
        IF source = 'update' OR outcome = 'conflict' THEN
            INSERT INTO monitoring.measurement_conflicts(machine_id, session_id, cycle_id,
                update_id, proposed, current_values, source, reason, server_revision)
            VALUES (machine, session, cycle, m->>'update_id', m,
                jsonb_build_object('revision', existing.metadata_revision,
                    'weight_g', existing.weight_g, 'length_mm', existing.length_mm,
                    'update_id', existing.metadata_update_id), source, outcome, existing.metadata_revision)
            ON CONFLICT DO NOTHING;
        END IF;
        RETURN outcome;
    END IF;
    UPDATE monitoring.cycles SET weight_g=weight, length_mm=length,
        metadata_revision=revision, metadata_update_id=m->>'update_id',
        metadata_updated_at=clock_timestamp(), metadata_client_updated_at_ns=client_ns
        WHERE machine_id=machine AND session_id=session AND cycle_id=cycle;
    RETURN 'applied';
END $$;

CREATE OR REPLACE FUNCTION monitoring.receive_measurements(machine text, session text, cycle bigint, m jsonb)
RETURNS text LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, monitoring, pg_temp AS $$
    SELECT monitoring._apply_measurements(machine, session, cycle, m, 'update')
$$;
-- Compatibility for existing SQL callers. New flow consumes the explicit result.
CREATE OR REPLACE FUNCTION monitoring.apply_measurements(machine text, session text, cycle bigint, m jsonb)
RETURNS boolean LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, monitoring, pg_temp AS $$
    SELECT monitoring.receive_measurements(machine, session, cycle, m) = 'applied'
$$;

CREATE OR REPLACE FUNCTION monitoring.register_capture(c jsonb, fingerprint text, m jsonb)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, monitoring, pg_temp AS $$
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
    PERFORM pg_advisory_xact_lock(hashtextextended(jsonb_build_array(machine,session)::text,0));
    IF EXISTS (SELECT FROM monitoring.cycles WHERE machine_id=machine AND session_id=session
               AND cycle_id<>cycle AND first_time_ns <= (c->>'last_time_ns')::bigint
               AND last_time_ns >= (c->>'first_time_ns')::bigint) THEN
        RAISE EXCEPTION 'Overlapping capture timestamps in the same machine/session';
    END IF;
    PERFORM monitoring._apply_measurements(machine, session, cycle, m, 'capture');
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

-- Guard both builder reruns and old generated SQL files. Never turn a native
-- capture into legacy; only accept a matching observed count and exact bounds.
CREATE OR REPLACE FUNCTION monitoring.import_legacy(c jsonb)
RETURNS void LANGUAGE plpgsql SET search_path = pg_catalog, monitoring, pg_temp AS $$
DECLARE existing monitoring.cycles;
BEGIN
    IF c->>'status' IS DISTINCT FROM 'legacy' THEN RAISE EXCEPTION 'Expected legacy manifest'; END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended(jsonb_build_array(c->>'machine_id',c->>'session_id')::text,0));
    SELECT * INTO existing FROM monitoring.cycles
        WHERE machine_id=c->>'machine_id' AND session_id=c->>'session_id'
          AND cycle_id=(c->>'cycle_id')::bigint FOR UPDATE;
    IF existing.capture IS NOT NULL THEN
        IF existing.first_time_ns <> (c->>'first_time_ns')::bigint OR
           existing.last_time_ns <> (c->>'last_time_ns')::bigint OR
           existing.sample_count <> (c->>'sample_count')::integer THEN
            RAISE EXCEPTION 'Backfill bounds/count differ from existing catalog: %, %, %',
                c->>'machine_id',c->>'session_id',c->>'cycle_id';
        END IF;
        RETURN;
    END IF;
    PERFORM monitoring.register_capture(c, md5(c::text),
        '{"revision":0,"update_id":"legacy","weight_g":null,"length_mm":null}'::jsonb);
    UPDATE monitoring.cycles SET waveform_status='legacy'
        WHERE machine_id=c->>'machine_id' AND session_id=c->>'session_id' AND cycle_id=(c->>'cycle_id')::bigint;
END $$;

-- Same columns/order as v1; only the predicate expression changes.
CREATE OR REPLACE VIEW monitoring.cycle_catalog AS
SELECT machine_id, session_id, cycle_id, session_cycle, material, mold_temperature_c,
       pressure_limit_bar, weight_g, length_mm, metadata_revision, waveform_status,
       first_time_ns, last_time_ns, sample_count,
       capture->>'mode' AS mode, capture->>'status' AS acquisition_status,
       capture->>'reason' AS acquisition_reason,
       to_timestamp(first_time_ns / 1000000000.0) AS observed_start,
       md5(jsonb_build_array(machine_id, session_id, cycle_id)::text) AS cycle_key,
       format('%s / %s / cycle %s', machine_id, session_id, cycle_id) AS cycle_label,
       format('("machine_id" = %s AND "session_id" = %s AND "cycle_num" = %s)',
              monitoring.influx_literal(machine_id), monitoring.influx_literal(session_id),
              cycle_id) AS influx_predicate
FROM monitoring.cycles WHERE capture IS NOT NULL;

DROP INDEX IF EXISTS monitoring.cycles_session;
DO $$ BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='monitoring_owner') THEN
        CREATE ROLE monitoring_owner NOLOGIN;
    END IF;
    IF EXISTS (SELECT FROM pg_roles WHERE rolname='monitoring_owner' AND (rolcanlogin OR rolsuper)) THEN
        RAISE EXCEPTION 'monitoring_owner must be a dedicated non-login, non-superuser role';
    END IF;
END $$;
ALTER SCHEMA monitoring OWNER TO monitoring_owner;
ALTER TABLE monitoring.cycles OWNER TO monitoring_owner;
ALTER TABLE monitoring.schema_migrations OWNER TO monitoring_owner;
ALTER TABLE monitoring.measurement_conflicts OWNER TO monitoring_owner;
ALTER VIEW monitoring.cycle_catalog OWNER TO monitoring_owner;
DO $$ DECLARE f record; BEGIN
    FOR f IN SELECT p.oid::regprocedure AS name FROM pg_proc p
             JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='monitoring'
    LOOP
        EXECUTE format('ALTER FUNCTION %s OWNER TO monitoring_owner', f.name);
        EXECUTE format('ALTER FUNCTION %s SET search_path = pg_catalog, monitoring, pg_temp', f.name);
    END LOOP;
END $$;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA monitoring FROM PUBLIC;
GRANT EXECUTE ON FUNCTION monitoring.receive_measurements(text,text,bigint,jsonb) TO monitoring_ingest;
GRANT SELECT ON monitoring.measurement_conflicts TO monitoring_reader;
INSERT INTO monitoring.schema_migrations(version) VALUES (2) ON CONFLICT DO NOTHING;
COMMIT;
