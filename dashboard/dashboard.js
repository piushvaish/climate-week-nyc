/* MIT. All imported text is rendered as text, never trusted HTML. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const format = n => Number(n).toLocaleString('en-US', {maximumFractionDigits: 1});
  const date = s => {
    if (!s) return 'Date unavailable';
    if (s.length === 4) return s;
    const parsed = new Date(s.length === 7 ? `${s}-01T12:00:00Z` : `${s.slice(0,10)}T12:00:00Z`);
    if (!Number.isFinite(+parsed)) return 'Date unavailable';
    return parsed.toLocaleDateString('en-GB', s.length === 7 ? {month:'short',year:'numeric'} : {day:'numeric',month:'short',year:'numeric'});
  };
  const node = (tag, cls, text) => {
    const n = document.createElement(tag); if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text; return n;
  };
  function link(url, label) {
    const a = node('a', '', label);
    try { const u = new URL(url); if (!['https:','http:'].includes(u.protocol) || u.username || u.password) return node('span','',label); a.href = u.href; }
    catch { return node('span','',label); }
    a.target = '_blank'; a.rel = 'noopener noreferrer'; return a;
  }
  let data = JSON.parse($('bootstrap').textContent), year = 2026, timer = null, allStories = false;
  let selectedEntity = 'brm', decoded = {}, images = {}, imageVersion = '';
  let renderVersion = '';
  const canvas = $('map'), ctx = canvas.getContext('2d');
  function array(base64, int16 = true) {
    const bytes = Uint8Array.from(atob(base64), c => c.charCodeAt(0));
    if (!int16) return bytes;
    const view = new DataView(bytes.buffer);
    return Array.from({length:bytes.length / 2}, (_, i) => view.getInt16(i * 2, true));
  }
  function loadSatellite() {
    const s = data.satellite; if (!s || imageVersion === s.generatedAt) return;
    imageVersion = s.generatedAt; decoded = {}; images = {};
    for (const [key, value] of Object.entries(s.arrays)) decoded[key] = array(value);
    decoded.common = array(s.commonMask, false);
    for (const scene of s.scenes) {
      const img = new Image(); images[scene.year] = img;
      img.onload = () => draw(); img.src = scene.image;
    }
    $('method-text').textContent = s.method;
    const table = node('table');
    const head = node('tr'); ['Year','Observation','Local valid area','Source'].forEach(t => head.append(node('th','',t)));
    const thead = node('thead'); thead.append(head); table.append(thead);
    const tbody = node('tbody');
    for (const scene of s.scenes) {
      const row = node('tr'); row.append(node('td','',scene.year),node('td','',date(scene.date)),node('td','',`${format(scene.coverage*100)}%`));
      const source = node('td'); source.append(link(scene.url,'STAC record ↗')); row.append(source); tbody.append(row);
    }
    table.append(tbody); $('scene-table').replaceChildren(table);
    $('satellite-sources').replaceChildren(...s.sources.map(s => link(s.url,s.label+' ↗')));
  }
  function draw() {
    const s = data.satellite, current = images[year], base = images[2022];
    if (!s || !current?.complete || !current.naturalWidth) return;
    ctx.clearRect(0,0,800,800); ctx.drawImage(current,0,0,800,800);
    const split = Number($('wipe').value)*8;
    if (base?.complete && base.naturalWidth && split > 0) {
      ctx.save(); ctx.beginPath(); ctx.rect(0,0,split,800); ctx.clip(); ctx.drawImage(base,0,0,800,800); ctx.restore();
    }
    const step = 800 / s.width, baseline = decoded.ndvi2022, values = decoded['ndvi'+year];
    if ($('mask-toggle').checked) {
      ctx.save(); ctx.beginPath(); ctx.rect(split,0,800-split,800); ctx.clip();
      for (let i=0; i<values.length; i++) {
        const x=(i%s.width)*step, y=Math.floor(i/s.width)*step;
        if (!decoded.common[i]) {
          ctx.fillStyle='rgba(21,31,28,.35)'; ctx.fillRect(x,y,step,step);
          if ((i%s.width+Math.floor(i/s.width))%3===0) {
            ctx.strokeStyle='rgba(207,220,211,.23)'; ctx.lineWidth=.8;
            ctx.beginPath(); ctx.moveTo(x,y+step); ctx.lineTo(x+step,y); ctx.stroke();
          }
          continue;
        }
        if (baseline[i] < s.baselineNdvi*10000) continue;
        if ((values[i]-baseline[i])/10000 < s.declineThreshold) ctx.fillStyle='rgba(220,101,52,.90)';
        else if (values[i] >= s.baselineNdvi*10000) ctx.fillStyle='rgba(51,170,113,.90)';
        else continue;
        ctx.fillRect(x,y,Math.max(2,step),Math.max(2,step));
      }
      ctx.restore();
    }
    if (split > 0 && split < 800) {
      ctx.strokeStyle='#fff'; ctx.lineWidth=2; ctx.beginPath();ctx.moveTo(split,0);ctx.lineTo(split,800);ctx.stroke();
    }
    $('wipe-label').textContent = split === 0 ? 'Selected image only' : `${Math.round(split/8)}% baseline image`;
    canvas.setAttribute('aria-label', `Calcatreu on ${s.scenes.find(x=>x.year===year).date}. ${format(s.commonCoverage*100)}% of the study window is comparable across all five observations.`);
  }
  function renderLand() {
    const s = data.satellite;
    if (!s) { $('scope').textContent = 'Satellite snapshot is not available yet. News and ownership records can still be explored.'; return; }
    const metrics=s.summary.find(v=>v.year===year), scene=s.scenes.find(v=>v.year===year);
    $('retained').textContent=`${format(metrics.retainedHa)} ha`;
    $('retained-context').textContent=`${metrics.retainedPercent}% of ${format(metrics.baselineVegetationHa)} ha observed in 2022`;
    $('retained-meter').style.width=metrics.retainedPercent+'%';
    $('decline').textContent=`${format(metrics.declineHa)} ha`;
    $('coverage').textContent=`${format(s.commonCoverage*100)}%`;
    $('coverage-context').textContent=`${format(s.commonCells*s.cellAreaHa)} of ${format(s.areaHa)} ha`;
    $('scope').textContent=`Coverage is limited: metrics describe the ${format(s.commonCoverage*100)}% of this study window observed in every year. Calcatreu's sparse vegetation is not a mapped forest; these values do not establish deforestation or mining causation.`;
    $('observation').textContent=`${date(scene.date)} · ${scene.sensor.replace('landsat-','Landsat ')}`;
    $('map-year').textContent=year; $('year-label').textContent=year; $('news-year').textContent=year;
    $('cell-detail').hidden=true; draw(); renderStories();
  }
  function storyCard(item, reviewed=false) {
    const card=node('article','story'), meta=node('div','story-meta');
    const when=item.date || item.publishedDate;
    meta.append(node('b','',item.category || 'Research'),node('span','',date(when)));
    card.append(meta,node('h4','',item.title),node('p','',item.excerpt));
    card.append(link(item.url,`${item.publisher} ↗`));
    if (reviewed) {
      const scene=data.satellite?.scenes.find(x=>x.year===year);
      const dayKnown=item.datePrecision==='day';
      const relation=scene && dayKnown && item.date>scene.date ? 'Report postdates this satellite image.' : 'Report and satellite dates are separate observations.';
      card.append(node('p','date-relation',relation));
    } else card.append(node('p','fine','Tavily discovery · source content requires review'));
    return card;
  }
  function renderStories() {
    const events=(data.evidence.events || []).filter(s=>s.year===year).sort((a,b)=>b.date.localeCompare(a.date));
    $('stories').replaceChildren(...events.slice(0,allStories?events.length:3).map(s=>storyCard(s,true)));
    if (events.length>3 && !allStories) {
      const more=node('button','','Show earlier event'); more.addEventListener('click',()=>{allStories=true;renderStories();});$('stories').append(more);
    }
    $('story-empty').hidden=!!events.length;
    // Search results can mention Calcatreu in unrelated navigation; require a relevant title.
    const stories=(data.news.stories || []).filter(s => /calcatreu|patagonia[\s_-]+gold/i.test(s.title) && !/(facebook|instagram|tiktok)\.com/.test(s.url));
    $('discovery-count').textContent=`(${stories.length})`;
    $('discovered-stories').replaceChildren(...stories.map(s=>storyCard(s)));
    $('news-updated').textContent=`Retrieved ${date(data.news.retrievedAt)}. Discovery covers 2022–2026; results without publication dates are not placed on the timeline.`;
    $('ai-brief').textContent=data.news.brief?.text || 'No AI brief is available in the saved snapshot.';
    $('ai-sources').replaceChildren(...(data.news.brief?.sourceUrls || []).map((s,i)=>link(s,`Source ${i+1} ↗`)));
  }
  function renderEntity() {
    const e=data.evidence, entity=e.entities.find(v=>v.id===selectedEntity);
    if (!entity) return;
    document.querySelectorAll('.entity').forEach(n=>n.setAttribute('aria-pressed',String(n.dataset.id===selectedEntity)));
    const ul=node('ul');
    for (const edge of e.relationships.filter(r=>r.from===selectedEntity || r.to===selectedEntity)) {
      const from=e.entities.find(n=>n.id===edge.from)?.name || edge.from, to=e.entities.find(n=>n.id===edge.to)?.name || edge.to;
      ul.append(node('li','',`${from} → ${to}: ${edge.label}.`));
    }
    $('entity-detail').replaceChildren(node('strong','',entity.name),ul);
    if (selectedEntity==='brm') $('entity-detail').append(node('p','',e.controlNote));
    $('entity-detail').append(link(e.filingUrl,'Source: June 2025 filing, note 19 ↗'));
  }
  function renderMoney() {
    const e=data.evidence;
    const lookup=Object.fromEntries((e.entities || []).map(v=>[v.id,v]));
    const items=[];
    const entityButton=id=>{const item=lookup[id];if(!item)return node('span');const b=node('button','entity',item.name);b.dataset.id=id;b.append(node('small','',item.detail));b.addEventListener('click',()=>{selectedEntity=id;renderEntity();});return b;};
    items.push(entityButton('corp'),node('span'),node('div','network-arrow','↓ 100%'),node('span'));
    items.push(entityButton('pgl'),entityButton('brm'));
    items.push(node('div','network-arrow','↘ 60% common'),node('div','network-arrow','↙ 40% preferred · US$40m'));
    const canada=entityButton('pgi'), argentina=entityButton('minera'), arrow=node('div','network-arrow','↓ 100%');
    for (const n of [canada,arrow,argentina]) {n.style.gridColumn='1 / -1';n.style.textAlign='center';}
    items.push(canada,arrow,argentina);
    $('network').replaceChildren(...items);
    $('filing-link').href=e.filingUrl;
    renderEntity(); renderPhase();
    const ready=data.sayari.status==='ok';
    $('sayari-status').textContent=ready?'Sayari · imported evidence snapshot':'Sayari · authorization pending';
    if (ready) {
      $('sayari-description').textContent=`Sayari evidence snapshot retrieved ${date(data.sayari.retrievedAt)}. These records are separate from the June 2025 public filing.`;
      const entries=(data.sayari.entities || []).map(e=>{const p=node('p','',`${e.name} · ${e.id}`);if(e.sourceUrl)p.append(' ',link(e.sourceUrl,'Evidence ↗'));return p;});
      for(const r of data.sayari.relationships || []) {const p=node('p','',`${r.from} → ${r.to}: ${r.label}`);if(r.sourceUrl)p.append(' ',link(r.sourceUrl,'Evidence ↗'));entries.push(p);}
      $('sayari-results').replaceChildren(...entries);
    }
  }
  function renderPhase() {
    const s=data.evidence.distributionStages?.[Number($('phase').value)];if(!s)return;
    $('allocation').replaceChildren();
    for(const [key,cls] of [['brm','purple'],['pgl','green']]) {
      if(!s[key])continue;const bar=node('div',cls,`${s[key]}%`);bar.style.width=s[key]+'%';$('allocation').append(bar);
    }
    $('allocation').setAttribute('aria-label',`Contractual distribution: Black River Mine ${s.brm}%, Patagonia Gold Limited ${s.pgl}%.`);
    $('phase-detail').textContent=s.description;
  }
  function stop() {if(timer)clearInterval(timer);timer=null;$('play').textContent='Play';}
  function setYear(value) {year=Number(value);$('year').value=year;allStories=false;renderLand();}
  $('year').addEventListener('input',e=>{stop();setYear(e.target.value);});
  $('wipe').addEventListener('input',draw);$('mask-toggle').addEventListener('change',draw);
  $('phase').addEventListener('change',renderPhase);
  $('play').addEventListener('click',()=>{
    if(timer){stop();return;}if(year===2026)setYear(2022);
    $('play').textContent='Pause';timer=setInterval(()=>{setYear(year+1);if(year>=2026)stop();},1800);
  });
  for (const tab of ['land','money']) $(tab+'-tab').addEventListener('click',()=>{
    stop();for(const id of ['land','money']){$(id+'-tab').setAttribute('aria-pressed',String(id===tab));$(id+'-panel').hidden=id!==tab;}
  });
  $('method-button').addEventListener('click',()=>{$('method').open=true;$('method').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'start'});});
  canvas.addEventListener('click',e=>{
    const s=data.satellite;if(!s)return;const rect=canvas.getBoundingClientRect();
    const col=Math.min(s.width-1,Math.floor((e.clientX-rect.left)/rect.width*s.width)),row=Math.min(s.height-1,Math.floor((e.clientY-rect.top)/rect.height*s.height));
    const i=row*s.width+col,b=decoded.ndvi2022[i],v=decoded['ndvi'+year][i];
    $('cell-detail').hidden=false;$('cell-detail').textContent=`Cell ${row+1}, ${col+1} · 4 ha\n${decoded.common[i]?`2022 NDVI ${(b/10000).toFixed(2)} → ${year} ${(v/10000).toFixed(2)}\nChange ${((v-b)/10000).toFixed(2)}`:'Excluded: not valid in all five observations.'}`;
  });
  document.addEventListener('visibilitychange',()=>{if(document.hidden)stop();});
  window.updateDashboard = snapshot => {
    data=snapshot;
    const version=JSON.stringify([data.satellite?.generatedAt,data.news.retrievedAt,data.evidence,data.sayari]);
    if (version!==renderVersion) {renderVersion=version;loadSatellite();renderLand();renderMoney();}
    const service=data.service || {};
    $('connection').textContent=service.mode==='static'
      ? (service.newsRefreshConfigured?'Published snapshot · scheduled news updates':'Published snapshot · news automation not configured')
      : service.lastError?'News refresh failed · saved snapshot':service.refreshing?'Refreshing news…':service.tavilyConfigured?'Tavily connected · hourly refresh':'Saved snapshot · Tavily not configured';
    $('refresh-news').disabled=service.mode==='static' ? false : !!service.refreshing || !service.tavilyConfigured;
    $('snapshot-time').textContent=`News retrieved ${date(data.news.retrievedAt)} · Satellite ${date(data.satellite?.generatedAt)}`;
    if(service.lastError)$('refresh-status').textContent=service.lastError;
  };
  window.updateDashboard(data);
})();
