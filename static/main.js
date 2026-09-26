'use strict';
const $ = (selector) => document.querySelector(selector);
const escapeHTML = (value) => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let session = null, items = [], view = 'inventory', modalAction = null;
let lastOption = Date.now(), toastTimer, busy = false;
const money = cents => cents == null ? 'Precio pendiente' : new Intl.NumberFormat('es-MX',{style:'currency',currency:'MXN'}).format(cents/100) + ' MXN';
const staff = () => session?.role === 'staff';
const dateLabel = (d) => d.map((n,i) => i < 2 ? String(n).padStart(2,'0') : n).join('/');
const symbols = {'Motor':'⚙','Frenos':'◉','Carrocería':'◇','Suspensión':'↕','Eléctrico':'ϟ'};

async function api(path, data) {
  const response = await fetch('/api/' + path, data === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json','X-CSRF-Token':session?.csrf || ''},body:JSON.stringify(data)});
  const result = await response.json();
  if (!response.ok) {
    if (response.status === 401) showLogin();
    throw new Error(result.error || 'No se pudo completar la acción.');
  }
  return result;
}
function toast(message, bad=false) {
  clearTimeout(toastTimer); $('#toast').textContent = message; $('#toast').classList.toggle('bad',bad); $('#toast').hidden = false;
  toastTimer = setTimeout(() => $('#toast').hidden = true, 4500);
}
// La carga dura 800 ms: una función expresa el requisito de espera <= 5 s.
async function loading() { $('#loading').hidden = false; await new Promise(resolve => setTimeout(resolve, 800)); $('#loading').hidden = true; }
function showLogin() {
  session = null; $('#workspace').hidden = true; $('#login').hidden = false;
  for (const dialog of document.querySelectorAll('dialog[open]')) dialog.close();
  $('#login-form').elements.password.value = ''; $('#login-form').elements.name.focus();
}
async function logout() { try { await api('logout',{}); showLogin(); } catch(e) { toast(e.message,true); } }
function status(item) {
  return item.quantity === 0 ? ['out','Agotada'] : staff() && item.quantity <= item.minimum ? ['low','Stock bajo'] : ['available','Disponible'];
}
function badge(item) { const [c,t] = status(item); return `<span class="tag ${c}">${t}</span>`; }
function nav() {
  const low = items.filter(p => p.quantity <= p.minimum).length;
  const links = staff() ? [['inventory','▦','Inventario'],['alerts','△','Por reabastecer'],['history','↔','Movimientos'],['retire','×','Dar de baja piezas']] : [['inventory','▦','Catálogo de piezas']];
  $('#navigation').innerHTML = links.map(([id,icon,label]) => `<button class="nav-item ${id === view ? 'active' : ''}" data-view="${id}" ${id === view ? 'aria-current="page"' : ''}><span class="nav-symbol">${icon}</span>${label}${id === 'alerts' ? `<span class="nav-count">${low}</span>` : ''}</button>`).join('');
}
function stats() {
  const total = items.reduce((sum,p) => sum + p.quantity, 0), available = items.filter(p=>p.quantity>0).length, low = items.filter(p=>p.quantity<=p.minimum).length, out = items.filter(p=>!p.quantity).length;
  const cards = staff() ? [['Refacciones registradas',items.length,'Códigos en el catálogo','▦'],['Unidades en existencia',total,'Piezas disponibles','↗'],['Por reabastecer',low,'En o debajo del mínimo','△'],['Sin existencias',out,'Requieren reposición','—']] : [['Refacciones en catálogo',items.length,'Encuentra tu siguiente pieza','▦'],['Piezas disponibles',available,'Tipos con existencias','✓'],['Categorías',new Set(items.map(p=>p.category)).size,'Para distintas necesidades','◇'],['Unidades disponibles',total,'Consulta su compatibilidad','↗']];
  $('#stats').innerHTML = cards.map(([label,value,sub,mark],i) => `<article class="stat ${staff() && i===2 ? 'alert' : ''}"><span class="stat-label">${label}</span><span class="stat-mark" aria-hidden="true">${mark}</span><strong class="stat-value">${value}</strong><small>${sub}</small></article>`).join('');
}
async function refresh() {
  items = (await api('inventory')).items;
  const previous = $('#category').value;
  $('#category').innerHTML = '<option value="">Todas las categorías</option>' + [...new Set(items.map(p=>p.category))].sort().map(c=>`<option>${escapeHTML(c)}</option>`).join('');
  if ([...$('#category').options].some(o=>o.value===previous)) $('#category').value = previous;
  stats(); nav(); renderInventory();
}
async function enterWorkspace() {
  $('#login').hidden = true; $('#workspace').hidden = false; view = 'inventory'; lastOption = Date.now();
  $('#user-label').textContent = session.name; $('#avatar').textContent = session.name.slice(0,1).toUpperCase();
  $('#role-label').textContent = staff() ? 'Personal del taller' : 'Cliente';
  $('#space-label').textContent = staff() ? 'ESPACIO DEL TALLER' : 'ESPACIO DEL CLIENTE';
  $('#work-date').textContent = staff() ? 'Fecha de trabajo · ' + dateLabel(session.date) : 'Catálogo público';
  $('#staff-access').hidden = staff(); $('#logout').hidden = !staff();
  $('#availability').querySelector('[value="low"]').hidden = !staff();
  $('#availability').hidden = !staff();
  $('#search').value = ''; $('#availability').value = ''; $('#category').value = '';
  await refresh(); await selectView('inventory');
}
async function selectView(next) {
  view = next; lastOption = Date.now(); nav();
  for (const id of ['inventory','history']) $(`#${id}-view`).hidden = !(id===view || (id==='inventory' && ['alerts','retire'].includes(view)));
  $('#stats').hidden = view==='retire' || view==='history';
  $('#add-part').hidden = !staff() || !['inventory','alerts'].includes(view);
  const titles = {inventory: staff()?'Inventario de refacciones':'Encuentra tu refacción',alerts:'Piezas por reabastecer',history:'Historial de movimientos',retire:'Dar de baja piezas'};
  $('#page-title').textContent = titles[view];
  $('#page-description').textContent = view==='inventory' ? `Hola, ${session.name}. ${staff()?'Este es el estado actual de tu inventario.':'Busca por pieza, código o vehículo y consulta su disponibilidad.'}` : view==='alerts' ? 'Estas piezas alcanzaron su stock mínimo o están agotadas.' : view==='history' ? 'Consulta las altas, entradas, salidas y bajas registradas.' : 'Retira las piezas que ya no maneja el taller. Dejarán de generar alertas de faltantes.';
  $('#kicker').textContent = staff()?'TODO EN SU LUGAR':'UNA NUEVA VIDA PARA CADA PIEZA';
  $('#breadcrumb').textContent = (staff()?'Taller':'Clientes') + ' / ' + titles[view];
  if (view==='history') await renderHistory();
  renderInventory();
}
function renderInventory() {
  const query = $('#search').value.toLocaleLowerCase('es').trim(), category = $('#category').value, availability = $('#availability').value;
  const filtered = items.filter(p => (!query || `${p.name} ${p.code} ${p.vehicle}`.toLocaleLowerCase('es').includes(query)) && (!category || p.category===category) && (view!=='alerts' || p.quantity<=p.minimum) && (!availability || availability==='available' && p.quantity>0 || availability==='low' && p.quantity>0 && p.quantity<=p.minimum || availability==='out' && p.quantity===0));
  $('#result-count').textContent = `${filtered.length} refacciones encontradas`;
  $('#catalog-note').textContent = staff() ? (view==='retire' ? 'Las bajas conservan el historial de la pieza' : 'Stock bajo: existencias ≤ mínimo') : 'Compatibilidad sujeta a revisión en taller';
  if (!filtered.length) { $('#inventory-content').innerHTML = `<div class="empty"><h3>${items.length ? 'No se encontraron refacciones' : staff() ? 'Tu inventario está vacío' : 'Aún no hay refacciones disponibles'}</h3><p>${items.length ? 'Prueba otra búsqueda o cambia los filtros.' : staff() ? 'Haz clic en Nueva refacción para registrar tu primera pieza con su precio.' : 'Aquí aparecerán las piezas que el taller registre con existencias.'}</p></div>`; return; }
  $('#inventory-content').innerHTML = staff() ? `<div class="table-wrap"><table><thead><tr><th>REFACCIÓN / CÓDIGO</th><th>APLICACIÓN</th><th>PRECIO / PIEZA</th><th>STOCK</th><th>ESTADO</th><th>ACCIONES</th></tr></thead><tbody>${filtered.map(p=>`<tr><td><div class="piece-cell"><span class="piece-symbol" aria-hidden="true">${symbols[p.category] || '◇'}</span><div><strong>${escapeHTML(p.name)}</strong><small class="mono">${escapeHTML(p.code)}</small></div></div></td><td>${escapeHTML(p.vehicle)}<small>${escapeHTML(p.category)} · ${escapeHTML(p.condition)}</small></td><td><strong>${money(p.price_cents)}</strong><button class="text-button" data-price="${escapeHTML(p.code)}">Editar precio</button></td><td><strong>${p.quantity} <small>mín. ${p.minimum}</small></strong></td><td>${badge(p)}</td><td><div class="actions">${view==='retire' ? `<button class="secondary" data-retire="${escapeHTML(p.code)}">Dar de baja</button>` : `<button class="action-button" data-move="Entrada" data-code="${escapeHTML(p.code)}" aria-label="Registrar entrada de ${escapeHTML(p.name)}" title="Registrar entrada">+</button><button class="action-button" data-move="Salida" data-code="${escapeHTML(p.code)}" aria-label="Registrar salida de ${escapeHTML(p.name)}" title="Registrar salida" ${p.quantity===0?'disabled':''}>−</button>`}</div></td></tr>`).join('')}</tbody></table></div>` : `<div class="catalog-grid">${filtered.map(p=>`<article class="part-card"><div class="card-top"><span class="category-label">${escapeHTML(p.category)}</span>${badge(p)}</div><div class="card-body"><h3>${escapeHTML(p.name)}</h3><span class="mono">${escapeHTML(p.code)}</span><p class="application">${escapeHTML(p.vehicle)}</p><span class="tag">${escapeHTML(p.condition)}</span><p class="unit-price"><strong>${money(p.price_cents)}</strong><small> / pieza</small></p><div class="card-bottom"><span class="stock-number">${p.quantity} <small>${p.quantity===1?'unidad':'unidades'}</small></span><button class="text-button" data-detail="${escapeHTML(p.code)}">Ver detalles ↗</button></div></div></article>`).join('')}</div>`;
}
async function renderHistory() {
  const rows = (await api('history')).items;
  $('#history-view').innerHTML = rows.length ? `<div class="results-line"><span>Últimos ${rows.length} movimientos (máximo 200)</span></div><div class="table-wrap"><table><thead><tr><th>FECHA</th><th>REFACCIÓN</th><th>TIPO</th><th>UNIDADES</th><th>USUARIO</th><th>MOTIVO</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${escapeHTML(r.date)}</td><td class="mono">${escapeHTML(r.code)}</td><td><span class="tag ${r.kind==='Salida'?'low':'available'}">${escapeHTML(r.kind)}</span></td><td>${r.amount}</td><td>${escapeHTML(r.user)}</td><td>${escapeHTML(r.note)}</td></tr>`).join('')}</tbody></table></div>` : '<div class="empty"><h3>Aún no hay movimientos</h3><p>Registra una entrada o salida desde Inventario.</p></div>';
}
function openModal(title, content, action, saveLabel='Guardar') {
  $('#modal-title').textContent = title; $('#modal-body').innerHTML = content; $('#modal-error').textContent = '';
  $('#modal-save').hidden = !action; $('#modal-save').textContent = saveLabel; modalAction = action; $('#modal').showModal();
}
function addPart() {
  openModal('Nueva refacción',`<div class="form-grid"><label>Código<input name="code" placeholder="MOT-009" pattern="[A-Za-z0-9-]+" maxlength="24" required></label><label>Categoría<select name="category">${Object.keys(symbols).map(c=>`<option>${c}</option>`).join('')}<option>Otros</option></select></label><label class="wide">Nombre de la pieza<input name="name" maxlength="120" required placeholder="Ej. Bomba de agua"></label><label class="wide">Vehículo / aplicación<input name="vehicle" maxlength="120" required placeholder="Marca, modelo y años compatibles"></label><label class="wide">Condición<select name="condition"><option>Usada</option><option>Nueva</option><option>Reacondicionada</option></select></label><label class="wide">Precio por pieza (MXN)<input name="price" type="number" min="0" max="9999999.99" step="0.01" placeholder="0.00" required></label><label>Existencias iniciales<input name="quantity" type="number" min="0" max="9999999" step="1" value="0" required></label><label>Stock mínimo<input name="minimum" type="number" min="0" max="9999999" step="1" value="1" required></label></div>`, async data=>{ await api('parts',data); await refresh(); },'Registrar refacción');
}
function editPrice(code) {
  const p = items.find(p=>p.code===code);
  openModal('Precio por pieza', `<p><strong>${escapeHTML(p.name)}</strong></p><input type="hidden" name="code" value="${escapeHTML(code)}"><label>Precio unitario (MXN)<input name="price" type="number" min="0" max="9999999.99" step="0.01" required value="${p.price_cents==null?'':(p.price_cents/100).toFixed(2)}"></label>`, async data=>{await api('price',data); await refresh();}, 'Guardar precio');
}
function movement(code,kind) {
  const p = items.find(p=>p.code===code);
  openModal(`Registrar ${kind.toLowerCase()}`,`<p><strong>${escapeHTML(p.name)}</strong><br><span class="mono">${escapeHTML(code)}</span> · ${p.quantity} unidades disponibles</p><input type="hidden" name="code" value="${escapeHTML(code)}"><input type="hidden" name="kind" value="${kind}"><label>Cantidad<input type="number" name="amount" min="1" max="${kind==='Salida'?p.quantity:9999999}" step="1" required value="1"></label><label>Motivo<input name="note" maxlength="240" placeholder="Ej. Venta en mostrador / recepción de proveedor" required></label><p class="small muted">Se registrará con fecha ${dateLabel(session.date)}.</p>`, async data=>{await api('move',data); await refresh();},`Confirmar ${kind.toLowerCase()}`);
}
function detail(code) {
  const p = items.find(p=>p.code===code);
  openModal(p.name,`<p class="mono">${escapeHTML(p.code)}</p><div class="detail-grid"><div><small>Categoría</small>${escapeHTML(p.category)}</div><div><small>Condición</small>${escapeHTML(p.condition)}</div><div><small>Precio por pieza</small>${money(p.price_cents)}</div><div><small>Existencias</small>${p.quantity} unidades</div><div><small>Disponibilidad</small>${badge(p)}</div></div><p class="detail-notice"><strong>Aplicación de referencia</strong><br>${escapeHTML(p.vehicle)}<br><br>Antes de adquirir la pieza, confirma en el taller su número de parte y compatibilidad. Esta consulta no reserva unidades.</p>`,null);
}
function retirePart(code) {
  const p = items.find(p=>p.code===code);
  openModal('Confirmar baja', `<p><strong>${escapeHTML(p.name)}</strong> · ${escapeHTML(code)}</p><p>Se retirará del inventario activo, del catálogo y de las alertas. Su historial se conservará.</p><p>Existencias que quedarán fuera del inventario activo: <strong>${p.quantity}</strong>.</p><input type="hidden" name="code" value="${escapeHTML(code)}"><label>Motivo de baja<input name="note" maxlength="240" required placeholder="Ej. Ya no manejamos esta pieza"></label><label>Escribe ${escapeHTML(code)} para confirmar<input name="confirm" required maxlength="24" autocomplete="off"></label>`, async data=>{await api('retire',data); await refresh();}, 'Confirmar baja');
}
$('#login-form').addEventListener('submit',async e=>{
  e.preventDefault(); $('#login-error').textContent=''; $('#enter').disabled=true;
  try { const result = await api('login',Object.fromEntries(new FormData(e.target))); session = result.session; await loading(); await enterWorkspace(); toast(result.welcome); }
  catch(e) { $('#login-error').textContent=e.message; }
  finally { $('#enter').disabled=false; $('#loading').hidden=true; }
});
$('#logout').addEventListener('click',logout);
$('#add-part').addEventListener('click',addPart);
for (const id of ['search','category','availability']) $('#'+id).addEventListener('input',renderInventory);
document.addEventListener('click', async e=>{
  if (e.target.closest('button,a,select')) lastOption=Date.now();
  const button = e.target.closest('button'); if(!button) return;
  try {
    if(button.dataset.view) { $('#availability').value=''; $('#search').value=''; await selectView(button.dataset.view); }
    if(button.dataset.price) editPrice(button.dataset.price);
    if(button.dataset.move) movement(button.dataset.code,button.dataset.move);
    if(button.dataset.detail) detail(button.dataset.detail);
    if(button.dataset.retire && staff()) retirePart(button.dataset.retire);
    if(button.classList.contains('close-modal')) $('#modal').close();
  } catch(e) {toast(e.message,true);}
});
// Escribir también cuenta como actividad para no interrumpir una captura.
document.addEventListener('input',()=>{lastOption=Date.now();});
$('#modal-form').addEventListener('submit',async e=>{
  e.preventDefault(); if(!modalAction || busy) return; busy=true; $('#modal-save').disabled=true;
  try {await modalAction(Object.fromEntries(new FormData(e.target))); $('#modal').close(); toast('Registro guardado correctamente.');}
  catch(e) {$('#modal-error').textContent=e.message;}
  finally {busy=false; $('#modal-save').disabled=false;}
});
setInterval(()=>{ if(staff() && Date.now()-lastOption>=600000 && !$('#idle-modal').open){$('#idle-form').reset();$('#idle-error').textContent='';$('#idle-modal').showModal();}},1000);
$('#idle-modal').addEventListener('cancel',e=>e.preventDefault());
$('#idle-form').addEventListener('submit',async e=>{e.preventDefault();const answer=e.target.elements.answer.value.trim().toLowerCase();if(['sí','si'].includes(answer)){$('#idle-modal').close();lastOption=Date.now();}else if(answer==='no'){await logout();}else{$('#idle-error').textContent='Escribe sí o no.';}});
(async()=>{const d=new Date();$('#login-form').elements.date.value=dateLabel([d.getDate(),d.getMonth()+1,d.getFullYear()]);try{const result=await api('session');session=result.session;if(location.pathname==='/taller' && !staff()){showLogin();}else{await enterWorkspace();}}catch(e){toast('No se pudo conectar con el servidor. '+e.message,true);}})();

// Mantiene al día los saldos mientras el catálogo permanece abierto.
setInterval(() => { if(session && ['inventory','alerts','retire'].includes(view) && !document.querySelector('dialog[open]') && !busy) refresh().catch(e=>toast(e.message,true)); }, 30000);
window.addEventListener('focus',()=>{if(session && ['inventory','alerts','retire'].includes(view)) refresh().catch(e=>toast(e.message,true));});
