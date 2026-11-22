"""Turn stored report bodies into (a) text that reads well aloud, (b) Markdown, (c) short briefs for voice Q&A.
Pure functions over the JSON the modules saved; nothing here calls the network or the AI."""


def _sev(n, word):
    return f"{n} {word}" if n else ""


def brief_lines(module: str, body: dict, limit: int = 6) -> list[str]:
    out: list[str] = []
    if module == "civicprobe":
        for f in (body.get("findings") or [])[:limit]:
            out.append(f"[{f['severity']}] {f['description']} ({f['url']})")
    elif module == "infoconflict":
        for c in (body.get("conflicts") or [])[:limit]:
            vals = "; ".join(f"{x['source']}: {x['value']}" + (f" (page {x['page']})" if x.get("page") else "") for x in c["claims"])
            out.append(f"Conflict in {c['field'].replace('_', ' ')} [{c['severity']}]: {vals}")
        for a in (body.get("agreements") or [])[:3]:
            out.append(f"Sources agree on {a['field'].replace('_', ' ')}: {a['value']}")
    elif module == "accessshadow":
        for f in (body.get("automated_findings") or [])[:limit]:
            out.append(f"[{f['severity']}] {f['description']} (x{f.get('count', 1)})")
    elif module == "rulestress":
        out.append(f"Scenario: {body.get('scenario', '')}")
        out.append(f"Verdict: {body.get('verdict', '').replace('_', ' ')}. {body.get('answer', '')}")
        for c in (body.get("conditions") or [])[:limit]:
            out.append(f"Condition ({c['status'].replace('_', ' ')}): {c['condition']}")
    elif module == "promisetrace":
        for p in (body.get("projects") or [])[:limit]:
            bit = f"{p['title']}: {p['status'].replace('_', ' ')}"
            if p.get("target_date"):
                bit += f", target {p['target_date']}"
            if p.get("status_note"):
                bit += f". {p['status_note']}"
            out.append(bit)
    return out


def speakable(title: str, module: str, body: dict) -> str:
    parts = [f"Report: {title}."]
    if body.get("summary"):
        parts.append(body["summary"])
    if module == "civicprobe" and body.get("health_score") is not None:
        parts.append(f"Heuristic health score: {body['health_score']} out of 100.")
    if module == "rulestress":
        parts = [f"Report: {title}.", f"Situation: {body.get('scenario', '')}.", f"Result: {body.get('verdict', '').replace('_', ' ')}.", body.get("answer", "")]
        for m in (body.get("missing_information") or [])[:4]:
            parts.append(f"Missing information: {m}.")
    lines = brief_lines(module, body) if module != "rulestress" else []
    for i, l in enumerate(lines, 1):
        parts.append(f"Item {i}. {l}.")
    if module == "accessshadow" and body.get("manual_review_items"):
        parts.append(f"{len(body['manual_review_items'])} further checks need manual testing, such as colour contrast and a screen reader walkthrough.")
    for lim in (body.get("limitations") or [])[:2]:
        parts.append(f"Note: {lim}")
    return " ".join(p.strip() for p in parts if p and p.strip())


def to_markdown(title: str, module: str, created_at: str, body: dict) -> str:
    md = [f"# {title}", f"*Module: {module} · Generated: {created_at}*", ""]
    if body.get("summary"):
        md += [f"**Summary:** {body['summary']}", ""]
    if module == "civicprobe":
        md += [f"- Pages scanned: {body.get('pages_scanned')}", f"- Links checked: {body.get('links_checked')}",
               f"- Broken/unreachable links: {body.get('broken_links')}", f"- Heuristic health score: {body.get('health_score')}/100", "", "## Findings"]
        for f in body.get("findings", []):
            md += [f"### [{f['severity'].upper()}] {f['type'].replace('_', ' ')} ({f['origin']}, confidence: {f['confidence']})",
                   f"{f['description']}", f"- URL: {f['url']}", f"- Evidence: `{f['evidence']}`"]
            if f.get("found_on"):
                md.append("- Found on: " + ", ".join(f["found_on"]))
            md.append("")
    elif module == "infoconflict":
        md.append("## Conflicts")
        for c in body.get("conflicts", []):
            md += [f"### {c['field'].replace('_', ' ').title()} [{c['severity']}]", c["explanation"], ""]
            for x in c["claims"]:
                md.append(f"- **{x['source']}**" + (f" (page {x['page']})" if x.get("page") else "") + f": {x['value']} — “{x['evidence']}”")
            md += ["", f"_{c['resolution']}_", ""]
        md.append("## Matching information")
        for a in body.get("agreements", []):
            md.append(f"- {a['field'].replace('_', ' ')}: {a['value']}")
    elif module == "accessshadow":
        md.append("## Automated findings")
        for f in body.get("automated_findings", []):
            md += [f"- **[{f['severity']}] {f['rule']}** ×{f.get('count', 1)} — {f['description']} ({f.get('wcag', '')}). Evidence: `{f['evidence']}`"]
        md += ["", "## Needs manual testing"]
        for m in body.get("manual_review_items", []):
            md.append(f"- **{m['check']}** — {m['how_to_test']}")
    elif module == "rulestress":
        md += [f"**Scenario:** {body.get('scenario')}", f"**Verdict:** {body.get('verdict')} (confidence: {body.get('confidence')})", "", body.get("answer", ""), "", "## Conditions"]
        for c in body.get("conditions", []):
            md.append(f"- {c['condition']} — **{c['status']}** (page {c.get('page') or 'n/a'}): “{c['evidence']}”")
        md += ["", "## Ambiguities"] + [f"- {a['issue']} — “{a['evidence']}”" for a in body.get("ambiguities", [])]
    elif module == "promisetrace":
        for p in body.get("projects", []):
            md += [f"## {p['title']} — {p['status'].replace('_', ' ')}", f"Commitment: “{p['commitment']['quote']}” ({p['commitment']['source']}, page {p['commitment'].get('page') or 'n/a'})"]
            if p.get("status_note"):
                md.append(f"_{p['status_note']}_")
            md += [f"- {e['date']}: {e['type']} — {e['label']}" for e in p.get("timeline", [])] + [""]
    if body.get("limitations"):
        md += ["", "## Limitations"] + [f"- {l}" for l in body["limitations"]]
    return "\n".join(md) + "\n"
