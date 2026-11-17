# ============================================================
# TEST DASHBOARD
# Builds reports/dashboard.html after every pytest run (called from conftest.py).
# History of all runs is kept in reports/history.json.
# No need to touch this file.
# ============================================================
import datetime as dt
import json
import os
from html import escape

import config


def load_history(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_history(path, history):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)


def mins(seconds):
    m, s = divmod(int(seconds or 0), 60)
    return f"{m}m {s:02d}s" if m else f"{s}s"


def badge(outcome):
    ok = outcome == "passed"
    return f'<span class="badge {"pass" if ok else "fail"}">{"PASSED" if ok else "FAILED"}</span>'


# ---------- page sections ----------
def kpi_cards(history, latest):
    total = len(history)
    passed = sum(1 for r in history if r["outcome"] == "passed")
    failed = total - passed
    rate = f"{passed / total * 100:.0f}%" if total else "-"
    durations = [r["duration"] for r in history if r["outcome"] == "passed"]
    avg = mins(sum(durations) / len(durations)) if durations else "-"
    l_pass = sum(1 for r in latest if r["outcome"] == "passed")
    return f"""
    <section class="cards">
      <div class="card"><div class="label">Total runs</div><div class="value">{total}</div></div>
      <div class="card"><div class="label">Passed</div><div class="value green">{passed}</div></div>
      <div class="card"><div class="label">Failed</div><div class="value red">{failed}</div></div>
      <div class="card"><div class="label">Pass rate</div><div class="value">{rate}</div>
        <div class="meter"><span style="width:{passed / total * 100 if total else 0:.0f}%"></span></div></div>
      <div class="card"><div class="label">Avg time (passed)</div><div class="value">{avg}</div></div>
      <div class="card"><div class="label">Latest run</div><div class="value">{l_pass}/{len(latest)}</div>
        <div class="sub">passed</div></div>
    </section>"""


def latest_run_section(latest):
    blocks = []
    for r in latest:
        steps = r.get("steps", [])
        longest = max([s["seconds"] for s in steps] or [1]) or 1
        rows = "".join(
            f"""<div class="step">
                  <div class="sname">{i}. {escape(s['name'])}</div>
                  <div class="track"><div class="bar {'ok' if s['status'] == 'done' else 'bad'}"
                       style="width:{max(2, s['seconds'] / longest * 100):.0f}%"></div></div>
                  <div class="stime">{'FAILED ' if s['status'] != 'done' else ''}{mins(s['seconds'])}</div>
                </div>"""
            for i, s in enumerate(steps, 1))
        user = r.get("user") or {}
        error = f'<div class="error">{escape(r["error"])}</div>' if r.get("error") else ""
        shot = (f'<a class="shot" href="{escape(r["screenshot"])}" target="_blank">'
                f'<img src="{escape(r["screenshot"])}" alt="failure screenshot"></a>') if r.get("screenshot") else ""
        blocks.append(f"""
        <div class="panel">
          <div class="panel-head">
            <div><b>{escape(r['test'])}</b> {badge(r['outcome'])}</div>
            <div class="muted">{escape(r['date'])} &middot; {mins(r['duration'])}</div>
          </div>
          <div class="muted user">{escape(user.get('full_name', ''))} &middot; {escape(user.get('email', ''))}
             &middot; {escape(user.get('phone_number', ''))}</div>
          {rows or '<div class="muted">No steps recorded</div>'}
          {error}{shot}
        </div>""")
    return "".join(blocks)


def trend_section(history):
    recent = history[-30:]
    longest = max([r["duration"] for r in recent] or [1]) or 1
    bars = "".join(
        f"""<div class="tbar {'ok' if r['outcome'] == 'passed' else 'bad'}"
                 style="height:{max(6, r['duration'] / longest * 100):.0f}%"
                 title="{escape(r['date'])} | {escape((r.get('user') or {}).get('full_name', ''))} | {r['outcome'].upper()} | {mins(r['duration'])}"></div>"""
        for r in recent)
    return f"""<div class="panel"><div class="panel-head"><b>Last {len(recent)} runs</b>
               <div class="muted">bar height = time taken &middot; hover for details</div></div>
               <div class="trend">{bars}</div>
               <div class="legend"><span class="dot ok"></span>Passed <span class="dot bad"></span>Failed</div></div>"""


def step_stats_section(history):
    # average time per step (passed steps) + how often each step failed
    totals, counts, fails, order = {}, {}, {}, []
    for r in history:
        for s in r.get("steps", []):
            name = s["name"]
            if name not in order:
                order.append(name)
            if s["status"] == "done":
                totals[name] = totals.get(name, 0) + s["seconds"]
                counts[name] = counts.get(name, 0) + 1
            else:
                fails[name] = fails.get(name, 0) + 1
    if not order:
        return ""
    longest = max([totals.get(n, 0) / counts[n] for n in order if counts.get(n)] or [1]) or 1
    rows = ""
    for n in order:
        avg = totals.get(n, 0) / counts[n] if counts.get(n) else 0
        f = fails.get(n, 0)
        rows += f"""<tr><td>{escape(n)}</td>
                  <td><div class="track"><div class="bar ok" style="width:{max(2, avg / longest * 100):.0f}%"></div></div></td>
                  <td class="num">{mins(avg)}</td>
                  <td class="num {'red' if f else ''}">{f}</td></tr>"""
    return f"""<div class="panel"><div class="panel-head"><b>Steps</b>
               <div class="muted">average time and number of failures</div></div>
               <table class="steps"><thead><tr><th>Step</th><th></th><th>Avg time</th><th>Failures</th></tr></thead>
               <tbody>{rows}</tbody></table></div>"""


def history_table(history):
    rows = ""
    for r in reversed(history):
        user = r.get("user") or {}
        shot = f'<a href="{escape(r["screenshot"])}" target="_blank">view</a>' if r.get("screenshot") else ""
        rows += f"""<tr data-outcome="{r['outcome']}">
              <td>{escape(r['date'])}</td><td>{escape(r['test'])}</td>
              <td>{escape(user.get('full_name', ''))}</td><td>{escape(user.get('email', ''))}</td>
              <td>{badge(r['outcome'])}</td><td class="num">{mins(r['duration'])}</td>
              <td>{escape(r.get('failed_step') or '')}</td>
              <td class="err" title="{escape(r.get('error') or '')}">{escape((r.get('error') or '')[:80])}</td>
              <td>{shot}</td></tr>"""
    return f"""<div class="panel">
      <div class="panel-head"><b>All runs</b>
        <div class="filters">
          <button class="active" data-f="all">All</button>
          <button data-f="passed">Passed</button>
          <button data-f="failed">Failed</button>
        </div></div>
      <div class="table-wrap"><table class="history"><thead><tr>
        <th>Date</th><th>Test case</th><th>User</th><th>Email</th><th>Result</th><th>Time</th>
        <th>Failed step</th><th>Error</th><th>Screenshot</th></tr></thead>
        <tbody>{rows}</tbody></table></div></div>"""


CSS = """
:root{--bg:#f4f6fa;--card:#fff;--text:#1c2433;--muted:#6b7385;--line:#e3e7ef;--green:#1f9d55;--red:#d64545;
      --green-soft:#e3f5ea;--red-soft:#fbe6e6;--track:#eef1f6;--accent:#1f3864}
@media (prefers-color-scheme:dark){:root{--bg:#12161f;--card:#1b212c;--text:#e6e9ef;--muted:#9aa3b5;--line:#2a3240;
      --green:#3ccf7e;--red:#ff6b6b;--green-soft:#173826;--red-soft:#3d1c1c;--track:#262e3b;--accent:#8fb0ff}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 "Segoe UI",Arial,sans-serif}
header{padding:20px 24px 8px}
h1{margin:0;font-size:22px;color:var(--accent)}
.muted{color:var(--muted);font-size:12.5px}
main{padding:8px 24px 32px;display:grid;gap:16px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.card,.panel{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.label{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.04em}
.value{font-size:28px;font-weight:700;margin-top:4px}
.sub{color:var(--muted);font-size:12px}
.green{color:var(--green)}.red{color:var(--red)}
.meter{height:6px;background:var(--red-soft);border-radius:4px;margin-top:8px;overflow:hidden}
.meter span{display:block;height:100%;background:var(--green)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media (max-width:900px){.grid2{grid-template-columns:1fr}}
.panel-head{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:10px}
.user{margin:-4px 0 10px}
.badge{display:inline-block;padding:2px 8px;border-radius:20px;font-size:11px;font-weight:700;margin-left:6px}
.badge.pass{background:var(--green-soft);color:var(--green)}
.badge.fail{background:var(--red-soft);color:var(--red)}
.step{display:grid;grid-template-columns:190px 1fr 90px;gap:10px;align-items:center;margin:5px 0}
.sname{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.track{background:var(--track);border-radius:4px;height:12px;overflow:hidden}
.bar{height:100%;border-radius:4px}
.bar.ok{background:var(--green)}.bar.bad{background:var(--red)}
.stime{text-align:right;color:var(--muted);font-variant-numeric:tabular-nums}
.error{margin-top:10px;padding:8px 10px;background:var(--red-soft);color:var(--red);border-radius:8px;
       font-family:Consolas,monospace;font-size:12px;white-space:pre-wrap;word-break:break-word}
.shot img{margin-top:10px;max-width:100%;max-height:260px;border:1px solid var(--line);border-radius:8px}
.trend{display:flex;align-items:flex-end;gap:4px;height:140px;padding-top:6px}
.tbar{flex:1;min-width:6px;max-width:28px;border-radius:3px 3px 0 0}
.tbar.ok{background:var(--green)}.tbar.bad{background:var(--red)}
.legend{margin-top:8px;color:var(--muted);font-size:12px}
.dot{display:inline-block;width:10px;height:10px;border-radius:2px;margin:0 4px 0 10px;vertical-align:-1px}
.dot.ok{background:var(--green)}.dot.bad{background:var(--red)}
table{width:100%;border-collapse:collapse}
th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:middle}
th{color:var(--muted);font-weight:600;font-size:12px}
td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
table.steps td:nth-child(2){width:45%}
.table-wrap{overflow-x:auto}
.history td{white-space:nowrap}
.history td.err{white-space:normal;min-width:220px;color:var(--muted);font-size:12px}
a{color:var(--accent)}
.filters button{border:1px solid var(--line);background:var(--card);color:var(--text);padding:4px 12px;
                border-radius:16px;cursor:pointer;font:inherit;font-size:12.5px}
.filters button.active{background:var(--accent);color:var(--card);border-color:var(--accent)}
"""

JS = """
document.querySelectorAll('.filters button').forEach(b => b.addEventListener('click', () => {
  document.querySelectorAll('.filters button').forEach(x => x.classList.remove('active'));
  b.classList.add('active');
  document.querySelectorAll('table.history tbody tr').forEach(tr => {
    tr.style.display = (b.dataset.f === 'all' || tr.dataset.outcome === b.dataset.f) ? '' : 'none';
  });
}));
"""


def build_dashboard(history, latest, path):
    now = dt.datetime.now().strftime("%d %b %Y, %I:%M %p")
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ROA Test Dashboard</title><style>{CSS}</style></head>
<body>
<header>
  <h1>ROA Automation &ndash; Test Dashboard</h1>
  <div class="muted">Updated {now} &middot; {escape(config.BASE_URL)}</div>
</header>
<main>
  {kpi_cards(history, latest)}
  <div class="grid2">
    <div><h3>Latest run</h3>{latest_run_section(latest)}</div>
    <div style="display:grid;gap:16px;align-content:start"><h3 style="margin-bottom:-8px">Trends</h3>
      {trend_section(history)}{step_stats_section(history)}</div>
  </div>
  {history_table(history)}
</main>
<script>{JS}</script>
</body></html>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path
