#!/usr/bin/env python3
"""Checks the optional sale of the family home (Step 1 question, Step 2 card, plan) in a headless browser.
Run: python3 scripts/test_home_sale.py   (needs: pip install playwright). CI runs it (Checks workflow).
Proves: the card is hidden until Yes; the net money (price - selling costs - mortgage - smaller home and buying costs) is invested in the sale year
(TFSA up to the room, the rest non-registered, or all non-registered); a rent plan invests the whole net and changes spending; nothing happens with No;
save/reload keeps the answers; the plan with a sale ends with more savings than the plan without.
WHEN THIS GOES RED: give Claude the FAIL lines and CLAUDE.md (docs/common-edits.md, home sale recipe 18)."""
import os, sys
from playwright.sync_api import sync_playwright
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
fails = []
def check(c, m):
    if not c: fails.append(m)
with sync_playwright() as pw:
    br = pw.chromium.launch(); pg = br.new_page(viewport={'width': 390, 'height': 800}); errors = []
    pg.on('pageerror', lambda e: errors.append(str(e))); pg.route('**/*.js', lambda r: r.abort())
    pg.goto('file://' + os.path.join(ROOT, 'index.html')); pg.wait_for_function("typeof hsUi === 'function'")
    pg.evaluate("document.documentElement.classList.remove('awr-locked')")
    age_id = pg.evaluate("document.getElementById('qppStartAge') ? 'qppStartAge' : 'cppStartAge'")
    pg.evaluate("""(a) => { const set = (i, v) => { document.getElementById(i).value = v; };
        set('currentAge', 60); set('targetAge', 62); set('lifeExpectancy', 92); set('currentRrsp', 400000); set('currentTfsa', 60000); set('tfsaRoomNow', 20000);
        set('spendAmount', 5000); set('optimizerMode', 'manual'); set(a, 65); set('oasStartAge', 65); set('inflationMode', 'none'); set('returnModel', 'flat');
        set('homeSaleAge', 75); set('homeSalePrice', 800000); set('homeSaleCostPct', 5); set('homeSaleOwing', 40000); set('homeSaleNewPrice', 450000); set('homeSaleBuyPct', 3);
        set('homeSaleSaved', 9000); set('homeSaleNewCost', 3000); }""", age_id)
    vis = lambda: pg.evaluate("document.getElementById('homeSaleCard').style.display !== 'none'")
    run = lambda: pg.evaluate("calculateRetirementPlan(); (() => { const r = lastFinalRun; return {rows: r.scheduleRows.map(x => ({age: x.age, net: x.homeSaleNet, t: x.homeSaleTfsa, n: x.homeSaleNon, tgt: x.targetSpend})), end: r.taxAtDeath.portfolioAtEnd}; })()")
    check(not vis(), 'card should be hidden for No')
    base = run()
    check(all(not r['net'] for r in base['rows']), 'No should invest nothing')
    pg.evaluate("document.getElementById('homeSaleDecl').value = 'downsize'; hsUi(true)")
    check(vis(), 'card should show for downsize'); check(pg.evaluate("document.getElementById('hsDownRows').style.display !== 'none'"), 'smaller-home rows should show for downsize')
    want = 800000 * 0.95 - 40000 - 450000 * 1.03        # 256,500
    d = run(); row = [r for r in d['rows'] if r['age'] == 75][0]
    check(abs(row['net'] - want) < 1, 'net %s expected %s' % (row['net'], want))
    check(abs(row['t'] + row['n'] - row['net']) < 0.01, 'split must add up to the net')
    check(0 < row['t'] <= row['net'] and row['n'] >= 0, 'TFSA part must be positive and at most the net: %s' % row)
    check(sum(1 for r in d['rows'] if r['net'] > 0) == 1, 'sale must happen in one year only')
    check(d['end'] > base['end'], 'ending savings should be higher with the sale (%s vs %s)' % (d['end'], base['end']))
    t0 = [r for r in base['rows'] if r['age'] == 74][0]['tgt']; t1 = [r for r in d['rows'] if r['age'] == 76][0]['tgt']; tb = [r for r in base['rows'] if r['age'] == 76][0]['tgt']
    check(abs((t1 - tb) - (3000 - 9000)) < 1, 'yearly spending should change by -6000 after the sale: %s' % (t1 - tb))
    check(abs([r for r in d['rows'] if r['age'] == 74][0]['tgt'] - t0) < 1, 'spending must not change before the sale')
    pg.evaluate("document.getElementById('homeSaleDest').value = 'nonreg'")
    d2 = run(); row2 = [r for r in d2['rows'] if r['age'] == 75][0]
    check(row2['t'] == 0 and abs(row2['n'] - want) < 1, 'all-non-registered option: %s' % row2)
    pg.evaluate("document.getElementById('homeSaleDecl').value = 'rent'; hsUi(true)")
    check(pg.evaluate("document.getElementById('hsDownRows').style.display === 'none'"), 'smaller-home rows hidden for rent')
    d3 = run(); row3 = [r for r in d3['rows'] if r['age'] == 75][0]
    check(abs(row3['net'] - (800000 * 0.95 - 40000)) < 1, 'rent plan should invest the whole net: %s' % row3['net'])
    # save and reload
    prof = pg.evaluate("getFormProfile()")
    check(prof['homeSaleMode'] == 'rent' and prof['homeSalePrice'] == 800000 and prof['homeSaleDest'] == 'nonreg', 'profile fields missing')
    pg.evaluate("document.getElementById('homeSaleDecl').value = 'no'; hsUi(); document.getElementById('homeSalePrice').value = 1")
    pg.evaluate("(p) => populateForm(p)", prof)
    check(pg.evaluate("document.getElementById('homeSaleDecl').value") == 'rent' and pg.evaluate("document.getElementById('homeSalePrice').value") == '800000', 'reload should restore the answers')
    # TFSA room is respected: no room carried in, sale in the first retirement year -> only that year's limit fits
    pg.evaluate("document.getElementById('homeSaleDecl').value = 'downsize'; document.getElementById('homeSaleDest').value = 'tfsa'; document.getElementById('homeSaleAge').value = 62; document.getElementById('tfsaRoomNow').value = 0")
    d5 = run(); r5 = [r for r in d5['rows'] if r['age'] == 62][0]
    check(abs(r5['t'] - 7000) < 1 and abs(r5['n'] - (r5['net'] - 7000)) < 1, 'TFSA part should be capped at the 7000 yearly limit: %s' % r5)
    pg.evaluate("document.getElementById('homeSaleDecl').value = 'rent'; document.getElementById('homeSaleAge').value = 75; document.getElementById('tfsaRoomNow').value = 20000")
    # results note
    pg.evaluate("calculateRetirementPlan()")
    check('Home sale at age 75' in pg.evaluate("document.getElementById('heroSummary').innerText"), 'results note missing')
    # a sale before retirement age is moved to the first retirement year
    pg.evaluate("document.getElementById('homeSaleAge').value = 50"); d4 = run()
    check([r['age'] for r in d4['rows'] if r['net'] > 0] == [62], 'sale age below retirement age should happen at 62: %s' % [r['age'] for r in d4['rows'] if r['net'] > 0])
    if pg.evaluate("!!(window.QCRP_I18N && window.QCRP_I18N.toggle)"):
        pg.evaluate("document.getElementById('homeSaleAge').value = 75; calculateRetirementPlan(); window.QCRP_I18N.toggle()"); pg.wait_for_timeout(600)
        txt = pg.evaluate("document.getElementById('homeSaleCard').innerText + ' ' + document.getElementById('heroSummary').innerText")
        check('Vente de votre maison' in txt and 'Vente de la maison' in txt, 'French text missing: %r' % txt[:160])
    check(not errors, 'page errors: %s' % errors[:3])
    br.close()
if fails:
    print('FAIL:'); [print('  - ' + f) for f in fails]; sys.exit(1)
print('OK: home sale card, plan, save/reload and results note')
