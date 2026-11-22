#!/usr/bin/env python3
"""End-to-end test of the sign-in gate and encrypted saved plans, with Supabase stubbed
(no real network, no real accounts). Needs: pip install playwright; Chrome installed.
Run from the repo root:  python3 scripts/test_account.py
Proves: app is hidden until sign-in; wrong password / no access are refused; a saved plan reaches the
server only as ciphertext; the right passphrase reopens it, the wrong one does not; sign-out can clear
device plans; the planner itself runs without script errors."""
import http.server, threading, json, os, re, sys, functools
from playwright.sync_api import sync_playwright

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
html = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
js = open(os.path.join(ROOT, 'account.js'), encoding='utf-8').read()
APP = re.search(r"app: '([^']+)'", js).group(1)
PREFIX = re.search(r"lsPrefix: '([^']+)'", js).group(1)
PROFILEKEY = re.search(r"profileKey: '([^']+)'", js).group(1)
FR = "fr: true" in js
SB = 'https://ipnajvgwtjrlecbqfwrh.supabase.co'
USERS = {'tester@example.com': ('pw-ok', True), 'other@example.com': ('pw-ok', False)}
rows = []
fails = []
def check(cond, msg):
    print(('PASS ' if cond else 'FAIL ') + msg)
    if not cond: fails.append(msg)

def user_of(auth):
    m = re.match(r'Bearer tok-(.+)', auth or ''); return m.group(1) if m else None

def handler(route, request):
    cors = {'access-control-allow-origin': '*', 'access-control-allow-headers': '*', 'access-control-allow-methods': '*'}
    if request.method == 'OPTIONS':
        return route.fulfill(status=204, headers=cors)
    url, m = request.url, request.method
    body = json.loads(request.post_data) if request.post_data else None
    u = user_of(request.headers.get('authorization'))
    def send(status, data=None):
        route.fulfill(status=status, headers=dict(cors, **{'content-type': 'application/json'}), body=json.dumps(data) if data is not None else '')
    if '/auth/v1/token?grant_type=password' in url:
        pw = USERS.get(body['email'])
        if not pw or pw[0] != body['password']: return send(400, {'error': 'invalid'})
        return send(200, {'access_token': 'tok-' + body['email'], 'refresh_token': 'ref-' + body['email'], 'expires_in': 3600, 'user': {'email': body['email']}})
    if '/auth/v1/token?grant_type=refresh_token' in url:
        e = body['refresh_token'][4:]; return send(200, {'access_token': 'tok-' + e, 'refresh_token': 'ref-' + e, 'expires_in': 3600, 'user': {'email': e}})
    if '/rpc/has_app_access' in url:
        if u not in USERS: return send(401, {})
        return send(200, USERS[u][1])
    if '/rest/v1/planner_profiles' in url:
        if u not in USERS or not USERS[u][1]: return send(403, {})
        if m == 'GET': return send(200, [r for r in rows if r['user'] == u and ('app=eq.' + APP) in url])
        if m == 'POST':
            assert set(body.keys()) == {'app', 'blob'}, body.keys()
            rows.append({'id': 'row%d' % (len(rows) + 1), 'user': u, 'app': body['app'], 'blob': body['blob'], 'updated_at': '2026-11-22T00:00:00Z'}); return send(201)
        rid = re.search(r'id=eq\.([^&]+)', url).group(1)
        if m == 'PATCH':
            for r in rows:
                if r['id'] == rid and r['user'] == u: r['blob'] = body['blob']
            return send(204)
        if m == 'DELETE':
            rows[:] = [r for r in rows if not (r['id'] == rid and r['user'] == u)]; return send(204)
    return send(404, {})

class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Q, directory=ROOT))
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = 'http://127.0.0.1:%d/index.html' % srv.server_address[1]

with sync_playwright() as pw:
    try: br = pw.chromium.launch(channel='chrome')
    except Exception: br = pw.chromium.launch()
    ctx = br.new_context(); page = ctx.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    ctx.route(SB + '/**', handler)
    page.goto(URL); page.wait_for_selector('#awr-gate')
    check(page.query_selector('#awr-gate .awr-req') is None, 'private app: no request-access line on the sign-in screen')
    check(page.is_hidden('#currentAge'), 'planner hidden before sign-in')
    check(page.locator('#awr-mi-plans').count() == 0, 'no account button before sign-in')
    page.fill('#awr-email', 'tester@example.com'); page.fill('#awr-pw', 'wrong'); page.click('#awr-gate button[type=submit]')
    page.wait_for_function("document.querySelector('#awr-gate .awr-msg').textContent.length>0")
    check(page.is_hidden('#currentAge'), 'wrong password refused')
    page.fill('#awr-email', 'other@example.com'); page.fill('#awr-pw', 'pw-ok'); page.click('#awr-gate button[type=submit]')
    page.wait_for_function("document.querySelector('#awr-gate .awr-msg').textContent.length>0")
    check(page.is_hidden('#currentAge'), 'account without access refused')
    page.fill('#awr-email', 'tester@example.com'); page.fill('#awr-pw', 'pw-ok'); page.click('#awr-gate button[type=submit]')
    page.wait_for_selector('#awr-mi-plans', state='attached')
    check(page.is_visible('#currentAge'), 'planner visible after sign-in')
    check('tester@example.com' in page.inner_text('#awr-welcome'), 'welcome banner shows the signed-in email')
    page.click('#menuBtn'); page.wait_for_selector('#awr-who')
    first = page.evaluate("document.querySelector('#toolMenu').firstElementChild.id")
    check(first == 'awr-who' and 'tester@example.com' in page.inner_text('#awr-who'), 'menu first row says logged in as the email')
    DOCS = re.search(r"docs: '([^']*)'", js).group(1)
    if DOCS: check(page.get_attribute('#awr-mi-docs', 'href') == DOCS, 'menu has a documentation link')
    page.click('#menuBtn')
    # save a plan
    page.fill('#currentAge', '61')
    page.click('#menuBtn'); page.click('#awr-mi-plans'); page.wait_for_selector('#awr-p1')
    check(page.locator('#awr-p2').count() == 1, 'first time asks to repeat the passphrase')
    page.fill('#awr-p1', 'short'); page.fill('#awr-p2', 'short'); page.click('#awr-panel .awr-btn')
    check('10' in page.inner_text('#awr-panel .awr-msg'), 'short passphrase refused')
    page.fill('#awr-p1', 'correct horse battery'); page.fill('#awr-p2', 'correct horse battery'); page.click('#awr-panel .awr-btn')
    page.wait_for_function("[...document.querySelectorAll('#awr-panel .awr-btn')].some(b=>/Save|Enregistrer ce plan/.test(b.textContent))")
    page.click('text=/^Save this plan$|^Enregistrer ce plan$/'); page.wait_for_function("document.querySelector('#awr-panel .awr-msg.good')")
    check(len(rows) == 1, 'one row stored on the server')
    blob = rows[0]['blob'] if rows else ''
    check(rows and 'currentAge' not in blob and 'tester' not in blob and '"salt"' in blob and '"data"' in blob, 'stored blob is ciphertext only (no field names, no email)')
    # save again: updates the same row
    page.click('text=/^Save this plan$|^Enregistrer ce plan$/'); page.wait_for_function("document.querySelector('#awr-panel .awr-msg.good')")
    page.wait_for_timeout(500)
    check(len(rows) == 1, 'saving the same plan again updates the row instead of adding one')
    # reload: session persists, wrong then right passphrase
    page.reload(); page.wait_for_selector('#awr-mi-plans', state='attached')
    page.fill('#currentAge', '40')
    page.click('#menuBtn'); page.click('#awr-mi-plans'); page.wait_for_selector('#awr-p1')
    check(page.locator('#awr-p2').count() == 0, 'returning user is asked for the passphrase once')
    page.fill('#awr-p1', 'wrong passphrase here'); page.click('#awr-panel .awr-btn')
    page.wait_for_function("document.querySelector('#awr-panel .awr-msg.bad')")
    check(True, 'wrong passphrase refused')
    page.fill('#awr-p1', 'correct horse battery'); page.click('#awr-panel .awr-btn')
    page.wait_for_selector('#awr-panel .awr-row')
    page.click('text=/^Open in the form$|^Ouvrir dans le formulaire$/')
    page.wait_for_timeout(300)
    check(page.input_value('#currentAge') == '61', 'saved plan reopened with its values')
    # sign out and clear device plans
    page.click('#menuBtn'); page.click('#awr-mi-plans'); page.click('text=/^Sign out$|^Se déconnecter$/'); page.click('#awr-so-clear'); page.click('#awr-so-clear')
    page.wait_for_selector('#awr-gate')
    check(page.evaluate("localStorage.getItem('%s_profile_v1')" % PREFIX) is None, 'device plans cleared on sign-out')
    check(page.is_hidden('#currentAge'), 'planner hidden again after sign-out')
    # delete path through a second login
    page.fill('#awr-email', 'tester@example.com'); page.fill('#awr-pw', 'pw-ok'); page.click('#awr-gate button[type=submit]'); page.wait_for_selector('#awr-mi-plans', state='attached')
    page.click('#menuBtn'); page.click('#awr-mi-plans'); page.fill('#awr-p1', 'correct horse battery'); page.click('#awr-panel .awr-btn'); page.wait_for_selector('#awr-panel .awr-row')
    page.once('dialog', lambda d: d.accept()); page.click('text=/^Delete$|^Supprimer$/')
    page.wait_for_function("!document.querySelector('#awr-panel .awr-row')")
    check(len(rows) == 0, 'delete removes the row')
    if FR:
        page.evaluate("localStorage.setItem('qcrp_lang','fr')"); page.reload(); page.wait_for_selector('#awr-mi-plans', state='attached')
        page.click('#menuBtn'); page.wait_for_timeout(500)
        check('Connecté en tant que tester@example.com' in page.inner_text('#awr-who'), 'menu first row is in French')
        page.evaluate("localStorage.removeItem('awr_x')")
        ctx2 = br.new_context(); p2 = ctx2.new_page(); ctx2.route(SB + '/**', handler)
        p2.add_init_script("localStorage.setItem('qcrp_lang','fr')"); p2.goto(URL); p2.wait_for_selector('#awr-gate')
        check('Connexion' in p2.inner_text('#awr-gate'), 'sign-in screen follows the French setting')
    # planner runs
    res = page.evaluate("(function(){try{ if(typeof getProfileData!=='function') return 'no getProfileData'; var p=getProfileData(); return typeof p.currentAge; }catch(e){return String(e)}})()")
    check(res == 'number', 'planner form data readable (' + str(res) + ')')
    check(not errors, 'no script errors on the page: ' + '; '.join(errors)[:300])
    br.close()
print('\nFAILED: %d' % len(fails) if fails else '\nALL PASSED')
sys.exit(1 if fails else 0)
