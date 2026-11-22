from io import BytesIO
from pypdf import PdfWriter
from pypdf.generic import NameObject, TextStringObject, DictionaryObject, BooleanObject

from app.services.accessshadow import analyze_html, analyze_pdf, summarize, script_share

BAD = """<html><head><meta name="viewport" content="width=device-width, user-scalable=no"></head><body>
<img src="/a.png"><img src="/b.png" alt=""><img src="/c.png" alt="Map of districts">
<h2>Services</h2><h4>Pensions</h4>
<form><input type="text" placeholder="Name"><input id="e" type="text"><label for="e">Email</label>
<input type="hidden" name="t"><select name="s"></select><button></button></form>
<a href="/x">click here</a><a href="/y"></a><a href="/z"><img src="i.png" alt="Home"></a>
<div onclick="go()">Open</div><div tabindex="3">x</div>
<iframe src="/f"></iframe>
<table><tr><td>a</td></tr><tr><td>b</td></tr></table>
<p>ಕರ್ನಾಟಕ ಸರ್ಕಾರದ ಎಲ್ಲಾ ಯೋಜನೆಗಳ ಮಾಹಿತಿ ಇಲ್ಲಿ ಲಭ್ಯವಿದೆ ಮತ್ತು ನಾಗರಿಕರಿಗೆ ಸಹಾಯ ಮಾಡುತ್ತದೆ</p>
</body></html>"""

GOOD = """<html lang="en"><head><title>Pensions</title><meta name="viewport" content="width=device-width, initial-scale=1"></head><body>
<a href="#main">Skip to main content</a><main id="main"><h1>Pensions</h1><h2>Eligibility</h2>
<img src="a.png" alt="Pension office"><label for="n">Name</label><input id="n" type="text">
<a href="/apply">Apply for the old age pension</a><button>Submit</button></main></body></html>"""


def rules(res):
    return {f["rule"] for f in res["automated_findings"]}


def test_bad_page_flags_expected_rules():
    r = analyze_html(BAD, "https://x.gov.in/")
    got = rules(r)
    for rule in ["missing_lang", "missing_title", "img_missing_alt", "no_h1", "skipped_heading_level", "form_control_no_label",
                 "button_no_name", "link_no_name", "generic_link_text", "click_not_keyboard_accessible", "positive_tabindex",
                 "frame_no_title", "table_no_headers", "zoom_disabled", "no_skip_link"]:
        assert rule in got, rule
    by = {f["rule"]: f for f in r["automated_findings"]}
    assert by["img_missing_alt"]["count"] == 1               # only the img with NO alt attribute
    assert by["form_control_no_label"]["count"] == 2         # placeholder-only input + unlabelled select; labelled/hidden inputs are fine
    assert "link_no_name" in by and by["link_no_name"]["count"] == 1   # linked image with alt is fine
    assert any(m["check"].startswith("Confirm empty-alt") for m in r["manual_review_items"])
    sh = r["stats"]["script_share"]; assert sh["Kannada"] > 0.5 and sh["Latin"] > 0.3   # mixed page


def test_good_page_has_no_automated_findings_but_still_manual_items():
    r = summarize(analyze_html(GOOD, "https://x.gov.in/"))
    assert r["automated_findings"] == [], rules(r)
    assert len(r["manual_review_items"]) >= 4
    assert "does not mean the content is fully accessible" in r["summary"]


def test_language_mismatch():
    html = '<html lang="en"><head><title>t</title></head><body><h1>ಶೀರ್ಷಿಕೆ</h1><p>ಇದು ಕನ್ನಡ ಪಠ್ಯ ಆಗಿದೆ ಮತ್ತು ಇಲ್ಲಿ ಹೆಚ್ಚಿನ ಮಾಹಿತಿ ಇದೆ</p></body></html>'
    r = analyze_html(html, "u")
    assert [x["rule"] for x in r["language_findings"]] == ["declared_language_mismatch"]


def _pdf(lang=False, title=False):
    w = PdfWriter(); w.add_blank_page(300, 300)
    if lang:
        w._root_object[NameObject("/Lang")] = TextStringObject("en-IN")
    if title:
        w.add_metadata({"/Title": "Scheme circular"})
    b = BytesIO(); w.write(b); return b.getvalue()


def test_pdf_checks():
    r = analyze_pdf(_pdf(), "scan.pdf")
    got = rules(r)
    assert {"pdf_untagged", "pdf_no_language", "pdf_no_title", "pdf_no_text_layer"} <= got
    assert r["stats"]["tagged"] is False and r["stats"]["pages_with_text"] == 0
    r2 = analyze_pdf(_pdf(lang=True, title=True), "x.pdf")
    got2 = rules(r2)
    assert "pdf_no_language" not in got2 and "pdf_no_title" not in got2 and "pdf_title_not_displayed" in got2
    assert all(m["why_manual"] for m in r2["manual_review_items"])


def test_script_share():
    s = script_share("Hello world ನಮಸ್ಕಾರ")
    assert set(s) == {"Latin", "Kannada"} and abs(sum(s.values()) - 1) < 0.01
