/* Local service polling. Satellite and Sayari records remain dated snapshots. */
(() => {
  let busy = false;
  async function poll() {
    if (busy || document.hidden) return;
    busy = true;
    try {
      const response = await fetch('/api/dashboard', {cache:'no-store'});
      if (!response.ok) throw new Error('Unavailable');
      window.updateDashboard(await response.json());
    } catch {
      document.getElementById('connection').textContent = 'Server unavailable · showing saved page';
    } finally { busy=false; }
  }
  document.getElementById('refresh-news').addEventListener('click',async () => {
    const status=document.getElementById('refresh-status');
    try {
      const response=await fetch('/api/refresh-news',{method:'POST',headers:{'X-Dashboard-Request':'refresh'}});
      const result=await response.json();
      status.textContent=response.ok?'Refresh started; the saved evidence remains visible.':result.error || 'Refresh failed.';
      await poll();
    } catch { status.textContent='Cannot reach the local dashboard server.'; }
  });
  setInterval(poll,60000);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)poll();});
})();
