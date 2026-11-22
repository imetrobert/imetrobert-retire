#!/usr/bin/env python3
"""Checks the optional expense list (Step 2): it fills and locks the spending fields, saves with the profile,
survives reload of a saved profile, and the plan uses the total. Run: python3 scripts/test_expenses.py (needs playwright)."""
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
    pg.wait_for_function("typeof openExpenses === 'function' && typeof getProfileData === 'function'")
    pg.evaluate("document.documentElement.classList.remove('awr-locked'); showStep(2)")  # the sign-in gate hides the page until login
    check(not pg.evaluate("document.getElementById('spendAmount').disabled"), 'fields start editable')
    pg.evaluate("openExpenses()")
    check(pg.evaluate("document.getElementById('expFreq').value") == 'monthly', 'default is monthly')
    rows = pg.locator('#expList .exp-row')
    check(rows.count() >= 3, 'starts with blank rows')
    pg.locator('#expList .en').nth(0).fill('Groceries'); pg.locator('#expList .ea').nth(0).fill('900.50')
    pg.locator('#expList .en').nth(1).fill('Insurance'); pg.locator('#expList .ea').nth(1).fill('300')
    check('$1,200.5' in pg.inner_text('#expTotal'), 'total shown: ' + pg.inner_text('#expTotal'))
    pg.select_option('#expFreq', 'weekly'); check('week' in pg.inner_text('#expTotLbl'), 'label follows weekly')
    pg.select_option('#expFreq', 'monthly')
    pg.evaluate("expCommit()")
    check(pg.evaluate("document.getElementById('spendAmount').disabled && document.getElementById('spendFrequency').disabled"), 'fields locked after Use')
    check(pg.evaluate("document.getElementById('spendAmount').value") == '1200.5', 'amount filled')
    check(pg.is_visible('#expLockBox'), 'lock box visible')
    p = pg.evaluate("getProfileData()")
    check(p['spendAmount'] == 1200.5 and p['expenseOn'] is True and len(p['expenseItems']) == 2, 'profile carries list')
    # saved profile round trip
    pg.evaluate("p => { expLoad({expenseOn:false}); populateForm(p); }", p)
    check(pg.evaluate("document.getElementById('spendAmount').disabled"), 'restored locked from saved profile')
    # weekly list
    pg.evaluate("openExpenses(); expDraft.freq='weekly'; expDraft.items=[{name:'x',amount:'200'}]; expCommit()")
    check(pg.evaluate("document.getElementById('spendFrequency').value") == 'weekly', 'weekly applied')
    check(pg.evaluate("getProfileData().spendAmount") == 200, 'weekly total in profile')
    # empty list is refused
    pg.evaluate("openExpenses(); expDraft.items=[{name:'',amount:''}]; expCommit()")
    check(pg.evaluate("!document.getElementById('expErr').hidden"), 'empty list refused')
    pg.evaluate("expCancel()")
    check(pg.evaluate("EXP.on") is True, 'cancel keeps previous list')
    # stop using: editable again, value kept
    pg.evaluate("expStop()")
    check(not pg.evaluate("document.getElementById('spendAmount').disabled"), 'editable after stop')
    check(pg.evaluate("getProfileData().expenseOn") is False, 'profile says off')
    # old profile without the fields loads fine
    pg.evaluate("p => { delete p.expenseOn; delete p.expenseItems; delete p.expenseFreq; populateForm(p); }", p)
    check(not pg.evaluate("document.getElementById('spendAmount').disabled"), 'old profile loads unlocked')
    # plan runs on the total
    pg.evaluate("openExpenses(); expDraft.items=[{name:'a',amount:'3500'}]; expDraft.freq='monthly'; expCommit()")
    out = pg.evaluate("() => { const p = getProfileData(); return getAnnualNetNeed(p); }")
    check(out == 42000, 'annual need uses the total: %s' % out)
    if pg.evaluate("!!(window.QCRP_I18N && QCRP_I18N.toggle)"):
        pg.evaluate("QCRP_I18N.toggle()"); pg.evaluate("openExpenses()"); pg.wait_for_timeout(300)
        txt = pg.inner_text('#expSheet') + ' ' + pg.inner_text('#expLockBox')
        for w in ('Vos dépenses', 'Utiliser cette liste', 'Ajouter une dépense', 'Total par mois'):
            check(w in txt, 'French missing: ' + w)
        check('Vos dépenses totalisent' in txt and 'par mois' in txt, 'French lock text: ' + txt[-200:])
    # paste a list: tab or space separated, $ and CA$ and thousands commas, zero and total lines skipped
    pg.evaluate("openExpenses(); expDraft.items = []; expRender()")
    pg.evaluate("document.getElementById('expPaste').closest('details').open = true")
    pg.fill('#expPaste', "Alpha bus\t10.00 $\nBeta\tCA$5.25\nGamma food\t1,500.00 $\nZero item\t0.00 $\n\t1,515.25 $\n")
    pg.evaluate("expPasteRows()")
    got = pg.evaluate("expDraft.items.map(i => [i.name, i.amount])")
    check(got == [['Alpha bus', '10'], ['Beta', '5.25'], ['Gamma food', '1500']], 'pasted rows: %s' % got)
    check('Added 3 expenses' in pg.inner_text('#expPasteMsg'), 'paste message: ' + pg.inner_text('#expPasteMsg'))
    pg.evaluate("expCancel()")
    check(not errs, 'page errors: %s' % errs[:2])
    br.close()
if bad:
    print('FAILED:'); [print('  FAIL ' + b) for b in bad]; sys.exit(1)
print('OK: the optional expense list works (fills, locks, saves, restores, plan uses it).')
