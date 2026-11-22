#!/usr/bin/env python3
"""Household mode: you and a spouse fill in the same form separately; results merge them.
Run: python3 scripts/test_household.py (needs playwright). CI runs it."""
import os, sys
from playwright.sync_api import sync_playwright
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
bad = []
def check(ok, msg):
    if not ok: bad.append(msg)
with sync_playwright() as pw:
    br = pw.chromium.launch(); pg = br.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.route('**/*.js', lambda r: r.abort())
    pg.goto('file://' + os.path.join(ROOT, 'index.html'))
    pg.wait_for_function("typeof hhSwitch === 'function' && typeof getProfileData === 'function'")
    pg.evaluate("document.documentElement.classList.remove('awr-locked')")
    # single mode is untouched
    check(pg.evaluate("document.getElementById('hhBar').hidden"), 'bar hidden in single mode')
    pg.evaluate("calculateRetirementPlan()")
    check(pg.evaluate("document.getElementById('hhTabs').hidden"), 'no household tabs in single mode')
    pg.evaluate("showStep(1)")
    # choose couple
    pg.select_option('#calcMode', 'couple')
    check(pg.is_visible('#hhBar') and pg.is_visible('#hhNamesRow'), 'bar and name boxes show for a couple')
    pg.fill('#hhNameMe', 'Robert'); pg.fill('#hhNameSp', 'Dana')
    check(pg.inner_text('#hhBtnSp') == 'Dana', 'spouse button uses the name')
    pg.evaluate("document.getElementById('currentRrsp').value = 400000; document.getElementById('currentTfsa').value = 60000; document.getElementById('spendAmount').value = 6000")
    # calculating before the spouse is filled in sends you to the spouse form
    pg.evaluate("calculateRetirementPlan()")
    check(pg.evaluate("HH.who") == 'spouse', 'guard switches to the spouse form')
    check(pg.evaluate("document.getElementById('spendAmount').disabled && document.getElementById('calcMode').disabled"), 'household fields locked in the spouse view')
    check(pg.evaluate("document.getElementById('spendAmount').value") == '6000', 'spouse view shows the household spending')
    pg.evaluate("closeInfo()")
    pg.evaluate("document.getElementById('currentAge').value = 52; document.getElementById('currentRrsp').value = 50000; document.getElementById('currentTfsa').value = 20000")
    pg.evaluate("hhSwitch('me')")
    check(pg.evaluate("document.getElementById('currentRrsp').value") == '400000', 'my own values come back')
    check(not pg.evaluate("document.getElementById('spendAmount').disabled"), 'spending editable again in my view')
    p = pg.evaluate("getProfileData()")
    check(p['hhSpouse']['currentRrsp'] == 50000 and p['hhSpouse']['currentAge'] == 52, 'saved profile carries the spouse form')
    check(p['hhNames'] == {'me': 'Robert', 'sp': 'Dana'}, 'names saved')
    # household results
    pg.evaluate("calculateRetirementPlan()")
    check(pg.is_visible('#hhPanel') and pg.is_visible('#hhTabs'), 'household panel shows')
    check(pg.locator('.hh-table tbody tr').count() >= 20, 'household grid has rows')
    check('Dana' in pg.inner_text('#hhPanel') and 'Robert' in pg.inner_text('#hhPanel'), 'names appear in the grid')
    shares = pg.evaluate("[HH.prof.me.spendAmount, HH.prof.sp.spendAmount, HH.me.spendAmount, HH.prof.me.calcMode]")
    check(abs(shares[0] + shares[1] - shares[2]) < 0.02 and shares[3] == 'single', 'shares add up to the household spending: %s' % shares)
    # the household person plan equals a plain single-person plan on that share
    same = pg.evaluate("""() => { const A = HH.plans.me, r = getTaxRules(); const run = runSimulation(A.p, A.q, A.o, r, true); return Math.abs(run.finalPortfolio - A.run.finalPortfolio) < 1; }""")
    check(same, 'person plan matches the single-person engine')
    # person tabs
    pg.evaluate("hhShowView('me')"); check(pg.is_visible('#yearCards') or pg.is_visible('#heroSummary'), 'my tab shows the normal results')
    check(not pg.is_visible('#hhPanel'), 'panel hidden on my tab')
    pg.evaluate("hhShowView('sp')"); check(pg.evaluate("lastExportProfile.hhRole") == 'Your spouse', 'spouse tab runs the spouse plan')
    pg.evaluate("hhShowView('house')"); check(pg.is_visible('#hhPanel'), 'back to household')
    # manual split
    pg.fill('#hhSplitIn', '70'); pg.evaluate("hhSetSplit()")
    check(abs(pg.evaluate("HH.prof.me.spendAmount") - 4200) < 0.02, 'manual split applied')
    # round trip through a saved profile
    p2 = pg.evaluate("getProfileData()")
    pg.evaluate("p => populateForm(p)", p2)
    check(pg.evaluate("HH.spouse.currentRrsp") == 50000 and pg.evaluate("HH.names.sp") == 'Dana' and pg.evaluate("HH.visited") is True, 'profile loads back with the spouse and names')
    # expense list with who-pays
    pg.evaluate("openExpenses()")
    check(pg.is_visible('#expHhBox'), 'who-pays box shows for a couple')
    pg.evaluate("expDraft.items = [{name:'Mortgage',amount:'2500',pct:''},{name:'Groceries',amount:'1200',pct:''},{name:'Travel',amount:'800',pct:''}]; expRender()")
    check(pg.locator('#expList .ep').count() == 3, 'one % box per expense')
    pg.evaluate("hhRecommendSplit()")
    rec = pg.inner_text('#expRec'); check('Recommended: your share is' in rec, 'recommendation text: ' + rec)
    pcts = pg.evaluate("expDraft.items.map(i => i.pct)")
    check(all(isinstance(x, (int, float)) and 0 <= x <= 100 for x in pcts), 'every expense got a percent: %s' % pcts)
    pg.evaluate("expCommit()")
    pg.evaluate("calculateRetirementPlan('house')")
    exp = pg.evaluate("[HH.expShare, HH.prof.me.spendAmount + HH.prof.sp.spendAmount, HH.me.spendAmount]")
    check(exp[0] is not None and abs(exp[1] - exp[2]) < 0.05, 'expense-driven split adds up: %s' % exp)
    check(pg.evaluate("document.getElementById('hhSplitIn').disabled"), 'manual split disabled when the expense list sets it')
    # life events: who pays
    pg.evaluate("hhSwitch('me'); showStep(7)")
    check(pg.evaluate("document.getElementById('event1Pct').closest('.hh-evpct').hidden") is False, 'event share box shows for a couple')
    pg.evaluate("""() => { const me = HH.me; document.getElementById('event1Name').value = 'Wedding'; document.getElementById('event1Amount').value = 10000;
        document.getElementById('event1Age').value = 70; document.getElementById('event1Pct').value = 60;
        document.getElementById('event2Name').value = 'Roof'; document.getElementById('event2Amount').value = 8000; document.getElementById('event2Age').value = 71;
        document.getElementById('recur1Name').value = 'Condo'; document.getElementById('recur1Amount').value = 2000; document.getElementById('recur1StartAge').value = 66; document.getElementById('recur1EndAge').value = 68; document.getElementById('recur1Pct').value = 25; }""")
    pg.evaluate("calculateRetirementPlan('house')")
    ev = pg.evaluate("""() => { const d = HH.spouse.currentAge - HH.me.currentAge; return { d: d, me: HH.prof.me.events.map(e => [e.name, e.amount, e.age]), sp: HH.prof.sp.events.map(e => [e.name, e.amount, e.age]),
        rme: HH.prof.me.recurringEvents.map(e => [e.amount, e.startAge, e.endAge]), rsp: HH.prof.sp.recurringEvents.map(e => [e.amount, e.startAge, e.endAge]) }; }""")
    d = ev['d']
    check(['Wedding', 6000, 70] in ev['me'] and ['Wedding', 4000, 70 + d] in ev['sp'], 'one-time event split 60/40 with the spouse age shifted: %s' % ev)
    check(['Roof', 8000, 71] in ev['me'] and not any(e[0] == 'Roof' for e in ev['sp']), 'blank share means the filler pays all')
    check([500, 66, 68] in ev['rme'] and [1500, 66 + d, 68 + d] in ev['rsp'], 'recurring event split 25/75: %s' % ev)
    pg.evaluate("hhSwitch('spouse')")
    pg.evaluate("document.getElementById('event1Name').value = 'Car'; document.getElementById('event1Amount').value = 3000; document.getElementById('event1Age').value = 55; document.getElementById('event1Pct').value = 50")
    pg.evaluate("calculateRetirementPlan('house')")
    car = pg.evaluate("[HH.prof.me.events.filter(e => e.name === 'Car').map(e => [e.amount, e.age]), HH.prof.sp.events.filter(e => e.name === 'Car').map(e => [e.amount, e.age])]")
    check(car[1] == [[1500, 55]] and car[0] == [[1500, 55 - d]], 'an event entered in the spouse form splits too: %s' % car)
    p3 = pg.evaluate("getProfileData()"); pg.evaluate("p => populateForm(p)", p3)
    check(pg.evaluate("document.getElementById('event1Pct').value") == '60', 'my event share survives a saved profile')
    pg.evaluate("hhSwitch('me'); calculateRetirementPlan('house')")
    # older joint profiles become a spouse form
    pg.evaluate("populateForm({calcMode:'couple', currentAge:60, targetAge:65, spouseAge:58, spouseRetirementAge:63, spendAmount:5000, spendFrequency:'monthly', spouseTfsa:30000})")
    check(pg.evaluate("HH.spouse.currentAge") == 58 and pg.evaluate("HH.spouse.currentTfsa") == 30000 and pg.evaluate("HH.legacy") != '', 'legacy joint profile migrates')
    # back to single
    pg.evaluate("populateForm({calcMode:'single'})"); check(pg.evaluate("document.getElementById('hhBar').hidden"), 'single mode hides the bar')
    # French
    if pg.evaluate("!!(window.QCRP_I18N && QCRP_I18N.toggle)"):
        pg.evaluate("p => populateForm(p)", p2); pg.evaluate("calculateRetirementPlan('house')")
        pg.evaluate("QCRP_I18N.toggle()"); pg.wait_for_timeout(400)
        txt = pg.inner_text('#hhPanel')
        for w in ('Plan du ménage', 'Année par année', 'entièrement financé', 'retire'):
            check(w in txt, 'French missing: ' + w)
    check(not errs, 'page errors: %s' % errs[:3])
    br.close()
if bad:
    print('FAILED:'); [print('  FAIL ' + b) for b in bad]; sys.exit(1)
print('OK: household mode works (separate forms, names, merged grid, split, who-pays, saved plans).')
