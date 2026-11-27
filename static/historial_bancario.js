(() => {
 'use strict';
 const dialog=document.getElementById('historial-bancario');
 const opener=document.querySelector('[data-bank-history-open]');
 if(!dialog||!opener)return;
 opener.addEventListener('click',()=>{if(!dialog.open)dialog.showModal();});
 dialog.querySelector('[data-bank-history-close]')?.addEventListener('click',()=>dialog.close());
 dialog.addEventListener('close',()=>opener.focus({preventScroll:true}));
 dialog.addEventListener('click',event=>{
   if(event.target!==dialog)return;
   const rect=dialog.getBoundingClientRect();
   if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)dialog.close();
 });
})();
