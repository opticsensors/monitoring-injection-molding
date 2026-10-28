// PostgreSQL semantics and Node-RED routing, entirely isolated through PGlite.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import history from '../iot/nodered/history_api.cjs';
const {PGlite} = await import(pathToFileURL(resolve('data/validation/node_modules/@electric-sql/pglite/dist/index.js')));
const db = new PGlite();
const c = {machine_id:'55t',session_id:'review-test',cycle_id:1,session_cycle:1,
    mode:'cycle',status:'complete',reason:'test',base_time_ns:'1785838969691369500',
    first_time_ns:'1785838969691369501',last_time_ns:'1785838969691369502',sample_count:2,
    trigger_start_ns:'1785838969691369500',trigger_end_ns:'1785838969691369503',
    material:'PP',mold_temperature_c:40,pressure_settings_bar:{limit:null},injection_speed_mm_s:35,
    signal_peaks:{CH0_T_futaba:40},config_snapshot:{field_names:['CH0_T_futaba']}};
const m = {revision:0,update_id:'initial',weight_g:null,length_mm:null};
const errors=[];
const route = payload => new Function('msg','node',fs.readFileSync('iot/nodered/nodered_function.js','utf8'))
    ({payload}, {error: e=>errors.push(e)});
const message = review => ({schema_version:1,kind:'review',machine_id:c.machine_id,session_id:c.session_id,cycle_id:c.cycle_id,review});
const send = async review => { const msg=route(message(review))[1]; return (await db.query(msg.query,msg.params)).rows[0].result; };
const r1={revision:1,update_id:'first',updated_at_ns:'1792400000000000001',excluded:true,
    settings:{mold_temperature_c:80,melt_temperature_c:220}};
try {
    for(const name of ['001_cycle_metadata.sql','002_ingestion_recovery.sql','003_history_reader.sql'])
        await db.exec(fs.readFileSync('iot/postgres/'+name,'utf8'));
    await db.query('SELECT monitoring.register_capture($1,md5($2),$3)',[c,'waveform',m]);
    await db.query('SELECT monitoring.mark_stored($1,$2,$3,md5($4))',[c.machine_id,c.session_id,c.cycle_id,'waveform']);
    for(let n=0;n<2;n++) await db.exec(fs.readFileSync('iot/postgres/004_cycle_review.sql','utf8'));
    for(let n=0;n<2;n++) await db.exec(fs.readFileSync('iot/postgres/005_machine_correction.sql','utf8'));
    let row=(await db.query('SELECT * FROM monitoring.cycle_catalog')).rows[0];
    assert.equal(row.melt_temperature_c,null);
    assert.equal(row.excluded,false);
    await db.exec('SET ROLE monitoring_ingest');
    assert.equal(await send(r1),'applied');
    assert.equal(await send(r1),'replay');
    const r2={...r1,revision:2,update_id:'second',settings:{machine_id:'160t',material:null,mold_temperature_c:0,melt_temperature_c:230}};
    assert.equal(await send(r2),'applied');
    assert.equal(await send(r1),'stale');
    assert.equal(await send({...r1,revision:2,update_id:'competing'}),'conflict');
    for(const settings of [{melt_temperature_c:-274},{injection_speed_mm_s:-1},{machine_id:'bad machine'},{machine_id:null},{material:3}]) {
        assert.equal(route(message({...r2,settings})),null);
        await assert.rejects(db.query('SELECT monitoring.receive_review($1,$2,$3,$4)',
            [c.machine_id,c.session_id,c.cycle_id,{...r2,settings}]),/Invalid|Unknown/);
    }
    await db.exec('RESET ROLE');
    row=(await db.query('SELECT * FROM monitoring.cycle_catalog')).rows[0];
    assert.equal(row.material,null);
    assert.equal(row.mold_temperature_c,0);
    assert.equal(row.melt_temperature_c,230);
    assert.equal(row.review_revision,2);
    assert.equal(row.effective_machine_id,'160t');
    assert.equal(row.machine_id,'55t');
    assert.match(row.influx_predicate,/55t/);
    assert.equal(row.excluded,true);
    assert.deepEqual((await db.query('SELECT capture FROM monitoring.cycles')).rows[0].capture,c);
    await db.query('SELECT monitoring.register_capture($1,md5($2),$3)',[c,'waveform',m]);
    assert.deepEqual((await db.query('SELECT review FROM monitoring.cycles')).rows[0].review,r2);
    await db.exec(fs.readFileSync('iot/postgres/005_machine_correction.sql','utf8'));
    assert.deepEqual((await db.query('SELECT review FROM monitoring.cycles')).rows[0].review,r2);
    const exported=(await db.query(fs.readFileSync('iot/postgres/export_metadata.sql','utf8'))).rows[0].jsonb_build_object;
    assert.deepEqual(exported.cycles[0].capture,c);
    assert.equal(exported.cycles[0].effective_settings.mold_temperature_c,0);
    assert.equal(exported.cycles[0].review.excluded,true);
    await db.exec('SET ROLE monitoring_reader');
    const api=history.createApi({config:{token:'test'},query:(sql,params)=>db.query(sql,params)});
    const read=query=>api.handle({method:'GET',path:'/monitoring/history',authorization:'Bearer test',query});
    assert.deepEqual((await read({})).body.cycles,[]);
    assert.equal((await read({include_excluded:'1'})).body.cycles.length,1);
    const refresh=await read({keys:JSON.stringify([[c.machine_id,c.session_id,c.cycle_id]])});
    assert.equal(refresh.body.cycles[0].review.excluded,true);
    assert.equal(refresh.body.cycles[0].effective_settings.melt_temperature_c,230);
    assert.equal((await read({keys:'invalid'})).status,400);
    await assert.rejects(send({...r2,revision:3}),/permission denied/);
    await db.exec('RESET ROLE');
    assert.equal(await send({...r2,revision:3,update_id:'restore',excluded:false}),'applied');
    assert.equal((await read({})).body.cycles.length,1);
    // Edits may precede capture delivery without losing either source.
    c.session_id='offline-first';
    assert.equal(await send(r1),'applied');
    await db.query('SELECT monitoring.register_capture($1,md5($2),$3)',[c,'waveform',m]);
    const later=(await db.query("SELECT capture,review FROM monitoring.cycles WHERE session_id='offline-first'")).rows[0];
    assert.deepEqual(later.capture,c);
    assert.deepEqual(later.review,r1);
    console.log('PASS: migration upgrade/rerun, immutable originals, latest corrections, null/zero, stale/conflict rejection, exclusion/restore, targeted History refresh, export and role permissions.');
} finally { await db.close(); }
