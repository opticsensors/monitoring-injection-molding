import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {simulate,PRESETS,NOMINAL,DEFAULTS,distance,distortLocal} from './model.js';
const near=(a,b,tolerance=1e-8)=>assert.ok(Math.abs(a-b)<tolerance,`${a} != ${b} (tol ${tolerance})`);
const flat=simulate(PRESETS.flat.values);
near(flat.spatial_mm,NOMINAL,1e-4);near(flat.error_mm,0);near(flat.mm_per_px,(800-35)*.0024/35);
const up=simulate(PRESETS.raised.values);near(up.apparent_mm,up.spatial_mm*800/799);
assert.equal(DEFAULTS.scale_error_pct,0);assert.equal(DEFAULTS.distortion_pct,0);
for(const percent of [-1,-.02,.02,1]){
  const r=simulate({...PRESETS.flat.values,scale_error_pct:percent});
  near(r.error_mm,flat.spatial_mm*percent/100);near(r.diameter_error_worst_mm,4*percent/100);
  near(r.mm_per_px,flat.mm_per_px);near(r.applied_mm_per_px,flat.mm_per_px*(1+percent/100));
  assert.equal(r.fully_visible,flat.fully_visible);assert.deepEqual(r.points,flat.points);
}
const compound=simulate({...PRESETS.raised.values,scale_error_pct:.1});near(compound.error_mm,flat.spatial_mm*(800/799*1.001-1));
for(const sign of [-1,1]){
  const r=simulate({...PRESETS.flat.values,distortion_pct:sign});
  assert.ok(r.error_mm*sign>0);assert.ok(r.diameter_error_worst_mm*sign>0);
  near(r.error_mm,r.geometry_error_mm+r.distortion_delta_mm+r.scale_delta_mm);
  assert.deepEqual(r.points,flat.points);
}
// Distorsión radial: el estiramiento radial y tangencial son distintos.
const radius=100,pos=50,half=2,pct=1,a=pct/100;
near(distance(distortLocal(pos-half,0,radius,pct),distortLocal(pos+half,0,radius,pct)),4*(1+a*(3*pos**2+half**2)/radius**2));
near(distance(distortLocal(pos,-half,radius,pct),distortLocal(pos,half,radius,pct)),4*(1+a*(pos**2+half**2)/radius**2));
near(distortLocal(radius,0,radius,pct)[0],radius*1.01);
assert.ok(distortLocal(100*radius,0,radius,-5)[0]>radius,'No reentrada espuria por extrapolación');
const offAxis=simulate({...PRESETS.flat.values,distortion_pct:1,camera_x:30});
assert.ok(Math.abs(offAxis.error_mm-simulate({...PRESETS.flat.values,distortion_pct:1}).error_mm)>1e-3);
near(up.error_mm,.638934,2e-6);
near(flat.diameter_error_max_abs_mm,0);near(up.diameter_error_worst_mm,4/799);
near(simulate({...PRESETS.raised.values,diameter:3}).diameter_error_worst_mm,3/799);
near(simulate({...PRESETS.raised.values,calibration_z:1}).diameter_error_max_abs_mm,0);
near(simulate({...PRESETS.raised.values,calibration_z:1}).error_mm,0);
const tilted=simulate(PRESETS.tilted.values);near(tilted.spatial_mm,flat.spatial_mm);near(tilted.z_min_mm,-.5);near(tilted.z_max_mm,.5);
assert.ok(tilted.orthographic_mm<tilted.spatial_mm);
for(const shape of ['wave','bump'])for(const span of [1,10,20])for(const waves of [1,3,8]){
  const r=simulate({shape,span,waves,tilt:5,phase:25});near(r.spatial_mm,flat.spatial_mm);
  for(let i=1;i<r.points.length;i++)near(distance(r.points[i],r.points[i-1]),distance(r.base[i].slice(0,2),r.base[i-1].slice(0,2)),1e-10);
}
const wave=simulate(PRESETS.wave.values);near(wave.z_min_mm,-.5);near(wave.z_max_mm,.5);
near(wave.diameter_error_max_abs_mm,4*.5/799.5);
// El extremo interior permanece fijo en XYZ, incluso al cambiar fase e inclinación.
for(const shape of ['wave','bump','radial_drop'])for(const span of [0,1,10,20])for(const tilt of [0,5]){
  const r=simulate({shape,span,tilt,lift:2,phase:40});
  near(r.points[0][0],r.base[0][0]);near(r.points[0][1],r.base[0][1]);near(r.points[0][2],2);
}
for(const span of [0,1,10,20]){
  const r=simulate({shape:'radial_drop',span});near(r.z_max_mm,0);near(r.z_min_mm,-span);
  near(r.diameter_error_worst_mm,-4*span/(800+span));
  for(let i=0;i<r.points.length;i++){
    near(r.points[i][0],r.base[i][0]);near(r.points[i][1],r.base[i][1]);
    if(i)assert.ok(r.points[i][2]<=r.points[i-1][2]+1e-9,'Descenso progresivo');
  }
  if(span)assert.ok(r.spatial_mm>flat.spatial_mm,'Conservar XY al añadir Z aumenta longitud 3D');
  assert.equal(r.parameters.deformation,'fixed_xy');assert.equal(r.parameters.anchor,'start');
  const bump=simulate({shape:'bump',span});near(bump.z_min_mm,0);near(bump.z_max_mm,span);
}
near(simulate(PRESETS.positive.values).z_min_mm,0);near(simulate(PRESETS.positive.values).z_max_mm,1);
const xy=simulate({...PRESETS.wave.values,deformation:'fixed_xy'});near(xy.orthographic_mm,flat.spatial_mm);assert.ok(xy.spatial_mm>flat.spatial_mm);
const focal=simulate({...PRESETS.wave.values,focal:75});near(focal.error_mm,wave.error_mm);assert.ok(focal.fov_mm[0]<wave.fov_mm[0]);
const clipped=simulate({shape:'flat',focal:100,camera_z:250});assert.equal(clipped.fully_visible,false);assert.ok(clipped.visible_mm<clipped.apparent_mm);
const outside=simulate({shape:'flat',focal:100,camera_z:250,camera_x:150});near(outside.visible_mm,0);
near(wave.error_mm,wave.projection_loss_mm+wave.perspective_delta_mm);
const fine=simulate(PRESETS.wave.values,.02);near(fine.spatial_mm,NOMINAL,1e-5);near(fine.error_mm,wave.error_mm,1e-6);
// Referencia Python ejecutada de nuevo, no una copia de los resultados del navegador.
const py=spawnSync('py',['-3.11','-X','utf8','model.py','--step','.02'],{encoding:'utf8'});
assert.equal(py.status,0,py.stderr);const report=JSON.parse(py.stdout);
const keys=['spatial_mm','orthographic_mm','apparent_mm','ideal_apparent_mm','distorted_apparent_mm','error_mm','geometry_error_mm','distortion_delta_mm','scale_delta_mm','visible_mm','z_min_mm','z_max_mm','z_mean_arclength_mm','z_start_mm','mm_per_px','applied_mm_per_px','diameter_error_min_mm','diameter_error_max_mm','diameter_error_worst_mm','diameter_error_max_abs_mm'];
for(const [name,expected] of Object.entries(report.scenarios)){
  const actual=simulate(expected.parameters,.02);
  for(const key of keys)near(actual[key],expected[key],5e-8);
  assert.equal(actual.fully_visible,expected.fully_visible,name);
  assert.equal(actual.diameter_fully_visible,expected.diameter_fully_visible,name);
  near(actual.error_mm,actual.geometry_error_mm+actual.distortion_delta_mm+actual.scale_delta_mm);
}
console.log(JSON.stringify({status:'PASS',checks:['geometría nominal','elevación analítica','calibración a altura de pieza','rotación rígida','conservación por segmento: 18 configuraciones','centro fijo con desnivel, fase e inclinación','bulto apoyado','caída radial: XY y descenso','error de diámetro analítico y signo','desniveles centrado y positivo','XY fijo','invariancia con focal a Z fijo','recorte parcial y total','descomposición del error','convergencia',`${Object.keys(report.scenarios).length} escenarios Python/JavaScript`],default_example:{zmin:wave.z_min_mm,zmax:wave.z_max_mm,length3d:wave.spatial_mm,interpreted:wave.apparent_mm,error:wave.error_mm,diameter_error:wave.diameter_error_worst_mm}},null,2));
