"""HTML Dashboard served by FastAPI."""

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AU Grants Agent — Dashboard</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; background: #0a0a0a; color: #e0e0e0; }
  a { color: #00ff88; text-decoration: none; }
  a:hover { text-decoration: underline; }

  .header { background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 100%); border-bottom: 2px solid #00ff88; padding: 20px 40px; display: flex; align-items: center; justify-content: space-between; }
  .header h1 { color: #00ff88; font-size: 24px; }
  .header .links a { margin-left: 20px; font-size: 14px; color: #888; }
  .header .links a:hover { color: #00ff88; }

  .container { max-width: 1400px; margin: 0 auto; padding: 20px 40px; }

  .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 30px; }
  .stat-card { background: #141414; border: 1px solid #222; border-radius: 12px; padding: 20px; text-align: center; transition: border-color 0.2s; }
  .stat-card:hover { border-color: #00ff88; }
  .stat-card .value { font-size: 36px; font-weight: bold; color: #00ff88; }
  .stat-card .label { font-size: 13px; color: #888; margin-top: 4px; text-transform: uppercase; letter-spacing: 1px; }

  .section { margin-bottom: 30px; }
  .section h2 { font-size: 18px; color: #00ff88; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid #222; }

  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
  @media (max-width: 900px) { .grid-2 { grid-template-columns: 1fr; } }

  .chart-card { background: #141414; border: 1px solid #222; border-radius: 12px; padding: 20px; }
  .chart-card h3 { font-size: 14px; color: #aaa; margin-bottom: 12px; }

  .bar-row { display: flex; align-items: center; margin-bottom: 6px; font-size: 13px; }
  .bar-label { width: 140px; text-align: right; padding-right: 10px; color: #aaa; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .bar-fill { height: 20px; background: linear-gradient(90deg, #00ff88, #00cc6a); border-radius: 4px; min-width: 2px; transition: width 0.5s ease; }
  .bar-value { margin-left: 8px; color: #00ff88; font-weight: 600; min-width: 30px; }

  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th { text-align: left; padding: 10px 12px; color: #00ff88; border-bottom: 2px solid #00ff88; font-weight: 600; text-transform: uppercase; font-size: 11px; letter-spacing: 1px; }
  td { padding: 10px 12px; border-bottom: 1px solid #1a1a1a; }
  tr:hover td { background: #1a1a1a; }
  .status-open { color: #00ff88; font-weight: 600; }
  .status-closed { color: #666; }
  .urgent { color: #ff4444; font-weight: 600; }

  .source-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
  .source-nsw { background: #1a2a1a; color: #00ff88; }
  .source-arc { background: #1a1a2a; color: #6688ff; }
  .source-business { background: #2a2a1a; color: #ffaa00; }
  .source-grants { background: #2a1a1a; color: #ff6666; }
  .source-arena { background: #1a2a2a; color: #00cccc; }
  .source-nhmrc { background: #2a1a2a; color: #cc66ff; }

  .crawl-btn { background: #00ff88; color: #000; border: none; padding: 8px 20px; border-radius: 6px; font-weight: 600; cursor: pointer; font-size: 13px; }
  .crawl-btn:hover { background: #00cc6a; }
  .crawl-btn:disabled { background: #333; color: #666; cursor: not-allowed; }

  .loading { text-align: center; padding: 40px; color: #666; }
  .loading .spinner { display: inline-block; width: 24px; height: 24px; border: 3px solid #333; border-top: 3px solid #00ff88; border-radius: 50%; animation: spin 1s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }

  .search-box { width: 100%; padding: 10px 16px; background: #1a1a1a; border: 1px solid #333; border-radius: 8px; color: #e0e0e0; font-size: 14px; margin-bottom: 16px; }
  .search-box:focus { outline: none; border-color: #00ff88; }

  .pagination { display: flex; gap: 8px; justify-content: center; margin-top: 16px; }
  .pagination button { background: #1a1a1a; border: 1px solid #333; color: #aaa; padding: 6px 12px; border-radius: 4px; cursor: pointer; }
  .pagination button.active { border-color: #00ff88; color: #00ff88; }
  .pagination button:hover { border-color: #00ff88; }

  .filters { display: flex; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; }
  .filter-select { background: #1a1a1a; border: 1px solid #333; color: #e0e0e0; padding: 8px 12px; border-radius: 6px; font-size: 13px; }
  .filter-select:focus { outline: none; border-color: #00ff88; }

  .toast { position: fixed; bottom: 20px; right: 20px; background: #00ff88; color: #000; padding: 12px 24px; border-radius: 8px; font-weight: 600; display: none; z-index: 1000; }
</style>
</head>
<body>

<div class="header">
  <h1>AU Grants Agent</h1>
  <div class="links">
    <a href="/docs">API Docs</a>
    <a href="/api/stats">Stats JSON</a>
    <a href="https://github.com/tuantqse90/au-grants-agent" target="_blank">GitHub</a>
  </div>
</div>

<div class="container">
  <!-- Stats Cards -->
  <div class="stats-grid" id="stats-grid">
    <div class="stat-card"><div class="value" id="total-grants">—</div><div class="label">Total Grants</div></div>
    <div class="stat-card"><div class="value" id="open-grants">—</div><div class="label">Open Grants</div></div>
    <div class="stat-card"><div class="value" id="sources-count">—</div><div class="label">Sources</div></div>
    <div class="stat-card"><div class="value" id="urgent-count">—</div><div class="label">Closing 7 Days</div></div>
    <div class="stat-card"><div class="value" id="proposals-count">—</div><div class="label">Proposals</div></div>
  </div>

  <!-- Charts Row -->
  <div class="grid-2 section">
    <div class="chart-card">
      <h3>Grants by Source</h3>
      <div id="source-chart"></div>
    </div>
    <div class="chart-card">
      <h3>Funding Distribution</h3>
      <div id="funding-chart"></div>
    </div>
  </div>

  <div class="grid-2 section">
    <div class="chart-card">
      <h3>Top Categories</h3>
      <div id="category-chart"></div>
    </div>
    <div class="chart-card">
      <h3>Top Agencies</h3>
      <div id="agency-chart"></div>
    </div>
  </div>

  <!-- Urgent Grants -->
  <div class="section">
    <h2>Urgent — Closing Within 7 Days</h2>
    <div id="urgent-table"><div class="loading"><div class="spinner"></div></div></div>
  </div>

  <!-- Browse Grants -->
  <div class="section">
    <h2>Browse Grants</h2>
    <div class="filters">
      <select class="filter-select" id="filter-status" onchange="loadGrants()">
        <option value="">All Status</option>
        <option value="Open" selected>Open</option>
        <option value="Closed">Closed</option>
      </select>
      <select class="filter-select" id="filter-source" onchange="loadGrants()">
        <option value="">All Sources</option>
      </select>
      <input type="text" class="search-box" id="search-box" placeholder="Search grants..." onkeyup="debounceSearch()" style="flex:1;margin-bottom:0;">
      <button class="crawl-btn" onclick="runCrawl()" id="crawl-btn">Crawl Now</button>
    </div>
    <div id="grants-table"><div class="loading"><div class="spinner"></div></div></div>
    <div class="pagination" id="pagination"></div>
  </div>

  <!-- Crawl History -->
  <div class="section">
    <h2>Crawl History</h2>
    <div id="crawl-history"><div class="loading"><div class="spinner"></div></div></div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
const API = '';
let allGrants = [];
let currentPage = 0;
const PAGE_SIZE = 20;
let searchTimer = null;

async function fetchJSON(url) {
  const r = await fetch(API + url);
  return r.json();
}

function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.display = 'block';
  setTimeout(() => t.style.display = 'none', 3000);
}

function sourceClass(s) {
  if (!s) return '';
  if (s.includes('nsw')) return 'source-nsw';
  if (s.includes('arc')) return 'source-arc';
  if (s.includes('business')) return 'source-business';
  if (s.includes('grants.gov')) return 'source-grants';
  if (s.includes('arena')) return 'source-arena';
  if (s.includes('nhmrc')) return 'source-nhmrc';
  return '';
}

function renderBars(containerId, data, maxItems = 10) {
  const el = document.getElementById(containerId);
  const entries = Object.entries(data).slice(0, maxItems);
  const maxVal = Math.max(...entries.map(e => e[1]), 1);
  el.innerHTML = entries.map(([k, v]) => `
    <div class="bar-row">
      <div class="bar-label" title="${k}">${k}</div>
      <div class="bar-fill" style="width: ${(v / maxVal * 100)}%"></div>
      <div class="bar-value">${v.toLocaleString()}</div>
    </div>
  `).join('');
}

async function loadStats() {
  const s = await fetchJSON('/api/stats');
  document.getElementById('total-grants').textContent = s.total_grants.toLocaleString();
  document.getElementById('open-grants').textContent = s.open_grants.toLocaleString();
  document.getElementById('sources-count').textContent = Object.keys(s.sources).length;
  document.getElementById('proposals-count').textContent = s.total_proposals;

  renderBars('source-chart', s.sources);
  renderBars('category-chart', s.top_categories);

  // Populate source filter
  const sel = document.getElementById('filter-source');
  Object.keys(s.sources).forEach(src => {
    const opt = document.createElement('option');
    opt.value = src; opt.textContent = src;
    sel.appendChild(opt);
  });
}

async function loadAnalytics() {
  const a = await fetchJSON('/api/analytics/funding');
  renderBars('funding-chart', a.amount_distribution);
  renderBars('agency-chart', a.top_agencies, 8);

  const t = await fetchJSON('/api/analytics/timeline?days=7');
  document.getElementById('urgent-count').textContent = t.urgent_next_7_days.length;

  const urgentEl = document.getElementById('urgent-table');
  if (t.urgent_next_7_days.length === 0) {
    urgentEl.innerHTML = '<p style="color:#666;padding:10px;">No grants closing in the next 7 days.</p>';
    return;
  }
  urgentEl.innerHTML = `<table>
    <tr><th>ID</th><th>Title</th><th>Closing Date</th><th>Agency</th></tr>
    ${t.urgent_next_7_days.map(g => `
      <tr>
        <td style="color:#666">${g.id}</td>
        <td class="urgent">${g.title}</td>
        <td class="urgent">${g.date}</td>
        <td>${g.agency || ''}</td>
      </tr>
    `).join('')}
  </table>`;
}

async function loadGrants() {
  currentPage = 0;
  const status = document.getElementById('filter-status').value;
  const source = document.getElementById('filter-source').value;
  let url = `/api/grants?limit=500`;
  if (status) url += `&status=${status}`;
  if (source) url += `&source=${source}`;

  allGrants = await fetchJSON(url);
  filterAndRender();
}

function debounceSearch() {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => { currentPage = 0; filterAndRender(); }, 300);
}

function filterAndRender() {
  const q = document.getElementById('search-box').value.toLowerCase();
  let filtered = allGrants;
  if (q) {
    filtered = allGrants.filter(g =>
      (g.title || '').toLowerCase().includes(q) ||
      (g.agency || '').toLowerCase().includes(q) ||
      (g.category || '').toLowerCase().includes(q)
    );
  }

  const start = currentPage * PAGE_SIZE;
  const page = filtered.slice(start, start + PAGE_SIZE);
  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);

  const el = document.getElementById('grants-table');
  if (page.length === 0) {
    el.innerHTML = '<p style="color:#666;padding:10px;">No grants found.</p>';
    document.getElementById('pagination').innerHTML = '';
    return;
  }

  el.innerHTML = `<table>
    <tr><th>Title</th><th>Agency</th><th>Category</th><th>Amount</th><th>Closing</th><th>Status</th><th>Source</th></tr>
    ${page.map(g => {
      let amt = '';
      if (g.amount_min && g.amount_max) amt = '$' + g.amount_min.toLocaleString() + ' – $' + g.amount_max.toLocaleString();
      else if (g.amount_min) amt = '$' + g.amount_min.toLocaleString();
      const sc = g.status === 'Open' ? 'status-open' : 'status-closed';
      return `<tr>
        <td><a href="${g.source_url || '#'}" target="_blank">${(g.title || '').substring(0, 60)}</a></td>
        <td>${(g.agency || '').substring(0, 30)}</td>
        <td>${(g.category || '').substring(0, 20)}</td>
        <td style="white-space:nowrap">${amt}</td>
        <td>${g.closing_date || ''}</td>
        <td class="${sc}">${g.status}</td>
        <td><span class="source-badge ${sourceClass(g.source)}">${g.source || ''}</span></td>
      </tr>`;
    }).join('')}
  </table>`;

  // Pagination
  const pagEl = document.getElementById('pagination');
  if (totalPages <= 1) { pagEl.innerHTML = ''; return; }
  let html = '';
  for (let i = 0; i < totalPages && i < 10; i++) {
    html += `<button class="${i === currentPage ? 'active' : ''}" onclick="goPage(${i})">${i + 1}</button>`;
  }
  html += `<span style="color:#666;padding:6px"> (${filtered.length} grants)</span>`;
  pagEl.innerHTML = html;
}

function goPage(p) { currentPage = p; filterAndRender(); }

async function loadCrawlHistory() {
  const d = await fetchJSON('/api/analytics/crawls');
  const el = document.getElementById('crawl-history');
  const stats = d.source_stats;
  if (!stats || Object.keys(stats).length === 0) {
    el.innerHTML = '<p style="color:#666;padding:10px;">No crawl history yet.</p>';
    return;
  }
  el.innerHTML = `<table>
    <tr><th>Source</th><th>Crawls</th><th>Total Found</th><th>New</th><th>Errors</th><th>Avg Duration</th><th>Last Crawl</th></tr>
    ${Object.entries(stats).map(([src, s]) => `
      <tr>
        <td><span class="source-badge ${sourceClass(src)}">${src}</span></td>
        <td>${s.total_crawls}</td>
        <td>${s.total_found.toLocaleString()}</td>
        <td>${s.total_new.toLocaleString()}</td>
        <td style="color:${s.errors > 0 ? '#ff4444' : '#00ff88'}">${s.errors}</td>
        <td>${s.avg_duration}s</td>
        <td style="color:#666">${(s.last_crawl || '').substring(0, 19)}</td>
      </tr>
    `).join('')}
  </table>`;
}

async function runCrawl() {
  const btn = document.getElementById('crawl-btn');
  btn.disabled = true; btn.textContent = 'Crawling...';
  showToast('Crawling all sources...');
  try {
    const r = await fetch(API + '/api/crawl', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({})
    });
    const results = await r.json();
    const total = results.reduce((s, r) => s + r.grants_found, 0);
    const newG = results.reduce((s, r) => s + r.grants_new, 0);
    showToast(`Crawl done! ${total} found, ${newG} new`);
    // Reload everything
    loadStats(); loadAnalytics(); loadGrants(); loadCrawlHistory();
  } catch(e) { showToast('Crawl failed: ' + e.message); }
  btn.disabled = false; btn.textContent = 'Crawl Now';
}

// Init
loadStats();
loadAnalytics();
loadGrants();
loadCrawlHistory();
</script>
</body>
</html>"""
