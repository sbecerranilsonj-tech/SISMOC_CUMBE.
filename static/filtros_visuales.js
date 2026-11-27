(() => {
 'use strict';
 if (window.flatpickr) document.querySelectorAll('.filtros-asistencia input[type="date"]').forEach(input => {
   flatpickr(input, {locale:'es',altInput:true,altFormat:'d/m/Y',dateFormat:'Y-m-d',allowInput:true,disableMobile:true,monthSelectorType:'dropdown',ariaDateFormat:'d/m/Y'});
 });
 document.querySelectorAll('[data-bars]').forEach(chart => {
   const rows=[...chart.querySelectorAll('[data-bar-value]')];
   const values=rows.map(row=>Math.max(0,Number(row.dataset.barValue)||0));
   const max=Math.max(...values,0);
   rows.forEach((row,index)=>row.style.setProperty('--bar-size',`${max ? values[index]/max*100 : 0}%`));
 });
 document.querySelectorAll('[data-jornadas-chart]').forEach(chart => {
   const values=[chart.dataset.approved,chart.dataset.pending,chart.dataset.observed].map(v=>Math.max(0,Number(v)||0));
   const total=values.reduce((a,b)=>a+b,0), length=2*Math.PI*46;
   let offset=0;
   chart.querySelectorAll('[data-chart-segment]').forEach((segment,index)=>{
     const size=total ? values[index]/total*length : 0;
     segment.style.stroke=['#16805d','#b66b12','#b34053'][index];
     segment.style.strokeDasharray=`${size} ${length-size}`;
     segment.style.strokeDashoffset=-offset;
     offset+=size;
   });
 });
})();
