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
        cases = r.get("testcases") or []
        tcs = f"{tc_counts(cases)['PASSED']}/{len(cases)}" if cases else ""
        rows += f"""<tr data-outcome="{r['outcome']}">
              <td>{escape(r['date'])}</td><td>{escape(r['test'])}</td>
              <td>{escape(user.get('full_name', ''))}</td><td>{escape(user.get('email', ''))}</td>
              <td>{badge(r['outcome'])}</td><td class="num">{tcs}</td><td class="num">{mins(r['duration'])}</td>
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
        <th>Date</th><th>Test case</th><th>User</th><th>Email</th><th>Result</th><th>TCs passed</th><th>Time</th>
        <th>Failed step</th><th>Error</th><th>Screenshot</th></tr></thead>
        <tbody>{rows}</tbody></table></div></div>"""


# ---------- test cases (from the test case sheet) ----------
STATUSES = ["PASSED", "FAILED", "BLOCKED", "SKIPPED"]


def tc_badge(status):
    return f'<span class="badge tc-{status.lower().replace(" ", "")}">{escape(status)}</span>'


def tc_counts(cases):
    counts = {s: 0 for s in STATUSES}
    for c in cases:
        counts[c["status"]] = counts.get(c["status"], 0) + 1
    return counts


def subcase_list(case):
    """Every step (action) and check of one test case, in the order they ran."""
    items = case.get("checks") or []
    if not items:
        why = "Not executed" if case["status"] in ("BLOCKED", "NOT RUN") else "No sub-cases recorded"
        return f'<div class="muted">{why}</div>'
    icons = {"PASSED": "&#10004;", "FAILED": "&#10008;", "INFO": "&#8505;", "SKIPPED": "&#8212;"}
    kinds = {"step": "Step", "check": "Check", "info": "Info"}
    lis = ""
    for i, k in enumerate(items, 1):
        detail = f'<span class="sub-detail">{escape(k["detail"])}</span>' if k.get("detail") else ""
        secs = f'<span class="muted">{k["seconds"]}s</span>' if k.get("kind") == "step" else ""
        lis += (f'<li class="sc sc-{k["status"].lower()}"><span class="sc-icon">{icons.get(k["status"], "")}</span>'
                f'<span class="sc-kind">{kinds.get(k["kind"], k["kind"])}</span>'
                f'<span class="sc-name">{i}. {escape(k["name"])} {detail}</span>{secs}</li>')
    return f'<ul class="subcases">{lis}</ul>'


def testcase_section(latest):
    blocks = []
    for r in latest:
        cases = r.get("testcases") or []
        if not cases:
            continue
        counts = tc_counts(cases)
        total = len(cases)
        executed = total - counts["SKIPPED"]
        rate = f"{counts['PASSED'] / executed * 100:.0f}%" if executed else "-"
        cards = "".join(
            f'<button class="tc-card" data-s="{s}"><span class="label">{s.title()}</span>'
            f'<span class="value tc-{s.lower()}-text">{counts[s]}</span></button>' for s in STATUSES)
        legend = "".join(f'<span class="dot tc-{s.lower()}-bg"></span>{s.title()} ' for s in STATUSES)

        # per stage: stacked bar of statuses
        stages = {}
        for c in cases:
            stages.setdefault(c["stage"], []).append(c)
        stage_rows = ""
        for stage, items in stages.items():
            sc = tc_counts(items)
            segs = "".join(f'<span class="seg tc-{s.lower()}-bg" style="flex:{sc[s]}" title="{s}: {sc[s]}"></span>'
                           for s in STATUSES if sc[s])
            stage_rows += (f'<tr><td>{escape(stage)}</td><td><div class="stack">{segs}</div></td>'
                           f'<td class="num">{sc["PASSED"]}/{len(items)}</td></tr>')

        rows = ""
        for c in cases:
            checks = [k for k in c.get("checks", []) if k["status"] in ("PASSED", "FAILED")]
            ok = sum(1 for k in checks if k["status"] == "PASSED")
            score = f'<span class="{"tc-failed-text" if ok < len(checks) else "muted"}">{ok}/{len(checks)}</span>' \
                if checks else '<span class="muted">-</span>'
            rows += f"""<tr data-s="{c['status']}" class="tc-row">
                <td class="nowrap"><button class="toggle" aria-expanded="false" title="Show sub-cases">&#9656;</button>
                    <b>{escape(c['id'])}</b></td>
                <td class="nowrap muted">{escape(c['stage'].split(' - ')[0])}</td>
                <td><div>{escape(c['scenario'])}</div></td>
                <td class="nowrap">{escape(c['priority'])}</td>
                <td>{tc_badge(c['status'])}</td>
                <td class="num">{score}</td>
                <td class="actual">{escape(c['actual'])}</td>
                <td class="num">{c['seconds']}s</td></tr>
              <tr class="sub" data-s="{c['status']}" hidden><td></td><td colspan="7">
                <div class="expected"><b>Expected:</b> {escape(c['expected'])}</div>
                {subcase_list(c)}</td></tr>"""
        user = r.get("user") or {}
        blocks.append(f"""
        <div class="panel">
          <div class="panel-head"><b>Test cases &ndash; {escape(r['test'])}</b>
            <div class="muted">{escape(r['date'])} &middot; {escape(user.get('email', ''))} &middot;
              pass rate {rate} of executed</div></div>
          <div class="tc-tools"><button class="expand-all">Expand all</button>
            <button class="collapse-all">Collapse all</button>
            <span class="muted">{sum(len(c.get("checks", [])) for c in cases)} sub-cases (steps + checks)</span></div>
          <div class="tc-cards">{cards}<button class="tc-card active" data-s="all"><span class="label">All</span>
            <span class="value">{total}</span></button></div>
          <div class="grid-tc">
            <div><table class="steps"><thead><tr><th>Stage</th><th></th><th>Passed</th></tr></thead>
              <tbody>{stage_rows}</tbody></table>
              <div class="legend">{legend}</div></div>
            <div class="table-wrap"><table class="tc-table"><thead><tr><th>TC ID</th><th>Stage</th><th>Scenario</th>
              <th>Priority</th><th>Status</th><th>Sub-cases</th><th>Actual result</th><th>Time</th></tr></thead>
              <tbody>{rows}</tbody></table></div>
          </div>
        </div>""")
    return "".join(blocks)


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
:root{--amber:#b7791f;--amber-soft:#fdf1dc;--grey:#8a93a6;--grey-soft:#eceff4}
@media (prefers-color-scheme:dark){:root{--amber:#f0b44c;--amber-soft:#3a2d14;--grey:#9aa3b5;--grey-soft:#2a3240}}
.badge.tc-passed{background:var(--green-soft);color:var(--green)}
.badge.tc-failed{background:var(--red-soft);color:var(--red)}
.badge.tc-blocked{background:var(--amber-soft);color:var(--amber)}
.badge.tc-skipped,.badge.tc-notrun{background:var(--grey-soft);color:var(--grey)}
.tc-passed-text{color:var(--green)}.tc-failed-text{color:var(--red)}.tc-blocked-text{color:var(--amber)}
.tc-skipped-text{color:var(--grey)}
.tc-passed-bg{background:var(--green)}.tc-failed-bg{background:var(--red)}.tc-blocked-bg{background:var(--amber)}
.tc-skipped-bg{background:var(--grey)}
.tc-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:10px;margin-bottom:14px}
.tc-card{display:flex;flex-direction:column;align-items:flex-start;gap:2px;border:1px solid var(--line);
         background:var(--card);color:var(--text);border-radius:10px;padding:10px 12px;cursor:pointer;font:inherit}
.tc-card .value{font-size:24px;font-weight:700}
.tc-card.active{outline:2px solid var(--accent)}
.grid-tc{display:grid;grid-template-columns:minmax(260px,1fr) 3fr;gap:18px;align-items:start}
@media (max-width:1100px){.grid-tc{grid-template-columns:1fr}}
.stack{display:flex;height:12px;border-radius:4px;overflow:hidden;background:var(--track)}
.seg{display:block;height:100%}
.tc-table td{vertical-align:top}
.tc-table td.actual{min-width:220px;max-width:420px;font-size:12.5px;word-break:break-word}
.tc-table details{margin-top:2px}.tc-table summary{cursor:pointer;color:var(--muted);font-size:12px}
.nowrap{white-space:nowrap}
.toggle{border:0;background:none;color:var(--muted);cursor:pointer;font-size:13px;padding:0 4px 0 0;
        transition:transform .15s}
.toggle[aria-expanded="true"]{transform:rotate(90deg)}
tr.tc-row{cursor:pointer}
tr.sub td{background:var(--bg);border-bottom:1px solid var(--line);padding:8px 10px 12px}
.expected{font-size:12.5px;color:var(--muted);margin-bottom:8px}
.subcases{list-style:none;margin:0;padding:0;display:grid;gap:3px}
.sc{display:grid;grid-template-columns:18px 48px 1fr auto;gap:8px;align-items:baseline;font-size:13px;
    padding:3px 6px;border-radius:6px}
.sc-failed{background:var(--red-soft)}
.sc-icon{font-weight:700;text-align:center}
.sc-passed .sc-icon{color:var(--green)}.sc-failed .sc-icon{color:var(--red)}
.sc-info .sc-icon,.sc-skipped .sc-icon{color:var(--grey)}
.sc-kind{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.sub-detail{color:var(--red);margin-left:6px;font-size:12px}
.sc-info .sc-name{color:var(--muted)}
.tc-tools{display:flex;gap:8px;align-items:center;margin-bottom:10px;flex-wrap:wrap}
.tc-tools button{border:1px solid var(--line);background:var(--card);color:var(--text);padding:4px 12px;
                 border-radius:16px;cursor:pointer;font:inherit;font-size:12.5px}
.filters button{border:1px solid var(--line);background:var(--card);color:var(--text);padding:4px 12px;
                border-radius:16px;cursor:pointer;font:inherit;font-size:12.5px}
.filters button.active{background:var(--accent);color:var(--card);border-color:var(--accent)}
"""

JS = """
document.querySelectorAll('.tc-card').forEach(b => b.addEventListener('click', () => {
  const panel = b.closest('.panel');
  panel.querySelectorAll('.tc-card').forEach(x => x.classList.remove('active'));
  b.classList.add('active');
  panel.querySelectorAll('table.tc-table tbody tr').forEach(tr => {
    tr.style.display = (b.dataset.s === 'all' || tr.dataset.s === b.dataset.s) ? '' : 'none';
  });
}));
function setOpen(row, open) {
  row.nextElementSibling.hidden = !open;
  row.querySelector('.toggle').setAttribute('aria-expanded', open);
}
document.querySelectorAll('tr.tc-row').forEach(row => {
  row.addEventListener('click', () => setOpen(row, row.nextElementSibling.hidden));
  if (row.dataset.s === 'FAILED') setOpen(row, true);          // failed test cases start open
});
document.querySelectorAll('.expand-all, .collapse-all').forEach(b => b.addEventListener('click', () => {
  b.closest('.panel').querySelectorAll('tr.tc-row').forEach(r => setOpen(r, b.classList.contains('expand-all')));
}));
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
  {testcase_section(latest)}
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
