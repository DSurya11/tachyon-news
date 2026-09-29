/* Dependency-free SVG charts. All colours come from CSS variables so both themes work. */
import { esc, fmtPrice, fmtDay } from './util.js';

let uid = 0;

/** Tiny inline trend line. */
export function sparkline(values, { width = 72, height = 22, up } = {}) {
  const v = (values || []).filter((x) => x != null && !Number.isNaN(+x)).map(Number);
  if (v.length < 2) return `<svg class="spark" width="${width}" height="${height}" aria-hidden="true"></svg>`;
  const min = Math.min(...v), max = Math.max(...v), rng = max - min || 1;
  const pts = v.map((y, i) => [(i / (v.length - 1)) * width, height - 2 - ((y - min) / rng) * (height - 4)]);
  const line = pts.map((p) => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ');
  const rising = up ?? v[v.length - 1] >= v[0];
  const id = `sg${++uid}`;
  const color = rising ? 'var(--bull)' : 'var(--bear)';
  const [lx, ly] = pts[pts.length - 1];
  return `<svg class="spark" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" aria-hidden="true">
    <defs><linearGradient id="${id}" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0" stop-color="${color}" stop-opacity=".28"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient></defs>
    <polygon points="0,${height} ${line} ${width},${height}" fill="url(#${id})"/>
    <polyline points="${line}" fill="none" stroke="${color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
    <circle cx="${lx.toFixed(1)}" cy="${ly.toFixed(1)}" r="2" fill="${color}"/></svg>`;
}

/**
 * Interactive price chart with gradient area, min/max guides and a hover crosshair.
 * Renders into `el` and wires its own pointer events.
 */
export function priceChart(el, dates, closes) {
  const n = closes.length;
  if (n < 2) {
    el.innerHTML = '<div class="chart-empty">No price history yet</div>';
    return;
  }
  const W = 400, H = 160, PAD_T = 12, PAD_B = 18;
  const min = Math.min(...closes), max = Math.max(...closes), rng = max - min || 1;
  const x = (i) => (i / (n - 1)) * W;
  const y = (v) => PAD_T + (1 - (v - min) / rng) * (H - PAD_T - PAD_B);
  const up = closes[n - 1] >= closes[0];
  const color = up ? 'var(--bull)' : 'var(--bear)';
  const id = `pc${++uid}`;
  const line = closes.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ');

  el.innerHTML = `
    <svg class="price-chart" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img"
         aria-label="${esc(`Price from ${fmtPrice(closes[0])} to ${fmtPrice(closes[n - 1])}`)}">
      <defs><linearGradient id="${id}" x1="0" x2="0" y1="0" y2="1">
        <stop offset="0" stop-color="${color}" stop-opacity=".30"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient></defs>
      <line class="guide" x1="0" x2="${W}" y1="${y(max)}" y2="${y(max)}"/>
      <line class="guide" x1="0" x2="${W}" y1="${y(min)}" y2="${y(min)}"/>
      <polygon points="0,${H - PAD_B} ${line} ${W},${H - PAD_B}" fill="url(#${id})"/>
      <polyline points="${line}" fill="none" stroke="${color}" stroke-width="2" vector-effect="non-scaling-stroke" stroke-linejoin="round"/>
      <line class="cross" x1="0" x2="0" y1="${PAD_T}" y2="${H - PAD_B}" visibility="hidden"/>
    </svg>
    <span class="chart-label hi mono">${fmtPrice(max)}</span>
    <span class="chart-label lo mono">${fmtPrice(min)}</span>
    <span class="chart-dot" hidden></span>
    <div class="chart-tip mono" hidden></div>
    <div class="chart-axis mono"><span>${esc(fmtDay(dates[0]))}</span><span>${esc(fmtDay(dates[n - 1]))}</span></div>`;

  const svg = el.querySelector('svg');
  const cross = el.querySelector('.cross');
  const tip = el.querySelector('.chart-tip');
  const dot = el.querySelector('.chart-dot');
  dot.style.background = color;

  const move = (ev) => {
    const r = svg.getBoundingClientRect();
    const rel = Math.min(1, Math.max(0, (ev.clientX - r.left) / r.width));
    const i = Math.round(rel * (n - 1));
    const px = (x(i) / W) * r.width;
    const py = (y(closes[i]) / H) * r.height;
    cross.setAttribute('x1', x(i)); cross.setAttribute('x2', x(i));
    cross.setAttribute('visibility', 'visible');
    const chg = ((closes[i] - closes[0]) / closes[0]) * 100;
    tip.innerHTML = `<b>${fmtPrice(closes[i])}</b> <span class="${chg >= 0 ? 'up' : 'down'}">${chg >= 0 ? '+' : ''}${chg.toFixed(2)}%</span><br>${esc(fmtDay(dates[i]))}`;
    tip.hidden = false; dot.hidden = false;
    dot.style.left = `${px}px`; dot.style.top = `${py}px`;
    tip.style.left = `${Math.min(Math.max(px, 60), r.width - 60)}px`;
  };
  const leave = () => { cross.setAttribute('visibility', 'hidden'); tip.hidden = true; dot.hidden = true; };
  svg.addEventListener('pointermove', move);
  svg.addEventListener('pointerleave', leave);
}

/** Stacked hourly bars (bullish / neutral / bearish) for the sentiment timeline. */
export function sentimentBars(buckets) {
  const W = 720, H = 120, gap = 2;
  const max = Math.max(1, ...buckets.map((b) => b.bullish + b.neutral + b.bearish));
  const bw = W / buckets.length - gap;
  const bars = buckets.map((b, i) => {
    const x = i * (bw + gap);
    let yTop = H;
    const seg = (v, cls) => {
      if (!v) return '';
      const h = (v / max) * (H - 4);
      yTop -= h;
      return `<rect class="${cls}" x="${x.toFixed(1)}" y="${yTop.toFixed(1)}" width="${bw.toFixed(1)}" height="${h.toFixed(1)}" rx="1.5"/>`;
    };
    const total = b.bullish + b.neutral + b.bearish;
    const hour = b.t.toLocaleString('en-US', { timeZone: 'America/New_York', weekday: 'short', hour: 'numeric' });
    return `<g><title>${esc(`${hour} ET — ${total} stories: ${b.bullish} bullish, ${b.neutral} neutral, ${b.bearish} bearish`)}</title>
      <rect class="hit" x="${x.toFixed(1)}" y="0" width="${(bw + gap).toFixed(1)}" height="${H}"/>
      ${seg(b.bearish, 'bear')}${seg(b.neutral, 'neu')}${seg(b.bullish, 'bull')}</g>`;
  }).join('');
  const labels = buckets
    .map((b, i) => ({ i, b }))
    .filter(({ i }) => i % 12 === 0)
    .map(({ i, b }) => `<span style="left:${((i * (bw + gap)) / W) * 100}%">${esc(
      b.t.toLocaleString('en-US', { timeZone: 'America/New_York', weekday: 'short', hour: 'numeric' }))}</span>`)
    .join('');
  return `<div class="bars-wrap"><svg class="bars" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img"
    aria-label="Stories per hour by sentiment, last ${buckets.length} hours">${bars}</svg>
    <div class="bars-axis mono">${labels}<span style="right:0">now</span></div></div>`;
}

/** 100%-stacked sentiment split bar. */
export function splitBar({ bullish = 0, neutral = 0, bearish = 0 }, { thin = false } = {}) {
  const total = bullish + neutral + bearish || 1;
  const pct = (v) => ((v / total) * 100).toFixed(1);
  return `<div class="split${thin ? ' thin' : ''}" role="img" aria-label="${bullish} bullish, ${neutral} neutral, ${bearish} bearish">
    <i class="bull" style="width:${pct(bullish)}%"></i><i class="neu" style="width:${pct(neutral)}%"></i><i class="bear" style="width:${pct(bearish)}%"></i></div>`;
}

/** Background tint for a net-sentiment score in [-1, 1]. */
export function netTint(net) {
  const pct = Math.round(Math.min(0.32, 0.06 + Math.abs(net) * 0.3) * 100);
  if (net >= 0.05) return `color-mix(in srgb, var(--bull) ${pct}%, transparent)`;
  if (net <= -0.05) return `color-mix(in srgb, var(--bear) ${pct}%, transparent)`;
  return 'var(--bg-2)';
}
