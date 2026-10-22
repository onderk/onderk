"""Profile updater / Profil güncelleyici.

Builds two things for the profile README:
  1. assets/contributions.svg  - the classic green contribution grid (TR/EN)
  2. the block between ACTIVITY markers in README.md - last 7 days summary
     and latest events from ALL repositories.

Privacy rule: for private repositories only counts, event type and time are
written. Repository names, branch names, commit and PR titles stay hidden.

Token: env PROFILE_TOKEN (read-only fine-grained token). Falls back to
GITHUB_TOKEN. Without a token the script stops with a clear message.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

LOGIN = "onderk"
ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
SVG_OUT = ROOT / "assets" / "contributions.svg"
TZ = timezone(timedelta(hours=3))  # Türkiye, UTC+3 all year
START, END = "<!--ACTIVITY:START-->", "<!--ACTIVITY:END-->"
MAX_ROWS = 12

LEVEL_COLORS = {
    "NONE": "#161b22",
    "FIRST_QUARTILE": "#0e4429",
    "SECOND_QUARTILE": "#006d32",
    "THIRD_QUARTILE": "#26a641",
    "FOURTH_QUARTILE": "#39d353",
}
MONTHS = ["Jan/Oca", "Feb/Şub", "Mar/Mar", "Apr/Nis", "May/May", "Jun/Haz",
          "Jul/Tem", "Aug/Ağu", "Sep/Eyl", "Oct/Eki", "Nov/Kas", "Dec/Ara"]


def token() -> str:
    tok = os.environ.get("PROFILE_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not tok:
        sys.exit("PROFILE_TOKEN is missing / PROFILE_TOKEN tanımlı değil")
    return tok


def api(url: str, body: dict | None = None):
    if not url.startswith("https://"):
        url = "https://api.github.com/" + url.lstrip("/")
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode() if body else None,
        headers={
            "Authorization": f"Bearer {token()}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "profile-updater",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


# ---------------------------------------------------------------- graph
def calendar() -> dict:
    q = """query($l:String!){user(login:$l){contributionsCollection{
      contributionCalendar{totalContributions weeks{contributionDays{
      date contributionCount contributionLevel}}}}}}"""
    cal = api("graphql", {"query": q, "variables": {"l": LOGIN}})
    return cal["data"]["user"]["contributionsCollection"]["contributionCalendar"]


THEMES = {
    "dark": {"bg": "#0d1117", "border": "#30363d", "text": "#c9d1d9", "muted": "#8b949e", "tr": "#5eead4",
             "levels": LEVEL_COLORS},
    "light": {"bg": "#ffffff", "border": "#d0d7de", "text": "#1f2328", "muted": "#57606a", "tr": "#0f766e",
              "levels": {"NONE": "#ebedf0", "FIRST_QUARTILE": "#9be9a8", "SECOND_QUARTILE": "#40c463",
                         "THIRD_QUARTILE": "#30a14e", "FOURTH_QUARTILE": "#216e39"}},
}
SIZES = {  # desktop: full year, phone: last 22 weeks with bigger cells and text
    "desktop": {"weeks": None, "cell": 11, "gap": 3, "left": 46, "top": 58, "h1": 15, "h2": 12, "small": 9, "legend": 10},
    "phone": {"weeks": 22, "cell": 20, "gap": 4, "left": 62, "top": 92, "h1": 21, "h2": 16, "small": 13, "legend": 14},
}


def contribution_svg(cal: dict, theme: str = "dark", size: str = "desktop") -> str:
    t, z = THEMES[theme], SIZES[size]
    weeks, total = cal["weeks"], cal["totalContributions"]
    if z["weeks"]:
        weeks = weeks[-z["weeks"]:]
    cell, gap, left, top = z["cell"], z["gap"], z["left"], z["top"]
    step = cell + gap
    width = left + len(weeks) * step + 20
    height = top + 7 * step + 3 * z["legend"] + 10
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" '
        f'aria-label="{total} contributions in the last year / son bir yılda katkı">',
        f'<rect width="{width}" height="{height}" rx="10" fill="{t["bg"]}" stroke="{t["border"]}"/>',
        f'<g font-family="Segoe UI,Helvetica,Arial,sans-serif" fill="{t["text"]}">',
        f'<text x="{left}" y="{z["h1"] + 12}" font-size="{z["h1"]}" font-weight="600">'
        f'{total:,} contributions in the last year</text>',
        f'<text x="{left}" y="{z["h1"] + z["h2"] + 20}" font-size="{z["h2"]}" fill="{t["tr"]}">'
        f'Son bir yılda {total:,} katkı (gizli işler dahil, içerik gösterilmez)</text>',
    ]
    for row, lab in ((1, "Mon/Pzt"), (3, "Wed/Çar"), (5, "Fri/Cum")):
        y = top + row * step + cell - 2
        out.append(f'<text x="4" y="{y}" font-size="{z["small"]}" fill="{t["muted"]}">{lab}</text>')
    last_month, last_i = None, -9
    for i, w in enumerate(weeks):
        x = left + i * step
        m = int(w["contributionDays"][-1]["date"][5:7])
        if m != last_month:
            last_month = m
            first_partial = i == 0 and len(weeks) > 2 and int(weeks[2]["contributionDays"][-1]["date"][5:7]) != m
            if not first_partial and i - last_i >= 3 and i < len(weeks) - 2:  # keep labels apart
                out.append(f'<text x="{x}" y="{top - 6}" font-size="{z["small"]}" fill="{t["muted"]}">{MONTHS[m - 1]}</text>')
                last_i = i
        for d in w["contributionDays"]:
            wd = (datetime.fromisoformat(d["date"]).weekday() + 1) % 7  # Sunday=0
            color = t["levels"].get(d["contributionLevel"], t["levels"]["NONE"])
            out.append(
                f'<rect x="{x}" y="{top + wd * step}" width="{cell}" height="{cell}" rx="2" fill="{color}">'
                f'<title>{d["date"]}: {int(d["contributionCount"])}</title></rect>'
            )
    ly = top + 7 * step + z["legend"]
    lx = width - 20 - 5 * step - 5 * z["legend"]
    out.append(f'<text x="{lx - 4 * z["legend"] - 6}" y="{ly + cell - 2}" font-size="{z["legend"]}" fill="{t["muted"]}">Less/Az</text>')
    for k, c in enumerate(t["levels"].values()):
        out.append(f'<rect x="{lx + k * step}" y="{ly}" width="{cell}" height="{cell}" rx="2" fill="{c}"/>')
    out.append(f'<text x="{lx + 5 * step + 4}" y="{ly + cell - 2}" font-size="{z["legend"]}" fill="{t["muted"]}">More/Çok</text>')
    out.append("</g></svg>")
    return "\n".join(out)


# ---------------------------------------------------------------- events
def safe(text: str, limit: int = 80) -> str:
    """Neutralise text that comes from outside (PR titles, branch names).

    Anyone can name a branch or PR; never let that text become Markdown or
    HTML on the profile (links, images, table breaks). Keep letters, digits
    and a small set of punctuation, then cut to a fixed length.
    """
    allowed = set(" .,:;_-#/()+")
    out = "".join(ch if (ch.isalnum() or ch in allowed) else " " for ch in str(text))
    out = " ".join(out.split())
    # GitHub turns bare addresses into links; break them
    out = out.replace("://", ": ").replace("www.", "www ")
    return out[:limit] + ("…" if len(out) > limit else "")


def commit_count(repo: str, before: str, head: str) -> int | None:
    try:
        return api(f"repos/{repo}/compare/{before}...{head}")["total_commits"]
    except Exception:
        return None


def describe(ev: dict) -> tuple[str, str] | None:
    """Return (event label, detail) or None to skip. Detail is empty for private."""
    t, p, public = ev["type"], ev["payload"], ev.get("public", False)
    repo = ev["repo"]["name"]
    if t == "PushEvent":
        n = commit_count(repo, p.get("before", ""), p.get("head", ""))
        label = f"⬆️ Push · {n} commit" if n else "⬆️ Push"
        branch = p.get("ref", "").removeprefix("refs/heads/")
        return label, (safe(branch, 40) if public else "")
    if t == "PullRequestEvent":
        act = p.get("action")
        names = {"merged": "🟣 PR merged / birleştirildi", "opened": "🟢 PR opened / açıldı",
                 "closed": "⚪ PR closed / kapatıldı", "reopened": "🟢 PR reopened / yeniden açıldı"}
        if act not in names:
            return None
        if not public:  # private: no number, no title
            return names[act], ""
        detail = f"#{int(p.get('number') or 0)}"
        try:
            detail += " " + safe(api(f"repos/{repo}/pulls/{int(p['number'])}")["title"])
        except Exception:
            pass
        return names[act], detail
    if t == "CreateEvent":
        kind = p.get("ref_type")
        if kind == "repository":
            return "✨ Repository created / Depo açıldı", ""
        if kind == "branch":
            return "🌿 Branch created / Dal açıldı", (safe(p.get("ref", ""), 40) if public else "")
        if kind == "tag":
            return "🏷️ Tag / Etiket", (safe(p.get("ref", ""), 40) if public else "")
        return None
    if t == "ReleaseEvent":
        return "🚀 Release / Sürüm", (safe(p.get("release", {}).get("name") or "") if public else "")
    if t in ("IssuesEvent", "IssueCommentEvent"):
        return ("💬 Comment / Yorum" if t == "IssueCommentEvent" else "📝 Issue / Konu"), ""
    return None


def activity_block(cal: dict) -> str:
    events = []
    for page in (1, 2, 3):
        batch = api(f"users/{LOGIN}/events?per_page=100&page={page}")
        events += batch
        if len(batch) < 100:
            break

    per_day = {d["date"]: d["contributionCount"]
               for w in cal["weeks"] for d in w["contributionDays"]}
    stamp_of = lambda ev: datetime.fromisoformat(ev["created_at"].replace("Z", "+00:00")).astimezone(TZ)
    events.sort(key=stamp_of, reverse=True)
    oldest = stamp_of(events[-1]).date() if events else None

    # last 7 days summary (counts only, safe for private work)
    today = datetime.now(TZ).date()
    days = {today - timedelta(days=i): defaultdict(int) for i in range(7)}
    repos_per_day = defaultdict(set)
    for ev in events:
        d = datetime.fromisoformat(ev["created_at"].replace("Z", "+00:00")).astimezone(TZ).date()
        if d not in days:
            continue
        repos_per_day[d].add(ev["repo"]["name"])
        if ev["type"] == "PushEvent":
            days[d]["push"] += 1
        elif ev["type"] == "PullRequestEvent":
            days[d][ev["payload"].get("action", "")] += 1
        elif ev["type"] == "CreateEvent" and ev["payload"].get("ref_type") == "repository":
            days[d]["repo"] += 1

    lines = [
        "| Day / Gün | Contributions / Katkı | Active repos / Aktif depo | Pushes / Gönderim | PRs opened / Açılan PR | PRs merged / Birleşen PR | New repos / Yeni depo |",
        "|:--|:-:|:-:|:-:|:-:|:-:|:-:|",
    ]
    for d in sorted(days, reverse=True):
        c = days[d]
        total = per_day.get(d.isoformat(), 0)
        if oldest is None or d < oldest:  # outside the event window: unknown, not zero
            lines.append(f"| {d:%d.%m.%Y} | {total} | — | — | — | — | — |")
        else:
            lines.append(f"| {d:%d.%m.%Y} | {total} | {len(repos_per_day[d])} | {c['push']} | "
                         f"{c['opened']} | {c['merged']} | {c['repo']} |")

    rows = []
    for ev in events:
        desc = describe(ev)
        if not desc:
            continue
        when = datetime.fromisoformat(ev["created_at"].replace("Z", "+00:00")).astimezone(TZ)
        if ev.get("public"):
            full = safe(ev["repo"]["name"], 100).replace(" ", "")
            proj = f"[{full.split('/', 1)[-1]}](https://github.com/{full})"
        else:
            proj = "🔒 Private / Gizli"
        rows.append(f"| {when:%d.%m.%Y %H:%M} | {proj} | {desc[0]} | {desc[1]} |")
        if len(rows) >= MAX_ROWS:
            break

    stamp = datetime.now(TZ).strftime("%d.%m.%Y %H:%M")
    return "\n".join([
        START,
        "",
        "**Last 7 days / Son 7 gün**",
        "",
        *lines,
        "",
        "<sub>— = older than the event window GitHub keeps / GitHub'ın olay kaydı süresinden eski</sub>",
        "",
        "**Latest events / Son hareketler**",
        "",
        "| Time / Zaman (TRT) | Project / Proje | Event / Olay | Detail / Ayrıntı |",
        "|:--|:--|:--|:--|",
        *rows,
        "",
        f"<sub>Updated automatically / Otomatik güncellendi: {stamp} TRT · "
        "private work shows counts only / gizli işlerde yalnız sayılar gösterilir</sub>",
        "",
        END,
    ])


def main() -> None:
    """--graph: only the green graph (GitHub Actions, narrow token).
    --activity: only the README activity table (owner's computer: needs a token that sees private events).
    No option: both."""
    args = set(sys.argv[1:])
    do_graph = not args or "--graph" in args
    do_activity = not args or "--activity" in args
    cal = calendar()
    if do_graph:
        for theme in ("dark", "light"):
            for size in ("desktop", "phone"):
                name = "contributions" + ("_m" if size == "phone" else "") + ("_light" if theme == "light" else "")
                (SVG_OUT.parent / f"{name}.svg").write_text(contribution_svg(cal, theme, size), encoding="utf-8")
        print("ok: contributions (4 variants)")
    if not do_activity:
        return
    text = README.read_text(encoding="utf-8")
    if START not in text or END not in text:
        sys.exit("ACTIVITY markers not found in README / README'de işaretler yok")
    head, rest = text.split(START, 1)
    tail = rest.split(END, 1)[1]
    README.write_text(head + activity_block(cal) + tail, encoding="utf-8", newline="\n")
    print("ok: README activity block")


if __name__ == "__main__":
    main()
