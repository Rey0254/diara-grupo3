'use strict';
const $=id=>document.getElementById(id);
const set=(id,value)=>{$(id).textContent=String(value??'Información no disponible');};
const dateLabel=value=>{if(!value)return 'No disponible';const d=new Date(`${String(value).slice(0,10)}T12:00:00`);return Number.isNaN(d.getTime())?String(value):new Intl.DateTimeFormat('es-CR',{dateStyle:'long'}).format(d);};
const available=r=>r.estado_datos==='disponible';
let records=[];
function showPage(){const requested=location.hash.slice(1)||'inicio';const page=requested==='obra'?'inicio':requested;const valid=['inicio','actividad','seguridad','galeria','chatbot','transparencia'].includes(page)?page:'inicio';document.querySelectorAll('[data-view]').forEach(el=>el.hidden=el.dataset.view!==valid);document.querySelectorAll('[data-page]').forEach(a=>{if(a.dataset.page===valid)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});window.scrollTo(0,0);document.dispatchEvent(new CustomEvent('diaraVistaActiva',{detail:valid}));}
function showDay(index){const r=records[index];if(!r)return;$('fecha-selector').value=String(index);selectedIndex=index;const parts=String(r.fecha).split('-').map(Number);if(parts.length===3&&parts.every(Number.isFinite))month=new Date(parts[0],parts[1]-1,1,12);renderCalendar();const target=$('day-detail');target.replaceChildren();const h=document.createElement('h3');h.textContent=dateLabel(r.fecha);target.append(h);const p=document.createElement('p');p.textContent=available(r)?'Registro disponible. Los valores corresponden a detecciones de la fuente.':'Sin datos disponibles. No se puede determinar la actividad de ese día.';target.append(p);if(available(r)){const grid=document.createElement('div');grid.className='day-values';for(const [label,value] of [['Personas detectadas',r.personas_detectadas],['Maquinaria detectada',r.maquinaria_detectada]]){const box=document.createElement('div'),strong=document.createElement('strong');strong.textContent=value??'No disponible';box.append(label,strong);grid.append(box);}target.append(grid);}document.dispatchEvent(new CustomEvent('diaraFechaSeleccionada',{detail:r}));}
function mostrarInformacionObra(datos){const obra=datos.obra??{};records=[...(datos.registros??[])].sort((a,b)=>String(a.fecha).localeCompare(String(b.fecha)));set('nombre-obra',obra.nombre);set('ubicacion-obra',obra.ubicacion);set('ultima-actualizacion',`Último registro informado: ${dateLabel(obra.ultima_actualizacion)}`);set('aviso-datos',/simulad/i.test(datos.tipo_datos??'')?'Modo demostración · Los datos son simulados, no mediciones reales.':datos.tipo_datos??'Fuente de datos no identificada');set('fuente-datos',datos.tipo_datos??'Fuente no identificada');const count=records.filter(available).length;set('estado-actividad',count?'Con registros':'Sin registros disponibles');set('avance-contractual',obra.avance_contractual??'No disponible');set('total-registros',new Set(records.filter(available).map(r=>r.fecha)).size);set('dias-sin-datos',new Set(records.filter(r=>r.estado_datos==='sin datos').map(r=>r.fecha)).size);const info=$('info-obra');info.replaceChildren();for(const [label,value] of [['Nombre',obra.nombre],['Ubicación',obra.ubicacion],['Institución responsable',obra.institucion_responsable],['Avance contractual',obra.avance_contractual],['Fuente',datos.tipo_datos]]){const p=document.createElement('p');const b=document.createElement('strong');b.textContent=label+': ';p.append(b,String(value??'Información no disponible'));info.append(p);}const select=$('fecha-selector'),timeline=$('mini-timeline');select.replaceChildren();timeline.replaceChildren();records.forEach((r,i)=>{const option=document.createElement('option');option.value=String(i);option.textContent=dateLabel(r.fecha);select.append(option);});select.disabled=!records.length;if(records.length)showDay(records.length-1);else {set('day-detail','No hay registros disponibles.');renderCalendar();}}
async function cargarDatos(){try{const response=await fetch('../data/datos_demo.json');if(!response.ok)throw new Error(`HTTP ${response.status}`);const datos=await response.json();window.datosDiara=datos;mostrarInformacionObra(datos);document.dispatchEvent(new CustomEvent('datosDiaraListos',{detail:datos}));}catch(error){console.error(error);set('aviso-datos','No fue posible cargar los datos. Verifique el servidor y el archivo JSON.');set('day-detail','Información no disponible.');$('fecha-selector').disabled=true;renderCalendar();const retry=document.createElement('button');retry.className='quiet';retry.textContent='Volver a intentar';retry.onclick=cargarDatos;$('aviso-datos').append(' ',retry);}}
function init(){showPage();window.addEventListener('hashchange',showPage);$('fecha-selector').addEventListener('change',e=>showDay(Number(e.target.value)));initExtras();cargarDatos();}document.addEventListener('DOMContentLoaded',init);

let month=new Date(),selectedIndex=-1;
function renderCalendar(){
 const grid=$('mini-timeline');grid.replaceChildren();const y=month.getFullYear(),m=month.getMonth();
 set('calendar-month',new Intl.DateTimeFormat('es-CR',{month:'long',year:'numeric'}).format(month));
 const offset=(new Date(y,m,1).getDay()+6)%7;
 for(let i=0;i<offset;i++)grid.append(document.createElement('span'));
 const n=new Date(y,m+1,0).getDate();
 for(let d=1;d<=n;d++){
  const key=`${y}-${String(m+1).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
  const idx=records.findIndex(r=>r.fecha===key);const r=records[idx];
  const b=document.createElement('button');b.type='button';b.textContent=d;
  const mark=document.createElement('span');mark.textContent=r?(available(r)?'●':'◇'):'–';b.append(mark);
  b.className=r?(available(r)?'has-data':'missing'):'unlisted';
  b.setAttribute('aria-label',dateLabel(key)+': '+(r?(available(r)?'Con datos':'Sin datos informados'):'Fecha sin registro listado'));
  b.setAttribute('aria-pressed',String(idx>=0&&idx===selectedIndex));
  b.onclick=()=>{if(idx>=0){showDay(idx);}else{selectedIndex=-1;$('fecha-selector').selectedIndex=-1;renderCalendar();set('day-detail',dateLabel(key)+' · No hay un registro listado para esta fecha. No permite determinar la actividad.');}};
  grid.append(b);
 }
}
function initExtras(){
 const panel=$('access-panel'),toggle=$('access-toggle');
 function close(){panel.hidden=true;toggle.setAttribute('aria-expanded','false');}
 toggle.onclick=()=>{panel.hidden=!panel.hidden;toggle.setAttribute('aria-expanded',String(!panel.hidden));};
 document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!panel.hidden){close();toggle.focus();}});
 document.addEventListener('click',e=>{if(!panel.hidden&&!panel.contains(e.target)&&!toggle.contains(e.target))close();});
 function pref(id,cls,value){document.body.classList.toggle(cls,value);$(id).setAttribute('aria-pressed',String(value));try{localStorage.setItem('diara-'+id,String(value));}catch{}}
 for(const [id,cls] of [['text-size','large-text'],['contrast','high-contrast']]){let val=false;try{val=localStorage.getItem('diara-'+id)==='true';}catch{}pref(id,cls,val);$(id).onclick=()=>pref(id,cls,!document.body.classList.contains(cls));}
 $('reset-access').onclick=()=>{pref('text-size','large-text',false);pref('contrast','high-contrast',false);};
 for(const [id,delta] of [['prev-month',-1],['next-month',1]])$(id).onclick=()=>{month=new Date(month.getFullYear(),month.getMonth()+delta,1,12);renderCalendar();};
 $('share').onclick=async()=>{const url=new URL(location.href);url.hash='inicio';try{if(navigator.share){await navigator.share({title:'dIAra | Obras a la vista',url:url.href});}else if(navigator.clipboard){await navigator.clipboard.writeText(url.href);set('share-status','Enlace copiado');}else{set('share-status',url.href);}}catch(e){if(e.name!=='AbortError')set('share-status','No se pudo compartir. Copie el enlace de la barra del navegador.');}};
}
