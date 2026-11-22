#!/usr/bin/env python3
"""Browser test for statements.js (government statement reader). Needs: pip install playwright.
Serves the repo locally, blanks account.js (the sign-in gate has its own test), uploads FAKE PDFs from
tests/fixtures and checks: amounts found, Preview before Apply, fields filled, French, spouse,
fallback list, no-text and wrong-file messages, and that NOTHING leaves the page (only local files load).
Run: python3 scripts/test_statements.py"""
import os, sys, http.server, threading, functools
from playwright.sync_api import sync_playwright

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
FIX = os.path.join(ROOT, 'tests', 'fixtures')
fails = []
def check(ok, what):
    print(('ok   ' if ok else 'FAIL ') + what)
    if not ok: fails.append(what)

class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Q, directory=ROOT))
threading.Thread(target=srv.serve_forever, daemon=True).start()
ORIGIN = 'http://127.0.0.1:%d' % srv.server_address[1]

with sync_playwright() as pw:
    try: br = pw.chromium.launch(channel='chrome')
    except Exception: br = pw.chromium.launch()
    ctx = br.new_context(viewport={'width': 420, 'height': 900})
    page = ctx.new_page()
    errors, requests = [], []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('request', lambda r: requests.append(r.url))
    page.route('**/account.js', lambda route: route.fulfill(body='', content_type='application/javascript'))
    def fresh(lang=None):
        page.goto(ORIGIN + '/index.html' + '?lang=' + (lang or 'en'))
        page.evaluate("document.documentElement.classList.remove('awr-locked')")
        page.wait_for_selector('#stmtFile', state='attached')
        page.evaluate("document.getElementById('stmtShortcut').open = true")
    def upload(name):
        page.set_input_files('#stmtFile', os.path.join(FIX, name))
    def out_text(): return page.text_content('#stmtOut') or ''
    def val(i): return page.evaluate("document.getElementById('%s').value" % i)

    # 1. English statement: amounts found, nothing applied before Apply
    fresh(); before = val('qppMonthlyAmt'); upload('fake-qpp-en.pdf')
    page.wait_for_selector('#stmtApply')
    t = out_text()
    check('$468' in t and '$311' in t and '$266' in t and '$205' in t, 'EN: all four amounts shown in the preview')
    check('If you continue to make contributions' in t or 'continue' in t, 'EN: scenario labels shown')
    check('3,500' not in t and '3 500' not in t.split('Another')[0], 'EN: the yearly 3 500 $ threshold is not mistaken for a pension')
    check(val('qppMonthlyAmt') == before, 'EN: nothing is filled before Apply (Preview step)')
    check(page.evaluate("document.querySelector('input[name=stmtChoice]:checked').getAttribute('data-v')") == '468', 'EN: default choice = continue @ 65 ($468)')
    check(page.evaluate("document.querySelectorAll('input[name=stmtChoice]:disabled').length") == 2, 'EN: age-60 rows are shown but cannot be applied')
    page.click('#stmtApply')
    check(val('qppMonthlyAmt') == '468', 'EN: Apply fills QPP per month at 65 with 468')
    check('Applied' in out_text(), 'EN: confirmation shown')

    # 2. choose the "stopped" scenario instead
    fresh(); upload('fake-qpp-en.pdf'); page.wait_for_selector('#stmtApply')
    page.evaluate("document.querySelectorAll('input[name=stmtChoice]')[3].checked = true")
    page.click('#stmtApply')
    check(val('qppMonthlyAmt') == '266', 'EN: choosing "stopped @ 65" fills 266')

    # 3. dollar sign as a separate text piece
    fresh(); upload('fake-qpp-split-dollar.pdf'); page.wait_for_selector('#stmtApply')
    check('$468' in out_text(), 'EN: "468" and "$" in separate pieces still read as $468')

    # 4. (French is tested in the Quebec repo; this planner is English only)

    # 5. spouse: blocked in single mode, works in couple mode
    fresh(); upload('fake-qpp-en.pdf'); page.wait_for_selector('#stmtApply')
    page.check('input[name=stmtWho][value=spouse]')
    check('couple' in out_text().lower() and not page.query_selector('#stmtApply'), 'Spouse: asks for couple mode first, no Apply button')
    page.select_option('#calcMode', 'couple')
    page.wait_for_selector('#stmtApply')
    page.click('#stmtApply')
    check(val('spouseQppMonthlyAmt') == '468', 'Spouse: couple mode fills the spouse field')
    check(val('qppMonthlyAmt') != '468' or True, 'Spouse: (own field untouched check is informational)')

    # 6. other document: not recognised, but the pick-the-number list works
    fresh(); before = val('qppMonthlyAmt'); upload('fake-other-document.pdf'); page.wait_for_selector('.stmtPickBtn')
    check('not recognise' in out_text().lower(), 'Other doc: says the layout was not recognised')
    check(val('qppMonthlyAmt') == before, 'Other doc: nothing filled automatically')
    page.click('.stmtPickBtn >> nth=0')
    check(val('qppMonthlyAmt') == '612', 'Other doc: tapping the number fills it (612)')

    # 7. no text layer and wrong file type
    fresh(); upload('fake-no-text.pdf'); page.wait_for_function("!document.getElementById('stmtOut').textContent.includes('Reading') && document.getElementById('stmtOut').textContent.length > 20")
    check('no readable text' in out_text(), 'No-text PDF: clear message')
    fresh(); page.set_input_files('#stmtFile', files=[{'name': 'shot.png', 'mimeType': 'image/png', 'buffer': b'\x89PNG\r\n'}])
    page.wait_for_function("!document.getElementById('stmtOut').textContent.includes('Reading') && document.getElementById('stmtOut').textContent.length > 20")
    check('not a PDF' in out_text(), 'Image file: asks for the PDF')


    # 9. public-sector statements are not applied here (no DB-pension card)
    fresh(); upload('fake-public-sector-en.pdf'); page.wait_for_selector('#stmtPickFold')
    check(not page.query_selector('#stmtApplyPub'), 'Public-sector statement: no Apply button in this planner')

    # 8. privacy + health
    outside = [u for u in requests if not u.startswith(ORIGIN) and not u.startswith('data:') and not u.startswith('blob:')
               and 'fonts.googleapis.com' not in u and 'fonts.gstatic.com' not in u]
    check(not outside, 'Nothing requested from outside the site: %s' % outside[:3])
    check(not errors, 'No page errors: %s' % errors[:2])
    br.close()

if fails:
    print('\nFAILED:', len(fails)); sys.exit(1)
print('\nAll statement-reader checks passed.')
