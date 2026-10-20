// Filesystem + PGlite + actual flow functions. HTTP responses are simulated;
// deployment must additionally run tests/check_stack.py against real services.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {PGlite} from '../data/validation/node_modules/@electric-sql/pglite/dist/index.js';
import store from '../iot/nodered/capture_queue.cjs';
const root=fs.mkdtempSync(path.join(os.tmpdir(),'capture-recovery-'));
const db=new PGlite();
let now=1000000;
let q=new store.CaptureQueue(root,{now:()=>now,leaseMs:1000});
const logs=[];
const node={error:(error,msg)=>{msg.error={message:error};logs.push(msg);},warn:()=>{}};
const globals={get:()=>({...store,queue:()=>q})};
const fn=(file,msg)=>new Function('msg','node','global',fs.readFileSync('iot/nodered/'+file,'utf8'))(msg,node,globals);
try {
    await db.exec(fs.readFileSync('iot/postgres/001_cycle_metadata.sql','utf8'));
    await db.exec(fs.readFileSync('iot/postgres/002_ingestion_recovery.sql','utf8'));
    const id=q.enqueue('{"test":true}','review/sensors');
    assert.equal(q.enqueue('{"test":true}','review/sensors'),id);
    assert.equal(q.status().length,1);
    const abandoned=q.claim();
    assert.equal(q.claim(),null);
    q=new store.CaptureQueue(root,{now:()=>now,leaseMs:1000});
    assert.equal(q.claim(),null); // restart keeps an unexpired lease
    now+=1001;
    const recovered=q.claim();
    assert.notEqual(recovered.queueLease,abandoned.queueLease);
    assert.equal(q.complete(abandoned),false);
    q.fail(recovered,'temporary PostgreSQL outage');
    assert.equal(q.claim(),null);
    now+=300000;
    const retry=q.claim();
    assert.equal(retry.payload,'{"test":true}');
    q.fail(retry,'review required',true);
    assert.equal(q.status()[0].folder,'quarantine');
    q.requeue(id);
    q.complete(q.claim());
    assert.deepEqual(q.status(),[]);
    assert.throws(()=>q.requeue('../outside'),/Invalid queue ID/);

    // Limit bytes as well as rows, including UTF-8 machine/session IDs.
    const lines=['sensor_data,machine_id=é x=1 1','sensor_data,machine_id=é x=2 2'];
    const byteLimit=Buffer.byteLength(lines[0]);
    assert.equal(store.splitLines(lines.join('\n'),5000,byteLimit).length,2);
    assert.throws(()=>store.splitLines(lines[0],5000,1),/oversized/);

    const base=1785838969691369500n;
    const samples=Array.from({length:12001},(_,i)=>({timestamp_ns:String(base+BigInt(i)*1000000n),
        time_s:i/1000,sample_index:i,CH0_T_futaba:35+i/7}));
    const c={machine_id:'queue-test',session_id:'queue-test-session',cycle_id:0,session_cycle:0,
        mode:'continuous',status:'complete',reason:'stop',base_time_ns:String(base),
        first_time_ns:samples[0].timestamp_ns,last_time_ns:samples.at(-1).timestamp_ns,sample_count:samples.length,
        trigger_start_ns:null,trigger_end_ns:null,material:null,mold_temperature_c:null,
        pressure_settings_bar:{limit:null},config_snapshot:{field_names:['CH0_T_futaba'],saved_indices:[0]}};
    const payload={schema_version:1,kind:'capture',capture:c,
        measurements:{revision:0,update_id:'initial',weight_g:null,length_mm:null},samples};
    fn('nodered_enqueue.js',{payload:JSON.stringify(payload),topic:'queue-test/sensors'});
    const influxPoints=new Map();
    let totalRequests=0;
    async function attempt(failure) {
        let job=fn('nodered_claim.js',{});
        assert(job);
        let msg=fn('nodered_function.js',job)[0];
        if(failure==='postgres') {
            msg.error={message:'simulated unavailable PostgreSQL'};
            fn('nodered_queue_error.js',msg); return;
        }
        msg.payload=(await db.query(msg.query,msg.params)).rows;
        msg=fn('nodered_prepare_write.js',msg);
        assert.equal(msg.writeChunks.length,3);
        while(true) {
            assert(Buffer.byteLength(msg.payload)<=4000000);
            assert(msg.payload.split('\n').length<=5000);
            totalRequests++;
            if(failure==='middle-chunk' && msg.chunkIndex===1) {
                msg.statusCode=500; msg.payload='simulated Influx outage';
                assert.equal(fn('nodered_store_complete.js',msg),null);
                fn('nodered_queue_error.js',msg); return;
            }
            for(const line of msg.payload.split('\n')) {
                const stamp=line.slice(line.lastIndexOf(' ')+1);
                if(influxPoints.has(stamp)) assert.equal(influxPoints.get(stamp),line);
                influxPoints.set(stamp,line);
            }
            msg.statusCode=204; msg.payload='';
            const [more,finished]=fn('nodered_store_complete.js',msg);
            if(more) {msg=more;continue;}
            msg=finished;
            if(failure==='mark-stored') {
                msg.error={message:'simulated PostgreSQL failure after all Influx writes'};
                fn('nodered_queue_error.js',msg);return;
            }
            msg.payload=(await db.query(msg.query,msg.params)).rows;
            fn('nodered_queue_complete.js',msg); return;
        }
    }
    await attempt('postgres');
    assert.equal(Number((await db.query('SELECT count(*) FROM monitoring.cycles')).rows[0].count),0);
    now+=300000;
    await attempt('middle-chunk');
    assert.equal(influxPoints.size,5000);
    assert.equal((await db.query('SELECT waveform_status FROM monitoring.cycles')).rows[0].waveform_status,'pending');
    now+=300000;
    q=new store.CaptureQueue(root,{now:()=>now,leaseMs:1000});
    await attempt('mark-stored');
    assert.equal(influxPoints.size,samples.length);
    assert.equal(q.status().length,1);
    assert.equal((await db.query('SELECT waveform_status FROM monitoring.cycles')).rows[0].waveform_status,'pending');
    now+=300000;
    await attempt();
    assert.equal(influxPoints.size,samples.length);
    assert.equal(totalRequests,8);
    assert.equal((await db.query('SELECT waveform_status FROM monitoring.cycles')).rows[0].waveform_status,'stored');
    assert.deepEqual(q.status(),[]);
    // Invalid JSON and legacy arrays are saved BEFORE validation, then quarantined.
    for(const raw of ['not-json','[{"cycle_id":3}]']) {
        fn('nodered_enqueue.js',{payload:raw,topic:'legacy/sensors'});
        const msg=fn('nodered_claim.js',{});
        assert.equal(fn('nodered_function.js',msg),null);
        fn('nodered_queue_error.js',msg);
        assert.equal(JSON.parse(fs.readFileSync(q.file('quarantine',msg.queueId),'utf8')).raw,raw);
    }
    assert.equal(q.status().filter(s=>s.folder==='quarantine').length,2);
    const archived=q.status()[0].id;
    q.archive(archived,'Reviewed test-only invalid message');
    assert(fs.existsSync(q.file('archive',archived)));
    assert.equal(q.status().length,1);
    console.log('PASS: durable enqueue, deduplication, leases/restarts, stale completion, backoff, quarantine/requeue, byte/row limits, DB outage, partial Influx writes, failed final receipt and exact replay.');
} finally {
    await db.close();
    fs.rmSync(root,{recursive:true,force:true});
}
