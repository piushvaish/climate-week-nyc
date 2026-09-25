/* MIT. GitHub Pages reads only published JSON; no provider key reaches a visitor. */
(() => {
  let busy=false;
  const button=document.getElementById('refresh-news');
  button.textContent='Check for published updates';
  const status=document.getElementById('refresh-status');
  async function check(manual=false) {
    if(busy || (!manual && document.hidden)) return;
    busy=true;button.disabled=true;
    try {
      const response=await fetch(new URL('snapshot.json',location.href),{cache:'no-store'});
      if(!response.ok)throw new Error('Snapshot unavailable');
      const snapshot=await response.json();
      if(snapshot.service?.mode!=='static' || !snapshot.satellite?.scenes)throw new Error('Unexpected snapshot');
      window.updateDashboard(snapshot);
      if(manual)status.textContent='Loaded the latest published snapshot. News retrieval runs in GitHub Actions.';
    } catch {
      if(manual)status.textContent='Could not check for updates. The current view remains available.';
    } finally {busy=false;button.disabled=false;}
  }
  button.addEventListener('click',()=>check(true));
  setInterval(()=>check(),60000);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)check();});
})();
