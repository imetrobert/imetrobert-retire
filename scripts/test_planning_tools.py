#!/usr/bin/env python3
"""Checks the "Compare and stress-test" tools, the one-page summary, text size and life-event presets in a headless browser.
Run: python3 scripts/test_planning_tools.py   (needs: pip install playwright). CI runs it (Checks workflow).

What it proves
  * every comparison row for "your plan as entered" equals the main plan's own numbers (the tools call the same engine)
  * weaker markets never improve the result (normal >= weak >= severe) and start-age / strategy tables list the options
  * the estate table's last row matches the plan's own estate; the one-page summary builds and names the verdict
  * two saved scenarios compare from their saved results
  * text size cycles and is remembered; each life-event preset fills the next empty row, one-time and yearly
WHEN THIS GOES RED: a change broke a tool; give Claude the FAIL lines and CLAUDE.md (docs/common-edits.md, recipe 16).
"""
import os, sys, re
from playwright.sync_api import sync_playwright

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
fails = []
def check(cond, msg):
    if not cond: fails.append(msg)
def num(s):
    return float(re.sub(r'[^0-9.\-]', '', s.replace('−', '-')) or 0)

with sync_playwright() as pw:
    br = pw.chromium.launch(); pg = br.new_page(viewport={'width': 390, 'height': 800})
    errors = []
    pg.on('pageerror', lambda e: errors.append(str(e)))
    pg.route('**/*.js', lambda r: r.abort())
    pg.goto('file://' + os.path.join(ROOT, 'index.html'))
    pg.wait_for_function("typeof runSimulation === 'function' && typeof ptStartAges === 'function'")
    pg.evaluate("document.documentElement.classList.remove('awr-locked')")
    pg.evaluate("document.getElementById('currentAge').value = 58; document.getElementById('targetAge').value = 62; document.getElementById('lifeExpectancy').value = 92;"
                "document.getElementById('currentRrsp').value = 600000; document.getElementById('currentTfsa').value = 90000; document.getElementById('currentNonReg').value = 150000;"
                "document.getElementById('spendAmount').value = 5000; document.getElementById('optimizerMode').value = 'manual';"
                "document.getElementById('qppStartAge').value = 65; document.getElementById('oasStartAge').value = 65;")
    pg.evaluate("calculateRetirementPlan()")
    base = pg.evaluate("(() => { const r = lastFinalRun, t = r.taxAtDeath; return {tax: r.totalTaxesPaidToday, left: t.portfolioAtEndToday, estate: t.afterTaxEstateToday}; })()")

    def rows(box):
        return pg.evaluate("(id) => Array.from(document.querySelectorAll('#' + id + ' tr')).slice(1).map(r => Array.from(r.children).map(c => c.textContent))", box)

    # 1. start ages
    pg.evaluate("ptStartAges()"); r = rows('ptBoxStart')
    check(len(r) == 6, 'start ages: expected 6 rows, got %d' % len(r))
    if r:
        check('your plan' in r[0][0], 'start ages: first row is not your plan')
        check(abs(num(r[0][1]) - round(base['tax'])) <= 1, 'start ages: your-plan tax %s != main plan %s' % (r[0][1], base['tax']))
        check(abs(num(r[0][4]) - round(base['estate'])) <= 1, 'start ages: your-plan estate %s != main plan %s' % (r[0][4], base['estate']))
        check(len({x[4] for x in r}) > 1, 'start ages: every option gave the same estate')

    # 2. strategies
    pg.evaluate("ptStrategies()"); r = rows('ptBoxStrat')
    check(len(r) >= 7, 'strategies: expected at least 7 rows, got %d' % len(r))
    if r:
        check(r[0][0] == 'Your plan as entered' and abs(num(r[0][1]) - round(base['tax'])) <= 1 and abs(num(r[0][4]) - round(base['estate'])) <= 1, 'strategies: first row differs from the main plan')
        check(len({x[4] for x in r}) > 2, 'strategies: options do not change the result')

    # 3. stress
    pg.evaluate("ptStress()"); r = rows('ptBoxStress')
    check(len(r) == 4, 'stress: expected 4 rows, got %d' % len(r))
    if len(r) == 4:
        check(abs(num(r[0][3]) - round(base['estate'])) <= 1, 'stress: first row estate differs from the main plan')
        e = [num(x[3]) for x in r]
        check(e[0] >= e[1] >= e[2], 'stress: weaker markets did not lower the estate in order (%s)' % e)
        check(e[3] <= e[0], 'stress: slow growth is better than your plan')

    # 4. estate
    pg.evaluate("ptEstate()"); r = rows('ptBoxEstate')
    check(len(r) >= 9, 'estate: expected breakdown plus age rows, got %d' % len(r))
    if r:
        check(abs(num(r[5][1]) - round(base['estate'])) <= 1, 'estate: breakdown total differs from the main plan')
        ages = [x for x in r if x[0].startswith('If the plan ended at')]
        check(any(x[0].endswith('92') and abs(num(x[3]) - round(base['estate'])) <= 1 for x in ages), 'estate: the plan-until-age row differs from the main plan')
        check(any(x[0].endswith('75') for x in ages) and any(x[0].endswith('85') for x in ages), 'estate: missing the 75 or 85 row')

    # 5. one-page summary
    h = pg.evaluate("ptOnePageHtml()")
    check('Retirement plan summary' in h and ('Your money lasts to age 92' in h or 'Money runs short' in h), 'one page: no title or verdict')
    check('Year by year' in h and 'Left to family after tax' in h and 'not tax, legal or investment advice' in h, 'one page: missing sections or disclaimer')
    pg.evaluate("window.print = () => { window.__printed = document.body.classList.contains('print-onepage'); }; ptOnePage()")
    pg.wait_for_function("window.__printed !== undefined", timeout=3000)
    check(pg.evaluate("window.__printed") is True, 'one page: body class not set when printing')

    # 6. saved scenarios
    pg.evaluate("document.getElementById('profileName').value = 'Base'; saveProfileAndResultsNow()")
    pg.evaluate("(() => { const all = getAllProfiles(), id = Object.keys(all)[0]; const c = JSON.parse(JSON.stringify(all[id])); c.name = 'Later'; c.targetAge = 65; c.results.finalPortfolio = 1000; all['copy1'] = c; putAllProfiles(all); })()")
    pg.evaluate("ptFillSaved()")
    check(pg.evaluate("document.getElementById('ptSavedA').options.length") >= 3, 'saved compare: expected the screen plan plus 2 saved')
    pg.evaluate("document.getElementById('ptSavedA').selectedIndex = 1; document.getElementById('ptSavedB').selectedIndex = 2; ptCompareSaved()")
    r = rows('ptBoxSaved')
    check(len(r) == 9, 'saved compare: expected 9 rows, got %d' % len(r))
    if r:
        check(r[0][0] == 'Retirement age' and r[0][1] != r[0][2], 'saved compare: retirement ages should differ')
        # Regression: the saved tax at death was NaN (an estate object was rounded), so the table showed $NaN
        check(not any('NaN' in c for row in r for c in row), 'saved compare: a cell shows NaN')
        want = pg.evaluate("Math.round(lastFinalRun.taxAtDeath.taxAtDeath)")
        saved = pg.evaluate("resultsSummary().taxAtDeath")
        check(saved == want, 'saved compare: saved tax at death %s != plan %s' % (saved, want))

    # 6b. results top: withdrawal bar chart (one stacked bar per year, total above each bar)
    pg.evaluate("calculateRetirementPlan()")
    wd = pg.evaluate("""(() => { const c = document.querySelector('.plan-sum .wd-chart'); if (!c) return null;
        const t = Array.from(c.querySelectorAll('text.wd-total')).map(x => x.textContent);
        return {bars: t.length, rects: c.querySelectorAll('rect').length, legend: c.querySelectorAll('.wd-key').length, first: t[0]}; })()""")
    check(wd is not None, 'withdraw chart: missing from the results top')
    if wd:
        nyears = pg.evaluate("lastFinalRun.schedule ? lastFinalRun.schedule.filter(r => r.age <= getProfileData().lifeExpectancy).length : -1")
        check(wd['bars'] >= 5 and wd['rects'] >= wd['bars'] and wd['legend'] >= 1, 'withdraw chart: expected bars, segments and a legend, got %s' % wd)
        check(wd['first'].startswith('$') or wd['first'] == '–', 'withdraw chart: the first bar has no total label (%s)' % wd['first'])

    # 6b2. pension start lines on the withdrawal chart (solid line plus label at the QPP/CPP and OAS start ages)
    pg.evaluate("document.getElementById('qppStartAge').value = 65; document.getElementById('oasStartAge').value = 67; calculateRetirementPlan()")
    ml = pg.evaluate("""(() => { const c = document.querySelector('.plan-sum .wd-chart'); if (!c) return null;
        return {lines: Array.from(c.querySelectorAll('line[stroke-width="2"]')).length, labels: Array.from(c.querySelectorAll('text')).map(t => t.textContent).filter(t => /starts|start$/.test(t))}; })()""")
    check(ml is not None and ml['lines'] == 2 and len(ml['labels']) == 2, 'pension lines: expected 2 lines and 2 labels, got %s' % ml)
    pg.evaluate("document.getElementById('qppStartAge').value = 67; document.getElementById('oasStartAge').value = 67; calculateRetirementPlan()")
    ml = pg.evaluate("(() => { const c = document.querySelector('.plan-sum .wd-chart'); return c ? Array.from(c.querySelectorAll('line[stroke-width=\"2\"]')).length : -1; })()")
    check(ml == 1, 'pension lines: same start age should give one joint line, got %s' % ml)

    # 6b3. tapping a bar opens that year's card
    pg.evaluate("calculateRetirementPlan()")
    tap = pg.evaluate("""(() => { const h = document.querySelectorAll('.plan-sum .wd-hit'); if (!h.length) return null;
        const r = h[2]; const m = r.getAttribute('onclick').match(/goToYear\\((\\d+)\\)/); r.dispatchEvent(new MouseEvent('click', {bubbles: true}));
        const d = document.getElementById('yp-' + m[1]); return {found: !!d, open: !!(d && d.open)}; })()""")
    check(tap is not None and tap['found'] and tap['open'], 'bar tap: expected the year card to open, got %s' % tap)

    # 6c. results headline colour: green when the money lasts, red when it runs out
    hcol = pg.evaluate("(() => { const h = document.querySelector('.hero h2.hero-h'); return h ? [h.className, getComputedStyle(h).color] : null; })()")
    check(hcol is not None, 'headline colour: hero headline has no hero-h class')
    if hcol:
        want = {'ok': 'rgb(21, 128, 61)', 'risk': 'rgb(180, 83, 9)', 'short': 'rgb(185, 28, 28)'}
        lvl = [k for k in want if k in hcol[0].split()]
        check(len(lvl) == 1 and hcol[1] == want[lvl[0]], 'headline colour: class %s gives %s' % (hcol[0], hcol[1]))

    # 7. text size
    pg.evaluate("cycleTextSize()")
    check(pg.evaluate("document.body.style.zoom") == '1.15' and pg.evaluate("document.getElementById('tsLabel').textContent") == 'Large', 'text size: first tap should give Large')
    pg.evaluate("cycleTextSize(); ptInitTextSize()")
    check(pg.evaluate("document.body.style.zoom") == '1.3', 'text size: second tap / reload should give Extra large')
    check(pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 2"), 'text size: page scrolls sideways at Extra large')
    pg.evaluate("cycleTextSize()")
    check(pg.evaluate("document.body.style.zoom") == '', 'text size: third tap should return to Normal')

    # 8. presets
    pg.evaluate("document.getElementById('presetSel').value = 'car'; ptAddPreset(); document.getElementById('presetSel').value = 'help'; ptAddPreset();"
                "document.getElementById('presetSel').value = 'care'; ptAddPreset(); document.getElementById('presetSel').value = 'travel'; ptAddPreset();")
    ev = pg.evaluate("collectEvents().filter(e => e.name)"); rc = pg.evaluate("collectRecurringEvents().filter(e => e.name)")
    check([e['name'] for e in ev] == ['Replace the car', 'Help a child or grandchild'], 'presets: one-time events not added in order: %s' % ev)
    check(ev and ev[0]['age'] == 70 and ev[1]['age'] == 67, 'presets: ages should be retirement age + offset (70, 67)')
    check(len(rc) == 2 and rc[0]['startAge'] == 85 and rc[0]['endAge'] == 92 and rc[1]['startAge'] == 62 and rc[1]['endAge'] == 71, 'presets: yearly cost ages wrong: %s' % rc)
    pg.evaluate("calculateRetirementPlan()")
    check(pg.evaluate("lastFinalRun.scheduleRows.some(r => (r.eventTotalThisYear || 0) > 0)"), 'presets: a preset event did not reach the plan')
    check(not errors, 'page errors: %s' % errors[:3])
    br.close()

if fails:
    print('FAIL: planning tools')
    for f in fails: print(' -', f)
    sys.exit(1)
print('OK: planning tools (start ages, strategies, stress test, estate, saved compare, one page, text size, presets).')
