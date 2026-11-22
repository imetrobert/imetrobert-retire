# Common edits - recipes (Personal Retirement Planner)

Edit only the block named; find it with `grep -n` or `docs/code-map.md`. Then run
`python3 scripts/check_planner.py` (or let the Checks workflow run). Commit to main; Pages redeploys.

## 1. Yearly tax update (every January)
1. `getDefaultTaxRules()`: federal and Quebec brackets, basic amounts, age and pension credits, and
   `verifiedDate`. Source: Canada Revenue Agency and the provincial tax authority tables for the new year.
2. `TFSA_ANNUAL_LIMIT` (the new year's limit).
3. Government pension defaults: the maximum QPP and OAS monthly amounts in the input defaults
   (`cppMonthlyAmt`, `oasMonthlyAmt` and the spouse versions). OAS maximum changes each quarter.
4. `APP_VERSION` and `<title>` say "2026 rules": update the year. 5. Run the check and one plan.
Users who customised rules on screen keep their own (`csl_tax_rules_v1`); that is expected.

## 2. Change wording of a label or note
grep the English text in `index.html`, change it in the HTML. Do not touch ids.
- English only: there is no French layer in this app.

## 3. Add a question (field) to the form
1. Add the `<input id="newField">` in the right `data-step` block (grep `data-step="2"`).
2. Money field: add its id to `MONEY_FIELDS` if it also appears in results rows.
3. Save/load: add it to `getProfileData()` and `populateForm()`.
4. Use it in `runSimulation()`. 5. If it is shown in results, add it to `yearCardsHtml()`.
6. Keep the invariant: money in = spending + tax + clawback + reinvested.

## 4. Change a hard-coded rule (e.g. RRIF minimum, 50% inclusion)
grep the constant (see CLAUDE.md "Hard-coded"), change it, and test a plan before and after.

## 5. Mobile layout or colours
CSS is one `<style>` block at the top (see `docs/code-map.md` for its line). Change the one class.
Test on a narrow phone width. The app is phone-first.

## 6. Disclaimers, independence notice, contact details
The app has NO visible disclaimer today (only the PDF guides carry an independence notice). Add one
before the address goes public: a short footer or a first-screen note saying results are estimates,
not tax, legal or investment advice, and the tool is independent of any government or employer.
Put it in the HTML near the end of `data-step="4"` and on step 1.

## 7. Add a new province (new repo)
Copy this repo, rename storage keys to a new prefix, then replace the provincial parts: the credits and
tax function (`calculateTax` and the helpers named in the AI MAP), `federalLifMaxPct` or the provincial
LIF table, withholding, and the labels. Check against an independent calculation (the Quebec app was
checked on 84 cases).

## 8. Something broke after an edit
Run `python3 scripts/check_planner.py`: it names a syntax error or duplicate id. Otherwise
`git log -p -3 -- index.html` and revert the last change.

## 9. Add a minor feature (a button, a line in the results, a new note)
1. Say what the user sees and where. Find the nearest similar thing in `docs/code-map.md` and copy its pattern.
2. Work only in `index.html`. New field: recipe 3 (it must be saved by `getProfileData` and loaded by `populateForm`
   so saved plans include it automatically). New result line: add it in `renderResultsUi`.
3. Do not call the network, add libraries, or rename ids/`csl_*` keys.
4. Run `python3 scripts/check_planner.py`, then press "Show my plan" and confirm money in = money out.
5. Quebec only: add the French text (recipe 2). Update `APP_VERSION`.

## 10. Change the sign-in screen, welcome banner or saved plans
Edit `account.js` only (texts are in `T`, English and French). Keep: encryption before upload, no secret keys,
no innerHTML. Run `python3 scripts/test_account.py`. `CFG.docs` is blank (no guide here); set it to show a documentation link.
The same change usually belongs in the other planner's `account.js` too.

## 11. Government statements (read a PDF and fill a field)
`statements.js` + `vendor/pdfjs/` (self-hosted pdf.js, loaded only when a PDF is picked). The page block is
`<details id="stmtShortcut">` in step 1. The file is read in the browser only: no network call, nothing saved
(`check_planner.py` fails if `statements.js` names a web address or calls fetch).
- Today it reads the Retraite Québec Statement of Participation, section A ("Estimate of the amount of your
  retirement pension (monthly)": two rows, "continue contributing" / "stopped today", amounts at age 60 and 65)
  and fills `qppMonthlyAmt` (or `spouseQppMonthlyAmt`) after a Preview and a tap on Apply. Layout source: the
  public example on retraitequebec.gouv.qc.ca ("Statement of Participation under the QPP").
- Also reads a public-sector pension statement (RREGOP and similar; `parsePublic()`): three yearly scenarios (earliest possible, earliest unreduced, at 65), fills `ownPensionAnnual` and `ownPensionStartAge` and sets `pensionType` to a DB option. Skipped automatically in planners without `#ownPensionAnnual`. Layout source: Retraite Québec's public example PDF; the amount positions there were not visible to me, so it is the least verified reader.
- If Retraite Québec changes wording: edit `START_RX`, `END_RX`, `KIND_CONT`, `KIND_STOP` at the top of the
  QPP block in `statements.js`. Unknown layouts still work through the "Pick the number yourself" list.
- New statement type (OAS, CPP, a tax slip): copy `parseQpp()` into `parseXxx()`, add its fixture to
  `scripts/make_fake_statements.py` (FAKE data only; this repo is public), add a case to
  `scripts/test_statements.py`, and add the French text to `TXT.fr`.
- Never commit a real statement. Test with `python3 scripts/make_fake_statements.py` then
  `python3 scripts/test_statements.py` (needs `pip install playwright reportlab`).
- Screenshots and scans are NOT read (no OCR yet); the message asks for the PDF.


## 12. The tax check (scripts/test_tax.py) went red
It compares the planner's tax engine and yearly plan with a SEPARATE calculation using its own copy of the official numbers
(the "2026 PARAMETERS" block at the top of the script). The Actions run prints lines starting FAIL.
- You just changed tax numbers (new year, or an edit in `getDefaultTaxRules`): update the PARAMETERS block to the same official figures. Two copies on purpose: if they disagree, one has a typo. Find which by checking the official table (canada.ca, Revenu Québec or Ontario), not by copying one into the other.
- You did not touch tax numbers: a code change broke a calculation. Revert it or fix it, then run `python3 scripts/test_tax.py`.
- The check does not block the site (Pages deploys on its own); it only alerts you.

## 13. The optional expense list (Step 2 spending)
Under the spending field a link opens "Your expenses": a list of name + amount + how often it is billed (each row is Monthly, Weekly or Yearly, default Monthly; "Set all rows to" changes every row, a row can then be overridden; "Show the total per" picks the unit that fills `spendFrequency`, which also accepts yearly). Items are `{name, amount, freq, pct}`; old saved items without `freq` inherit the saved `expenseFreq`. In household mode each row shows two linked % boxes (`hhExpPctInput`): editing one sets the other to 100 minus it, blank = automatic split; only `pct` (the first person's share) is stored. The spouse's tab has a "Household expenses" link (`hhOpenSharedExp`) that opens the same shared list. Life events have the same two linked boxes (`eventNPct` / `eventNPctO`, `recurNPct` / `recurNPctO`, built by `hhEnsureEventPct`); in just-me mode with others only my % counts (`evMine`, used in `runSimulation`); in couple mode `hhRecommendEvents` / `hhOptimizeEvents` pick one % for all events of the open form by tax and depletion score. Conversion helpers: `expMult`/`freqMult` (52, 12, 1), `freqWord`, `freqShort`. "Use this list" fills `spendAmount` and `spendFrequency` with the total and greys both out; "Edit expense list" or "Stop using the list" are the only ways to change them. Code: the block that starts `// ---- Optional expense list` in `index.html` (`EXP`, `expSync`, `openExpenses`, `expCommit`, `expStop`). It is saved with the plan as `expenseOn`, `expenseFreq`, `expenseItems` (read in `populateForm` via `expLoad`, written in `getProfileData`). The plan itself still just reads `spendAmount` and `spendFrequency`, so nothing else changes.
- Wording: edit the strings inside `buildExpSheet()` and the three lines under `spendFrequencyNote` and add the French to the `Object.assign(EXACT, {...})` block right after `P.push(["· not adding"...` (and the two `Your expenses add up to` patterns).
- Test: `python3 scripts/test_expenses.py` (runs in Checks).
- Paste a list: the sheet has a "Paste a list" box (`expPasteRows`): one `name amount` line per expense, `$`/`CA$`/commas allowed, zero or nameless lines skipped. Personal planner only. Never commit real figures; paste them in the app and save with My plans.
- Share of expenses when you live with others but plan just for yourself (calcMode single, livesAlone = no): `expShareMode()`; each row gets a "Your %" box (blank = 100%), `expSpend()` is the total that drives spendAmount, `expSetAll()` fills every row. In couple mode the same `pct` field means who-pays between spouses.

## 14. Household mode (you and a spouse each fill in their own form)
Step 1 asks "Are you filling this out for you, or for you and a spouse?". Choosing both shows a "Filling in" switch (names optional) and a second copy of the SAME form for the spouse: the page keeps two profiles (`HH.me`, `HH.spouse`) and swaps them into the one form (`hhSwitch`). Spending, inflation and returns are household settings: entered once in your form, greyed out in the spouse's (`HH_KEYS` / `HH_IDS`). Results: a Household tab (merged grid, `hhRenderHouse`) plus one tab per person that shows the normal results. Each person runs as an ordinary single-person plan (`calcMode` single) on their share of the household spending, so the tax engine is unchanged. The share is automatic (in proportion to expected retirement income, `hhShares`), a typed percent, or set by the "who pays" boxes in the expense list; "Recommend an optimized split" (`hhOptimizeSplit`) tries splits and picks the best combined result. Saved with the plan as `hhSpouse`, `hhSplit`, `hhNames`; old joint plans are converted by `hhFromLegacy`.
- The old spouse fields (`spouse*`) are hidden and only read when an old joint plan is loaded.
- Not modeled: pension income splitting, spousal rollover. Each life event has a "Share you pay (%)" box (blank = the person filling in the form pays all); `hhShareEvents` sends the rest to the other person's plan in the same calendar year (ages shifted by the age gap).
- Wording: edit the strings in the `// ---- Household mode` block. In the Quebec planner keep labels in their own elements (the French layer translates whole text units).
- Pension income splitting: block `// ---- Pension income splitting` (`hhSplitPensions`). Each person's plan accepts `p.hhTaxAdj[yearIndex]` (income moved to or from them, for tax and OAS clawback only; cash does not move). Every year up to 50% of the higher earner's eligible pension income (employer pension; RRIF/LIF at 65+) moves to even out the two taxable incomes; the result is kept only if combined tax and clawback fall. Switch: `HH.pis` ('on' by default, saved as `hhPis`). Tests: `scripts/test_household.py` (zero-sum, 50% cap, switch) and `scripts/test_tax.py` (tax with moved income vs the independent calculation). Spousal rollover is still not modeled.
- Spousal rollover: block `// ---- Spousal rollover` (`hhRollover`). The plan with fewer rows is the first death; its end balances (`run.endState`) are added to the survivor's accounts in the engine through `p.hhSurv` (and the deceased's estate tax is skipped via `p.hhRollover`); the survivor then covers `HH.survPct`% (default 75) of household spending. Switch `HH.roll` (saved as `hhRoll`, `hhSurvPct`). Not modeled: QPP/CPP survivor benefits and employer-pension survivor payments. Test: `scripts/test_household.py`.
- Test: `python3 scripts/test_household.py` (runs in Checks).

## Year view: which events an account pays for
- In `yearCardsHtml` (grep `Goes to life events`) each account block lists the year's events by name under that line. The names and costs come from `r.eventDetailsThisYear` (set in the simulation next to `eventNamesThisYear`; each item has name, today, future, rec). An account's event amount (`x.evt`) is shared across events in proportion to each event's cost that year, the same rule as the "How each dollar is used" view. The engine does not track which dollar paid which event. For a shared event (household mode, or just-me with others) the event objects carry `_full` and `_share` (set in `hhShareEvents` and `evMine`), so each event line also says what percent you cover, the total cost, who covers the balance (the other person's name, "your spouse" or "your spouse or others"; `p.hhKey` tells which person's plan it is) and links to Life events (`showStep(7)`).

## Year view: transfers between accounts
- In `yearCardsHtml`, the account that gives money to another account shows a blue `.yp-xfer.out` line ("➜ Moved into TFSA, part of this withdrawal") per destination, and the receiving account (TFSA or Non-registered) shows a green `.yp-xfer.in` line ("⬅ Transfer in from RRSP / RRIF") per source, including "QPP / OAS / pension" when income is moved. Amounts split a source's transfer across destinations in proportion to what each destination received. Styles are at the start of the `autoAgeCss` style block. Quebec French fragments sit next to "Also receives".

## Saving and cloud status (wording)
- Results screen: "Save on this device" (`saveProfileAndResults`) and "Save on device and cloud" (`saveToBoth`). The device list (`renderProfileManager`) shows JUST SAVED / LATEST SAVE and a green / orange / grey cloud line per scenario with a "Sync to cloud" button (`window.awrSyncPlan` in `account.js`). The status compares a fingerprint (`planSig`) stored at the last cloud save from this device (`<profiles key>_cloudsync`); it cannot see saves made from another device. Save / Cancel bars: expense sheet (`.exp-save`) and Life events (`#evBar`).

## Menu and saved copies (wording)
- Planner menu rows are in `#toolMenu` in `index.html` (Life events, Expenses, Saved on this device, ...); the account rows (My plans (cloud), Documentation, Sign out) are added by `account.js` (`refreshMenu`). There is no floating account button any more: My plans opens from the menu only.
- "Saved on this device" = scenarios in this browser's localStorage (`showProfileManager`); "My plans (cloud)" = encrypted copies in the user's account. Keep these two names distinct everywhere.
