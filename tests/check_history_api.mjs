// Real PostgreSQL semantics through PGlite; injected Influx responses, no server access.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import history from '../iot/nodered/history_api.cjs';
const {PGlite} = await import(pathToFileURL(resolve('data/validation/node_modules/@electric-sql/pglite/dist/index.js')));
const db = new PGlite();
const token = 'test-only-history', queries = [], influxQueries = [];
const samples = [35, 40, 37];
const document = (columns, values) => ({results:[{series:[{columns,values}]}]});
let mismatch = false;
const influx = async query => {
    influxQueries.push(query);
    if(query.startsWith('SHOW')) return document(['fieldKey'], [['CH0_T_futaba']]);
    if(query.startsWith('SELECT max')) return document(['CH0_T_futaba'], [[40]]);
    return document(['time','t_ms','CH0_T_futaba'],
        samples.slice(0,mismatch?2:3).map((value,i)=>['2026-08-04T10:22:49.691369501Z',i*10,value]));
};
const api = history.createApi({config:{token}, influx,
    query:(query,params)=>{queries.push([query,params]);return db.query(query,params);}});
const request = (path='/monitoring/history', query={}, authorization='Bearer '+token, method='GET') =>
    api.handle({path,query,authorization,method});
try {
    for(const file of ['001_cycle_metadata.sql','002_ingestion_recovery.sql','003_history_reader.sql','004_cycle_review.sql','004_cycle_review.sql'])
        await db.exec(fs.readFileSync('iot/postgres/'+file,'utf8'));
    assert.equal((await request(undefined,{},'')).status,401);
    assert.equal(queries.length,0);
    assert.equal((await request(undefined,{},'Bearer '+token,'POST')).status,405);
    assert.equal((await request('/monitoring/history',{cursor:'invalid'})).status,400);
    assert.equal((await request('/monitoring/waveform',{machine_id:'55t',session_id:'x',cycle_id:'1 OR 1=1'})).status,400);
    const entries=[];
    for(let n=0;n<13;n++) {
        const first=1785838969691369501n + BigInt(n)*1000000000n;
        const c={machine_id:n%2?'160t':'55t',session_id:"history'\\test",cycle_id:n+1,session_cycle:n+1,
            mode:'cycle',status:'complete',reason:'test',base_time_ns:String(first),
            first_time_ns:String(first),last_time_ns:String(first+20000000n),sample_count:3,
            trigger_start_ns:String(first),trigger_end_ns:String(first+30000000n),material:'PP',
            mold_temperature_c:40,pressure_settings_bar:{limit:null},injection_speed_mm_s:35,
            signal_peaks:{CH0_T_futaba:40},config_snapshot:{field_names:['CH0_T_futaba'],field_units:['°C']}};
        if(n===0){delete c.signal_peaks;c.config_snapshot={};}
        const m={revision:0,update_id:'initial-'+n,weight_g:null,length_mm:null,updated_at_ns:'1792400000000000001'};
        await db.query('SELECT monitoring.register_capture($1,md5($2),$3)',[c,'samples'+n,m]);
        await db.query('SELECT monitoring.mark_stored($1,$2,$3,md5($4))',[c.machine_id,c.session_id,c.cycle_id,'samples'+n]);
        entries.push(c);
    }
    // Real access grants: the API uses only the reader role.
    await db.exec('SET ROLE monitoring_reader');
    const first=await request();
    assert.equal(first.status,200,JSON.stringify(first));
    assert.equal(first.body.cycles.length,10);
    assert.equal(first.body.cycles[0].capture.cycle_id,13);
    assert.equal(influxQueries.length,0,'New summaries should not query waveform storage');
    assert.equal(first.body.cycles[0].measurements.updated_at_ns,'1792400000000000001');
    const second=await request('/monitoring/history',{cursor:first.body.next_cursor});
    assert.equal(second.status,200);
    assert.deepEqual(second.body.cycles.map(e=>e.capture.cycle_id),[3,2,1]);
    assert.equal(second.body.next_cursor,null);
    assert.equal(second.body.cycles.at(-1).summary.signal_peaks.CH0_T_futaba,40);
    const count=influxQueries.length;
    await request('/monitoring/history',{cursor:first.body.next_cursor});
    assert.equal(influxQueries.length,count,'Legacy summary should be cached');
    for(const c of [entries[0],entries[1]]) {
        const query={machine_id:c.machine_id,session_id:c.session_id,cycle_id:String(c.cycle_id)};
        const wave=await request('/monitoring/waveform',query);
        assert.equal(wave.status,200,JSON.stringify(wave));
        assert.deepEqual(wave.body.time_s,[0,.01,.02]);
        assert.deepEqual(wave.body.values.CH0_T_futaba,samples);
        assert(influxQueries.at(-1).includes('time >= '+c.first_time_ns));
        assert(influxQueries.at(-1).includes("\"session_id\" = 'history\\'\\\\test'"));
    }
    mismatch=true;
    assert.equal((await request('/monitoring/waveform',
        {machine_id:'55t',session_id:"history'\\test",cycle_id:'1'})).status,409);
    await assert.rejects(db.query("DELETE FROM monitoring.cycles"),/permission denied/);
    console.log('PASS: reader permissions, auth, pagination across machines, exact bounds, legacy peaks, raw waveforms and count mismatch.');
} finally { await db.close(); }
