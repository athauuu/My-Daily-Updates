"""
Athau's Daily Dashboard Generator
Fetches tasks from Notion and builds index.html for GitHub Pages.
"""

import os
import json
import requests
from datetime import date, datetime

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
DB_ID = "246bb0f1-6f61-8120-8245-def6cd522296"

KNOWN_PROJECTS = {
    "307bb0f1-6f61-80c4-ac72-c9d3f03d8d1c": "FPCI UB",
    "34fbb0f1-6f61-8019-abe3-d0121ad94e01": "PRODIADBIS",
}

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}


def query_activities():
    url = f"https://api.notion.com/v1/databases/{DB_ID}/query"
    payload = {
        "filter": {
            "property": "Status",
            "status": {"does_not_equal": "Done"}
        },
        "sorts": [{"property": "Deadline", "direction": "ascending"}],
        "page_size": 100,
    }
    results = []
    while True:
        r = requests.post(url, headers=HEADERS, json=payload)
        r.raise_for_status()
        data = r.json()
        results.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        payload["start_cursor"] = data["next_cursor"]
    return results


def get_project_name(relation_list):
    for item in relation_list:
        pid = item["id"]
        if pid in KNOWN_PROJECTS:
            return KNOWN_PROJECTS[pid]
    return None


def parse_task(page):
    props = page["properties"]

    title_items = props.get("Assignment Name", {}).get("title", [])
    name = "".join(t["plain_text"] for t in title_items) or "Untitled"

    deadline_prop = props.get("Deadline", {}).get("date")
    deadline = deadline_prop["start"] if deadline_prop else None

    project = None
    for field in ["My projects", "Courses", "My Comps", "My Online Courses"]:
        relation = props.get(field, {}).get("relation", [])
        if relation:
            project = get_project_name(relation) or field
            break

    loc_items = props.get("Location", {}).get("rich_text", [])
    location = "".join(t["plain_text"] for t in loc_items) or None

    return {"name": name, "deadline": deadline, "project": project, "location": location}


def categorize(tasks):
    today = date.today()
    overdue, today_tasks, upcoming, no_date = [], [], [], []
    for t in tasks:
        d = t["deadline"]
        if not d:
            no_date.append(t)
            continue
        task_date = datetime.fromisoformat(d[:10]).date()
        if task_date < today:
            overdue.append(t)
        elif task_date == today:
            today_tasks.append(t)
        else:
            upcoming.append(t)
    return overdue, today_tasks, upcoming, no_date


def fmt_date(d):
    if not d:
        return ""
    return datetime.fromisoformat(d[:10]).strftime("%b %d")


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def task_html(t, kind):
    icon = {"overdue": "⚠️", "today": "📌", "upcoming": "📅"}.get(kind, "📋")
    meta = ""
    if t.get("project"):
        meta += f'<span>📁 {esc(t["project"])}</span>'
    if t.get("location"):
        meta += f'<span>📍 {esc(t["location"])}</span>'
    meta_html = f'<div class="task-meta">{meta}</div>' if meta else ""
    dl = f'<span class="task-deadline">{fmt_date(t["deadline"])}</span>' if t["deadline"] else ""
    return f"""
        <li class="task-item">
          <span class="task-icon">{icon}</span>
          <div class="task-body">
            <div class="task-name" title="{esc(t['name'])}">{esc(t['name'])}</div>
            {meta_html}
          </div>
          {dl}
        </li>"""


def section_html(title, kind, tasks, icon):
    items = "".join(task_html(t, kind) for t in tasks) if tasks else ""
    body = f'<ul class="task-list">{items}</ul>' if tasks else f'<div class="empty-state">✓ No {title.lower()}</div>'
    return f"""
      <div class="section {kind}">
        <div class="section-header">
          <div class="section-title"><span class="dot"></span>{icon} {title}</div>
          <span class="badge">{len(tasks)}</span>
        </div>
        {body}
      </div>"""


def build_html(overdue, today_tasks, upcoming, last_updated):
    stats = f"""
<div class="stats">
  <div class="stat-card overdue"><div class="stat-label">Overdue</div><div class="stat-value">{len(overdue)}</div></div>
  <div class="stat-card today"><div class="stat-label">Due Today</div><div class="stat-value">{len(today_tasks)}</div></div>
  <div class="stat-card upcoming"><div class="stat-label">Upcoming</div><div class="stat-value">{len(upcoming)}</div></div>
</div>"""

    sections = (
        section_html("Overdue", "overdue", overdue, "🔴") +
        section_html("Due Today", "today", today_tasks, "🟡") +
        section_html("Upcoming", "upcoming", upcoming, "🟢")
    )

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Athau's Daily Updates</title>
  <style>
    :root[data-theme="dark"] {{
      --bg:#0f1117;--surface:#1a1d27;--surface2:#22263a;--border:#2e3250;
      --text:#e8eaf6;--text-muted:#7b82a8;--accent:#7c6ff7;
      --overdue:#f87171;--overdue-bg:rgba(248,113,113,.08);
      --today:#fbbf24;--today-bg:rgba(251,191,36,.08);
      --upcoming:#34d399;--upcoming-bg:rgba(52,211,153,.08);
      --toggle-bg:#22263a;--toggle-knob:#7c6ff7;--shadow:0 4px 24px rgba(0,0,0,.4);
    }}
    :root[data-theme="light"] {{
      --bg:#f0f2f9;--surface:#fff;--surface2:#f5f6fb;--border:#dde0f0;
      --text:#1a1d2e;--text-muted:#7b82a8;--accent:#5b52e8;
      --overdue:#dc2626;--overdue-bg:rgba(220,38,38,.06);
      --today:#d97706;--today-bg:rgba(217,119,6,.06);
      --upcoming:#059669;--upcoming-bg:rgba(5,150,105,.06);
      --toggle-bg:#dde0f0;--toggle-knob:#5b52e8;--shadow:0 4px 24px rgba(0,0,0,.08);
    }}
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;padding:24px 16px 48px;transition:background .3s,color .3s}}
    header{{max-width:860px;margin:0 auto 32px;display:flex;align-items:center;justify-content:space-between}}
    .header-left h1{{font-size:1.5rem;font-weight:700;letter-spacing:-.02em}}
    .subtitle{{font-size:.8rem;color:var(--text-muted);margin-top:2px}}
    .toggle-wrap{{display:flex;align-items:center;gap:8px}}
    .toggle-label{{font-size:.78rem;color:var(--text-muted)}}
    .toggle{{position:relative;width:44px;height:24px;cursor:pointer}}
    .toggle input{{display:none}}
    .toggle-track{{width:100%;height:100%;background:var(--toggle-bg);border-radius:99px;border:1px solid var(--border);transition:background .3s}}
    .toggle-knob{{position:absolute;top:3px;left:3px;width:18px;height:18px;background:var(--toggle-knob);border-radius:50%;transition:transform .25s}}
    [data-theme="light"] .toggle-knob{{transform:translateX(20px)}}
    .stats{{max-width:860px;margin:0 auto 28px;display:flex;gap:12px}}
    .stat-card{{flex:1;background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:14px 18px;box-shadow:var(--shadow)}}
    .stat-label{{font-size:.72rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:.06em}}
    .stat-value{{font-size:1.7rem;font-weight:700;line-height:1.1;margin-top:4px}}
    .stat-card.overdue .stat-value{{color:var(--overdue)}}
    .stat-card.today .stat-value{{color:var(--today)}}
    .stat-card.upcoming .stat-value{{color:var(--upcoming)}}
    .sections{{max-width:860px;margin:0 auto;display:flex;flex-direction:column;gap:20px}}
    .section{{background:var(--surface);border:1px solid var(--border);border-radius:16px;overflow:hidden;box-shadow:var(--shadow)}}
    .section-header{{display:flex;align-items:center;justify-content:space-between;padding:16px 20px;border-bottom:1px solid var(--border)}}
    .section-title{{display:flex;align-items:center;gap:10px;font-weight:600;font-size:.9rem}}
    .dot{{width:10px;height:10px;border-radius:50%}}
    .section.overdue .dot{{background:var(--overdue);box-shadow:0 0 6px var(--overdue)}}
    .section.today .dot{{background:var(--today);box-shadow:0 0 6px var(--today)}}
    .section.upcoming .dot{{background:var(--upcoming);box-shadow:0 0 6px var(--upcoming)}}
    .badge{{font-size:.72rem;font-weight:600;padding:2px 9px;border-radius:99px}}
    .section.overdue .badge{{background:var(--overdue-bg);color:var(--overdue)}}
    .section.today .badge{{background:var(--today-bg);color:var(--today)}}
    .section.upcoming .badge{{background:var(--upcoming-bg);color:var(--upcoming)}}
    .task-list{{list-style:none}}
    .task-item{{display:flex;align-items:flex-start;gap:14px;padding:14px 20px;border-bottom:1px solid var(--border);transition:background .15s}}
    .task-item:last-child{{border-bottom:none}}
    .task-item:hover{{background:var(--surface2)}}
    .task-icon{{margin-top:2px;font-size:.9rem;flex-shrink:0}}
    .task-body{{flex:1;min-width:0}}
    .task-name{{font-size:.88rem;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
    .task-meta{{display:flex;gap:10px;margin-top:4px;flex-wrap:wrap}}
    .task-meta span{{font-size:.72rem;color:var(--text-muted)}}
    .task-deadline{{font-size:.72rem;font-weight:600;padding:2px 8px;border-radius:6px;flex-shrink:0;align-self:center}}
    .section.overdue .task-deadline{{background:var(--overdue-bg);color:var(--overdue)}}
    .section.today .task-deadline{{background:var(--today-bg);color:var(--today)}}
    .section.upcoming .task-deadline{{background:var(--upcoming-bg);color:var(--upcoming)}}
    .empty-state{{padding:28px 20px;text-align:center;color:var(--text-muted);font-size:.85rem}}
    footer{{max-width:860px;margin:32px auto 0;text-align:center;font-size:.74rem;color:var(--text-muted)}}
    footer a{{color:var(--accent);text-decoration:none}}
    @media(max-width:600px){{.stats{{flex-direction:column;gap:8px}}}}
  </style>
</head>
<body>
<header>
  <div class="header-left">
    <h1>Athau's Daily Updates</h1>
    <div class="subtitle">Last updated: {last_updated}</div>
  </div>
  <div class="toggle-wrap">
    <span class="toggle-label" id="mode-label">Dark</span>
    <label class="toggle">
      <input type="checkbox" id="theme-toggle" onchange="toggleTheme()" />
      <div class="toggle-track"></div>
      <div class="toggle-knob"></div>
    </label>
  </div>
</header>
{stats}
<div class="sections">
  {sections}
</div>
<footer>Synced from <a href="https://notion.so" target="_blank">Notion</a> · Auto-updated daily at 4:00 AM WIB</footer>
<script>
  function toggleTheme(){{
    const html=document.documentElement;
    const isDark=html.getAttribute('data-theme')==='dark';
    html.setAttribute('data-theme',isDark?'light':'dark');
    document.getElementById('mode-label').textContent=isDark?'Light':'Dark';
    localStorage.setItem('theme',isDark?'light':'dark');
  }}
  const saved=localStorage.getItem('theme')||'dark';
  document.documentElement.setAttribute('data-theme',saved);
  document.getElementById('mode-label').textContent=saved==='dark'?'Dark':'Light';
  if(saved==='light')document.getElementById('theme-toggle').checked=true;
</script>
</body>
</html>"""


def main():
    print("Fetching Notion activities...")
    pages = query_activities()
    tasks = [parse_task(p) for p in pages]
    overdue, today_tasks, upcoming, no_date = categorize(tasks)
    upcoming += no_date  # tasks with no deadline go to upcoming

    last_updated = datetime.utcnow().strftime("%b %d, %Y at %I:%M %p UTC")
    html = build_html(overdue, today_tasks, upcoming, last_updated)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Done — {len(overdue)} overdue · {len(today_tasks)} today · {len(upcoming)} upcoming")


if __name__ == "__main__":
    main()
