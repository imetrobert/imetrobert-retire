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

## Two files, two jobs (details: `docs/feature-notes.md`)
- `index.html` = the planner (forms, tax, results). Almost every minor feature goes here.
- `account.js` = sign-in gate, menu rows, encrypted cloud copies. `account.js` must stay identical in all three planners; touch it only for sign-in or save/load.
- `statements.js` = reads a government statement PDF on the device. No network calls. Fake sample PDFs only in `tests/fixtures/`.
- Optional features (household mode, pension splitting, spousal rollover, expense list, other income, compare/stress tools, Monte Carlo banner and "Judge the plan by", home sale, language start, gate test, tax check) are described, with their tests, in `docs/feature-notes.md`. Run the matching `scripts/test_*.py` after touching one.

## Words to keep the same everywhere
- **Everyday spending** is the one name for the normal day-to-day spending target (Step 2 field `spendAmountLabel` and its JS text, year-card lines "Everyday spending", "Goes to everyday spending"). Special, year-specific costs are Life events, never "spending" or "living costs". Do not reintroduce "living costs", "General living costs" or "Spending you want". If you rename it, change the English text, the info note under the field, the French entries (Quebec `EXACT` and `P.push`), the guide and the glossary row together; `scripts/test_home_sale.py` checks the label and the year cards.

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
