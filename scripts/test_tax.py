#!/usr/bin/env python3
"""Independent tax check. Runs the planner's own calculateTax() and runSimulation() in a headless browser and
compares them with a SEPARATE implementation written from the official 2026 parameters below.
Run: python3 scripts/test_tax.py   (needs: pip install playwright). CI runs it (Checks workflow).

WHEN THIS GOES RED
  * You just changed tax numbers (a new year, or an edit in getDefaultTaxRules): the numbers below must be updated
    to the same official figures. They are deliberately a second copy: if the two disagree, one has a typo.
  * You did not touch tax numbers: a code change broke a calculation. Paste the FAIL lines to Claude with CLAUDE.md.
"""
import os, sys, itertools, random
from playwright.sync_api import sync_playwright

# ------------------------------------------------------------------ 2026 PARAMETERS (independent copy; update each year)
INF = float('inf')
P = dict(
    fed_brackets=[(58523, .14), (117045, .205), (181440, .26), (258482, .29), (INF, .33)],
    fed_credit_rate=.14, fed_bpa_full=16452, fed_bpa_min=14829, fed_bpa_start=181440, fed_bpa_end=258482,
    fed_age_max=9208, fed_age_thresh=46432, fed_age_rate=.15, fed_pension_max=2000,
    # Quebec
    qc_abatement=.165, qc_brackets=[(54345, .14), (108680, .19), (132245, .24), (INF, .2575)], qc_bpa=18952, qc_credit_rate=.14,
    qc_age=3986, qc_retire=3541, qc_alone=2172, qc_red_thresh=42955, qc_red_rate=.1875,
    # Ontario
    on_brackets=[(53891, .0505), (107785, .0915), (150000, .1116), (220000, .1216), (INF, .1316)], on_bpa=12989, on_credit_rate=.0505,
    on_age=6342, on_pension=1796, on_red_thresh=47210, on_red_rate=.15, on_reduction=300, on_surtax1=5818, on_surtax2=7446,
    oas_threshold=95323, oas_rate=.15,
)
# ------------------------------------------------------------------ independent implementation
def brk(x, b):
    t, lo = 0.0, 0.0
    for hi, r in b:
        if x > lo: t += (min(x, hi) - lo) * r
        lo = hi
    return t

def fed_net(x, age, pens):
    bpa = P['fed_bpa_full'] if x <= P['fed_bpa_start'] else P['fed_bpa_min'] if x >= P['fed_bpa_end'] else \
        P['fed_bpa_full'] - (x - P['fed_bpa_start']) / (P['fed_bpa_end'] - P['fed_bpa_start']) * (P['fed_bpa_full'] - P['fed_bpa_min'])
    cr = bpa + (max(0, P['fed_age_max'] - P['fed_age_rate'] * max(0, x - P['fed_age_thresh'])) if age >= 65 else 0) + min(P['fed_pension_max'], max(0, pens))
    return max(0, brk(x, P['fed_brackets']) - P['fed_credit_rate'] * cr)

def quebec(x, age, pens, alone):
    f = fed_net(x, age, pens) * (1 - P['qc_abatement'])
    base = (P['qc_age'] + min(P['qc_retire'], max(0, pens)) if age >= 65 else 0) + (P['qc_alone'] if alone else 0)
    base = max(0, base - P['qc_red_rate'] * max(0, x - P['qc_red_thresh']))
    return f + max(0, brk(x, P['qc_brackets']) - P['qc_credit_rate'] * (P['qc_bpa'] + base))

def health_premium(ti):
    if ti <= 20000: return 0
    if ti <= 36000: return min(300, .06 * (ti - 20000))
    if ti <= 48000: return min(450, 300 + .06 * (ti - 36000))
    if ti <= 72000: return min(600, 450 + .25 * (ti - 48000))
    if ti <= 200000: return min(750, 600 + .25 * (ti - 72000))
    return min(900, 750 + .25 * (ti - 200000))

def ontario(x, age, pens, alone):
    f = fed_net(x, age, pens)
    cr = P['on_bpa'] + (max(0, P['on_age'] - P['on_red_rate'] * max(0, x - P['on_red_thresh'])) if age >= 65 else 0) + min(P['on_pension'], max(0, pens))
    basic = max(0, brk(x, P['on_brackets']) - P['on_credit_rate'] * cr)
    net = basic - min(basic, max(0, 2 * P['on_reduction'] - basic))
    sur = .20 * max(0, net - P['on_surtax1']) + .36 * max(0, net - P['on_surtax2'])
    return f + net + sur + health_premium(x)

# ------------------------------------------------------------------ run
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
fails = []
with sync_playwright() as pw:
    br = pw.chromium.launch(); pg = br.new_page()
    pg.route('**/*.js', lambda r: r.abort())          # no sign-in gate, no network
    pg.goto('file://' + os.path.join(ROOT, 'index.html'))
    pg.wait_for_function("typeof calculateTax === 'function' && typeof runSimulation === 'function'")
    is_qc = pg.evaluate("'qcBpa' in getDefaultTaxRules()")
    indep = quebec if is_qc else ontario
    incomes = [0, 12000, 19999, 25000, 36500, 42955, 47210, 54345, 60000, 72300, 95323, 100000, 108680, 132245, 150000, 181440, 220000, 258482, 500000] + list(range(1000, 260000, 7919))
    n = 0
    for x, age, pens, alone in itertools.product(incomes, (58, 65, 72), (0, 1500, 4000, 25000), (True, False)):
        got = pg.evaluate("([x,a,p,o]) => calculateTax(x,a,p,getDefaultTaxRules(),o).totalTax", [x, age, pens, {'alone': alone} if is_qc else {}])
        exp = indep(x, age, pens, alone); n += 1
        if abs(got - exp) > 0.02:
            fails.append('tax: age %d, taxable income $%s, pension income $%s, living alone %s: planner $%.2f, expected $%.2f' % (age, format(x, ','), format(pens, ','), alone, got, exp))
    print('tax engine: %d cases compared' % n)

    # yearly plan: money in must equal money out; tax and clawback must match calculateTax
    random.seed(11); rows_checked = 0
    key = 'qppMonthlyAmt' if is_qc else 'cppMonthlyAmt'
    for i in range(25):
        over = dict(calcMode='single', currentAge=random.choice([62, 66, 70]), alreadyRetired=True, spendFrequency='monthly', spendAmount=random.choice([3000, 6000, 10000]),
                    currentRrsp=random.choice([300000, 900000]), currentTfsa=random.choice([0, 100000]), currentNonReg=0, contribNonReg=0, contribRrsp=0, contribTfsa=0,
                    liraBalance=0, fedDcBalance=0, ftqBalance=0, ownPensionAnnual=random.choice([0, 30000]), ownPensionStartAge=60, inflationMode='none',
                    returnPre=4, returnPost=4, lifeExpectancy=92, livesAlone='yes', returnModel='flat', events=[], recurringEvents=[], extraRegAmt=0)
        over['targetAge'] = over['currentAge']; over[key] = 1000; over['oasMonthlyAmt'] = 740
        rows = pg.evaluate("""([o]) => { const p = Object.assign(getProfileData(), o), rules = getTaxRules();
            return runSimulation(p, 65, 65, rules, false).scheduleRows.map(r => {
              const reg = r.rrspDraw + r.liraDraw + r.rlifUnlockedDraw + r.ftqDraw, gov = r.qppInc || r.cppInc || 0;
              const taxable = reg + gov + (r.oasIncGross - r.clawback) + r.pensionInc + (r.nonRegYieldIncome || 0); // surplus reinvested outside registered accounts earns taxable yield
              const tax = calculateTax(taxable, r.age, r.age >= 65 ? reg + r.pensionInc : r.pensionInc, rules, {alone: true}).totalTax;
              const inn = r.rrspDraw + r.liraDraw + r.nonRegDraw + r.ftqDraw + r.tfsaDraw + r.rlifUnlockedDraw + gov + r.oasIncGross + r.pensionInc;
              return {age: r.age, resid: inn - (r.actualNetTakeHome + r.taxPaid + r.clawback + r.reinvested), dtax: r.taxPaid - tax}; }); }""", [over])
        for r in rows:
            rows_checked += 1
            if abs(r['resid']) > 1: fails.append('plan: age %d, scenario %d: money in minus money out is $%.2f (must be $0)' % (r['age'], i, r['resid']))
            if abs(r['dtax']) > 5: fails.append('plan: age %d, scenario %d: tax in the plan differs from calculateTax by $%.2f' % (r['age'], i, r['dtax']))
    print('yearly plan: %d rows checked' % rows_checked)
    br.close()

if fails:
    print('\nFAILED (%d). First ones:' % len(fails))
    for f in fails[:10]: print('  FAIL ' + f)
    print('\nWhat to do: if you just changed tax numbers, update the "2026 PARAMETERS" block at the top of scripts/test_tax.py to the same official figures.\n'
          'Otherwise a code change broke a calculation: give Claude these FAIL lines and CLAUDE.md (docs/common-edits.md, recipe on the tax check).')
    sys.exit(1)
print('OK: tax engine and yearly plan agree with the independent calculation.')
