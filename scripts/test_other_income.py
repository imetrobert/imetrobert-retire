#!/usr/bin/env python3
"""Checks the optional "other income in retirement" feature in a headless browser.
Run: python3 scripts/test_other_income.py   (needs: pip install playwright). CI runs it (Checks workflow).

What it proves
  * the Step 2 card stays hidden until Step 1 says "Yes" to other income
  * the year-by-year list is built from the ages in Steps 1 and 3 (first row = retirement age, last = plan-until age,
    calendar year = this year + age - age today)
  * saving the list locks the single yearly field; stopping the list unlocks it
  * the setting survives save and reload of a plan (getProfileData -> populateForm), and a spouse's form starts blank
  * the plan adds the income, and answering "No" switches it off again
  * (Quebec only) the French text is translated
WHEN THIS GOES RED: a change broke the feature; give Claude the FAIL lines and CLAUDE.md (docs/common-edits.md, recipe 15).
"""
import os, sys, datetime
from playwright.sync_api import sync_playwright

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)


with sync_playwright() as pw:
    br = pw.chromium.launch(); pg = br.new_page()
    errors = []
    pg.on('pageerror', lambda e: errors.append(str(e)))
    pg.route('**/*.js', lambda r: r.abort())          # no sign-in gate, no network
    pg.goto('file://' + os.path.join(ROOT, 'index.html'))
    pg.wait_for_function("typeof runSimulation === 'function' && typeof oiLoad === 'function'")
    has_fr = pg.evaluate("!!window.QCRP_I18N")

    # 1. hidden until declared
    check(pg.evaluate("document.getElementById('otherIncCard').style.display === 'none'"), 'card is visible before saying Yes')
    pg.evaluate("document.getElementById('currentAge').value = 60; document.getElementById('targetAge').value = 65; document.getElementById('lifeExpectancy').value = 70;"
                "document.getElementById('otherIncDecl').value = 'yes'; oiUi(true);")
    check(pg.evaluate("document.getElementById('otherIncCard').style.display !== 'none'"), 'card did not appear after saying Yes')

    # 2. the list is built from the ages
    pg.evaluate("openOtherIncome()")
    rows = pg.evaluate("Array.from(document.querySelectorAll('#oiList .oi-row')).map(r => [r.children[0].textContent, r.children[1].textContent])")
    this_year = datetime.date.today().year
    check(len(rows) == 6, 'expected 6 rows (ages 65 to 70), got %d' % len(rows))
    if rows:
        check(rows[0][0] == 'Age 65' and rows[0][1] == str(this_year + 5), 'first row should be Age 65 / %d, got %s' % (this_year + 5, rows[0]))
        check(rows[-1][0] == 'Age 70' and rows[-1][1] == str(this_year + 10), 'last row should be Age 70 / %d, got %s' % (this_year + 10, rows[-1]))

    # 3. save an empty list is refused; a real list locks the single field
    pg.evaluate("oiCommit()")
    check(pg.evaluate("!document.getElementById('oiErr').hidden"), 'an empty list was accepted')
    pg.evaluate("const i = document.querySelectorAll('#oiList input'); i[0].value = 10000; i[0].dispatchEvent(new Event('input')); i[2].value = 25000; i[2].dispatchEvent(new Event('input'));")
    check(pg.evaluate("document.getElementById('oiTotal').textContent") == '$35,000', 'list total should read $35,000')
    pg.evaluate("oiCommit()")
    check(pg.evaluate("OI.on === true && document.getElementById('otherIncAmt').disabled === true && !document.getElementById('oiLockBox').hidden"), 'list did not lock the single yearly field')
    check(pg.evaluate("document.getElementById('oiSheet').classList.contains('open')") is False, 'sheet stayed open after Save')

    # 4. save and reload
    prof = pg.evaluate("JSON.parse(JSON.stringify(getFormProfile()))")
    check(prof.get('otherIncOn') is True and prof.get('otherIncListOn') is True and prof['otherIncList'].get('65') == 10000 and prof['otherIncList'].get('67') == 25000, 'profile did not carry the list: %s' % {k: v for k, v in prof.items() if k.startswith('otherInc')})
    pg.evaluate("oiLoad({})")
    check(pg.evaluate("OI.on === false && document.getElementById('otherIncDecl').value === 'no' && document.getElementById('otherIncCard').style.display === 'none'"), 'loading a plan without the setting should switch it off')
    pg.evaluate("p => oiLoad(p)", prof)
    check(pg.evaluate("OI.on === true && OI.list[65] === 10000 && OI.list[67] === 25000 && document.getElementById('otherIncDecl').value === 'yes'"), 'reloading the plan lost the list')

    # 5. stopping the list unlocks the field; the single amount is used
    pg.evaluate("oiStop(); document.getElementById('otherIncAmt').value = 12000;")
    check(pg.evaluate("OI.on === false && document.getElementById('otherIncAmt').disabled === false"), 'stopping the list did not unlock the field')
    p2 = pg.evaluate("JSON.parse(JSON.stringify(getFormProfile()))")
    check(p2['otherIncAmt'] == 12000 and p2['otherIncListOn'] is False, 'single amount not saved')

    # 6. the plan uses it, and "No" switches it off
    out = pg.evaluate("""() => { const p = Object.assign(getProfileData(), {inflationMode: 'none', alreadyRetired: true, currentAge: 66, targetAge: 66, lifeExpectancy: 70, otherIncOn: true, otherIncAmt: 12000, otherIncListOn: false});
        const on = runSimulation(p, 65, 65, getTaxRules(), false).scheduleRows.map(r => r.otherInc);
        p.otherIncOn = false; const off = runSimulation(p, 65, 65, getTaxRules(), false).scheduleRows.map(r => r.otherInc);
        return {on: on, off: off}; }""")
    check(out['on'] and all(abs(v - 12000) < 0.01 for v in out['on']), 'plan did not use $12,000 every year: %s' % out['on'])
    check(out['off'] and all(v == 0 for v in out['off']), 'plan used other income although it was switched off')

    # 7. a spouse's form starts blank
    blank = pg.evaluate("p => { const s = hhBlank(Object.assign({}, p, {otherIncOn: true, otherIncAmt: 5000, otherIncListOn: true, otherIncList: {65: 1}})); return [s.otherIncOn, s.otherIncAmt, s.otherIncListOn, Object.keys(s.otherIncList).length]; }", p2)
    check(blank == [False, 0, False, 0], 'a new spouse form should start without other income, got %s' % blank)

    # 8. French (Quebec planner only)
    if has_fr:
        pg.evaluate("oiLoad({otherIncOn: true, otherIncAmt: 0}); QCRP_I18N.toggle()")
        fr = pg.evaluate("document.querySelector('label[for=otherIncDecl]').textContent")
        check('retraite' in fr.lower(), 'French label not translated: %s' % fr)
        pg.evaluate("openOtherIncome()")
        fr2 = pg.evaluate("document.querySelector('#oiSheet h3').textContent")
        check('année' in fr2.lower(), 'French sheet title not translated: %s' % fr2)
        pg.evaluate("QCRP_I18N.toggle()")
    check(not errors, 'page errors: %s' % errors[:3])
    br.close()

if fails:
    print('FAILED (%d):' % len(fails))
    for f in fails:
        print('  FAIL ' + f)
    sys.exit(1)
print('OK: other income card, year-by-year list, save/reload, plan and French all work.')
