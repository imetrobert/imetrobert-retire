#!/usr/bin/env python3
"""Checks index.html (the whole planner). Exit 1 on any problem.
Run: python3 scripts/check_planner.py   (needs python3 and node)
1. every inline <script> passes `node --check`
2. APP_VERSION and the AI MAP comment exist
3. no duplicate element ids (the JS reads ids; a duplicate silently breaks a screen)
4. the privacy promise: no fetch/XMLHttpRequest/sendBeacon of user data (only the font links are allowed)
5. the "money in = money out" invariant string is still documented in the AI MAP
"""
import re, subprocess, sys, tempfile, os, collections

raw = open(os.path.join(os.path.dirname(__file__), '..', 'index.html'), encoding='utf-8').read()
html = raw
problems = []
# the AI MAP comment mentions <script>; remove comments before looking at markup
nocomment = re.sub(r'<!--.*?-->', '', raw, flags=re.S)

# 1. syntax of every inline script
scripts = re.findall(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', nocomment, re.S)
if not scripts:
    problems.append('no inline <script> found')
for i, s in enumerate(scripts):
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as f:
        f.write(s)
        name = f.name
    r = subprocess.run(['node', '--check', name], capture_output=True, text=True)
    os.unlink(name)
    if r.returncode:
        problems.append(f'script #{i+1} has a syntax error:\n{r.stderr.strip()[:600]}')

# 2. version and AI MAP
if not re.search(r"APP_VERSION\s*=\s*'[^']+'", raw):
    problems.append('APP_VERSION constant missing')
if 'AI MAP' not in raw[:400]:
    problems.append('AI MAP comment missing at the top of index.html')

# 3. duplicate ids (static markup only)
markup = re.sub(r'<script.*?</script>', '', nocomment, flags=re.S)
markup = re.sub(r'<style.*?</style>', '', markup, flags=re.S)
ids = re.findall(r'\sid="([^"]+)"', markup)
dups = [k for k, v in collections.Counter(ids).items() if v > 1]
if dups:
    problems.append('duplicate element ids: ' + ', '.join(sorted(dups)[:15]))

# 4. privacy promise: nothing sent anywhere
for pat in (r'\bfetch\s*\(', r'XMLHttpRequest', r'sendBeacon', r'WebSocket\s*\('):
    if re.search(pat, '\n'.join(scripts)):
        problems.append(f'network call found ({pat}). The privacy promise says nothing is uploaded; '
                        'saving to an account is a separate, reviewed change (see CLAUDE.md).')

# 5. invariant documented
if 'CHECK: money in' not in raw[:6000]:
    problems.append('the "CHECK: money in = ..." line is missing from the AI MAP')

if problems:
    print('FAILED')
    for p in problems:
        print('-', p)
    sys.exit(1)
print(f'OK: {len(scripts)} script(s) parse, {len(ids)} ids, no duplicates, no network calls.')

# --- account.js: the only file allowed to talk to a server ---
import os
if os.path.exists('account.js'):
    a = open('account.js', encoding='utf-8').read()
    import subprocess
    if subprocess.run(['node', '--check', 'account.js']).returncode:
        sys.exit('account.js has a syntax error')
    hosts = set(re.findall(r'https?://[^\s\'"`)]+', a))
    bad = [h for h in hosts if 'ipnajvgwtjrlecbqfwrh.supabase.co' not in h and 'example' not in h and not h.startswith('https://') or 'sb_secret' in h]
    if 'sb_secret' in a:
        sys.exit('account.js contains a secret key. Only the publishable key (sb_publishable_...) may appear.')
    if 'innerHTML' in a:
        sys.exit('account.js uses innerHTML. Build elements with el() so account data cannot inject markup.')
    print('OK: account.js parses, no secret key, no innerHTML.')

