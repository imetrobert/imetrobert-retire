#!/usr/bin/env python3
"""Checks the Monte Carlo run summary ("This run: ...") and the Re-run another scenario button in a headless browser.
Run: python3 scripts/test_mc_run.py   (needs: pip install playwright). CI runs it (Checks workflow).

What it proves
  * with the Monte Carlo model the results page shows a run summary: scenario number, a verdict, four figures, the rank among the 300 trials
  * the figures are the ones the headline run really used (average of lastFinalRun.yearReturns)
  * Re-run another scenario shows scenario 2 with a different market (also when "same random markets" is on), and Show my plan returns to scenario 1 with the original market
  * no summary for the flat model; no page errors; (Quebec planner) the summary has French text
WHEN THIS GOES RED: give Claude the FAIL lines and CLAUDE.md (docs/common-edits.md, Monte Carlo run summary recipe).
"""
import os, sys, re
from playwright.sync_api import sync_playwright

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
fails = []
def check(cond, msg):
    if not cond: fails.append(msg)

with sync_playwright() as pw:
    br = pw.chromium.launch(); pg = br.new_page(viewport={'width': 390, 'height': 800})
    errors = []
    pg.on('pageerror', lambda e: errors.append(str(e)))
    pg.route('**/*.js', lambda r: r.abort())
    pg.goto('file://' + os.path.join(ROOT, 'index.html'))
    pg.wait_for_function("typeof runSimulation === 'function' && typeof mcRerun === 'function'")
    pg.evaluate("document.documentElement.classList.remove('awr-locked')")
    age_id = pg.evaluate("document.getElementById('qppStartAge') ? 'qppStartAge' : 'cppStartAge'")
    pg.evaluate("(a) => { const set = (i, v) => { document.getElementById(i).value = v; };"
                "set('currentAge', 58); set('targetAge', 62); set('lifeExpectancy', 92);"
                "set('currentRrsp', 600000); set('currentTfsa', 90000); set('spendAmount', 5000); set('optimizerMode', 'manual');"
                "set(a, 65); set('oasStartAge', 65);"
                "set('returnModel', 'montecarlo'); set('mcAvgReturn', 6); set('mcVolatility', 12);"
                "document.getElementById('mcRepeatable').checked = true; }", age_id)

    def banner():
        return pg.evaluate("document.getElementById('mcRunBanner').innerText")
    def avg_shown():
        return pg.evaluate("(() => { const c = Array.from(document.querySelectorAll('#mcRunBanner .mc-chip')).find(e => /yearly return|rendement annuel/i.test(e.innerText)); return c ? c.querySelector('b').innerText : ''; })()")
    def scenario():
        return pg.evaluate("(() => { const e = document.querySelector('#mcRunBanner .mc-tag b'); return e ? e.innerText : ''; })()")

    pg.evaluate("mcRerunN = 0; mcSeedShift = 0; calculateRetirementPlan()")
    b1 = banner(); a1 = avg_shown()
    check('This run' in b1 and 'Scenario' in b1, 'run summary missing after Show my plan')
    check(scenario() == '1', 'first scenario number should be 1, got %r' % scenario())
    check(pg.evaluate("document.querySelectorAll('#mcRunBanner .mc-chip').length") == 4, 'expected 4 figures')
    check(re.search(r'more savings than\s*\d+%\s*of the\s*300', b1) is not None, 'rank sentence missing: %r' % b1[-160:])
    expect = pg.evaluate("(() => { const y = lastFinalRun.yearReturns.filter(r => r.age <= 92); const m = y.reduce((t, r) => t + r.r, 0) / y.length; return (m < 0 ? '−' : '+') + Math.abs(m * 100).toFixed(1) + '%'; })()")
    check(a1 == expect, 'average shown %r but the headline run averaged %r' % (a1, expect))

    pg.evaluate("calculateRetirementPlan()")
    check(avg_shown() == a1, 'same random markets is on, so Show my plan again should repeat the market')

    pg.click('#mcRunBanner .mc-rerun')
    a2 = avg_shown()
    check(scenario() == '2', 'after Re-run the scenario number should be 2, got %r' % scenario())
    check(a2 != a1, 'Re-run gave the same market (%s)' % a2)

    pg.evaluate("document.querySelector('button[onclick*=\"mcRerunN = 0\"]').click()")
    check(scenario() == '1' and avg_shown() == a1, 'Show my plan should return to scenario 1 with the first market')

    # not repeatable: a re-run is still a different random draw
    pg.evaluate("document.getElementById('mcRepeatable').checked = false; calculateRetirementPlan()")
    r1 = avg_shown(); pg.click('#mcRunBanner .mc-rerun'); r2 = avg_shown()
    check(r1 != r2, 'Re-run without repeatable gave the same market')

    # "Judge the plan by": badge follows this run (default) or the share of the 300 markets that fund the plan
    pg.evaluate("document.getElementById('mcRepeatable').checked = true; mcRerunN = 0; mcSeedShift = 0; calculateRetirementPlan()")
    def hero():
        return pg.evaluate("(() => ({badge: document.querySelector('#heroSummary .hero-badge').innerText, h2: document.querySelector('#heroSummary h2').innerText, on: (document.querySelector('.mc-judge button.on')||{}).innerText}))()")
    h0 = hero()
    check(h0['on'] and h0['on'].strip().lower() in ('this run', 'cette simulation'), 'default judge should be This run: %r' % h0)
    pct = pg.evaluate("Math.round(lastAuditMeta.monteCarlo.successRate * 100)")
    lvl = 'ok' if pct >= 90 else ('risk' if pct >= 70 else 'short')
    pg.click('.mc-judge button:nth-of-type(2)')
    h1 = hero()
    check(('%d' % pct) in h1['h2'] and 'market' in h1['h2'].lower() or 'march' in h1['h2'].lower(), 'all-markets headline should show %d%%: %r' % (pct, h1))
    want = {'ok': ('You are on track', 'Sur la bonne voie'), 'risk': ('Some risk', 'Risque mod'), 'short': ('Needs a change', 'Changement')}[lvl]
    check(pg.evaluate("document.querySelector('#heroSummary .hero').classList.contains('short')") == (lvl != 'ok'), 'badge colour should match level %s at %d%%' % (lvl, pct))
    pg.click('#mcRunBanner .mc-rerun')
    check(pg.evaluate("(document.querySelector('.mc-judge button.on')||{}).innerText").strip().lower() in ('all markets', 'tous les march\u00e9s'), 'choice should stay on All markets after a re-run')
    pg.click('.mc-judge button:nth-of-type(1)')
    check(hero()['on'].strip().lower() in ('this run', 'cette simulation'), 'back to This run')
    pg.evaluate("document.getElementById('returnModel').value = 'flat'; calculateRetirementPlan()")
    check(pg.evaluate("document.querySelectorAll('.mc-judge').length") == 0, 'flat model should not show the judge toggle')
    pg.evaluate("document.getElementById('returnModel').value = 'montecarlo'; calculateRetirementPlan()")

    # French (Quebec planner only)
    if pg.evaluate("!!(window.QCRP_I18N && window.QCRP_I18N.toggle)"):
        pg.evaluate("window.QCRP_I18N.toggle()")
        pg.wait_for_timeout(600)
        fr = banner()
        check('Relancer un autre sc' in fr and 'Cette simulation' in fr, 'French summary text missing: %r' % fr[:200])

    # flat model: no summary
    pg.evaluate("document.getElementById('returnModel').value = 'flat'; calculateRetirementPlan()")
    check(banner().strip() == '', 'flat model should show no run summary')

    check(not errors, 'page errors: %s' % errors[:3])
    br.close()

if fails:
    print('FAIL:'); [print('  - ' + f) for f in fails]; sys.exit(1)
print('OK: Monte Carlo run summary and re-run button')
