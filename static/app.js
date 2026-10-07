const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const PAL = ['#ff9900', '#22d3ee', '#a78bfa', '#34d399', '#f472b6', '#facc15', '#60a5fa', '#fb7185'];
const inr = v => '₹' + Number(v).toLocaleString('en-IN', { maximumFractionDigits: 0 });
const num = v => Number(v).toLocaleString('en-IN');

Chart.defaults.color = '#8b95b3';
Chart.defaults.font.family = "'Space Grotesk', sans-serif";
Chart.defaults.borderColor = 'rgba(255,255,255,.07)';
Chart.defaults.plugins.legend.labels.usePointStyle = true;
Chart.defaults.maintainAspectRatio = false;

const charts = {};
function draw(id, config) {
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart($('#' + id), config);
}
function grad(ctx, color, h = 320) {
  const g = ctx.createLinearGradient(0, 0, 0, h);
  g.addColorStop(0, color + 'dd'); g.addColorStop(1, color + '11');
  return g;
}
async function api(url, opts) {
  const r = await fetch(url, opts);
  return r.json();
}
function toast(msg) {
  const t = $('#toast'); t.textContent = msg; t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2800);
}
function countUp(el, to, fmt) {
  const t0 = performance.now();
  (function step(t) {
    const p = Math.min(1, (t - t0) / 800);
    el.textContent = fmt(to * (1 - Math.pow(1 - p, 3)));
    if (p < 1) requestAnimationFrame(step);
  })(t0);
}
function kpi(label, value, fmt, color, sub) {
  return `<div class="kpi" style="--k:${color}"><small>${label}</small><b data-v="${value}" data-f="${fmt}">0</b>${sub || ''}</div>`;
}
const FMT = { inr, num, pct: v => v.toFixed(1) + '%' };
function animateKpis(box) {
  $$('b[data-v]', box).forEach(b => countUp(b, parseFloat(b.dataset.v), FMT[b.dataset.f]));
}
function delta(v) {
  if (v === null || v === undefined) return '<em class="muted">no prior data</em>';
  return `<em class="${v >= 0 ? 'up' : 'down'}">${v >= 0 ? '▲' : '▼'} ${Math.abs(v)}% vs previous</em>`;
}
const doughnut = (labels, values) => ({
  type: 'doughnut',
  data: { labels, datasets: [{ data: values, backgroundColor: PAL, borderColor: '#0b1020', borderWidth: 3, hoverOffset: 12 }] },
  options: { cutout: '64%', plugins: { legend: { position: 'right' }, tooltip: { callbacks: { label: c => ` ${c.label}: ${inr(c.parsed)}` } } } },
});

/* ---------- tabs ---------- */
const loaded = {};
const loaders = { overview: loadOverview, sales: () => loadSales(), customers: loadCustomers, orders: loadOrders, pipeline: loadPipeline };
function openTab(name) {
  $$('#tabs button').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
  $$('.tab').forEach(t => t.classList.toggle('active', t.id === 'tab-' + name));
  loaders[name](); loaded[name] = true;
}
$('#tabs').addEventListener('click', e => { if (e.target.dataset.tab) openTab(e.target.dataset.tab); });
const current = () => $('#tabs button.active').dataset.tab;

/* ---------- overview ---------- */
async function loadOverview() {
  const d = await api('/api/overview');
  $('#kpis').innerHTML =
    kpi('Total revenue', d.revenue, 'inr', '#ff9900') +
    kpi('Orders', d.orders, 'num', '#22d3ee') +
    kpi('Customers', d.customers, 'num', '#a78bfa') +
    kpi('Avg order value', d.aov, 'inr', '#34d399') +
    kpi('Today', d.today, 'inr', '#f472b6') +
    kpi('Last 30 days', d.rev30, 'inr', '#facc15', delta(d.growth30));
  animateKpis($('#kpis'));
  draw('ovCat', doughnut(d.categories.labels, d.categories.values));
  draw('ovProd', {
    type: 'bar',
    data: { labels: d.top_products.labels, datasets: [{ data: d.top_products.values, backgroundColor: PAL, borderRadius: 8 }] },
    options: { indexAxis: 'y', plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => ' ' + inr(c.parsed.x) } } } },
  });
  const s = await api('/api/sales?period=daily');
  drawCombo('ovTrend', s, 'line');
}

/* ---------- sales ---------- */
function drawCombo(id, s, type) {
  const ctx = $('#' + id).getContext('2d');
  draw(id, {
    data: {
      labels: s.labels,
      datasets: [
        {
          type, label: 'Revenue', data: s.revenue, yAxisID: 'y',
          backgroundColor: type === 'line' ? grad(ctx, '#ff9900') : '#ff9900', borderColor: '#ff9900',
          fill: true, tension: .4, borderRadius: 8, pointRadius: type === 'line' ? 2 : 0, order: 2,
        },
        { type: 'line', label: 'Orders', data: s.orders, yAxisID: 'y1', borderColor: '#22d3ee', backgroundColor: '#22d3ee', tension: .4, pointRadius: 2, borderWidth: 2, order: 1 },
      ],
    },
    options: {
      interaction: { mode: 'index', intersect: false },
      scales: {
        y: { ticks: { callback: v => inr(v) }, beginAtZero: true },
        y1: { position: 'right', grid: { display: false }, beginAtZero: true },
        x: { grid: { display: false }, ticks: { maxTicksLimit: 12 } },
      },
      plugins: { tooltip: { callbacks: { label: c => c.dataset.label === 'Revenue' ? ' Revenue: ' + inr(c.parsed.y) : ' Orders: ' + c.parsed.y } } },
    },
  });
}
let period = 'daily', ctype = 'bar';
async function loadSales() {
  const s = await api('/api/sales?period=' + period);
  const name = period[0].toUpperCase() + period.slice(1);
  $('#salesTitle').textContent = name + ' sales';
  const m = s.summary;
  $('#salesKpis').innerHTML =
    kpi('Total in range', m.total, 'inr', '#ff9900') +
    kpi('Orders', m.orders, 'num', '#22d3ee') +
    kpi('Average / ' + period.replace('ly', '').replace('dai', 'day').replace('week', 'week').replace('month', 'month'), m.avg, 'inr', '#a78bfa') +
    kpi('Best period', m.best_value, 'inr', '#34d399', `<em class="muted">${m.best_label}</em>`) +
    kpi('Latest period', s.revenue[s.revenue.length - 1] || 0, 'inr', '#f472b6', delta(m.change));
  animateKpis($('#salesKpis'));
  drawCombo('salesMain', s, ctype === 'line' ? 'line' : 'bar');
  draw('salesCat', doughnut(s.categories.labels, s.categories.values));
  const ctx = $('#salesOrders').getContext('2d');
  draw('salesOrders', {
    type: 'bar',
    data: { labels: s.labels, datasets: [{ label: 'Units sold', data: s.units, backgroundColor: grad(ctx, '#a78bfa', 280), borderRadius: 6 }] },
    options: { scales: { x: { grid: { display: false }, ticks: { maxTicksLimit: 12 } } }, plugins: { legend: { display: false } } },
  });
  $('#salesTable').innerHTML = '<tr><th>Period</th><th class="num">Revenue</th><th class="num">Orders</th><th class="num">Units</th></tr>' +
    s.labels.map((l, i) => `<tr><td>${l}</td><td class="num">${inr(s.revenue[i])}</td><td class="num">${s.orders[i]}</td><td class="num">${s.units[i]}</td></tr>`).reverse().join('');
}
$('#periodPills').addEventListener('click', e => {
  if (!e.target.dataset.p) return;
  period = e.target.dataset.p;
  $$('#periodPills button').forEach(b => b.classList.toggle('active', b === e.target));
  loadSales();
});
$('#typePills').addEventListener('click', e => {
  if (!e.target.dataset.t) return;
  ctype = e.target.dataset.t;
  $$('#typePills button').forEach(b => b.classList.toggle('active', b === e.target));
  loadSales();
});

/* ---------- customers ---------- */
async function loadCustomers() {
  const d = await api('/api/customers');
  $('#custKpis').innerHTML =
    kpi('Customers', d.total, 'num', '#a78bfa') +
    kpi('Repeat rate', d.repeat_rate, 'pct', '#34d399') +
    kpi('Avg lifetime value', d.avg_ltv, 'inr', '#ff9900');
  animateKpis($('#custKpis'));
  draw('custSeg', doughnut(d.segments.labels, d.segments.values));
  const ctx = $('#custNew').getContext('2d');
  draw('custNew', {
    type: 'line',
    data: { labels: d.new_customers.labels, datasets: [{ label: 'New customers', data: d.new_customers.values, borderColor: '#34d399', backgroundColor: grad(ctx, '#34d399', 280), fill: true, tension: .4 }] },
    options: { plugins: { legend: { display: false } }, scales: { x: { grid: { display: false } }, y: { beginAtZero: true } } },
  });
  draw('custCity', {
    type: 'bar',
    data: { labels: d.cities.labels, datasets: [{ data: d.cities.values, backgroundColor: PAL, borderRadius: 8 }] },
    options: { plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => ' ' + inr(c.parsed.y) } } }, scales: { x: { grid: { display: false } }, y: { ticks: { callback: v => inr(v) } } } },
  });
  $('#custTable').innerHTML = '<tr><th>#</th><th>Customer</th><th>City</th><th class="num">Orders</th><th class="num">Spend</th></tr>' +
    d.top.map((c, i) => `<tr><td>${i + 1}</td><td>${esc(c.name)}</td><td>${esc(c.city || '-')}</td><td class="num">${c.orders}</td><td class="num">${inr(c.spend)}</td></tr>`).join('');
}

/* ---------- orders ---------- */
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
async function loadOrders() {
  const q = encodeURIComponent($('#search').value || '');
  const rows = await api('/api/orders?q=' + q);
  $('#ordersTable').innerHTML = '<tr><th>Date</th><th>Customer</th><th>Product</th><th>Category</th><th class="num">Qty</th><th class="num">Total</th><th>Source</th></tr>' +
    rows.map(o => `<tr><td>${o.Date}</td><td>${esc(o.CustomerName)}</td><td>${esc(o.Product)}</td><td><span class="tag">${esc(o.Category)}</span></td><td class="num">${o.Qty}</td><td class="num">${inr(o.Total)}</td><td>${esc(o.Source)}</td></tr>`).join('');
}
let st; $('#search').addEventListener('input', () => { clearTimeout(st); st = setTimeout(loadOrders, 250); });
$('#entryForm [name=date]').value = new Date().toISOString().slice(0, 10);
$('#entryForm').addEventListener('submit', async e => {
  e.preventDefault();
  const f = Object.fromEntries(new FormData(e.target));
  const r = await api('/api/orders', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(f) });
  const m = $('#formMsg');
  if (r.ok) {
    m.className = 'msg up'; m.textContent = `Saved ${r.order_id} (${inr(r.total)}) to Excel.`;
    toast('Entry saved to Excel ✓');
    e.target.reset(); $('#entryForm [name=date]').value = new Date().toISOString().slice(0, 10);
    loadOrders();
  } else { m.className = 'msg down'; m.textContent = r.error; }
});

/* ---------- pipeline ---------- */
async function loadPipeline() {
  const s = await api('/api/pipeline/status');
  $('#pipeKpis').innerHTML =
    kpi('Source', 0, 'num', '#22d3ee', `<em>${esc(s.source)}</em>`).replace('<b data-v="0" data-f="num">0</b>', `<b>${esc(s.source)}</b>`) +
    kpi('Saved this session', s.total_added, 'num', '#34d399') +
    kpi('Last run', 0, 'num', '#ff9900', '').replace('<b data-v="0" data-f="num">0</b>', `<b style="font-size:15px">${s.last_run || 'never'}</b>`);
  animateKpis($('#pipeKpis'));
  $('#logBox').innerHTML = s.log.map(l => `<div class="${l.msg.startsWith('ERROR') ? 'err' : ''}"><span>${l.t}</span>${esc(l.msg)}</div>`).join('') || '<div><span>-</span>No runs yet. Click "Run pipeline now".</div>';
  $('#liveToggle').checked = s.auto; $('#liveBox').classList.toggle('on', s.auto);
  $('#interval').value = s.interval;
}
async function runPipeline() {
  const nodes = ['n1', 'n2', 'n3', 'n4'];
  nodes.forEach((n, i) => setTimeout(() => $('#' + n).classList.add('fire'), i * 220));
  const r = await api('/api/pipeline/run', { method: 'POST' });
  setTimeout(() => nodes.forEach(n => $('#' + n).classList.remove('fire')), 1200);
  toast(r.ok ? `Pipeline: ${r.added} new orders saved` : 'Pipeline error - see log');
  refreshCurrent();
}
$('#runNow').addEventListener('click', runPipeline);
$('#pullBtn').addEventListener('click', runPipeline);
async function setLive() {
  const on = $('#liveToggle').checked;
  await api('/api/pipeline/auto', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled: on, interval: +$('#interval').value || 15 }) });
  $('#liveBox').classList.toggle('on', on);
  toast(on ? 'Live feed ON' : 'Live feed OFF');
}
$('#liveToggle').addEventListener('change', setLive);
$('#interval').addEventListener('change', () => { if ($('#liveToggle').checked) setLive(); });

function refreshCurrent() { loaders[current()](); }
// While live mode is on, redraw whatever tab is open every few seconds.
setInterval(async () => {
  if (!$('#liveToggle').checked) return;
  const s = await api('/api/pipeline/status');
  if (s.last_run !== window._lastRun) { window._lastRun = s.last_run; refreshCurrent(); }
}, 4000);

openTab('overview');
(async () => { const s = await api('/api/pipeline/status'); $('#liveToggle').checked = s.auto; $('#liveBox').classList.toggle('on', s.auto); })();
