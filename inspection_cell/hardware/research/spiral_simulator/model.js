// Modelo geométrico independiente del visor. Su equivalente Python es model.py.
export const ARCS = [[13,13,0,180,360],[26,0,0,0,180],[39,13,0,180,360],[52,0,0,0,180],[65,13,0,180,270]];
export const NOMINAL = ARCS.reduce((s,[r,x,y,a,b])=>s+r*(b-a)*Math.PI/180,0);
export const SENSOR = [5472*.0024,3648*.0024];
export const DEFAULT_STEP_MM = .01;
export const DEFAULTS = {focal:35,camera_z:800,camera_x:0,camera_y:0,calibration_z:0,lift:0,shape:'wave',span:1,waves:3,phase:0,deformation:'inextensible',tilt:0,axis:90,anchor:'start',diameter:4,scale_error_pct:0,distortion_pct:0};
const rad = x=>x*Math.PI/180;
export const distance = (a,b)=>Math.hypot(...a.map((v,i)=>v-b[i]));
export const pathLength = p=>p.slice(1).reduce((sum,v,i)=>sum+distance(v,p[i]),0);
export function bounds(p,axis) { let lo=Infinity,hi=-Infinity;for(const q of p){lo=Math.min(lo,q[axis]);hi=Math.max(hi,q[axis]);}return [lo,hi]; }
// Brown k1, normalizado al radio de la esquina ideal. Continuación monótona
// fuera de 2 radios (siempre fuera del sensor) para evitar pliegues espurios.
export function distortLocal(x,y,cornerRadius,percent){
  if(percent===0)return [x,y];
  const a=percent/100,rho=Math.hypot(x,y)/cornerRadius;
  const factor=rho<=2?1+a*rho*rho:(2*(1+4*a)+(rho-2)*(1+12*a))/rho;
  return [x*factor,y*factor];
}
export function nominalPoints(step=DEFAULT_STEP_MM) {
  const result=[];let s0=0;
  for(const [r,cx,cy,a,b] of ARCS){const arc=r*rad(b-a),n=Math.ceil(arc/step);
    for(let j=0;j<=n;j++){if(result.length&&j===0)continue;const t=rad(a)+j/n*rad(b-a);result.push([cx+r*Math.cos(t),cy+r*Math.sin(t),s0+arc*j/n]);}s0+=arc;
  }return result;
}
function clipSegment(a,b,w,h) {
  const dx=b[0]-a[0],dy=b[1]-a[1];let lo=0,hi=1;
  for(const [p,q] of [[-dx,a[0]+w],[dx,w-a[0]],[-dy,a[1]+h],[dy,h-a[1]]]) {
    if(Math.abs(p)<1e-15){if(q<0)return 0;continue;}const t=q/p;
    if(p<0)lo=Math.max(lo,t);else hi=Math.min(hi,t);if(lo>hi)return 0;
  }return Math.max(0,hi-lo);
}
export function simulate(parameters={},step=DEFAULT_STEP_MM) {
  const p={...DEFAULTS,...parameters};
  if(!['flat','wave','bump','radial_drop'].includes(p.shape)||!['inextensible','fixed_xy'].includes(p.deformation)||!['start','middle','minimum'].includes(p.anchor))throw Error('Configuración no válida');
  if(!(p.diameter>0&&p.diameter<=20))throw Error('Diámetro fuera de rango');
  if(!Number.isFinite(p.scale_error_pct)||Math.abs(p.scale_error_pct)>1||!Number.isFinite(p.distortion_pct)||Math.abs(p.distortion_pct)>5)throw Error('Error simulado fuera de rango');
  // Esta forma mantiene exactamente XY antes de cualquier inclinación rígida.
  if(p.shape==='radial_drop'){p.deformation='fixed_xy';p.anchor='start';}
  if(!(step>0)||p.span<0||p.span>20||p.waves<1||p.waves>8)throw Error('Desnivel u ondas fuera de rango');
  const d=p.camera_z-p.calibration_z,f=p.focal;
  if(f<=0||d<=f)throw Error('La cámara debe estar a más de una focal del plano');
  const base=nominalPoints(step);let heights;
  if(p.shape==='flat')heights=base.map(()=>0);
  else if(p.shape==='radial_drop'){
    const radii=base.map(q=>Math.hypot(q[0]-base[0][0],q[1]-base[0][1])),maxRadius=Math.max(...radii);
    heights=radii.map(r=>-p.span*r/maxRadius);
  }else {
    const raw=base.map(([x,y,s])=>p.shape==='wave'?Math.sin(2*Math.PI*p.waves*s/NOMINAL+rad(p.phase)):Math.exp(-(((s/NOMINAL-.5)/.12)**2)));
    const lo=Math.min(...raw),hi=Math.max(...raw);heights=raw.map(z=>p.span*((z-lo)/(hi-lo)-.5));
  }
  if(p.anchor==='start'){const origin=heights[0];heights=heights.map(z=>z-origin);}
  let xy;
  if(p.deformation==='inextensible'&&p.shape!=='flat'){
    xy=[base[0].slice(0,2)];
    for(let i=1;i<base.length;i++){
      const dx=base[i][0]-base[i-1][0],dy=base[i][1]-base[i-1][1],ds=Math.hypot(dx,dy),dz=heights[i]-heights[i-1];
      if(Math.abs(dz)>ds+1e-12)throw Error('Perfil imposible sin estirar: reduce altura u ondas');
      const k=Math.sqrt(Math.max(0,1-(dz/ds)**2));xy.push([xy[i-1][0]+k*dx,xy[i-1][1]+k*dy]);
    }
    if(p.anchor!=='start')for(const axis of [0,1]){const a=bounds(base,axis),b=bounds(xy,axis),shift=(a[0]+a[1]-b[0]-b[1])/2;for(const q of xy)q[axis]+=shift;}
  }else xy=base.map(q=>q.slice(0,2));
  const angle=rad(p.tilt),ax=Math.cos(rad(p.axis)),ay=Math.sin(rad(p.axis)),co=Math.cos(angle),si=Math.sin(angle);
  const bx=bounds(xy,0),by=bounds(xy,1),px=p.anchor==='start'?xy[0][0]:(bx[0]+bx[1])/2,py=p.anchor==='start'?xy[0][1]:(by[0]+by[1])/2;
  const points=xy.map(([x,y],i)=>{x-=px;y-=py;const z=heights[i],dot=ax*x+ay*y;return [px+x*co+ay*z*si+ax*dot*(1-co),py+y*co-ax*z*si+ay*dot*(1-co),z*co+(ax*y-ay*x)*si];});
  let [zmin,zmax]=bounds(points,2);const anchor=p.anchor==='start'?points[0][2]:p.anchor==='middle'?(zmin+zmax)/2:zmin;
  for(const q of points)q[2]+=p.lift-anchor;
  [zmin,zmax]=bounds(points,2);if(zmax>=p.camera_z)throw Error('La espiral alcanza el centro óptico');
  const imageDistance=f*d/(d-f),fov=SENSOR.map(s=>s*d/imageDistance),mmPerPx=.0024*d/imageDistance;
  const radial=points.map(q=>d/(p.camera_z-q[2])),scale=1+p.scale_error_pct/100,cornerRadius=Math.hypot(...fov)/2;
  const ideal_projected=points.map(([x,y,z],i)=>[(x-p.camera_x)*radial[i]+p.camera_x,(y-p.camera_y)*radial[i]+p.camera_y]);
  const sensor_projected=ideal_projected.map(q=>{const v=distortLocal(q[0]-p.camera_x,q[1]-p.camera_y,cornerRadius,p.distortion_pct);return [p.camera_x+v[0],p.camera_y+v[1]];});
  const projected=sensor_projected.map(q=>[p.camera_x+(q[0]-p.camera_x)*scale,p.camera_y+(q[1]-p.camera_y)*scale]);
  const real=pathLength(points),ortho=pathLength(points.map(q=>q.slice(0,2))),idealApparent=pathLength(ideal_projected),distortedApparent=pathLength(sensor_projected),apparent=pathLength(projected);
  let visible=0,weightedZ=0;
  for(let i=1;i<points.length;i++){
    const a=sensor_projected[i-1],b=sensor_projected[i];visible+=scale*distance(a,b)*clipSegment([a[0]-p.camera_x,a[1]-p.camera_y],[b[0]-p.camera_x,b[1]-p.camera_y],fov[0]/2,fov[1]/2);
    weightedZ+=distance(points[i-1],points[i])*(points[i-1][2]+points[i][2])/2;
  }
  const inside=([x,y])=>Math.abs(x)<=fov[0]/2&&Math.abs(y)<=fov[1]/2;
  const fullyVisible=sensor_projected.every(q=>inside([q[0]-p.camera_x,q[1]-p.camera_y]));
  const nominalPolygon=pathLength(base.map(q=>q.slice(0,2)));
  // Segmento transversal horizontal, perpendicular a la tangente XY local.
  // Se proyectan AMBOS extremos: la distorsión no es una escala uniforme.
  let diameterVisible=true;
  const diameter_errors=points.map((q,i)=>{
    const a=points[Math.max(0,i-1)],b=points[Math.min(points.length-1,i+1)],dx=b[0]-a[0],dy=b[1]-a[1],norm=Math.hypot(dx,dy),nx=norm>1e-12?-dy/norm:1,ny=norm>1e-12?dx/norm:0,k=radial[i];
    const x=(q[0]-p.camera_x)*k,y=(q[1]-p.camera_y)*k,h=p.diameter*k/2;
    const lo=distortLocal(x-h*nx,y-h*ny,cornerRadius,p.distortion_pct),hi=distortLocal(x+h*nx,y+h*ny,cornerRadius,p.distortion_pct);
    diameterVisible=diameterVisible&&inside(lo)&&inside(hi);
    return p.distortion_pct===0?p.diameter*(k*scale-1):distance(lo,hi)*scale-p.diameter;
  });
  const radialMin=Math.min(...radial),radialMax=Math.max(...radial),diameterMin=Math.min(...diameter_errors),diameterMax=Math.max(...diameter_errors);
  const diameterWorst=Math.abs(diameterMin)>Math.abs(diameterMax)?diameterMin:diameterMax;
  return {parameters:p,nominal_analytic_mm:NOMINAL,nominal_polygon_mm:nominalPolygon,spatial_mm:real,orthographic_mm:ortho,apparent_mm:apparent,ideal_apparent_mm:idealApparent,distorted_apparent_mm:distortedApparent,visible_mm:visible,fully_visible:fullyVisible,error_mm:apparent-real,geometry_error_mm:idealApparent-real,distortion_delta_mm:distortedApparent-idealApparent,scale_delta_mm:apparent-distortedApparent,deformation_delta_mm:real-nominalPolygon,numerical_nominal_error_mm:nominalPolygon-NOMINAL,projection_loss_mm:ortho-real,perspective_delta_mm:idealApparent-ortho,z_min_mm:zmin,z_max_mm:zmax,z_mean_arclength_mm:weightedZ/real,z_start_mm:points[0][2],radial_factor_min:radialMin,radial_factor_max:radialMax,diameter_model:'horizontal_transverse_segment',diameter_fully_visible:diameterVisible,diameter_error_min_mm:diameterMin,diameter_error_max_mm:diameterMax,diameter_error_worst_mm:diameterWorst,diameter_error_max_abs_mm:Math.abs(diameterWorst),distortion_model:'synthetic_radial_k1_corner_percent',image_distance_mm:imageDistance,fov_mm:fov,mm_per_px:mmPerPx,applied_mm_per_px:mmPerPx*scale,points_count:points.length,step_mm:step,points,projected,ideal_projected,sensor_projected,diameter_errors,base,radial};
}
export const PRESETS = {
  flat:{label:'Plana · z = 0',values:{shape:'flat',span:0,tilt:0,lift:0,anchor:'start'}},
  raised:{label:'Subir entera +1 mm',values:{shape:'flat',span:0,tilt:0,lift:1,anchor:'start'}},
  tilted:{label:'Inclinar −0,5 / +0,5',values:{shape:'flat',span:0,tilt:Math.asin(1/104)*180/Math.PI,axis:90,lift:0,anchor:'start'}},
  wave:{label:'Ondular −0,5 / +0,5',values:{shape:'wave',span:1,waves:3,phase:0,tilt:0,lift:0,anchor:'start',deformation:'inextensible'}},
  positive:{label:'Ondular 0 / +1 mm',values:{shape:'wave',span:1,waves:3,phase:270,tilt:0,lift:0,anchor:'start',deformation:'inextensible'}},
  radial_drop:{label:'Caída radial 1 mm',values:{shape:'radial_drop',span:1,tilt:0,lift:0,anchor:'start',deformation:'fixed_xy'}}
};
