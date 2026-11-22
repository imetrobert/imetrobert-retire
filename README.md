# Personal Retirement Planner

Robert's private retirement calculator (Quebec taxes). One static file (`index.html`), no build step,
no server. Planned address: **https://retire.imetrobert.com** (only Robert; access set at access.imetrobert.com,
app id `retire-personal`; see "Access" below).

## How it is hosted
GitHub Pages, branch `main`, folder `/ (root)`. Custom domain comes from `CNAME`.
DNS record at the domain provider: `CNAME  retire  ->  imetrobert.github.io`.
Settings -> Pages -> Source: "Deploy from a branch", main, /(root); then Enforce HTTPS.

## Privacy (what the app promises)
All figures stay in the browser (localStorage keys `csl_*`) or in a file the user saves. Nothing is
uploaded. `scripts/check_planner.py` fails if a network call is added. The only outside request is
the Google Fonts stylesheet. Saving profiles to an account is a separate, reviewed change.

## Access
Not gated yet: until the login gate ships, do not publish the address or turn on Pages. Gate plan:
Supabase login plus `has_app_access('retire-on')`, saved profiles encrypted in the browser.

## Files
- `index.html` the whole app. `CLAUDE.md` the map for editing. `docs/common-edits.md` recipes.
- `docs/code-map.md` generated line numbers. `scripts/check_planner.py`, `scripts/code_map.py`.
- `.github/workflows/checks.yml` weekly and on change: runs both scripts.

## Accounts and saved plans
Access is only for Robert (access.imetrobert.com, app id `retire-personal`; never grant anyone else). Signed-in users see "Welcome <email> to your retirement
planner" and a "My plans" button; each saved plan is encrypted in the browser with the user's own passphrase
(unrecoverable if forgotten). One-time setup: run `migration/planner_profiles.sql` via the Supabase AI assistant
(the file lives in the Quebec repo, `aiwithrobert-retireqc`).

## Working on this with the free version of Claude
The file is large, so free Claude must not read it whole. Start a chat with this message and attach nothing else:

> Open `CLAUDE.md` and `docs/common-edits.md` in the repo imetrobert/imetrobert-retire. I want to: <one change>. Follow the recipe, edit only the lines it names (use grep, never read index.html whole), run `python3 scripts/check_planner.py`, and tell me what to commit.

Tips: ask for ONE change per chat; use the GitHub web editor (pencil icon) for copy changes; the Checks tab on GitHub must be green after each push; `docs/code-map.md` gives line numbers so only a small slice is read.
