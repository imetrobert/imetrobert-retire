# If something breaks (read this first, then fix only what it names)

1. **A red check or an email from GitHub:** Actions tab, open the failed run, read the last 20 lines of the red step.
   - "Checks" red: run `python3 scripts/check_planner.py` and the `scripts/test_*.py` it names. A tax test failure means the tax numbers and the "2026 PARAMETERS" block in `scripts/test_tax.py` disagree: fix whichever is wrong against the official table, never both blindly.
   - "Build guide" red: open `docs/guide/README.md`; usually a markup slip in `docs/guide/en.md` (or `fr.md`). Re-run it by hand after "Guide screenshots".
   - "Pages build and deployment" red once: re-run the job; it is usually a transient GitHub error.
2. **Sign-in or "no access":** the person needs the app id (see CLAUDE.md) granted at access.imetrobert.com. Cloud plans need the passphrase (unrecoverable by design). A phone opened from the Home Screen may show an old version: reload in Safari.
3. **Wrong number in a result:** do not guess. Run `python3 scripts/test_tax.py`, then follow the "Tax numbers" recipe in `docs/common-edits.md`.
4. **English showing on the French page (Quebec only):** `python3 scripts/audit_french.py`, then the French gotchas in `docs/common-edits.md`.
5. **Site not loading or wrong address:** Settings > Pages (source `main`, custom domain from `CNAME`), then DNS CNAME to `imetrobert.github.io`.
6. Never put a real person's figures or a secret key in this repo (it is public).
