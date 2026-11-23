# imetrobert-retire (Personal Retirement Planner) - read this first, it is the map

One static file: `index.html` (about 400-600 KB: HTML form for steps 1-3, results in step 4, one big
`<script>`). No build step. Data saved in localStorage keys `csl_*`. Recipes: `docs/common-edits.md`.
Line numbers: `docs/code-map.md` (generated). The first ~25 lines of `index.html` are an "AI MAP" comment
(functions, data flow, tax-rule location, edit rules). NEVER read index.html whole: use
`grep -n name index.html` or Read with offset and limit.

If something breaks (red check, wrong result, no access): `docs/if-something-breaks.md` (open it first).

## Rules (non-negotiable)
- Privacy: `index.html` makes NO network calls (checks fail on `fetch`, `XMLHttpRequest`, `sendBeacon`,
  `WebSocket`). Sign-in and saved plans live ONLY in `account.js`, which encrypts every plan in the
  browser before upload. Never send plain figures anywhere. Never put a secret key in either file.
- THIS REPO IS PUBLIC but the app is private (sign-in, only Robert, app id `retire-personal`). Never put Robert's real figures, family details or account numbers into ANY file here, not even as defaults or examples. His numbers live only as an encrypted saved plan ("My plans"). The defaults in index.html are neutral examples on purpose.
- Do not rename element ids (the JS reads them) or localStorage keys `csl_*` (users' saved data).
- Tax numbers are for Quebec/federal 2026. Never invent a rate: check the official table, then edit
  `getDefaultTaxRules()` and set `verifiedDate`.
- Free tier only. Pages from `main`; domain in `CNAME`.
- English only: there is no French layer in this app.
- Quebec taxes, Bell-style DC pension pool, Manulife/Wealthsimple and ETF-tracker import are features of this planner (see the AI MAP).

## Two files, two jobs
- `index.html` = the planner (forms, tax, results). Almost every minor feature goes here.
- `account.js` = sign-in gate, "Welcome <email>" banner, the rows it adds to the planner menu `#toolMenu` (Logged in as, My plans, Documentation, Sign out), saved plans. Touch it only for those.
  Its documentation link is `CFG.docs` (blank for now = link hidden; set it if a guide is added). App id `retire-personal`; the Quebec and Ontario planners have their own copies.
- `statements.js` (+ `vendor/pdfjs/`) = reads a government statement PDF on the device and fills QPP fields after Preview/Apply (recipe 11 in docs/common-edits.md). No network calls. Test: `python3 scripts/test_statements.py`. Only FAKE sample PDFs in `tests/fixtures/` (this repo is public; never a real statement).
- Household mode: spouse fills in their own full form, results merge (common-edits recipe on household mode). Test: `python3 scripts/test_household.py`.
- Pension income splitting (household mode, on by default): `hhSplitPensions` moves up to 50% of the higher earner's eligible pension income each year via `p.hhTaxAdj`; recipe in `docs/common-edits.md` (recipe 14).
- Spousal rollover (household mode, on by default): `hhRollover` passes the first-dying spouse's savings to the survivor tax-free (`p.hhSurv`, `p.hhRollover`); recipe 14 in `docs/common-edits.md`.
- Expense list: optional list on Step 2 that fills and locks the spending fields (common-edits recipe on the expense list). Test: `python3 scripts/test_expenses.py`.
- Tax check: `python3 scripts/test_tax.py` compares the tax engine and yearly plan with an independent calculation (own copy of the 2026 numbers at the top of the script). Update that copy whenever the tax numbers change (common-edits recipe on the tax check).
- Test the gate: `python3 scripts/test_account.py` (stubbed server, needs `pip install playwright`). CI runs it.
- Saved plans table: `migration/planner_profiles.sql` (run once via the Supabase AI prompt in the README).

## Where things are (grep the name)
- Tax rules: `getDefaultTaxRules`, `getTaxRules`, `validateTaxRulesShape`; engine `calculateTax`;
  withholding `calcWithholdingTax`; LIF/RRIF `rrifMinFactor`, `federalLifMaxPct`.
- Simulation: `calculateRetirementPlan` -> `runSimulation` (year by year) -> `renderResultsUi` -> `yearCardsHtml`.
- Form data: `getProfileData`, `populateForm`, `MONEY_FIELDS`. Pop-up notes: `showInfo`, `initInfoNotes`.
- Hard-coded: `TFSA_ANNUAL_LIMIT`, 50% capital-gains inclusion, RRIF 1/(90-age) before 71, QPP/OAS factors.
- Version string: `APP_VERSION` and the `<title>`.

## Before and after any edit
1. Make the change in one place (see recipes). 2. `python3 scripts/check_planner.py` must say OK.
3. Open the page, press "Show my plan", scroll the schedule: money in = spending + tax + clawback +
   reinvested every year. The Checks workflow also refreshes `docs/code-map.md` after a push.
