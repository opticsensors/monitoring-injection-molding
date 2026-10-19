"""PostgreSQL cycle selection for the Influx waveform dashboard generator."""
POSTGRES = {'type': 'grafana-postgresql-datasource', 'uid': 'cycle-metadata'}


def any_filter(column, variable):
    values = f'ARRAY[${{{variable}:sqlstring}}]::text[]'
    return f"('__all' = ANY({values}) OR {column} = ANY({values}))"


def selection_sql():
    conditions = ["waveform_status IN ('stored', 'legacy')", '$__timeFilter(observed_start)',
                  any_filter('machine_id', 'machine_id'), any_filter('session_id', 'session_id'),
                  any_filter("COALESCE(md5(material), '__unknown')", 'material'),
                  'mode = ${capture_mode:sqlstring}',
                  'acquisition_status = ANY(ARRAY[${outcome:sqlstring}]::text[])']
    for field, name in (('weight_g', 'weight'), ('mold_temperature_c', 'mold'),
                        ('pressure_limit_bar', 'pressure'), ('length_mm', 'length')):
        for bound, operator in (('min', '>='), ('max', '<=')):
            value = f"NULLIF(${{{name}_{bound}:sqlstring}}, '')::double precision"
            conditions.append(f'({value} IS NULL OR {field} {operator} {value})')
    return ("SELECT * FROM monitoring.cycle_catalog WHERE " + ' AND '.join(conditions)
            + " ORDER BY first_time_ns DESC, machine_id, session_id, cycle_id"
            + " LIMIT LEAST(100, GREATEST(1, ${n_cycles:sqlstring}::integer))")


def query_variable(name, label, sql, value='__all', multi=True, include_all=True, hide=0):
    return dict(name=name, label=label, type='query', datasource=dict(POSTGRES),
                query=sql, definition=sql, refresh=2, sort=0, hide=hide, multi=multi,
                includeAll=include_all, allValue='__all' if include_all else None,
                current={'text': 'All' if value == '__all' else value,
                         'value': '$__all' if value == '__all' else value}, options=[])


def variables(machine):
    result = [
        query_variable('machine_id', 'Machine',
                       'SELECT DISTINCT machine_id AS __text, machine_id AS __value FROM monitoring.cycle_catalog ORDER BY 1', machine),
        query_variable('session_id', 'Session', 'SELECT DISTINCT session_id AS __text, session_id AS __value '
                       'FROM monitoring.cycle_catalog WHERE ' + any_filter('machine_id', 'machine_id') + ' ORDER BY 1 DESC'),
        query_variable('material', 'Material', "SELECT DISTINCT COALESCE(material, '(unknown)') AS __text, "
                       "COALESCE(md5(material), '__unknown') AS __value FROM monitoring.cycle_catalog ORDER BY 1"),
        dict(name='capture_mode', label='Capture mode', type='custom', query='cycle,continuous',
             current={'text': 'cycle', 'value': 'cycle'}, options=[{'text': x, 'value': x, 'selected': x == 'cycle'}
                                                               for x in ('cycle', 'continuous')]),
        dict(name='outcome', label='Outcome', type='custom', query='complete,interrupted,legacy', multi=True,
             current={'text': ['complete', 'legacy'], 'value': ['complete', 'legacy']},
             options=[{'text': x, 'value': x, 'selected': x != 'interrupted'}
                      for x in ('complete', 'interrupted', 'legacy')]),
        dict(name='n_cycles', label='Latest cycles (max 100)', type='textbox', query='10',
             current={'text': '10', 'value': '10'}, options=[])
    ]
    for name, label in (('weight', 'Weight g'), ('mold', 'Mold °C'), ('pressure', 'Limit bar'), ('length', 'Spiral mm')):
        for bound in ('min', 'max'):
            result.append(dict(name=f'{name}_{bound}', label=f'{label} {bound}', type='textbox',
                               query='', current={'text': '', 'value': ''}, options=[]))
    recent = selection_sql()
    result.append(query_variable('cycle', 'Cycles',
        f'SELECT cycle_label AS __text, cycle_key AS __value FROM ({recent}) AS recent'))
    selected = any_filter('cycle_key', 'cycle')
    predicate = ("SELECT COALESCE(string_agg(influx_predicate, ' OR ' ORDER BY first_time_ns), "
                 "'(time < 0 AND time > 0)') AS __text FROM (" + recent + ') AS recent WHERE ' + selected)
    result.append(query_variable('cycle_predicate', 'Waveform bounds', predicate,
                                 value='(time < 0 AND time > 0)', multi=False, include_all=False, hide=2))
    return result


def metadata_panel(pid, y):
    return dict(id=pid, type='table', title='Selected cycles and part measurements',
        datasource=dict(POSTGRES), gridPos={'h': 8, 'w': 24, 'x': 0, 'y': y},
        fieldConfig={'defaults': {'custom': {'filterable': True}}, 'overrides': []},
        options={'showHeader': True}, targets=[dict(refId='A', datasource=dict(POSTGRES), format='table',
            editorMode='code', rawQuery=True, rawSql=(
                'SELECT observed_start, machine_id, session_id, cycle_id, session_cycle, material, '
                'mold_temperature_c, pressure_limit_bar, weight_g, length_mm, acquisition_status, sample_count '
                'FROM (' + selection_sql() + ') AS recent WHERE ' + any_filter('cycle_key', 'cycle')))])
