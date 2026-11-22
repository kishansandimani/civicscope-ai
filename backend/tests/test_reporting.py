from app.services.reporting import speakable, to_markdown, brief_lines

CP = {"summary": "Scanned 2 pages.", "health_score": 80, "pages_scanned": 2, "links_checked": 5, "broken_links": 1,
      "findings": [{"type": "broken_link", "severity": "high", "description": "Link returns HTTP 404.", "url": "https://a.gov.in/x",
                    "evidence": "HTTP 404", "confidence": "high", "origin": "automated", "found_on": ["https://a.gov.in/"]}],
      "limitations": ["Only 2 pages scanned."]}
PT = {"summary": "Found 1 commitment.", "projects": [{"title": "Buses", "status": "no_update_found", "target_date": "2024-12-31",
      "status_note": "Target date has passed; check official channels.", "commitment": {"quote": "will deploy", "source": "S", "page": 5}, "timeline": [{"date": "2024-12-31", "type": "target", "label": "Target date"}]}]}


def test_speakable_reads_real_content_only():
    t = speakable("Audit", "civicprobe", CP)
    assert "Link returns HTTP 404" in t and "80 out of 100" in t and "Only 2 pages scanned" in t
    assert "Buses: no update found, target 2024-12-31" in speakable("T", "promisetrace", PT)


def test_markdown_and_briefs():
    md = to_markdown("Audit", "civicprobe", "2026-11-18", CP)
    assert md.startswith("# Audit") and "[HIGH] broken link" in md and "- Evidence: `HTTP 404`" in md
    assert "no update found" in to_markdown("T", "promisetrace", "d", PT)
    assert brief_lines("civicprobe", {"findings": []}) == []
