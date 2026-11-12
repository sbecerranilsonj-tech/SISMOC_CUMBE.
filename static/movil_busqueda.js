(() => {
  function setup(picker){
  const form=picker.closest('form'), input=picker.querySelector('[data-persona-input]'), hidden=picker.querySelector('[data-persona-id]');
  const menu=picker.querySelector('[data-persona-opciones]'), status=picker.querySelector('[data-persona-estado]');
  const submit=form.querySelector('[data-persona-submit]'), details=form.querySelector('[data-persona-identidad]');
  const dni=details?.querySelector('[data-dni-conductor]');
  let timer,controller,sequence=0,results=[],active=-1;
  function close(){menu.hidden=true;input.setAttribute('aria-expanded','false');input.removeAttribute('aria-activedescendant');active=-1;}
  function select(person){
    sequence++;if(controller)controller.abort();clearTimeout(timer);
    hidden.value=person.id;input.value=person.nombre;input.setCustomValidity('');if(submit)submit.disabled=false;
    status.textContent=[person.tipo,person.area,person.sede].filter(Boolean).join(' · ');
    const funcion=form.querySelector('[name=funcion_app]');if(funcion){const inferred=person.funcion_app||'';funcion.disabled=!!inferred;funcion.value=inferred==='CONDUCTOR'?'':inferred;funcion.closest('label').hidden=!!inferred;const info=form.querySelector('[data-funcion-auto]');if(info){info.hidden=!inferred;info.textContent='Función asignada: '+({CONDUCTOR:'Conductor',BOLETERIA:'Ventas / Boletería',OPERADOR_EMBARQUE:'Embarque'}[inferred]||'Personal');}}
    if(details)details.hidden=!person.requiere_identidad;
    close();
  }
  function highlight(){
    [...menu.children].forEach((button,i)=>button.setAttribute('aria-selected',String(i===active)));
    if(active>=0){input.setAttribute('aria-activedescendant',menu.children[active].id);menu.children[active].scrollIntoView({block:'nearest'});}
  }
  input.addEventListener('input',()=>{
    hidden.value='';const roleLabel=form.querySelector('[data-funcion-label]');if(roleLabel)roleLabel.hidden=true;const roleInfo=form.querySelector('[data-funcion-auto]');if(roleInfo){roleInfo.hidden=false;roleInfo.textContent='La función se obtiene del área registrada.';}if(submit)submit.disabled=true;input.setCustomValidity('');if(details)details.hidden=true;if(dni)dni.value='';
    clearTimeout(timer);if(controller)controller.abort();const current=++sequence;const q=input.value.trim();close();
    if(!q){status.textContent='Escribe desde la primera letra para ver sugerencias.';return;}
    status.textContent='Buscando…';
    timer=setTimeout(async()=>{
      controller=new AbortController();
      try{
        const url=new URL(picker.dataset.url,location.href);url.searchParams.set('q',q);
        const response=await fetch(url,{signal:controller.signal,credentials:'same-origin',cache:'no-store'});
        if(!response.ok||response.redirected)throw new Error('sesion');
        const data=await response.json();if(current!==sequence)return;
        results=data.resultados;menu.replaceChildren();
        for(const [i,person] of results.entries()){
          const button=document.createElement('button');button.type='button';button.id=`${input.id}-opcion-${i}`;button.setAttribute('role','option');button.setAttribute('aria-selected','false');
          const name=document.createElement('strong');name.textContent=person.nombre;
          const detail=document.createElement('span');detail.textContent=[person.tipo,person.area,person.sede].filter(Boolean).join(' · ');
          button.append(name,detail);button.addEventListener('mousedown',e=>e.preventDefault());button.addEventListener('click',()=>select(person));menu.append(button);
        }
        menu.hidden=!results.length;input.setAttribute('aria-expanded',String(!!results.length));
        status.textContent=results.length?'Selecciona una sugerencia.':'No se encontraron coincidencias.';
      }catch(e){if(e.name!=='AbortError'&&current===sequence)status.textContent='No se pudo buscar. Revisa tu conexión o sesión.';}
    },180);
  });
  input.addEventListener('keydown',e=>{
    if(e.key==='Escape'){close();return;}
    if(!menu.hidden&&results.length){
      if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();active=active<0?(e.key==='ArrowDown'?0:results.length-1):(active+(e.key==='ArrowDown'?1:results.length-1))%results.length;highlight();}
      if(e.key==='Enter'){e.preventDefault();select(results[active>=0?active:0]);}
    }
  });
  form.addEventListener('submit',e=>{if(input.required&&!hidden.value){e.preventDefault();input.setCustomValidity('Selecciona una persona de las sugerencias.');input.reportValidity();}});
  document.addEventListener('click',e=>{if(!picker.contains(e.target))close();});
  }
  document.querySelectorAll('[data-persona-picker]').forEach(setup);
})();
