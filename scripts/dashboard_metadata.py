"""Select the latest recorded cycles behind the simple waveform dashboard."""
POSTGRES = {'type': 'grafana-postgresql-datasource', 'uid': 'cycle-metadata'}
EMPTY_PREDICATE = '(time < 0 AND time > 0)'


def selection_sql():
    # No date window: old recordings stay visible until new cycles replace them.
    # Bound the textbox before casting, including blank/malformed/huge input.
    count = "btrim(${n_cycles:sqlstring})"
    limit = (f"CASE WHEN {count} ~ '^[0-9]+$' THEN "
             f"CASE WHEN length({count}) > 9 THEN 100 "
             f"ELSE LEAST(100, GREATEST(1, {count}::integer)) END ELSE 10 END")
    return ("SELECT * FROM monitoring.cycle_catalog WHERE "
            "waveform_status IN ('stored', 'legacy') AND mode = 'cycle' "
            "AND machine_id IN ('55t', '160t') "
            "ORDER BY first_time_ns DESC, machine_id, session_id, cycle_id LIMIT " + limit)


def variables():
    # InfluxQL 1.x needs one shared time interval around the full identities.
    predicate = ("SELECT COALESCE('(time >= ' || min(first_time_ns)::text || ' AND time <= ' || "
                 "max(last_time_ns)::text || ' AND (' || "
                 "string_agg(influx_predicate, ' OR ' ORDER BY first_time_ns) || '))', "
                 f"'{EMPTY_PREDICATE}') AS __text FROM ({selection_sql()}) AS recent")
    return [
        dict(name='n_cycles', label='Latest cycles (max 100)', type='textbox', query='10',
             current={'text': '10', 'value': '10'}, options=[]),
        dict(name='cycle_predicate', type='query', datasource=dict(POSTGRES),
             query=predicate, definition=predicate, refresh=2, sort=0, hide=2,
             multi=False, includeAll=False, skipUrlSync=True,
             current={'text': EMPTY_PREDICATE, 'value': EMPTY_PREDICATE}, options=[]),
    ]
