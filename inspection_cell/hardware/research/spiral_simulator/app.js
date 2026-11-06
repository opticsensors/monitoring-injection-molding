import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {DEFAULTS,PRESETS,SENSOR,simulate} from './model.js';

const $=id=>document.getElementById(id);
const fmt=(x,n=3)=>new Intl.NumberFormat('es-ES',{minimumFractionDigits:n,maximumFractionDigits:n}).format(Math.abs(x)<.5*10**(-n)?0:x);
const signed=(x,n=4)=>(x>0?'+':'')+fmt(x,n);
const host=$('scene'),colors={part:0xd58a3d,fov:0x477d9e,nominal:0x9ca8b2};
let state={...DEFAULTS},result,scope='full',orientation='iso',pending=false;
let scene,renderer,camera,controls,dynamic,frustum,projection,nominal,grid,cameraBody,part,fitHeight=1000;
let showFov=true,showGrid=true;
const axes={x:new THREE.Vector3(1,0,0),y:new THREE.Vector3(0,1,0),z:new THREE.Vector3(0,0,1)};
const directions={iso:new THREE.Vector3(1,-1.4,.75).normalize(),top:new THREE.Vector3(0,-.00001,1).normalize(),front:new THREE.Vector3(0,-1,0),right:new THREE.Vector3(1,0,0)};
function gain(){return scope==='piece'?Number($('z-gain').value):1;}
function clean(group){while(group.children.length){const child=group.children[0];group.remove(child);child.traverse(o=>{o.geometry?.dispose();if(Array.isArray(o.material))o.material.forEach(m=>m.dispose());else o.material?.dispose();});}}
function line(points,color,dashed=false,opacity=1){
  const geom=new THREE.BufferGeometry().setFromPoints(points.map(q=>new THREE.Vector3(...q)));
  const mat=dashed?new THREE.LineDashedMaterial({color,dashSize:2,gapSize:1.5,transparent:opacity<1,opacity}):new THREE.LineBasicMaterial({color,transparent:opacity<1,opacity});
  const object=new THREE.Line(geom,mat);if(dashed)object.computeLineDistances();return object;
}
class PolyCurve extends THREE.Curve{
  constructor(points){super();this.points=points;}
  getPoint(t,target=new THREE.Vector3()){const x=t*(this.points.length-1),i=Math.min(Math.floor(x),this.points.length-2),k=x-i,a=this.points[i],b=this.points[i+1];return target.set(a[0]+k*(b[0]-a[0]),a[1]+k*(b[1]-a[1]),a[2]+k*(b[2]-a[2]));}
}
function drawScene(){
  clean(dynamic);const p=state,r=result,g=gain(),hw=r.fov_mm[0]/2,hh=r.fov_mm[1]/2,zc=p.calibration_z*g;
  const size=Math.max(180,Math.min(800,Math.max(...r.fov_mm)*1.2));
  grid=new THREE.GridHelper(size,Math.ceil(size/20),0xaebac5,0xc7d1db);grid.rotation.x=Math.PI/2;grid.visible=showGrid;grid.material.transparent=true;grid.material.opacity=.5;dynamic.add(grid);
  const points=r.points.filter((q,i)=>i%5===0||i===r.points.length-1).map(q=>[q[0],q[1],q[2]*g]);
  part=new THREE.Mesh(new THREE.TubeGeometry(new PolyCurve(points),1500,1,10,false),new THREE.MeshStandardMaterial({color:colors.part,roughness:.37,metalness:.15}));dynamic.add(part);
  nominal=line(r.base.filter((q,i)=>i%4===0||i===r.base.length-1).map(q=>[q[0],q[1],0]),colors.nominal,true);nominal.visible=$('show-nominal').checked;dynamic.add(nominal);
  projection=line(r.projected.map(q=>[q[0],q[1],zc+.02]),colors.fov,true);projection.material.depthTest=false;projection.renderOrder=2;projection.visible=$('show-projection').checked;dynamic.add(projection);
  frustum=new THREE.Group();const apex=[p.camera_x,p.camera_y,p.camera_z*g];
  const corners=[[-hw,-hh],[hw,-hh],[hw,hh],[-hw,hh]].map(([x,y])=>[x+p.camera_x,y+p.camera_y,zc]);
  frustum.add(line([...corners,corners[0]],colors.fov));for(const q of corners)frustum.add(line([apex,q],colors.fov,false,.58));
  const vertices=[];for(let i=0;i<4;i++)vertices.push(...apex,...corners[i],...corners[(i+1)%4]);
  const geom=new THREE.BufferGeometry();geom.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));
  frustum.add(new THREE.Mesh(geom,new THREE.MeshBasicMaterial({color:colors.fov,transparent:true,opacity:.025,side:THREE.DoubleSide,depthWrite:false})));
  frustum.add(line([apex,[p.camera_x,p.camera_y,zc]],0x8b9ba9,true,.45));frustum.visible=showFov;dynamic.add(frustum);
  cameraBody=new THREE.Group();cameraBody.position.set(...apex);
  const body=new THREE.Mesh(new THREE.BoxGeometry(29,29,30),new THREE.MeshStandardMaterial({color:0x566676,metalness:.35,roughness:.4}));body.position.z=27;cameraBody.add(body);
  const edges=new THREE.LineSegments(new THREE.EdgesGeometry(body.geometry),new THREE.LineBasicMaterial({color:0x33414f}));edges.position.copy(body.position);cameraBody.add(edges);
  for(const [radius,height,z,color] of [[10,20,3,0x273541],[12,5,12,0x435362],[10.5,3,-6,0x617a8c]]){
    const lens=new THREE.Mesh(new THREE.CylinderGeometry(radius,radius,height,32),new THREE.MeshStandardMaterial({color,roughness:.3,metalness:.5}));lens.rotation.x=Math.PI/2;lens.position.z=z;cameraBody.add(lens);
  }dynamic.add(cameraBody);
  $('gain-note').hidden=g===1;$('gain-note').textContent=`Relieve visual ×${g}`;render();
}
function sceneBounds(){
  const box=new THREE.Box3();
  if(scope==='piece'){
    for(const p of result.points)box.expandByPoint(new THREE.Vector3(p[0],p[1],p[2]*gain()));box.expandByScalar(8);
  }else{
    const p=state,w=result.fov_mm[0]/2,h=result.fov_mm[1]/2;
    box.expandByPoint(new THREE.Vector3(p.camera_x-w,p.camera_y-h,p.calibration_z));box.expandByPoint(new THREE.Vector3(p.camera_x+w,p.camera_y+h,p.calibration_z));
    box.expandByPoint(new THREE.Vector3(p.camera_x-16,p.camera_y-16,p.camera_z-8));box.expandByPoint(new THREE.Vector3(p.camera_x+16,p.camera_y+16,p.camera_z+44));
    for(const q of result.points)box.expandByPoint(new THREE.Vector3(...q));box.expandByScalar(10);
  }return box;
}
function fitView(newScope=scope,newOrientation=null){
  if(!camera||!result)return;
  const previousGain=gain();scope=newScope;if(previousGain!==gain())drawScene();
  if(newOrientation)orientation=newOrientation;
  const direction=newOrientation?directions[newOrientation]:camera.position.clone().sub(controls.target).normalize();
  if(direction.lengthSq()<.5)direction.copy(directions.iso);
  const box=sceneBounds(),center=box.getCenter(new THREE.Vector3()),size=box.getSize(new THREE.Vector3()),distance=Math.max(200,size.length()*2.8);
  controls.target.copy(center);camera.position.copy(center).addScaledVector(direction,distance);camera.up.set(0,0,1);camera.lookAt(center);camera.updateMatrixWorld(true);
  const inverse=camera.quaternion.clone().invert();let xMax=0,yMax=0;
  for(const x of [box.min.x,box.max.x])for(const y of [box.min.y,box.max.y])for(const z of [box.min.z,box.max.z]){
    const v=new THREE.Vector3(x,y,z).sub(center).applyQuaternion(inverse);xMax=Math.max(xMax,Math.abs(v.x));yMax=Math.max(yMax,Math.abs(v.y));
  }
  const aspect=host.clientWidth/host.clientHeight;fitHeight=Math.max(2*yMax,2*xMax/aspect)*1.12;camera.zoom=1;resizeProjection();controls.update();updateViewLabel();render();
}
function resizeProjection(){const aspect=host.clientWidth/host.clientHeight;camera.left=-fitHeight*aspect/2;camera.right=fitHeight*aspect/2;camera.top=fitHeight/2;camera.bottom=-fitHeight/2;camera.updateProjectionMatrix();}
function updateViewLabel(){const names={iso:'Isométrica',top:'Superior',front:'Frontal',right:'Derecha',free:'Libre'};$('view-label').textContent=names[orientation]+(scope==='piece'?' · Pieza':'');for(const key of ['iso','top','front','right'])$('view-'+key).setAttribute('aria-pressed',String(key===orientation));$('view-piece').setAttribute('aria-pressed',String(scope==='piece'));}
function drawGizmo(){if(!camera)return;const inverse=camera.quaternion.clone().invert();for(const [key,axis] of Object.entries(axes)){const v=axis.clone().applyQuaternion(inverse),x=40+v.x*28,y=40-v.y*28,button=$('axis-'+key),stroke=$('line-'+key);button.style.left=x+'px';button.style.top=y+'px';button.style.zIndex=String(Math.round(20+10*v.z));stroke.setAttribute('x1','40');stroke.setAttribute('y1','40');stroke.setAttribute('x2',String(x));stroke.setAttribute('y2',String(y));}}
function render(){if(renderer&&camera){renderer.render(scene,camera);drawGizmo();}}
function init3D(){
  renderer=new THREE.WebGLRenderer({antialias:true,alpha:true,preserveDrawingBuffer:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.setSize(host.clientWidth,host.clientHeight,false);host.prepend(renderer.domElement);$('loading').remove();
  scene=new THREE.Scene();scene.add(new THREE.AmbientLight(0xffffff,1.8));const light=new THREE.DirectionalLight(0xffffff,2.5);light.position.set(150,-350,900);scene.add(light);
  dynamic=new THREE.Group();scene.add(dynamic);camera=new THREE.OrthographicCamera(-500,500,500,-500,.1,100000);camera.up.set(0,0,1);camera.position.set(1000,-1400,1000);
  const canvas=renderer.domElement;
  // Captura antes de OrbitControls: Shift+MMB hace zoom; Ctrl+MMB hace pan.
  canvas.addEventListener('pointerdown',event=>{if(event.button===1)controls.mouseButtons.MIDDLE=event.shiftKey&&!event.ctrlKey?THREE.MOUSE.DOLLY:THREE.MOUSE.ROTATE;},true);
  controls=new OrbitControls(camera,canvas);controls.mouseButtons={LEFT:THREE.MOUSE.ROTATE,MIDDLE:THREE.MOUSE.ROTATE,RIGHT:THREE.MOUSE.PAN};controls.zoomToCursor=true;controls.screenSpacePanning=true;controls.minZoom=.03;controls.maxZoom=200;controls.rotateSpeed=.65;controls.zoomSpeed=1.1;controls.enableDamping=false;
  controls.addEventListener('change',render);controls.addEventListener('start',()=>{orientation='free';updateViewLabel();});canvas.addEventListener('dblclick',()=>fitView('piece'));
  new ResizeObserver(()=>{renderer.setSize(host.clientWidth,host.clientHeight,false);resizeProjection();render();}).observe(host);
}
function updateNumbers(){
  const r=result;$('real-value').textContent=fmt(r.spatial_mm,4)+' mm';$('apparent-value').textContent=r.fully_visible?fmt(r.apparent_mm,4)+' mm':'Recortada';$('error-value').textContent=r.fully_visible?signed(r.error_mm,4)+' mm':'—';
  $('diameter-error-value').textContent=r.fully_visible&&r.diameter_fully_visible?signed(r.diameter_error_worst_mm,4)+' mm':'—';
  $('diameter-error-value').title=`Ø horizontal ideal ${fmt(state.diameter,1)} mm. Incluye altura, escala y distorsión simuladas. Mayor error absoluto local, con signo. Rango: ${signed(r.diameter_error_min_mm,6)} a ${signed(r.diameter_error_max_mm,6)} mm.${r.diameter_fully_visible?'':' Ancho fuera del sensor.'}`;
  $('error-value').title=`Geometría: ${signed(r.geometry_error_mm,6)} mm; distorsión: ${signed(r.distortion_delta_mm,6)} mm; escala: ${signed(r.scale_delta_mm,6)} mm.`;
  $('height-value').textContent=fmt(r.z_min_mm,2)+' / '+fmt(r.z_max_mm,2)+' mm';$('fov-value').textContent=fmt(r.fov_mm[0],1)+' × '+fmt(r.fov_mm[1],1)+' mm';$('fov-value').title='Campo nominal sin distorsión';$('scale-value').textContent=fmt(r.applied_mm_per_px,6)+' mm/px';$('scale-value').title='Escala aplicada, incluido el sesgo simulado. La distorsión puede variar la escala local.';$('status').textContent=r.fully_visible?'':'Fuera del FOV';
  $('toggle-sim-errors').classList.toggle('active',state.scale_error_pct!==0||state.distortion_pct!==0);
}
function syncControls(){document.querySelectorAll('[data-param]').forEach(el=>{if(document.activeElement===el&&el.type==='number')return;const v=state[el.dataset.param];el.value=typeof v==='number'?String(Math.round(v*1e6)/1e6):v;});$('shape-controls').hidden=state.shape==='flat';$('waves-row').hidden=state.shape!=='wave';$('anchor').disabled=state.shape==='radial_drop';$('deformation').disabled=state.shape==='radial_drop';}
function refresh(){pending=false;try{result=simulate(state);state={...result.parameters};syncControls();updateNumbers();drawScene();window.spiralSim.lastError=null;}catch(error){$('status').textContent=error.message;window.spiralSim.lastError=error.message;}}
function queueRefresh(){if(!pending){pending=true;requestAnimationFrame(refresh);}}
function setState(values,fit=false){state={...state,...values};refresh();if(fit)fitView(scope);}
function layoutPanels(){$('sim-errors').style.left=innerWidth>=680&&!$('parameters').hidden?'254px':'8px';}
function togglePanel(id,open){const panel=$(id),button=$('toggle-'+id);panel.hidden=!(open??panel.hidden);button?.setAttribute('aria-expanded',String(!panel.hidden));if(!panel.hidden&&innerWidth<680){for(const other of ['parameters','sim-errors','measurements'])if(other!==id){$(other).hidden=true;$('toggle-'+other)?.setAttribute('aria-expanded','false');}}layoutPanels();}
window.addEventListener('resize',layoutPanels);
function download(name,content,type){const url=URL.createObjectURL(new Blob([content],{type})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),2000);$('save-menu').hidden=true;$('toggle-save').setAttribute('aria-expanded','false');}
function summary(){const {points,projected,ideal_projected,sensor_projected,diameter_errors,base,radial,...r}=result;return {kind:'synthetic_geometry_not_hardware_measurements',...r,viewer:{mode:scope,orientation,vertical_exaggeration:gain()}};}
function viewerState(){return {position:camera.position.toArray(),quaternion:camera.quaternion.toArray(),target:controls.target.toArray(),zoom:camera.zoom,projection:'orthographic'};}

for(const id of ['parameters','sim-errors','measurements'])$('toggle-'+id).addEventListener('click',()=>togglePanel(id));
document.querySelectorAll('[data-close]').forEach(el=>el.addEventListener('click',()=>togglePanel(el.dataset.close,false)));
$('scenario').addEventListener('change',()=>{const p=PRESETS[$('scenario').value];if(p)setState(p.values);});
document.querySelectorAll('[data-param]').forEach(el=>el.addEventListener('input',()=>{let value=el.tagName==='SELECT'?el.value:el.valueAsNumber;if(typeof value==='number'){if(!Number.isFinite(value))return;value=Math.max(Number(el.min),Math.min(Number(el.max),value));if(el.dataset.param==='waves')value=Math.round(value);}state[el.dataset.param]=value;if(el.dataset.param==='shape')state.anchor='start';$('scenario').value='custom';queueRefresh();}));
document.querySelectorAll('input[type=number]').forEach(el=>el.addEventListener('blur',()=>{el.value=String(Math.round(state[el.dataset.param]*1e6)/1e6);}));
$('fit200').addEventListener('click',()=>setState({camera_z:state.calibration_z+state.focal*(1+200/SENSOR[1])},true));$('fit').addEventListener('click',()=>fitView('full'));$('view-piece').addEventListener('click',()=>fitView('piece'));
for(const key of ['iso','top','front','right'])$('view-'+key).addEventListener('click',()=>fitView(scope,key));for(const [key,name] of [['x','right'],['y','front'],['z','top']])$('axis-'+key).addEventListener('click',()=>fitView(scope,name));
$('toggle-fov').addEventListener('click',()=>{showFov=!showFov;frustum.visible=showFov;$('toggle-fov').setAttribute('aria-pressed',String(showFov));render();});$('toggle-grid').addEventListener('click',()=>{showGrid=!showGrid;grid.visible=showGrid;$('toggle-grid').setAttribute('aria-pressed',String(showGrid));render();});
$('show-projection').addEventListener('change',()=>{projection.visible=$('show-projection').checked;render();});$('show-nominal').addEventListener('change',()=>{nominal.visible=$('show-nominal').checked;render();});$('z-gain').addEventListener('change',()=>{scope='piece';drawScene();fitView('piece');});
$('show-projection').addEventListener('change',()=>{$('show-error-projection').checked=$('show-projection').checked;});
$('show-error-projection').addEventListener('change',()=>{$('show-projection').checked=$('show-error-projection').checked;projection.visible=$('show-projection').checked;render();});
$('reset-errors').addEventListener('click',()=>setState({scale_error_pct:0,distortion_pct:0}));
$('reset').addEventListener('click',()=>{state={...DEFAULTS};$('scenario').value='wave';$('z-gain').value='1';scope='full';refresh();fitView('full','iso');});
$('toggle-save').addEventListener('click',()=>{$('save-menu').hidden=!$('save-menu').hidden;$('toggle-save').setAttribute('aria-expanded',String(!$('save-menu').hidden));});
$('save-json').addEventListener('click',()=>download('espiral-escenario.json',JSON.stringify(summary(),null,2),'application/json'));
$('save-csv').addEventListener('click',()=>{const rows=['s_nominal_mm,x_mm,y_mm,z_mm,x_interpretada_mm,y_interpretada_mm,factor_altura,x_ideal_mm,y_ideal_mm,error_diametro_mm,escala_error_pct,distorsion_pct'];result.points.forEach((q,i)=>rows.push([result.base[i][2],...q,...result.projected[i],result.radial[i],...result.ideal_projected[i],result.diameter_errors[i],state.scale_error_pct,state.distortion_pct].map(x=>x.toFixed(9)).join(',')));download('espiral-coordenadas.csv',rows.join('\n'),'text/csv;charset=utf-8');});
$('save-image').addEventListener('click',()=>{render();const src=renderer.domElement,out=document.createElement('canvas');out.width=src.width;out.height=src.height;const ctx=out.getContext('2d'),gradient=ctx.createLinearGradient(0,0,0,out.height);gradient.addColorStop(0,'#c5d1de');gradient.addColorStop(1,'#f2f4f6');ctx.fillStyle=gradient;ctx.fillRect(0,0,out.width,out.height);ctx.drawImage(src,0,0);ctx.font=`${12*renderer.getPixelRatio()}px Segoe UI`;ctx.fillStyle='#405566';ctx.fillText(`Simulación · Z ${fmt(state.camera_z,1)} mm · f ${fmt(state.focal,1)} mm · relieve ×${gain()} · escala ${signed(state.scale_error_pct,3)} % · distorsión ${signed(state.distortion_pct,2)} %`,15,24*renderer.getPixelRatio());const a=document.createElement('a');a.download='espiral-vista-3d.png';a.href=out.toDataURL('image/png');a.click();$('save-menu').hidden=true;$('toggle-save').setAttribute('aria-expanded','false');});
$('fullscreen').addEventListener('click',async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen();}catch{}});
window.addEventListener('keydown',event=>{if(['INPUT','SELECT','TEXTAREA'].includes(document.activeElement.tagName)||event.ctrlKey||event.altKey||event.metaKey)return;if(event.key.toLowerCase()==='f'){event.preventDefault();fitView('full');}if(event.key==='0')fitView(scope,'iso');if(event.key==='1')fitView(scope,'top');if(event.key==='2')fitView(scope,'front');if(event.key==='3')fitView(scope,'right');if(event.key==='Escape'){togglePanel('parameters',false);togglePanel('sim-errors',false);togglePanel('measurements',false);$('save-menu').hidden=true;}});
window.spiralSim={set:setState,get:()=>summary(),simulate,viewer:viewerState,view:(mode)=>mode==='detail'?fitView('piece'):mode==='full'?fitView('full'):fitView(scope,mode),preset:key=>setState(PRESETS[key].values),lastError:null};
try{init3D();refresh();fitView('full','iso');}catch(error){$('status').textContent='WebGL: '+error.message;$('loading')?.remove();window.spiralSim.lastError=error.message;console.error(error);}
