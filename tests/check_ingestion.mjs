// Run after installing the isolated PGlite test dependency under data/validation.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const {PGlite} = await import(pathToFileURL(resolve('data/validation/node_modules/@electric-sql/pglite/dist/index.js')));
const db = new PGlite();
const errors = [];
const node = {error: (error) => errors.push(error)};
function fn(file, msg) {
    return new Function('msg', 'node', fs.readFileSync('iot/' + file, 'utf8'))(msg, node);
}
const c = {machine_id:'test-machine', session_id:'test-session', cycle_id:3, session_cycle:1,
    mode:'cycle', status:'complete', reason:'trigger', base_time_ns:'1785838969691369500',
    first_time_ns:'1785838969691369501', last_time_ns:'1785838969691369502', sample_count:2,
    trigger_start_ns:'1785838969691369500', trigger_end_ns:'1785838969691369503',
    material:'PP', mold_temperature_c:40, pressure_settings_bar:{limit:100},
    config_snapshot:{field_names:['CH0_T_futaba'], saved_indices:[0]}};
const m = {revision:0, update_id:'initial', weight_g:null, length_mm:null};
const payload = {schema_version:1, kind:'capture', capture:c, measurements:m, samples:[
    {timestamp_ns:c.first_time_ns, time_s:0.000000001, sample_index:0, CH0_T_futaba:35},
    {timestamp_ns:c.last_time_ns, time_s:0.000000002, sample_index:1, CH0_T_futaba:36}]};
try {
    await db.exec(fs.readFileSync('iot/001_cycle_metadata.sql','utf8'));
    await db.exec(fs.readFileSync('iot/001_cycle_metadata.sql','utf8')); // reapply migration
    const update = {...m, revision:2, update_id:'newer', weight_g:12, length_mm:150};
    const edit = fn('nodered_function.js', {payload:{schema_version:1, kind:'measurements',
        machine_id:c.machine_id, session_id:c.session_id, cycle_id:c.cycle_id, measurements:update}})[1];
    await db.query(edit.query, edit.params); // edit before capture
    let rows = (await db.query('SELECT waveform_status FROM monitoring.cycles')).rows;
    assert.equal(rows[0].waveform_status, 'metadata_only');
    const routed = fn('nodered_function.js', {payload:structuredClone(payload)});
    assert(routed[0].lineProtocol.endsWith(c.last_time_ns));
    assert(!routed[0].lineProtocol.includes('material='));
    let msg = routed[0];
    msg.payload = (await db.query(msg.query, msg.params)).rows;
    msg = fn('nodered_prepare_write.js', msg);
    const failed = fn('nodered_store_complete.js', {...msg, statusCode:500, payload:'test failure'});
    assert.equal(failed, null);
    assert.equal((await db.query('SELECT waveform_status FROM monitoring.cycles')).rows[0].waveform_status, 'pending');
    msg = fn('nodered_store_complete.js', {...msg, statusCode:204, payload:''});
    await db.query(msg.query, msg.params);
    const replay = fn('nodered_function.js', {payload:structuredClone(payload)})[0];
    await db.query(replay.query, replay.params);
    rows = (await db.query('SELECT weight_g, metadata_revision, waveform_status, first_time_ns::text FROM monitoring.cycles')).rows;
    assert.equal(rows[0].weight_g, 12);
    assert.equal(Number(rows[0].metadata_revision), 2);
    assert.equal(rows[0].first_time_ns, c.first_time_ns);
    assert.equal(rows[0].waveform_status, 'stored');
    const stale = {...update, revision:1, weight_g:3};
    await db.query('SELECT monitoring.apply_measurements($1,$2,$3,$4)', [c.machine_id,c.session_id,c.cycle_id,stale]);
    assert.equal((await db.query('SELECT weight_g FROM monitoring.cycles')).rows[0].weight_g,12);
    await assert.rejects(db.query('SELECT monitoring.apply_measurements($1,$2,$3,$4)',
        [c.machine_id,c.session_id,c.cycle_id,{...update,weight_g:99}]), /Conflicting/);
    await db.query('SELECT monitoring.apply_measurements($1,$2,$3,$4)',
        [c.machine_id,c.session_id,c.cycle_id,{...update,revision:3,weight_g:null,length_mm:null}]);
    assert.equal((await db.query('SELECT weight_g FROM monitoring.cycles')).rows[0].weight_g,null);
    const conflicting = structuredClone(payload);
    conflicting.samples[0].CH0_T_futaba = 99;
    const conflict = fn('nodered_function.js', {payload:conflicting})[0];
    await assert.rejects(db.query(conflict.query,conflict.params), /Conflicting immutable/);
    const overlap = structuredClone(payload);
    overlap.capture.cycle_id = 4;
    const overlapping = fn('nodered_function.js', {payload:overlap})[0];
    await assert.rejects(db.query(overlapping.query,overlapping.params), /Overlapping/);
    const invalid = structuredClone(payload);
    invalid.samples[1].timestamp_ns = invalid.samples[0].timestamp_ns;
    assert.equal(fn('nodered_function.js',{payload:invalid}),null);
    const other = structuredClone(payload);
    other.capture.session_id = "other-session'\\escaped";
    const next = fn('nodered_function.js',{payload:other})[0];
    await db.query(next.query,next.params);
    assert.equal(Number((await db.query('SELECT count(*) FROM monitoring.cycles')).rows[0].count),2);
    const predicates = (await db.query('SELECT influx_predicate FROM monitoring.cycle_catalog')).rows;
    assert(predicates.every(r=>r.influx_predicate.includes('"session_id"') && r.influx_predicate.includes('time >=')));
    // Execute the generated Grafana SQL after representative safe interpolation.
    const dashboard = JSON.parse(fs.readFileSync('iot/grafana_dashboard.json','utf8'));
    const values = {machine_id:['__all'],session_id:['__all'],material:['__all'],capture_mode:['cycle'],
        outcome:['complete','legacy'],n_cycles:['10'],cycle:['__all']};
    const quote = v => "'" + String(v).replaceAll("'", "''") + "'";
    const interpolate = sql => sql.replace(/\$__timeFilter\(observed_start\)/g, 'TRUE')
        .replace(/\$\{(\w+):sqlstring\}/g, (_,key)=>(values[key] || ['']).map(quote).join(','));
    for (const variable of dashboard.templating.list.filter(v=>v.type==='query')) {
        await db.query(interpolate(variable.query));
    }
    const table = dashboard.panels.find(p=>p.title==='Selected cycles and part measurements');
    assert.equal((await db.query(interpolate(table.targets[0].rawSql))).rows.length,1);
    values.material=["x'); DROP TABLE monitoring.cycles; --"];
    assert.equal((await db.query(interpolate(table.targets[0].rawSql))).rows.length,0);
    const legacy = fn('nodered_function.js', {payload:[{machine_id:'55t',session_id:'legacy',cycle_id:3,
        time_s:.1,timestamp_ns:1785838969691369500,CH0_T_futaba:40}]});
    assert.equal(legacy[2].payload[0].fields.cycle_num,3);
    await db.exec('SET ROLE monitoring_reader');
    await db.query('SELECT * FROM monitoring.cycle_catalog');
    await assert.rejects(db.query('DELETE FROM monitoring.cycles'), /permission denied/);
    await db.exec('RESET ROLE');
    console.log('PASS: SQL migration, edit-before-capture, exact ns, replay/conflict, out-of-order edits, clearing, failure gating, legacy and reader permissions.');
    console.log((await db.query('SELECT version()')).rows[0].version);
} finally { await db.close(); }
