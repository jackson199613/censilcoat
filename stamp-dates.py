#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
给每个 .html 标注真实更新日期，数据源是 git 提交时间（不是"跑脚本的今天"）。

两处标注：
  1) JSON-LD @graph 里加/更新 WebPage 节点的 dateModified —— 给 Google / AI 读
  2) footer 版权行旁加可见 <time> —— 给人读

防自循环：git log 排除本脚本自己的 stamp 提交。否则 stamp 提交会成为
文件的"最后修改"，下次跑又要改，无限循环。
"""
import os, re, json, subprocess, sys

SITE = "https://censilcoat.com"
STAMP_MSG = "chore: stamp last-updated dates"
EXCLUDE_DIRS = {".git", ".github", "node_modules"}
EXCLUDE = {"404.html", "thanks.html", "thank-you.html"}
MON = {1:'January',2:'February',3:'March',4:'April',5:'May',6:'June',
       7:'July',8:'August',9:'September',10:'October',11:'November',12:'December'}

def git_lastmod(path):
    """最后一次【非 stamp】提交的日期。排除自己的提交是防循环的关键。"""
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cI",
             "--invert-grep", f"--grep={STAMP_MSG}", "--", path],
            capture_output=True, text=True, timeout=20).stdout.strip()
        return out[:10] if out else None
    except Exception:
        return None

def human(iso):
    y, m, d = iso.split("-")
    return f"{MON[int(m)]} {int(d)}, {y}"

def collect():
    out = []
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
        for f in files:
            if not f.endswith(".html"):
                continue
            rel = os.path.relpath(os.path.join(root, f), ".").replace(os.sep, "/")
            if rel in EXCLUDE or f in EXCLUDE:
                continue
            out.append(rel)
    return sorted(out)

def stamp_schema(s, url, iso):
    """在 @graph 里加/更新 WebPage.dateModified。找不到 JSON-LD 就跳过。"""
    m = re.search(r'(<script[^>]*type="application/ld\+json"[^>]*>)(.*?)(</script>)', s, re.S)
    if not m:
        return s, False
    try:
        d = json.loads(m.group(2))
    except Exception:
        return s, False
    if "@graph" not in d:
        return s, False
    g = d["@graph"]
    wp = next((x for x in g if x.get("@type") == "WebPage"), None)
    if wp is None:
        wp = {"@type": "WebPage", "@id": f"{url}#webpage", "url": url,
              "isPartOf": {"@id": f"{SITE}/#website"}, "dateModified": iso}
        # 放在 WebSite 之后，保持可读顺序
        idx = next((i for i, x in enumerate(g) if x.get("@type") == "WebSite"), len(g) - 1)
        g.insert(idx + 1, wp)
    else:
        if wp.get("dateModified") == iso:
            return s, False
        wp["dateModified"] = iso
    body = m.group(1) + "\n" + json.dumps(d, ensure_ascii=False, indent=2) + "\n" + m.group(3)
    return s[:m.start()] + body + s[m.end():], True

VIS_RE = re.compile(r'<p class="mt-0 text-white/50">(?:Last updated|C\u1eadp nh\u1eadt l\u1ea7n cu\u1ed1i) '
                    r'<time datetime="[^"]*">[^<]*</time></p>\s*')

# footer 商标行是逐语言写的，锚点也必须逐语言。少一个 vi 页就没有可见日期。
ANCHORS = [
    ('<p>Grade codes such as OK 412', 'Last updated'),
    ('<p>Các mã như OK 412',  'Cập nhật lần cuối'),
]

def stamp_visible(s, iso, label):
    """footer 版权行下加可见日期。先清掉旧的再插新的，保证幂等。"""
    s = VIS_RE.sub("", s)
    for anchor, word in ANCHORS:
        if anchor in s:
            new = (f'<p class="mt-0 text-white/50">{word} '
                   f'<time datetime="{iso}">{human(iso)}</time></p>\n      ' + anchor)
            return s.replace(anchor, new, 1), True
    print(f"  WARNING: no footer anchor matched, no visible date: {label}")
    return s, False

def main():
    changed = []
    for rel in collect():
        iso = git_lastmod(rel)
        if not iso:
            print(f"  skip (no git history): {rel}")
            continue
        url = f"{SITE}/{rel}"
        s0 = open(rel, encoding="utf-8").read()
        s, a = stamp_schema(s0, url, iso)
        s, b = stamp_visible(s, iso, rel)
        if s != s0:
            open(rel, "w", encoding="utf-8").write(s)
            changed.append(f"{rel} → {iso}")
    print(f"stamped {len(changed)} file(s)")
    for c in changed:
        print("  ", c)
    if not collect():
        print("ERROR: no html found", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
