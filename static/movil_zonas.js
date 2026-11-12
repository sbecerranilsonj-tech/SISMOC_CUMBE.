(() => {
  const form=document.querySelector('[data-zona-form]');if(!form)return;
  const scope=form.querySelector('[data-zona-alcance]'),sede=form.querySelector('[data-zona-sede]'),person=form.querySelector('[data-zona-persona]');
  function update(){const individual=scope.value==='trabajador';person.hidden=!individual;sede.required=!individual;form.querySelector('[data-zona-sede-label]').hidden=individual;person.querySelector('input[type=search]').required=individual;const area=form.querySelector('[data-zona-area]');area.hidden=scope.value!=='area';area.querySelector('input').required=scope.value==='area';}
  scope.addEventListener('change',update);update();
  form.querySelector('[data-maps-coordenadas]').addEventListener('input',e=>{
    const match=e.target.value.trim().match(/^(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)$/);
    e.target.setCustomValidity(match||!e.target.value?'':'Pega latitud y longitud separadas por una coma.');
    if(match){form.querySelector('[data-zona-lat]').value=match[1];form.querySelector('[data-zona-lon]').value=match[2];}
  });
  document.querySelectorAll('[data-zona-editar]').forEach(button=>button.addEventListener('click',()=>{
    const d=button.dataset;form.elements.accion.value='editar_zona';form.elements.zona.value=d.id;
    for(const [name,value] of Object.entries({nombre:d.nombre,sede:d.sede,area:d.area,latitud:d.lat,longitud:d.lon,radio:d.radio}))form.elements[name].value=value;
    scope.value=d.perfil?'trabajador':d.area?'area':'sede';update();
    person.querySelector('[data-persona-id]').value=d.perfil;person.querySelector('[data-persona-input]').value=d.persona;
    form.querySelector('[data-zona-guardar]').textContent='Guardar cambios';form.querySelector('[data-zona-cancelar]').hidden=false;
    form.scrollIntoView({behavior:'smooth',block:'center'});form.elements.nombre.focus();
  }));
  form.querySelector('[data-zona-cancelar]').addEventListener('click',()=>{
    form.reset();form.elements.accion.value='zona';form.elements.zona.value='';person.querySelector('[data-persona-id]').value='';update();
    form.querySelector('[data-zona-guardar]').textContent='Guardar zona';form.querySelector('[data-zona-cancelar]').hidden=true;
  });
  form.querySelector('[data-usar-ubicacion]').addEventListener('click',()=>{
    const info=form.querySelector('[data-zona-info]');
    if(!navigator.geolocation){info.textContent='Este navegador no dispone de ubicación. Copia latitud y longitud desde la app.';return;}
    info.textContent='Obteniendo ubicación…';
    navigator.geolocation.getCurrentPosition(p=>{
      form.querySelector('[data-zona-lat]').value=p.coords.latitude.toFixed(7);form.querySelector('[data-zona-lon]').value=p.coords.longitude.toFixed(7);
      info.textContent=`Ubicación obtenida. Precisión aproximada: ${Math.round(p.coords.accuracy)} m. Comprueba que corresponde al lugar; para pruebas elige Solo un trabajador.`;
    },()=>{info.textContent='No se pudo obtener la ubicación. Autoriza el permiso o copia las coordenadas desde la app.';},{enableHighAccuracy:true,timeout:20000,maximumAge:0});
  });
})();
