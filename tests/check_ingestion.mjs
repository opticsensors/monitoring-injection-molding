// Run after installing the isolated PGlite test dependency under data/validation.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import queueModule from '../iot/nodered/capture_queue.cjs';
const {PGlite} = await import(pathToFileURL(resolve('data/validation/node_modules/@electric-sql/pglite/dist/index.js')));
const db = new PGlite();
const errors = [];
const node = {error: (error) => errors.push(error)};
function fn(file, msg) {
    return new Function('msg', 'node', 'global', fs.readFileSync('iot/nodered/' + file, 'utf8'))
        (msg, node, {get: () => queueModule});
}
const c = {machine_id:JSON.parse(fs.readFileSync('config/daq_config_defaults.json','utf8')).machine_id,
    session_id:'test-session', cycle_id:3, session_cycle:1,
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
    const enriched=structuredClone(payload);
    enriched.capture.injection_speed_mm_s=35;
    enriched.capture.signal_peaks={CH0_T_futaba:36};
    assert(fn('nodered_function.js',{payload:structuredClone(enriched)})[0]);
    enriched.capture.signal_peaks.CH0_T_futaba=999;
    assert.equal(fn('nodered_function.js',{payload:enriched}),null);
    assert.match(errors.at(-1),/peak does not match/);
    await db.exec(fs.readFileSync('iot/postgres/001_cycle_metadata.sql','utf8'));
    await db.exec(fs.readFileSync('iot/postgres/001_cycle_metadata.sql','utf8')); // reapply migration
    const beforeUpgrade={...c,session_id:'before-upgrade'};
    await db.query('SELECT monitoring.register_capture($1,md5($2),$3)',[beforeUpgrade,'original',m]);
    await db.query('SELECT monitoring.mark_stored($1,$2,$3,md5($4))',[c.machine_id,'before-upgrade',c.cycle_id,'original']);
    await db.exec(fs.readFileSync('iot/postgres/002_ingestion_recovery.sql','utf8'));
    await db.exec(fs.readFileSync('iot/postgres/002_ingestion_recovery.sql','utf8')); // safe migration rerun
    const upgraded=(await db.query("SELECT capture,waveform_status FROM monitoring.cycles WHERE session_id='before-upgrade'")).rows[0];
    assert.deepEqual(upgraded.capture,beforeUpgrade);
    assert.equal(upgraded.waveform_status,'stored');
    await db.query("DELETE FROM monitoring.cycles WHERE session_id='before-upgrade'");
    const update = {...m, revision:2, update_id:'newer', weight_g:12, length_mm:150,
        updated_at_ns:'1792400000000000001'};
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
    msg = fn('nodered_store_complete.js', {...msg, statusCode:204, payload:''})[1];
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
    const rejected = await db.query('SELECT monitoring.receive_measurements($1,$2,$3,$4) AS result',
        [c.machine_id,c.session_id,c.cycle_id,{...update,weight_g:99}]);
    assert.equal(rejected.rows[0].result,'conflict');
    assert.equal(Number((await db.query('SELECT count(*) FROM monitoring.measurement_conflicts')).rows[0].count),2);
    const exported = (await db.query(fs.readFileSync('iot/postgres/export_metadata.sql','utf8'))).rows[0].jsonb_build_object;
    assert.equal(exported.source,'server');
    assert.equal(exported.cycles[0].measurements.updated_at_ns, update.updated_at_ns);
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
    other.capture.machine_id = c.machine_id === '55t' ? '160t' : '55t';
    other.capture.session_id = "other-session'\\escaped";
    const next = fn('nodered_function.js',{payload:other})[0];
    const nextReceipt = (await db.query(next.query,next.params)).rows[0];
    await db.query('SELECT monitoring.mark_stored($1,$2,$3,$4)',
        [other.capture.machine_id,other.capture.session_id,other.capture.cycle_id,nextReceipt.fingerprint]);
    assert.equal(Number((await db.query('SELECT count(*) FROM monitoring.cycles')).rows[0].count),2);
    const predicates = (await db.query('SELECT influx_predicate FROM monitoring.cycle_catalog')).rows;
    assert(predicates.every(r=>r.influx_predicate.includes('"session_id"') && !r.influx_predicate.includes('time >=')));
    // Exercise the actual generated latest-cycles query with Grafana sqlstring quoting.
    const dashboard = JSON.parse(fs.readFileSync('iot/grafana_dashboard.json','utf8'));
    const values = {n_cycles:['10']};
    const quote = v => "'" + String(v).replaceAll("'", "''") + "'";
    const interpolate = sql => sql.replace(/\$\{(\w+):sqlstring\}/g,
        (_,key)=> (values[key] || ['']).map(quote).join(','));
    for (const variable of dashboard.templating.list.filter(v=>v.type==='query')) {
        await db.query(interpolate(variable.query));
    }
    assert.deepEqual(dashboard.templating.list.filter(v=>v.hide!==2).map(v=>v.name), ['n_cycles']);
    assert(!dashboard.panels.some(p=>p.title==='Selected cycles and part measurements'));
    const predicateVar=dashboard.templating.list.find(v=>v.name==='cycle_predicate');
    assert.equal(predicateVar.skipUrlSync,true);
    const combined=(await db.query(interpolate(predicateVar.query))).rows[0].__text;
    assert.equal((combined.match(/time >=/g)||[]).length,1);
    assert.equal((combined.match(/time <=/g)||[]).length,1);
    assert(combined.includes(' OR '));
    assert(combined.includes('"machine_id" = \'55t\''));
    assert(combined.includes('"machine_id" = \'160t\''));
    for (const count of ['1', '0', '100', '1000', '999999999999999999999', '', 'abc', "1'); DROP TABLE monitoring.cycles; --"]) {
        values.n_cycles=[count];
        const result=(await db.query(interpolate(predicateVar.query))).rows[0].__text;
        assert(result.includes('time >='));
        assert.equal((result.match(/"cycle_num"/g)||[]).length, ['0','1'].includes(count)?1:2);
    }
    values.n_cycles=['10'];
    // A newer continuous capture, another machine, and a pending capture must
    // never displace recorded cycles from 55t and 160t. Reused IDs remain separate.
    for (const [session, overrides, stored] of [
        ['excluded-continuous', {mode:'continuous'}, true],
        ['excluded-machine', {machine_id:'another-machine'}, true],
        ['excluded-pending', {}, false],
    ]) {
        const fixture={...c, ...overrides, session_id:session, first_time_ns:'1785838969691369601',
            last_time_ns:'1785838969691369602'};
        await db.query('SELECT monitoring.register_capture($1,md5($2),$3)',[fixture,session,m]);
        if (stored) await db.query('SELECT monitoring.mark_stored($1,$2,$3,md5($4))',
            [fixture.machine_id,session,fixture.cycle_id,session]);
    }
    assert.equal((await db.query(interpolate(predicateVar.query))).rows[0].__text, combined);
    // Empty history gives a false predicate instead of an unbounded Influx read.
    await db.exec('BEGIN');
    await db.exec('DELETE FROM monitoring.cycles');
    assert.equal((await db.query(interpolate(predicateVar.query))).rows[0].__text, '(time < 0 AND time > 0)');
    await db.exec('ROLLBACK');
    // Select latest captures across BOTH machines, capped at 100 total.
    await db.exec('BEGIN');
    for(let i=0;i<105;i++) {
        const fixture={...c,machine_id:i%2===0?'160t':'55t',session_id:'count-limit',cycle_id:1000+i*10,
            first_time_ns:String(1785838970000000000n+BigInt(i)*10n),
            last_time_ns:String(1785838970000000001n+BigInt(i)*10n)};
        await db.query('SELECT monitoring.register_capture($1,md5($2),$3)',[fixture,String(i),m]);
        await db.query('SELECT monitoring.mark_stored($1,$2,$3,md5($4))',
            [fixture.machine_id,fixture.session_id,fixture.cycle_id,String(i)]);
    }
    values.n_cycles=['1000'];
    const capped=(await db.query(interpolate(predicateVar.query))).rows[0].__text;
    assert.equal((capped.match(/"cycle_num"/g)||[]).length,100);
    assert.equal((capped.match(/"machine_id" = '55t'/g)||[]).length,50);
    assert.equal((capped.match(/"machine_id" = '160t'/g)||[]).length,50);
    assert(!capped.includes('"cycle_num" = 1000)'));
    assert(capped.includes('"cycle_num" = 2040)'));
    values.n_cycles=['1'];
    const latest=(await db.query(interpolate(predicateVar.query))).rows[0].__text;
    assert(latest.includes('"cycle_num" = 2040)'));
    assert(latest.includes('"machine_id" = \'160t\''));
    assert.equal((latest.match(/"cycle_num"/g)||[]).length,1);
    await db.exec('ROLLBACK');
    values.n_cycles=['10'];
    const legacy = fn('nodered_function.js', {payload:[{machine_id:'55t',session_id:'legacy',cycle_id:3,
        time_s:.1,timestamp_ns:1785838969691369500,CH0_T_futaba:40}]});
    assert.equal(legacy,null);
    assert(errors.at(-1).includes('Legacy upload retained'));
    // Embedded measurement conflicts must not block a new waveform.
    const conflictPayload=structuredClone(payload);
    conflictPayload.capture.session_id='measurement-conflict';
    conflictPayload.measurements={...update,weight_g:99};
    await db.query('SELECT monitoring.receive_measurements($1,$2,$3,$4)',
        [c.machine_id,'measurement-conflict',c.cycle_id,update]);
    const conflicted=fn('nodered_function.js',{payload:conflictPayload})[0];
    await db.exec('SET ROLE monitoring_ingest');
    await db.query(conflicted.query,conflicted.params);
    await assert.rejects(db.query('SELECT * FROM monitoring.cycles'),/permission denied/);
    await db.exec('RESET ROLE');
    const kept=(await db.query("SELECT weight_g,waveform_status FROM monitoring.cycles WHERE session_id='measurement-conflict'")).rows[0];
    assert.equal(kept.weight_g,12);
    assert.equal(kept.waveform_status,'pending');
    // Repeated legacy imports, and stale generated SQL containing native rows,
    // must neither abort nor downgrade an existing matching native capture.
    const legacyCapture={...c,session_id:'historical',status:'legacy',reason:'historical_catalog'};
    await db.query('SELECT monitoring.import_legacy($1)',[legacyCapture]);
    await db.query('SELECT monitoring.import_legacy($1)',[legacyCapture]);
    await db.query('SELECT monitoring.import_legacy($1)',[{...c,status:'legacy',reason:'historical_catalog'}]);
    assert.equal((await db.query('SELECT waveform_status FROM monitoring.cycles WHERE session_id=$1',[c.session_id])).rows[0].waveform_status,'stored');
    await assert.rejects(db.query('SELECT monitoring.import_legacy($1)',[{...legacyCapture,sample_count:999}]),/bounds\/count differ/);
    const owners=(await db.query("SELECT DISTINCT pg_get_userbyid(proowner) AS owner FROM pg_proc WHERE pronamespace='monitoring'::regnamespace AND prosecdef")).rows;
    assert.deepEqual(owners,[{owner:'monitoring_owner'}]);
    await db.exec('SET ROLE monitoring_reader');
    await db.query('SELECT * FROM monitoring.cycle_catalog');
    await db.query('SELECT * FROM monitoring.measurement_conflicts');
    await assert.rejects(db.query('DELETE FROM monitoring.cycles'), /permission denied/);
    await db.exec('RESET ROLE');
    console.log('PASS: migrations, exact ns, replay/overlap, measurement conflicts, export/backfill, latest-cycle selection/cap, shared time bounds and role permissions.');
    console.log((await db.query('SELECT version()')).rows[0].version);
} finally { await db.close(); }
