(() => {
 function setup(id, placeholder, error, includeGeneral=false) {
 const select = document.getElementById(id);
 if (!select) return;
 const options = Array.from(select.options).filter(o => o.value || includeGeneral).map(o => ({value:o.value,label:o.textContent}));
 const box = document.createElement('span');
 box.className = 'rule-worker-search';
 const input = document.createElement('input');
 input.type = 'search'; input.id = select.id + '-buscar'; input.placeholder = placeholder;
 input.autocomplete = 'off'; input.setAttribute('role','combobox'); input.setAttribute('aria-autocomplete','list'); input.setAttribute('aria-expanded','false');
 const list = document.createElement('ul'); list.id = input.id + '-opciones'; list.setAttribute('role','listbox'); list.hidden = true;
 input.setAttribute('aria-controls',list.id);
 box.append(input,list); select.after(box); select.hidden = true;
 const label = document.querySelector('label[for="' + select.id + '"]'); if(label) label.htmlFor = input.id;
 input.value = options.find(o => o.value === select.value)?.label || '';
 const normalize = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim();
 let active = -1;
 function close(){list.hidden=true; input.setAttribute('aria-expanded','false'); input.removeAttribute('aria-activedescendant');}
 function choose(option){select.value=option.value; input.value=option.label; input.setCustomValidity(''); close(); select.dispatchEvent(new Event('change',{bubbles:true}));}
 function render(){
  list.replaceChildren(); active=-1;
  const query=normalize(input.value);
  if(!query){close(); return;}
  const matches=options.filter(o => query.split(/\s+/).every(word => normalize(o.label).includes(word))).slice(0,8);
  matches.forEach((option,index) => {const item=document.createElement('li');item.id=list.id+'-'+index;item.setAttribute('role','option');item.textContent=option.label;item.addEventListener('mousedown',event=>event.preventDefault());item.addEventListener('click',()=>choose(option));list.append(item);});
  if(!matches.length){const item=document.createElement('li');item.textContent='No hay coincidencias';item.className='rule-no-match';list.append(item);}
  list.hidden=false;input.setAttribute('aria-expanded','true');
  list._matches=matches;
 }
 input.addEventListener('input',()=>{select.value='';input.setCustomValidity('');render();});
 input.addEventListener('focus',render);
 input.addEventListener('keydown',event=>{
  if(event.key==='Escape'){close();return;}
  const matches=list._matches || [];
  if((event.key==='ArrowDown'||event.key==='ArrowUp') && matches.length){event.preventDefault();active=(active+(event.key==='ArrowDown'?1:-1)+matches.length)%matches.length;Array.from(list.children).forEach((item,i)=>item.setAttribute('aria-selected',String(i===active)));input.setAttribute('aria-activedescendant',list.children[active].id);}
  if(event.key==='Enter' && !list.hidden && matches.length){event.preventDefault();choose(matches[active<0?0:active]);}
 });
 document.addEventListener('click',event=>{if(!box.contains(event.target))close();});
 select.form.addEventListener('submit',event=>{if(input.value.trim() && !options.some(o => o.value === select.value && o.label === input.value)){event.preventDefault();input.setCustomValidity(error);input.reportValidity();input.focus();}});
 }
 setup('id_regla-trabajador', 'Escribe nombre o DNI', 'Selecciona un trabajador de las sugerencias.');
 setup('id_regla-area', 'Escribe el área', 'Selecciona un área de las sugerencias.', true);
})();
