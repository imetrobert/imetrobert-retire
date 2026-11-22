/* ==========================================================================
   account.js - sign-in gate + encrypted saved plans for the Personal Retirement Planner.
   Kept apart from index.html on purpose: the planner itself stays network-free
   (scripts/check_planner.py enforces that); everything that talks to the server is here.

   - Sign-in uses the shared Supabase project (same accounts as the other apps). The
     publishable key is public by design. Access = has_app_access('retire-personal'), granted at
     https://access.imetrobert.com.
   - Saved plans: each plan is encrypted IN THE BROWSER (AES-256-GCM, key from the user's own
     passphrase via PBKDF2-SHA256, 600,000 rounds) before it is sent. The server only ever holds
     ciphertext in table public.planner_profiles (one row per plan, rows visible only to their owner).
     We cannot recover a forgotten passphrase. Nothing is sent except sign-in and ciphertext.
   - Fails closed: index.html hides itself (class awr-locked) until this file has verified access.
   Edit here only for sign-in, access or saved-plan changes. Planner features belong in index.html.
   ========================================================================== */
(function () {
  'use strict';
  var CFG = {
    url: 'https://ipnajvgwtjrlecbqfwrh.supabase.co',
    key: 'sb_publishable_oPa7fZdSTeXKuCwpOF338Q_PcXS57go',
    app: 'retire-personal',
    name: 'Personal Retirement Planner',
    storageKey: 'awr_retirepersonal_auth',
    lsPrefix: 'csl',       // the planner's own localStorage prefix
    profileKey: 'csl_retire_profile_v2026',    // the planner's current-plan key
    profilesKey: 'csl_all_profiles_v2026',  // the planner's saved-plans list key
    langKey: '',       // where the planner keeps EN/FR ('' = English only)
    docs: '',                      // address of the documentation page; the link shows only when this is set
    fr: false
  };
  var KDF_ITER = 600000, AAD = new TextEncoder().encode('awr-account:1:' + CFG.app);
  var MAX_BLOB = 250000;

  /* ---------- text ---------- */
  var T = {
    en: {
      title: 'Sign in', sub: 'Access is by invitation. Use the email and password you set from your invitation.',
      email: 'Email', password: 'Password', signIn: 'Sign in', signingIn: 'Signing in…', signOut: 'Sign out',
      wrong: 'That email or password is not right.', noaccess: 'This account does not have access to this planner. Ask Robert to grant it.',
      offline: 'Cannot reach the sign-in service. Check your connection and try again.', revoked: 'Your session ended. Please sign in again.',
      error: 'Something went wrong. Please try again in a moment.', checking: 'Checking your access…', loadFail: 'Could not load sign-in. Check your connection and reload.',
      myPlans: 'My plans', close: 'Close', signedInAs: 'Signed in as',
      saveH: 'Save this plan to my account', saveHelp: 'Your plan is encrypted on this device before it is saved. Only your passphrase can open it, and it cannot be recovered if forgotten.',
      first: 'First time: choose a passphrase of at least 10 characters (a few words works well). You will need it on every device.',
      pass: 'Passphrase', pass2: 'Repeat the passphrase', unlock: 'Unlock my plans', saveBtn: 'Save this plan', lock: 'Lock',
      listH: 'My saved plans', none: 'No plans saved yet.', open: 'Open in the form', del: 'Delete', unnamed: 'Unnamed plan', savedOn: 'Saved',
      tooShort: 'The passphrase must be at least 10 characters.', mismatch: 'The two passphrases do not match.',
      badPass: 'Wrong passphrase, or a saved plan was damaged.', working: 'Working…', saved: 'Saved to your account.', unlocked: 'Unlocked.',
      deleted: 'Deleted.', opened: 'Plan opened in the form.', confirmDel: 'Delete this saved plan? This cannot be undone.',
      noCrypto: 'This browser cannot encrypt here. Open the page over https in a current browser.', saveFail: 'Could not save. Check your connection and try again.',
      soTitle: 'Sign out', soText: 'Do you also want to remove plans stored on this device?', soKeep: 'Sign out, keep device plans', soClear: 'Sign out and clear device plans', cancel: 'Cancel',
      welcome: 'Welcome {email} to your retirement planner', docsLink: 'Read the documentation',
      loggedIn: 'Logged in as {email}', docsMenu: 'Documentation', docsSub: 'User guide (PDF)', plansSub: 'Saved to your account, encrypted',
      lang: 'Français'
    },
    fr: {
      title: 'Connexion', sub: 'L’accès se fait sur invitation. Utilisez le courriel et le mot de passe définis depuis votre invitation.',
      email: 'Courriel', password: 'Mot de passe', signIn: 'Se connecter', signingIn: 'Connexion…', signOut: 'Se déconnecter',
      wrong: 'Ce courriel ou ce mot de passe n’est pas correct.', noaccess: 'Ce compte n’a pas accès à ce planificateur. Demandez à Robert de l’autoriser.',
      offline: 'Impossible de joindre le service de connexion. Vérifiez votre connexion et réessayez.', revoked: 'Votre session est terminée. Veuillez vous reconnecter.',
      error: 'Une erreur est survenue. Réessayez dans un instant.', checking: 'Vérification de votre accès…', loadFail: 'Impossible de charger la connexion. Vérifiez votre connexion et rechargez la page.',
      myPlans: 'Mes plans', close: 'Fermer', signedInAs: 'Connecté en tant que',
      saveH: 'Enregistrer ce plan dans mon compte', saveHelp: 'Votre plan est chiffré sur cet appareil avant d’être enregistré. Seule votre phrase secrète peut l’ouvrir, et elle ne peut pas être récupérée si elle est oubliée.',
      first: 'Première fois : choisissez une phrase secrète d’au moins 10 caractères (quelques mots suffisent). Vous en aurez besoin sur chaque appareil.',
      pass: 'Phrase secrète', pass2: 'Répétez la phrase secrète', unlock: 'Déverrouiller mes plans', saveBtn: 'Enregistrer ce plan', lock: 'Verrouiller',
      listH: 'Mes plans enregistrés', none: 'Aucun plan enregistré pour le moment.', open: 'Ouvrir dans le formulaire', del: 'Supprimer', unnamed: 'Plan sans nom', savedOn: 'Enregistré',
      tooShort: 'La phrase secrète doit contenir au moins 10 caractères.', mismatch: 'Les deux phrases secrètes ne correspondent pas.',
      badPass: 'Phrase secrète incorrecte, ou un plan enregistré est endommagé.', working: 'En cours…', saved: 'Enregistré dans votre compte.', unlocked: 'Déverrouillé.',
      deleted: 'Supprimé.', opened: 'Plan ouvert dans le formulaire.', confirmDel: 'Supprimer ce plan enregistré ? Cette action est irréversible.',
      noCrypto: 'Ce navigateur ne peut pas chiffrer ici. Ouvrez la page en https dans un navigateur récent.', saveFail: 'Enregistrement impossible. Vérifiez votre connexion et réessayez.',
      soTitle: 'Se déconnecter', soText: 'Voulez-vous aussi supprimer les plans conservés sur cet appareil ?', soKeep: 'Se déconnecter, garder les plans de l’appareil', soClear: 'Se déconnecter et effacer les plans de l’appareil', cancel: 'Annuler',
      welcome: 'Bienvenue {email} dans votre planificateur de retraite', docsLink: 'Lire la documentation',
      loggedIn: 'Connecté en tant que {email}', docsMenu: 'Documentation', docsSub: 'Guide de l’utilisateur (PDF)', plansSub: 'Enregistrés dans votre compte, chiffrés',
      lang: 'English'
    }
  };
  function lang() { try { return (CFG.fr && CFG.langKey && localStorage.getItem(CFG.langKey) === 'fr') ? 'fr' : 'en'; } catch (e) { return 'en'; } }
  function t(k) { return (T[lang()] && T[lang()][k]) || T.en[k] || k; }

  /* ---------- tiny DOM helper (text only, so data can never become markup) ---------- */
  function el(tag, attrs, kids) {
    var n = document.createElement(tag), k;
    for (k in (attrs || {})) {
      if (k === 'class') n.className = attrs[k];
      else if (k.slice(0, 2) === 'on') n.addEventListener(k.slice(2), attrs[k]);
      else n.setAttribute(k, attrs[k]);
    }
    (kids || []).forEach(function (c) { if (c != null) n.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
    return n;
  }

  /* ---------- styles ---------- */
  var css = '#awr-gate,#awr-panel{position:fixed;inset:0;z-index:2147483000;display:flex;align-items:center;justify-content:center;padding:16px;background:rgba(15,23,42,.72);font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif}' +
    '#awr-gate{background:#f1f5f9}' +
    '.awr-card{background:#fff;color:#0f172a;border-radius:14px;box-shadow:0 10px 40px rgba(0,0,0,.25);width:100%;max-width:440px;max-height:92vh;overflow:auto;padding:22px;box-sizing:border-box}' +
    '.awr-card h2{margin:0 0 6px;font-size:20px}.awr-card h3{margin:18px 0 6px;font-size:15px}.awr-card p{margin:6px 0;font-size:14px;line-height:1.45;color:#334155}' +
    '.awr-card label{display:block;margin:12px 0 4px;font-size:13px;font-weight:600}' +
    '.awr-card input{width:100%;box-sizing:border-box;padding:11px;border:1px solid #cbd5e1;border-radius:8px;font-size:16px}' +
    '.awr-btn{display:inline-block;margin:10px 8px 0 0;padding:11px 16px;border:0;border-radius:8px;background:#003DA5;color:#fff;font-size:15px;font-weight:600;cursor:pointer}' +
    '.awr-btn.sec{background:#e2e8f0;color:#0f172a}.awr-btn.bad{background:#b91c1c}.awr-btn[disabled]{opacity:.55;cursor:default}' +
    '.awr-msg{margin-top:10px;font-size:14px;min-height:18px}.awr-msg.bad{color:#b91c1c}.awr-msg.good{color:#166534}' +
    '.awr-row{border:1px solid #e2e8f0;border-radius:10px;padding:10px;margin:8px 0}.awr-row small{color:#475569}' +
    '#awr-pill{position:fixed;right:12px;bottom:calc(12px + env(safe-area-inset-bottom,0px));z-index:2147482000;padding:10px 14px;border:0;border-radius:999px;background:#003DA5;color:#fff;font-size:14px;font-weight:600;box-shadow:0 4px 14px rgba(0,0,0,.3);cursor:pointer}' +
    '#awr-welcome{position:relative;z-index:2147481000;background:#003DA5;color:#fff;padding:10px 40px 10px 14px;font:14px/1.4 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}#awr-welcome a{color:#fff;margin-left:10px;font-weight:600}#awr-welcome button{position:absolute;right:8px;top:6px;background:none;border:0;color:#fff;font-size:20px;cursor:pointer}' +
    '.awr-link{background:none;border:0;color:#003DA5;font-size:13px;text-decoration:underline;cursor:pointer;padding:6px 0}';
  document.head.appendChild(el('style', { id: 'awr-style' }, [css]));

  /* ---------- server calls ---------- */
  var S = { sess: null };
  function load() { try { return JSON.parse(localStorage.getItem(CFG.storageKey) || 'null'); } catch (e) { return null; } }
  function save(v) { try { localStorage.setItem(CFG.storageKey, JSON.stringify(v)); } catch (e) {} }
  function clear() { try { localStorage.removeItem(CFG.storageKey); } catch (e) {} }
  function mk(j, email) { return { access: j.access_token, refresh: j.refresh_token, expires: Date.now() + (j.expires_in || 3600) * 1000, email: email || (j.user && j.user.email) || '' }; }
  function call(method, path, body, token, extra) {
    var c = new AbortController(), to = setTimeout(function () { c.abort(); }, 15000);
    var headers = { apikey: CFG.key, 'Content-Type': 'application/json' };
    if (token) headers.Authorization = 'Bearer ' + token;
    if (extra) for (var k in extra) headers[k] = extra[k];
    return fetch(CFG.url + path, { method: method, headers: headers, body: body == null ? undefined : JSON.stringify(body), signal: c.signal })
      .then(function (r) { return r.text().then(function (txt) { var j = null; try { j = txt ? JSON.parse(txt) : null; } catch (e) {} return { ok: r.ok, status: r.status, json: j }; }); })
      .then(function (x) { clearTimeout(to); return x; }, function (e) { clearTimeout(to); throw e; });
  }
  function hasAccess(token) {
    return call('POST', '/rest/v1/rpc/has_app_access', { app_name: CFG.app }, token).then(function (r) {
      if (r.ok) return r.json === true; return r.status === 401 ? 'expired' : 'error';
    });
  }
  function refresh() {
    var s = S.sess; if (!s) return Promise.resolve('revoked');
    return call('POST', '/auth/v1/token?grant_type=refresh_token', { refresh_token: s.refresh }).then(function (r) {
      if (!r.ok) return r.status >= 500 ? 'error' : 'revoked';
      S.sess = mk(r.json, s.email); save(S.sess); return 'ok';
    });
  }
  /* returns a valid access token or throws 'revoked' / 'offline' */
  function token() {
    var s = S.sess; if (!s) return Promise.reject('revoked');
    if (s.expires > Date.now() + 60000) return Promise.resolve(s.access);
    return refresh().then(function (x) { if (x === 'ok') return S.sess.access; throw (x === 'revoked' ? 'revoked' : 'offline'); });
  }
  function signIn(email, pw) {
    return call('POST', '/auth/v1/token?grant_type=password', { email: email, password: pw }).then(function (r) {
      if (!r.ok) return r.status >= 500 ? 'error' : 'wrong';
      return hasAccess(r.json.access_token).then(function (ok) {
        if (ok !== true) return ok === false ? 'noaccess' : 'error';
        S.sess = mk(r.json, email); save(S.sess); return 'ok';
      });
    }, function () { return 'offline'; });
  }
  function verify() {
    S.sess = load(); if (!S.sess) return Promise.resolve('revoked');
    return token().then(function (tk) { return hasAccess(tk); }).then(function (ok) {
      if (ok === true) return 'ok';
      if (ok === false) { clear(); return 'noaccess'; }
      if (ok === 'expired') return refresh().then(function (x) { return x === 'ok' ? hasAccess(S.sess.access).then(function (y) { return y === true ? 'ok' : 'noaccess'; }) : x; });
      return 'error';
    }).catch(function (e) { if (e === 'revoked') { clear(); return 'revoked'; } return 'offline'; });
  }

  /* ---------- encryption (same parameters as the planner's own .file export) ---------- */
  function b64(buf) { var u = new Uint8Array(buf), s = ''; for (var i = 0; i < u.length; i += 0x8000) s += String.fromCharCode.apply(null, u.subarray(i, i + 0x8000)); return btoa(s); }
  function unb64(s) { var b = atob(s), u = new Uint8Array(b.length); for (var i = 0; i < b.length; i++) u[i] = b.charCodeAt(i); return u; }
  function cryptoOk() { return !!(window.crypto && crypto.subtle && window.isSecureContext !== false); }
  var keyCache = {};
  function deriveKey(pass, salt, iter) {
    var id = b64(salt) + ':' + iter + ':' + pass;
    if (keyCache[id]) return Promise.resolve(keyCache[id]);
    return crypto.subtle.importKey('raw', new TextEncoder().encode(pass.normalize('NFKC')), 'PBKDF2', false, ['deriveKey']).then(function (base) {
      return crypto.subtle.deriveKey({ name: 'PBKDF2', salt: salt, iterations: iter, hash: 'SHA-256' }, base, { name: 'AES-GCM', length: 256 }, false, ['encrypt', 'decrypt']);
    }).then(function (k) { keyCache[id] = k; return k; });
  }
  function encrypt(obj, pass, salt) {
    var iv = crypto.getRandomValues(new Uint8Array(12));
    return deriveKey(pass, salt, KDF_ITER).then(function (key) {
      return crypto.subtle.encrypt({ name: 'AES-GCM', iv: iv, additionalData: AAD }, key, new TextEncoder().encode(JSON.stringify(obj)));
    }).then(function (ct) { return JSON.stringify({ v: 1, kdf: 'PBKDF2-SHA256', iter: KDF_ITER, salt: b64(salt), iv: b64(iv), data: b64(ct) }); });
  }
  function decrypt(blob, pass) {
    var f; try { f = JSON.parse(blob); } catch (e) { return Promise.reject(new Error('format')); }
    if (!f || f.v !== 1 || !f.salt || !f.iv || !f.data) return Promise.reject(new Error('format'));
    var iter = Math.min(Math.max(parseInt(f.iter, 10) || KDF_ITER, 100000), 5000000);
    return deriveKey(pass, unb64(f.salt), iter).then(function (key) {
      return crypto.subtle.decrypt({ name: 'AES-GCM', iv: unb64(f.iv), additionalData: AAD }, key, unb64(f.data));
    }).then(function (pt) { return JSON.parse(new TextDecoder().decode(pt)); });
  }

  /* ---------- saved plans (rows of public.planner_profiles) ---------- */
  var V = { pass: null, rows: null, salt: null, haveRows: null };   // memory only
  function listRows() {
    return token().then(function (tk) {
      return call('GET', '/rest/v1/planner_profiles?app=eq.' + encodeURIComponent(CFG.app) + '&select=id,blob,updated_at&order=updated_at.desc', null, tk);
    }).then(function (r) { if (!r.ok) throw new Error('server'); return r.json || []; });
  }
  function unlockWith(pass, rows) {
    var out = [];
    return rows.reduce(function (p, row) {
      return p.then(function () { return decrypt(row.blob, pass).then(function (pl) { out.push({ rowId: row.id, updated: row.updated_at, p: pl.profile || {}, blob: row.blob }); }); });
    }, Promise.resolve()).then(function () { return out; });
  }
  function currentPlan() {
    var p = typeof getProfileData === 'function' ? getProfileData() : {};
    try { if (typeof resultsSummary === 'function') p.results = resultsSummary(); } catch (e) {}
    if (V.planId) p.id = V.planId;   // same plan keeps the same id, so saving again updates its row
    else if (!p.id) p.id = 'Profile_' + Date.now() + '_' + Math.random().toString(36).slice(2, 7);
    V.planId = p.id;
    return p;
  }
  function savePlan() {
    var p = currentPlan(), existing = (V.rows || []).filter(function (r) { return r.p && r.p.id === p.id; })[0];
    var salt = V.salt || crypto.getRandomValues(new Uint8Array(16));
    var payload = { format: 'awr-account', version: 1, app: CFG.app, savedAt: new Date().toISOString(), profile: p };
    return encrypt(payload, V.pass, salt).then(function (blob) {
      if (blob.length > MAX_BLOB) throw new Error('size');
      return token().then(function (tk) {
        if (existing) return call('PATCH', '/rest/v1/planner_profiles?id=eq.' + encodeURIComponent(existing.rowId), { blob: blob, updated_at: new Date().toISOString() }, tk, { Prefer: 'return=minimal' });
        return call('POST', '/rest/v1/planner_profiles', { app: CFG.app, blob: blob }, tk, { Prefer: 'return=minimal' });
      });
    }).then(function (r) { if (!r.ok) throw new Error('server'); });
  }
  function deleteRow(rowId) {
    return token().then(function (tk) { return call('DELETE', '/rest/v1/planner_profiles?id=eq.' + encodeURIComponent(rowId), null, tk); })
      .then(function (r) { if (!r.ok) throw new Error('server'); });
  }

  /* ---------- gate screen ---------- */
  function removeLock() { document.documentElement.classList.remove('awr-locked'); }
  function showGate(msgKey) {
    var g = document.getElementById('awr-gate'); if (g) g.remove();
    var email = el('input', { type: 'email', autocomplete: 'username', id: 'awr-email', inputmode: 'email' });
    var pw = el('input', { type: 'password', autocomplete: 'current-password', id: 'awr-pw' });
    var msg = el('div', { class: 'awr-msg bad', role: 'alert' }, [msgKey ? t(msgKey) : '']);
    var btn = el('button', { class: 'awr-btn', type: 'submit' }, [t('signIn')]);
    var form = el('form', { onsubmit: function (e) {
      e.preventDefault(); btn.disabled = true; btn.textContent = t('signingIn'); msg.textContent = '';
      signIn(email.value.trim(), pw.value).then(function (r) {
        if (r === 'ok') { g.remove(); unlocked(); } else { btn.disabled = false; btn.textContent = t('signIn'); msg.textContent = t(r); pw.value = ''; }
      });
    } }, [el('label', { for: 'awr-email' }, [t('email')]), email, el('label', { for: 'awr-pw' }, [t('password')]), pw, btn, msg]);
    var kids = [el('h2', {}, [CFG.name]), el('h3', {}, [t('title')]), el('p', {}, [t('sub')]), form];
    if (CFG.fr) kids.push(el('button', { class: 'awr-link', type: 'button', onclick: function () { try { localStorage.setItem(CFG.langKey, lang() === 'fr' ? 'en' : 'fr'); } catch (e) {} showGate(msgKey); } }, [t('lang')]));
    g = el('div', { id: 'awr-gate' }, [el('div', { class: 'awr-card' }, kids)]);
    document.body.appendChild(g);
  }
  function showChecking() {
    var g = document.getElementById('awr-gate'); if (g) g.remove();
    document.body.appendChild(el('div', { id: 'awr-gate' }, [el('div', { class: 'awr-card' }, [el('h2', {}, [CFG.name]), el('p', {}, [t('checking')])])]));
  }

  /* ---------- panel: My plans ---------- */
  function closePanel() { var p = document.getElementById('awr-panel'); if (p) p.remove(); }
  function say(node, text, cls) { node.className = 'awr-msg' + (cls ? ' ' + cls : ''); node.textContent = text; }
  function openPanel() {
    closePanel();
    var msg = el('div', { class: 'awr-msg', role: 'status' }), body = el('div'), card = el('div', { class: 'awr-card' });
    var panel = el('div', { id: 'awr-panel', onclick: function (e) { if (e.target === panel) closePanel(); } }, [card]);
    function render() {
      body.textContent = '';
      var first = V.haveRows === false && !V.pass;
      if (!V.pass) {
        body.appendChild(el('p', {}, [first ? t('first') : t('saveHelp')]));
        var p1 = el('input', { type: 'password', autocomplete: 'new-password', id: 'awr-p1' }), p2 = first ? el('input', { type: 'password', autocomplete: 'new-password', id: 'awr-p2' }) : null;
        body.appendChild(el('label', { for: 'awr-p1' }, [t('pass')])); body.appendChild(p1);
        if (p2) { body.appendChild(el('label', { for: 'awr-p2' }, [t('pass2')])); body.appendChild(p2); }
        var b = el('button', { class: 'awr-btn', type: 'button', onclick: function () {
          if (!cryptoOk()) { say(msg, t('noCrypto'), 'bad'); return; }
          if (p1.value.length < 10) { say(msg, t('tooShort'), 'bad'); return; }
          if (p2 && p1.value !== p2.value) { say(msg, t('mismatch'), 'bad'); return; }
          b.disabled = true; say(msg, t('working'));
          unlockWith(p1.value, V.rawRows || []).then(function (rows) {
            V.pass = p1.value; V.rows = rows; V.salt = rows.length ? unb64(JSON.parse(rows[0].blob).salt) : null; say(msg, t('unlocked'), 'good'); render();
          }).catch(function () { b.disabled = false; say(msg, t('badPass'), 'bad'); });
        } }, [t('unlock')]);
        body.appendChild(b);
        return;
      }
      body.appendChild(el('h3', {}, [t('saveH')]));
      var sb = el('button', { class: 'awr-btn', type: 'button', onclick: function () {
        sb.disabled = true; say(msg, t('working'));
        savePlan().then(function () { return listRows(); }).then(function (raw) { V.rawRows = raw; return unlockWith(V.pass, raw); }).then(function (rows) {
          V.rows = rows; V.haveRows = rows.length > 0; if (rows.length && !V.salt) V.salt = unb64(JSON.parse(rows[0].blob).salt); say(msg, t('saved'), 'good'); render();
        }).catch(function () { say(msg, t('saveFail'), 'bad'); render(); });
      } }, [t('saveBtn')]);
      body.appendChild(sb);
      body.appendChild(el('h3', {}, [t('listH')]));
      if (!V.rows.length) body.appendChild(el('p', {}, [t('none')]));
      V.rows.forEach(function (r) {
        var name = (r.p && r.p.name) || t('unnamed'), d = '';
        try { d = new Date(r.updated).toLocaleDateString(lang() === 'fr' ? 'fr-CA' : 'en-CA'); } catch (e) {}
        body.appendChild(el('div', { class: 'awr-row' }, [el('strong', {}, [name]), el('br'), el('small', {}, [t('savedOn') + ' ' + d]), el('br'),
          el('button', { class: 'awr-btn', type: 'button', onclick: function () { openPlan(r.p); closePanel(); } }, [t('open')]),
          el('button', { class: 'awr-btn sec bad', type: 'button', onclick: function () {
            if (!window.confirm(t('confirmDel'))) return;
            deleteRow(r.rowId).then(function () { V.rows = V.rows.filter(function (x) { return x.rowId !== r.rowId; }); V.haveRows = V.rows.length > 0; say(msg, t('deleted'), 'good'); render(); })
              .catch(function () { say(msg, t('saveFail'), 'bad'); });
          } }, [t('del')])]));
      });
      body.appendChild(el('button', { class: 'awr-btn sec', type: 'button', onclick: function () { V.pass = null; V.rows = null; V.salt = null; keyCache = {}; say(msg, ''); render(); } }, [t('lock')]));
    }
    card.appendChild(el('h2', {}, [t('myPlans')]));
    card.appendChild(el('p', {}, [t('signedInAs') + ' ' + ((S.sess && S.sess.email) || '')]));
    card.appendChild(body); card.appendChild(msg);
    card.appendChild(el('button', { class: 'awr-btn sec', type: 'button', onclick: closePanel }, [t('close')]));
    card.appendChild(el('button', { class: 'awr-btn sec', type: 'button', onclick: signOutDialog }, [t('signOut')]));
    document.body.appendChild(panel);
    if (V.rawRows == null) {
      say(msg, t('working'));
      listRows().then(function (raw) { V.rawRows = raw; V.haveRows = raw.length > 0; say(msg, ''); render(); }).catch(function () { say(msg, t('error'), 'bad'); });
    } else render();
  }
  function openPlan(p) {
    if (typeof populateForm !== 'function') return;
    V.planId = p.id || null;
    populateForm(p);
    try { localStorage.setItem(CFG.profileKey, JSON.stringify(p)); } catch (e) {}
    if (typeof showSaveBadge === 'function') showSaveBadge(t('opened'));
    if (typeof showStep === 'function') showStep(1);
  }
  function signOutDialog() {
    closePanel();
    function finish(clearDevice) {
      clear(); S.sess = null; V = { pass: null, rows: null, salt: null, haveRows: null, planId: null }; keyCache = {};
      if (clearDevice) { try { localStorage.removeItem(CFG.profileKey); localStorage.removeItem(CFG.profilesKey); } catch (e) {} }
      location.reload();
    }
    var panel = el('div', { id: 'awr-panel' }, [el('div', { class: 'awr-card' }, [el('h2', {}, [t('soTitle')]), el('p', {}, [t('soText')]),
      el('button', { class: 'awr-btn', type: 'button', onclick: function () { finish(false); } }, [t('soKeep')]),
      el('button', { class: 'awr-btn bad', type: 'button', onclick: function () { finish(true); } }, [t('soClear')]),
      el('button', { class: 'awr-btn sec', type: 'button', onclick: function () { panel.remove(); } }, [t('cancel')])])]);
    document.body.appendChild(panel);
  }

  function welcome() {
    if (document.getElementById('awr-welcome')) return;
    var em = (S.sess && S.sess.email) || '';
    var kids = [el('span', {}, [t('welcome').replace('{email}', em)])];
    if (CFG.docs) kids.push(el('a', { href: CFG.docs, target: '_blank', rel: 'noopener' }, [t('docsLink')]));
    kids.push(el('button', { type: 'button', 'aria-label': t('close'), onclick: function () { document.getElementById('awr-welcome').remove(); } }, ['×']));
    document.body.insertBefore(el('div', { id: 'awr-welcome' }, kids), document.body.firstChild);
  }
  /* The planner's own menu (#toolMenu): first row says who is logged in, plus My plans, Documentation, Sign out. */
  function refreshMenu() {
    var m = document.getElementById('toolMenu'); if (!m) return;
    var em = (S.sess && S.sess.email) || '';
    var who = document.getElementById('awr-who');
    if (!who) { who = el('div', { id: 'awr-who', class: 'menu-note', style: 'font-weight:600;word-break:break-all' }); m.insertBefore(who, m.firstChild); }
    who.textContent = t('loggedIn').replace('{email}', em);
    function mk(tag, id, ico, label, sub, attrs) {
      var a = attrs || {}; a.id = id; a.class = 'menu-item';
      return el(tag, a, [el('span', { class: 'mi-ico' }, [ico]), el('span', {}, [label, el('small', {}, [sub])])]);
    }
    ['awr-mi-plans', 'awr-mi-docs', 'awr-mi-out'].forEach(function (i) { var o = document.getElementById(i); if (o) o.remove(); });
    m.appendChild(mk('button', 'awr-mi-plans', '☁', t('myPlans'), t('plansSub'), { type: 'button', onclick: function () { if (typeof closeMenu === 'function') closeMenu(); openPanel(); } }));
    if (CFG.docs) m.appendChild(mk('a', 'awr-mi-docs', '📖', t('docsMenu'), t('docsSub'), { href: CFG.docs, target: '_blank', rel: 'noopener', style: 'text-decoration:none;color:inherit' }));
    m.appendChild(mk('button', 'awr-mi-out', '⎋', t('signOut'), (S.sess && S.sess.email) || '', { type: 'button', onclick: function () { if (typeof closeMenu === 'function') closeMenu(); signOutDialog(); } }));
  }
  function hookMenu() {
    ['menuBtn', 'langBtn'].forEach(function (id) {
      var b = document.getElementById(id);
      if (b) b.addEventListener('click', function () { setTimeout(refreshMenu, 0); setTimeout(refreshMenu, 300); });
    });
    refreshMenu();
  }
  function unlocked() {
    removeLock(); welcome(); hookMenu();
    if (!document.getElementById('awr-pill')) document.body.appendChild(el('button', { id: 'awr-pill', type: 'button', onclick: openPanel }, ['☁ ' + t('myPlans')]));
  }

  /* ---------- start ---------- */
  function boot() {
    if (!load()) { showGate(); return; }
    showChecking();
    verify().then(function (r) { var g = document.getElementById('awr-gate'); if (g) g.remove(); if (r === 'ok') unlocked(); else showGate(r); });
  }
  window.addEventListener('online', function () { if (document.documentElement.classList.contains('awr-locked') && load()) boot(); });
  window.AWR_ACCOUNT = { _test: { encrypt: encrypt, decrypt: decrypt } };   // for scripts/test_account.py only
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
