/* statements.js - read a government statement PDF inside the browser and fill planner fields.
 * PRIVACY: the PDF is read in memory on this device. NOTHING is uploaded, stored or logged.
 * This file must make NO network calls (scripts/check_planner.py enforces it). It only loads the
 * two self-hosted pdf.js files under vendor/pdfjs/, and only when a person picks a PDF.
 * How it works: pdf.js gives the text of each page with x/y positions. parseQpp() finds the
 * "Estimate of the amount of your retirement pension (monthly)" block (section A of the Retraite
 * Québec Statement of Participation), reads the dollar amounts per scenario and age, and the page
 * shows them in a Preview. Nothing changes until the person ticks one and taps Apply.
 * If the layout is not recognised, the "pick the number yourself" list shows every dollar amount.
 * Recipes: docs/common-edits.md ("Add a government statement"). Test: python3 scripts/test_statements.py
 */
(function () {
    'use strict';

    var PDFJS_SRC = 'vendor/pdfjs/pdf.min.js';
    var PDFJS_WORKER = 'vendor/pdfjs/pdf.worker.min.js';
    var MAX_PAGES = 6;
    var MIN_MONTHLY = 20, MAX_MONTHLY = 3000;   // plausible monthly QPP/CPP/OAS range; also filters out "3 500 $" (the yearly threshold)

    function isFr() { return !!(window.QCRP_I18N && window.QCRP_I18N.lang === 'fr'); }
    function norm(s) { return String(s).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase(); }
    function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }

    var TXT = {
        en: {
            sum: 'Read a government statement (Retraite Québec)',
            intro: 'Download your Statement of Participation as a PDF from Retraite Québec My Account, then choose it here. It is read on this device only; nothing is uploaded and nothing is saved. Your name and SIN are ignored.',
            file: 'Choose the PDF',
            forWho: 'This statement is for',
            me: 'me', spouse: 'my spouse',
            reading: 'Reading the PDF…',
            notPdf: 'That is not a PDF. Download the statement as a PDF from Retraite Québec My Account (a screenshot cannot be read yet).',
            noText: 'This PDF has no readable text (it may be a scan). Download the statement again from My Account, or use the pick-the-number list below if any numbers appear.',
            failed: 'Could not read that file. Try downloading the PDF again.',
            found: 'Found in your statement: estimated monthly retirement pension. Tick the one to use.',
            notFound: 'I could not recognise the layout of this statement. Nothing was filled in. Use the list below to pick the right number yourself.',
            rowContinue: 'If you continue to make contributions',
            rowStopped: 'If you stopped making contributions today',
            rowOther: 'Another estimate',
            age: 'age', perMonth: '/ month',
            only65: 'The planner asks for the age-65 amount and adjusts for your start age itself, so only age 65 can be applied from this table.',
            willSet: 'Will set “QPP per month at 65” (yours)',
            willSetSp: 'Will set “Spouse QPP per month at 65”',
            willSetFor: 'Will set the QPP per month at 65 for {n}',
            now: 'now', apply: 'Apply', applied: 'Applied. Review it in step 2, then calculate.',
            pickTitle: 'Not right? Pick the number yourself',
            pickHelp: 'Every dollar amount found in the PDF, with the words next to it. Tap the one that is the monthly pension at age 65.',
            pickNone: 'No dollar amounts were found.',
            page: 'page',
            privacy: 'Privacy: the file never leaves this page. Always check the number against your statement before relying on it.',
            needSpouse: 'Switch “Who is this plan for?” to couple mode to apply a spouse statement.',
            pubFound: 'Found: public-sector pension statement (RREGOP and similar). Yearly pension estimates. Tick the one to use.',
            pubEarly: 'At the earliest possible retirement date',
            pubUnred: 'At the earliest date for an unreduced pension',
            pub65: 'At age 65',
            pubUntil: 'payable until 65', pubFrom: 'payable from 65', pubYear: '/ year',
            pubWill: 'Will set “Pension per year” and “Starts at age” in your employer pension (yours only)',
            pubSpouse: 'Spouse pension statements cannot be applied yet. Use “me”, or enter the spouse figures by hand.',
            pubIdx: 'Check “Rises with inflation (%)” yourself: your statement’s Information Sheet gives the indexation.'
        },
        fr: {
            sum: 'Lire un relevé gouvernemental (Retraite Québec)',
            intro: 'Téléchargez votre relevé de participation en PDF depuis Mon dossier de Retraite Québec, puis choisissez-le ici. Il est lu sur cet appareil seulement; rien n’est envoyé ni enregistré. Votre nom et votre NAS sont ignorés.',
            file: 'Choisir le PDF',
            forWho: 'Ce relevé est celui de',
            me: 'moi', spouse: 'mon conjoint ou ma conjointe',
            reading: 'Lecture du PDF…',
            notPdf: 'Ce n’est pas un PDF. Téléchargez le relevé en PDF depuis Mon dossier de Retraite Québec (une capture d’écran ne peut pas encore être lue).',
            noText: 'Ce PDF ne contient pas de texte lisible (c’est peut-être une numérisation). Téléchargez de nouveau le relevé depuis Mon dossier, ou utilisez la liste ci-dessous si des montants apparaissent.',
            failed: 'Impossible de lire ce fichier. Essayez de télécharger de nouveau le PDF.',
            found: 'Trouvé dans votre relevé : estimation de la rente de retraite mensuelle. Cochez celle à utiliser.',
            notFound: 'Je n’ai pas reconnu la mise en page de ce relevé. Rien n’a été rempli. Utilisez la liste ci-dessous pour choisir vous-même le bon montant.',
            rowContinue: 'Si vous continuez de cotiser',
            rowStopped: 'Si vous cessiez de cotiser aujourd’hui',
            rowOther: 'Autre estimation',
            age: 'âge', perMonth: '/ mois',
            only65: 'Le planificateur demande le montant à 65 ans et ajuste lui-même selon votre âge de début; seul le montant à 65 ans peut donc être appliqué depuis ce tableau.',
            willSet: 'Remplira « RRQ mensuelle à 65 ans » (la vôtre)',
            willSetSp: 'Remplira « RRQ mensuelle du/de la conjoint(e) à 65 ans »',
            willSetFor: 'Remplira la RRQ mensuelle à 65 ans de {n}',
            now: 'actuel', apply: 'Appliquer', applied: 'Appliqué. Vérifiez à l’étape 2, puis calculez.',
            pickTitle: 'Ce n’est pas ça? Choisissez le montant vous-même',
            pickHelp: 'Tous les montants en dollars trouvés dans le PDF, avec les mots à côté. Touchez celui qui est la rente mensuelle à 65 ans.',
            pickNone: 'Aucun montant en dollars trouvé.',
            page: 'page',
            privacy: 'Confidentialité : le fichier ne quitte jamais cette page. Vérifiez toujours le montant avec votre relevé avant de vous y fier.',
            needSpouse: 'Passez « Planification pour » en mode couple pour appliquer le relevé d’un(e) conjoint(e).',
            pubFound: 'Trouvé : relevé de participation à un régime de retraite du secteur public (RREGOP et autres). Rentes annuelles estimées. Cochez celle à utiliser.',
            pubEarly: 'À la date de retraite la plus rapprochée',
            pubUnred: 'À la première date d’une rente sans réduction',
            pub65: 'À 65 ans',
            pubUntil: 'payable jusqu’à 65 ans', pubFrom: 'payable dès 65 ans', pubYear: '/ an',
            pubWill: 'Remplira « Pension par année » et « Commence à l’âge de » dans votre pension d’employeur (la vôtre seulement)',
            pubSpouse: 'Les relevés de pension d’un(e) conjoint(e) ne peuvent pas encore être appliqués. Choisissez « moi » ou entrez les chiffres à la main.',
            pubIdx: 'Vérifiez vous-même « Indexation (%) » : la feuille d’information de votre relevé donne l’indexation.'
        }
    };
    function t(k) { return (isFr() ? TXT.fr : TXT.en)[k]; }

    /* ---------- pdf.js loading (self-hosted, on demand) ---------- */
    var pdfjsPromise = null;
    function loadPdfJs() {
        if (window.pdfjsLib) return Promise.resolve(window.pdfjsLib);
        if (pdfjsPromise) return pdfjsPromise;
        pdfjsPromise = new Promise(function (resolve, reject) {
            var s = document.createElement('script');
            s.src = PDFJS_SRC;
            s.onload = function () {
                if (!window.pdfjsLib) { reject(new Error('pdfjs missing')); return; }
                window.pdfjsLib.GlobalWorkerOptions.workerSrc = PDFJS_WORKER;
                resolve(window.pdfjsLib);
            };
            s.onerror = function () { pdfjsPromise = null; reject(new Error('pdfjs load failed')); };
            document.head.appendChild(s);
        });
        return pdfjsPromise;
    }

    function readPages(buf) {
        return loadPdfJs().then(function (lib) {
            return lib.getDocument({ data: buf, isEvalSupported: false }).promise;
        }).then(function (pdf) {
            var n = Math.min(pdf.numPages, MAX_PAGES), jobs = [];
            for (var i = 1; i <= n; i++) {
                (function (p) {
                    jobs.push(pdf.getPage(p).then(function (pg) { return pg.getTextContent(); }).then(function (tc) {
                        return { page: p, tokens: tokenize(tc.items) };
                    }));
                })(i);
            }
            return Promise.all(jobs);
        });
    }

    /* ---------- tokens: merge neighbouring text pieces on the same line ---------- */
    function tokenize(items) {
        var its = [];
        items.forEach(function (i) {
            if (!i || typeof i.str !== 'string' || !i.str.trim()) return;
            its.push({ s: i.str.trim(), x: i.transform[4], y: i.transform[5], w: i.width || 0 });
        });
        its.sort(function (a, b) { return b.y - a.y; });
        var lines = [];
        its.forEach(function (it) {
            var ln = lines.length ? lines[lines.length - 1] : null;
            if (ln && Math.abs(ln.y - it.y) <= 2.5) ln.items.push(it); else lines.push({ y: it.y, items: [it] });
        });
        var out = [];
        lines.forEach(function (ln) {
            ln.items.sort(function (a, b) { return a.x - b.x; });
            var cur = null;
            ln.items.forEach(function (it) {
                if (cur && it.x - (cur.x + cur.w) < (it.s === '$' ? 12 : 4.5)) { cur.s += ' ' + it.s; cur.w = (it.x + it.w) - cur.x; }
                else { cur = { s: it.s, x: it.x, y: ln.y, w: it.w }; out.push(cur); }
            });
        });
        return out;
    }

    /* ---------- amounts ---------- */
    var AMT = /^(?:\$\s*)?(\d{1,3}(?:[   ,]\d{3})+|\d+)(?:[.,](\d{2}))?\s*\$?$/;
    function parseAmount(s) {
        if (s.indexOf('$') < 0) return null;
        var m = AMT.exec(s.trim());
        if (!m) return null;
        var whole = m[1].replace(/[   ,]/g, '');
        var v = parseFloat(whole + (m[2] ? '.' + m[2] : ''));
        return isFinite(v) ? v : null;
    }
    function ageOf(s) {
        var m = /^(?:age|a)?\s*(\d{2})\s*(?:ans|years?)?$/.exec(norm(s).trim());
        if (!m) return null;
        var n = parseInt(m[1], 10);
        return (n >= 55 && n <= 75) ? n : null;
    }

    function ageIn(s) {   // "Age 61", "61 ans", also inside longer text
        var m = /\b(?:age|a)\s*(\d{2})\b|\b(\d{2})\s*ans\b/.exec(norm(s));
        var n = m ? parseInt(m[1] || m[2], 10) : NaN;
        return (n >= 50 && n <= 75) ? n : null;
    }

    /* ---------- QPP statement, section A ---------- */
    var START_RX = /estimate of the amount of your retirement pension|estimation du montant de (?:votre|la) rente de retraite|montant de votre rente de retraite/;
    var END_RX = /pensionable earnings|revenus de travail admissibles|in the event of disability|en cas d.invalidite|your benefits are calculated|vos prestations sont calculees/;
    var KIND_CONT = /continue|continu|poursui/;
    var KIND_STOP = /stopped|cess|arret|plus de cotisation|do not make any more/;

    function parseQpp(pages) {
        var res = { recognised: false, rows: [] };
        for (var pi = 0; pi < pages.length; pi++) {
            var toks = pages[pi].tokens, startY = null, endY = -Infinity;
            toks.forEach(function (k) { if (startY === null && START_RX.test(norm(k.s))) startY = k.y; });
            if (startY === null) continue;
            toks.forEach(function (k) { if (k.y < startY - 2 && END_RX.test(norm(k.s)) && k.y > endY) endY = k.y; });
            var region = toks.filter(function (k) { return k.y < startY - 2 && k.y > endY; });
            var amts = [];
            region.forEach(function (k) {
                var v = parseAmount(k.s);
                if (v !== null && v >= MIN_MONTHLY && v <= MAX_MONTHLY) amts.push({ v: v, x: k.x + k.w / 2, y: k.y });
            });
            if (!amts.length) continue;
            amts.sort(function (a, b) { return b.y - a.y; });
            var rows = [];
            amts.forEach(function (a) {
                var r = rows.length ? rows[rows.length - 1] : null;
                if (r && Math.abs(r.y - a.y) <= 6) r.items.push(a); else rows.push({ y: a.y, items: [a] });
            });
            var ages = [];
            region.forEach(function (k) { var a = ageOf(k.s); if (a) ages.push({ a: a, x: k.x + k.w / 2, y: k.y }); });
            var labels = [];
            region.forEach(function (k) {
                var n = norm(k.s), kind = null;
                if (KIND_STOP.test(n)) kind = 'stopped'; else if (KIND_CONT.test(n)) kind = 'continue';
                if (kind) labels.push({ kind: kind, x: k.x, y: k.y });
            });
            rows.forEach(function (r, idx) {
                r.items.sort(function (a, b) { return a.x - b.x; });
                var best = null;
                labels.forEach(function (l) {
                    var d = Math.abs(l.y - r.y);
                    if (d <= 70 && (!best || l.x < best.l.x - 1 || (Math.abs(l.x - best.l.x) <= 1 && d < best.d))) best = { l: l, d: d };
                });
                var kind = best ? best.l.kind : (idx === 0 ? 'continue' : (idx === 1 ? 'stopped' : 'other'));
                var defaults = [60, 65, 70];
                var list = r.items.map(function (a, i) {
                    var near = null;
                    ages.forEach(function (g) {
                        var dx = Math.abs(g.x - a.x);
                        if (g.y < a.y && a.y - g.y < 60 && dx < 45 && (!near || dx < near.dx)) near = { age: g.a, dx: dx };
                    });
                    return { age: near ? near.age : defaults[i], value: a.v, guessedAge: !near, page: pages[pi].page };
                });
                res.rows.push({ kind: kind, amounts: list });
            });
            res.recognised = res.rows.length > 0;
            break;
        }
        return res;
    }


    /* ---------- public-sector pension statement (RREGOP and similar): yearly estimates by scenario ---------- */
    var PUB_SCEN = [
        { id: 'early', rx: /earliest possible|plus tot possible|plus rapprochee/, tx: 'pubEarly' },
        { id: 'unreduced', rx: /unreduced|sans reduction/, tx: 'pubUnred' },
        { id: 'age65', rx: /^at age 65|^a 65 ans/, tx: 'pub65' }
    ];
    var PUB_UNTIL = /payable until age 65|payable jusqu/, PUB_FROM = /payable as of age 65|payable des 65|payable a compter/;
    var MIN_YEARLY = 1000, MAX_YEARLY = 400000;

    function parsePublic(pages) {
        var res = { recognised: false, rows: [] };
        for (var pi = 0; pi < pages.length; pi++) {
            var toks = pages[pi].tokens, labs = [];
            toks.forEach(function (k) {
                var n = norm(k.s);
                for (var i = 0; i < PUB_SCEN.length; i++) {
                    if (PUB_SCEN[i].rx.test(n) && !PUB_UNTIL.test(n) && !PUB_FROM.test(n)) {
                        if (!labs.some(function (l) { return l.id === PUB_SCEN[i].id; })) labs.push({ id: PUB_SCEN[i].id, tx: PUB_SCEN[i].tx, x: k.x, y: k.y });
                        break;
                    }
                }
            });
            if (labs.length < 2) continue;
            labs.sort(function (a, b) { return b.y - a.y; });
            var hUntil = null, hFrom = null;
            toks.forEach(function (k) { var n = norm(k.s); if (PUB_UNTIL.test(n)) hUntil = k; else if (PUB_FROM.test(n)) hFrom = k; });
            labs.forEach(function (l, i) {
                var top = l.y + 14, bottom = (i + 1 < labs.length) ? labs[i + 1].y + 14 : l.y - 90;
                var found = [], age = null;
                toks.forEach(function (k) {
                    if (k.y > top || k.y <= bottom) return;
                    var v = parseAmount(k.s);
                    if (v !== null && v >= MIN_YEARLY && v <= MAX_YEARLY) found.push({ v: v, x: k.x + k.w / 2 });
                    var a = ageOf(k.s) || ageIn(k.s); if (a && !age) age = a;
                });
                if (!found.length) return;
                found.sort(function (a, b) { return a.x - b.x; });
                var cols = found.map(function (f, ci) {
                    var kind = 'plain';
                    if (hUntil && hFrom) kind = Math.abs(f.x - (hUntil.x + hUntil.w / 2)) <= Math.abs(f.x - (hFrom.x + hFrom.w / 2)) ? 'until' : 'from';
                    else if (found.length === 2) kind = ci === 0 ? 'until' : 'from';
                    return { value: f.v, kind: kind };
                });
                res.rows.push({ id: l.id, tx: l.tx, age: l.id === 'age65' ? 65 : age, cols: cols });
            });
            res.recognised = res.rows.length > 0;
            break;
        }
        return res;
    }

    /* every plausible dollar amount (also inside longer text such as "Monthly benefit: 612 $"),
       with the words nearby: the "pick the number yourself" fallback */
    var AMT_IN = /(\d{1,3}(?:[ \u00a0\u202f,]\d{3})+|\d+)(?:[.,](\d{2}))?\s*\$/g;
    function allAmounts(pages) {
        var out = [], seen = {};
        pages.forEach(function (pg) {
            pg.tokens.forEach(function (k) {
                var m, rx = new RegExp(AMT_IN.source, 'g');
                while ((m = rx.exec(k.s)) !== null) {
                    var v = parseFloat(m[1].replace(/[ \u00a0\u202f,]/g, '') + (m[2] ? '.' + m[2] : ''));
                    if (!isFinite(v) || v < MIN_MONTHLY || v > MAX_MONTHLY) continue;
                    var own = k.s.replace(m[0], '').replace(/\s+/g, ' ').trim();
                    var near = pg.tokens.filter(function (o) {
                        return o !== k && !/\d\s*\$/.test(o.s) && Math.abs(o.y - k.y) <= 30 && Math.abs(o.x - k.x) <= 150;
                    }).sort(function (a, b) { return Math.abs(a.y - k.y) - Math.abs(b.y - k.y) || a.x - b.x; })
                      .slice(0, 3).map(function (o) { return o.s; });
                    var ctx = (own ? [own].concat(near) : near).join(' · ');
                    var key = pg.page + '|' + v + '|' + Math.round(k.x) + '|' + Math.round(k.y);
                    if (seen[key]) continue; seen[key] = 1;
                    out.push({ value: v, ctx: ctx.slice(0, 90), page: pg.page });
                }
            });
        });
        return out.slice(0, 40);
    }

    /* ---------- page ---------- */
    var state = null;   // { parsed, picks, forWho }
    var mounted = false;

    function fmt(v) {
        var s = (Math.round(v * 100) / 100).toLocaleString(isFr() ? 'fr-CA' : 'en-CA', { minimumFractionDigits: 0, maximumFractionDigits: 2 });
        return isFr() ? s + ' $' : '$' + s;
    }
    function targetId(forWho) { return (forWho === 'spouse' && !hhOn()) ? 'spouseQppMonthlyAmt' : 'qppMonthlyAmt'; }
    // couple (household) mode: each person has their own form; a statement can be filed for the person on screen or for the other one
    function hhOn() { return isCouple() && typeof HH !== 'undefined' && !!HH; }
    function openWho() { return (hhOn() && HH.who === 'spouse') ? 'spouse' : 'me'; }
    function whoName(w) { try { if (typeof hhLabel === 'function') return hhLabel(w === 'spouse' ? 'sp' : 'me'); } catch (e) { /* ignore */ } return w === 'spouse' ? t('spouse') : t('me'); }
    function storedOnly(w) { return hhOn() && w !== openWho(); }   // the chosen person's form is not the one on screen
    function storedProfile(w) { if (w === 'spouse' && !HH.spouse && typeof hhEnsureSpouse === 'function') hhEnsureSpouse(); return w === 'spouse' ? HH.spouse : HH.me; }
    function whoBlock() {
        if (!hhOn()) return '';
        var w = (state && state.forWho) || openWho();
        function row(v) { return '<label class="ai-row"><input type="radio" name="stmtWho" value="' + v + '"' + (w === v ? ' checked' : '') + ' style="width:auto;margin:0 0.5rem 0 0"><span class="ai-lbl">' + esc(whoName(v)) + '</span></label>'; }
        return '<div id="stmtWho" style="margin:0.5rem 0"><div style="font-weight:600">' + esc(t('forWho')) + '</div>' + row('me') + row('spouse') + '</div>';
    }
    function isCouple() { var m = document.getElementById('calcMode'); return !!m && m.value === 'couple'; }
    function alreadyRetired() { var r = document.getElementById('alreadyRetired'); return !!(r && r.checked); }

    function render() {
        var sum = document.getElementById('stmtSum'), body = document.getElementById('stmtBody');
        if (!sum || !body) return;
        sum.textContent = t('sum');
        var keepFile = document.getElementById('stmtFile');
        var h = '<p style="margin:0 0 0.5rem;font-size:0.85rem;color:var(--medium-gray)">' + esc(t('intro')) + '</p>' +
            '<label for="stmtFile" style="font-weight:600">' + esc(t('file')) + '</label>' +
            '<div id="stmtFileSlot"></div>' +
            '<div id="stmtOut" aria-live="polite"></div>' +
            '<p style="margin:0.6rem 0 0;font-size:0.76rem">' + esc(t('privacy')) + '</p>';
        body.innerHTML = h;
        var slot = document.getElementById('stmtFileSlot');
        if (keepFile) slot.appendChild(keepFile);
        else {
            var inp = document.createElement('input');
            inp.type = 'file'; inp.id = 'stmtFile'; inp.accept = '.pdf,application/pdf';
            inp.addEventListener('change', onFile);
            slot.appendChild(inp);
        }
        renderResult();
    }

    function msg(cls, text) { return '<div class="ai-msg ' + cls + '">' + esc(text) + '</div>'; }

    function renderResult() {
        var out = document.getElementById('stmtOut');
        if (!out) return;
        if (!state) { out.innerHTML = ''; return; }
        if (state.error) { out.innerHTML = msg('bad', t(state.error)); if (state.picks && state.picks.length) out.innerHTML += pickList(); return; }
        var h = '';
        var p = state.parsed;
        if (p && p.recognised) {
            h += msg('', t('found'));
            h += '<div class="ai-table">';
            p.rows.forEach(function (r, ri) {
                var label = r.kind === 'continue' ? t('rowContinue') : (r.kind === 'stopped' ? t('rowStopped') : t('rowOther'));
                h += '<div style="font-weight:600;margin:0.4rem 0 0.1rem">' + esc(label) + '</div>';
                r.amounts.forEach(function (a, ai) {
                    var ok = (a.age === 65);
                    var id = 'stmtPick_' + ri + '_' + ai;
                    var def = ok && ((r.kind === 'continue' && !alreadyRetired()) || (r.kind === 'stopped' && alreadyRetired()));
                    h += '<label class="ai-row" style="opacity:' + (ok ? 1 : 0.55) + '"><input type="radio" name="stmtChoice" id="' + id + '" data-v="' + a.value + '"' + (ok ? '' : ' disabled') + (def ? ' checked' : '') + '>' +
                        '<span class="ai-lbl">' + esc(t('age')) + ' ' + a.age + (a.guessedAge ? ' ?' : '') + '</span><strong class="ai-new">' + esc(fmt(a.value)) + ' ' + esc(t('perMonth')) + '</strong></label>';
                });
            });
            h += '</div>' + msg('note', t('only65'));
            h += applyBlock();
        } else if (!(state.pub && state.pub.recognised && document.getElementById('ownPensionAnnual'))) {
            h += msg('bad', t('notFound'));
        }
        h += pubBlock();
        h += pickList();
        out.innerHTML = whoBlock() + h;
        var radios = out.querySelectorAll('input[name=stmtWho]');
        for (var ri2 = 0; ri2 < radios.length; ri2++) radios[ri2].addEventListener('change', function () { if (state) state.forWho = this.value; renderResult(); });
        wire(out);
    }


    function pubBlock() {
        var pb = state.pub;
        if (!pb || !pb.recognised || !document.getElementById('ownPensionAnnual')) return '';   // planners without a DB-pension card skip this
        var h = msg('', t('pubFound')) + '<div class="ai-table">';
        pb.rows.forEach(function (r, ri) {
            h += '<div style="font-weight:600;margin:0.4rem 0 0.1rem">' + esc(t(r.tx)) + (r.age ? ' (' + esc(t('age')) + ' ' + r.age + ')' : '') + '</div>';
            r.cols.forEach(function (c, ci) {
                var lab = c.kind === 'until' ? t('pubUntil') : (c.kind === 'from' ? t('pubFrom') : '');
                var def = r.id === 'age65' && c.kind !== 'until';
                h += '<label class="ai-row"><input type="radio" name="stmtPubChoice" data-v="' + c.value + '" data-age="' + (r.age || '') + '"' + (def ? ' checked' : '') + '>' +
                    '<span class="ai-lbl">' + esc(lab) + '</span><strong class="ai-new">' + esc(fmt(c.value)) + ' ' + esc(t('pubYear')) + '</strong></label>';
            });
        });
        h += '</div>';
        if (!hhOn() && ((state && state.forWho) || 'me') === 'spouse') return h + msg('bad', t('pubSpouse'));
        return h + msg('', t('pubWill')) + msg('note', t('pubIdx')) +
            '<div class="btn-row"><button type="button" class="save-btn" id="stmtApplyPub">' + esc(t('apply')) + '</button></div>';
    }

    function applyPublic(v, age) {
        var who2 = (state && state.forWho) || 'me', other = hhOn() && storedOnly(who2);
        if (other) {
            var sp2 = storedProfile(who2); if (!sp2) return false;
            sp2.ownPensionAnnual = Math.round(v); if (age) sp2.ownPensionStartAge = age;
            if (!sp2.pensionType || sp2.pensionType === 'none') sp2.pensionType = 'db'; else if (sp2.pensionType === 'dc') sp2.pensionType = 'both';
            var out0 = document.getElementById('stmtOut');
            if (out0) out0.insertAdjacentHTML('afterbegin', msg('good', t('applied') + ' ' + fmt(v) + ' ' + t('pubYear')));
            return true;
        }
        function put(id, val) {
            var el = document.getElementById(id); if (!el) return false;
            el.value = String(val);
            el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true }));
            return true;
        }
        var pt = document.getElementById('pensionType');
        if (pt && (pt.value === 'none' || pt.value === 'dc')) {
            pt.value = pt.value === 'dc' ? 'both' : 'db';
            pt.dispatchEvent(new Event('change', { bubbles: true }));
            if (typeof window.syncPensionType === 'function') { try { window.syncPensionType(); } catch (e) { /* ignore */ } }
        }
        var ok = put('ownPensionAnnual', Math.round(v));
        if (age) put('ownPensionStartAge', age);
        if (typeof window.refreshCollapsibleSummaries === 'function') { try { window.refreshCollapsibleSummaries(); } catch (e) { /* ignore */ } }
        var out = document.getElementById('stmtOut');
        if (ok && out) out.insertAdjacentHTML('afterbegin', msg('good', t('applied') + ' ' + fmt(v) + ' ' + t('pubYear')));
        return ok;
    }

    function applyBlock() {
        var who = (state && state.forWho) || 'me';
        if (who === 'spouse' && !isCouple()) return msg('bad', t('needSpouse'));
        var cur;
        if (hhOn() && storedOnly(who)) { var sp0 = storedProfile(who); cur = sp0 ? parseFloat(sp0.qppMonthlyAmt) : NaN; }
        else { var el = document.getElementById(targetId(who)); cur = el ? parseFloat(el.value) : NaN; }
        return '<div class="ai-msg">' + esc(hhOn() ? t('willSetFor').replace('{n}', whoName(who)) : (who === 'spouse' ? t('willSetSp') : t('willSet'))) + (isFinite(cur) ? ' (' + esc(t('now')) + ' ' + esc(fmt(cur)) + ')' : '') + '</div>' +
            '<div class="btn-row"><button type="button" class="save-btn" id="stmtApply">' + esc(t('apply')) + '</button></div>';
    }

    function pickList() {
        var picks = state.picks || [];
        var h = '<details class="fold" id="stmtPickFold"' + ((state.parsed && state.parsed.recognised) || (state.pub && state.pub.recognised) ? '' : ' open') + '><summary>' + esc(t('pickTitle')) + '</summary><div class="fold-body">' +
            '<p style="margin:0 0 0.4rem;font-size:0.85rem">' + esc(t('pickHelp')) + '</p>';
        if (!picks.length) h += msg('', t('pickNone'));
        picks.forEach(function (a, i) {
            h += '<button type="button" class="secondary stmtPickBtn" data-v="' + a.value + '" style="display:block;width:100%;text-align:left;margin:0.2rem 0">' +
                '<strong>' + esc(fmt(a.value)) + '</strong> <span style="font-size:0.8rem">· ' + esc(t('page')) + ' ' + a.page + (a.ctx ? ' · ' + esc(a.ctx) : '') + '</span></button>';
        });
        return h + '</div></details>';
    }

    function setValue(v) {
        var who = (state && state.forWho) || 'me';
        if (who === 'spouse' && !isCouple()) { var o = document.getElementById('stmtOut'); if (o) o.insertAdjacentHTML('afterbegin', msg('bad', t('needSpouse'))); return false; }
        if (hhOn() && storedOnly(who)) {
            var sp1 = storedProfile(who); if (!sp1) return false;
            sp1.qppMonthlyAmt = v;   // the other person's saved form; they see it when you switch to them
        } else {
            var el = document.getElementById(targetId(who));
            if (!el) return false;
            el.value = String(v);
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }
        if (typeof window.refreshCollapsibleSummaries === 'function') { try { window.refreshCollapsibleSummaries(); } catch (e) { /* ignore */ } }
        if (typeof window.showSaveBadge === 'function') { try { window.showSaveBadge('✓ ' + t('applied')); } catch (e) { /* ignore */ } }
        var out = document.getElementById('stmtOut');
        if (out) out.insertAdjacentHTML('afterbegin', msg('good', t('applied') + ' ' + fmt(v) + ' ' + t('perMonth')));
        return true;
    }

    function wire(out) {
        var ap = document.getElementById('stmtApply');
        if (ap) ap.addEventListener('click', function () {
            var c = out.querySelector('input[name=stmtChoice]:checked');
            if (!c) return;
            setValue(parseFloat(c.getAttribute('data-v')));
        });
        var ap2 = document.getElementById('stmtApplyPub');
        if (ap2) ap2.addEventListener('click', function () {
            var c = out.querySelector('input[name=stmtPubChoice]:checked');
            if (!c) return;
            applyPublic(parseFloat(c.getAttribute('data-v')), parseInt(c.getAttribute('data-age'), 10) || 0);
        });
        var btns = out.querySelectorAll('.stmtPickBtn');
        for (var i = 0; i < btns.length; i++) btns[i].addEventListener('click', function () { setValue(parseFloat(this.getAttribute('data-v'))); });
    }

    function onFile(ev) {
        var f = ev.target.files && ev.target.files[0];
        var out = document.getElementById('stmtOut');
        if (!f) return;
        state = { forWho: hhOn() ? openWho() : 'me' };
        if (!(/\.pdf$/i.test(f.name) || f.type === 'application/pdf')) { state.error = 'notPdf'; renderResult(); return; }
        if (out) out.innerHTML = msg('', t('reading'));
        var rd = new FileReader();
        rd.onerror = function () { state.error = 'failed'; renderResult(); };
        rd.onload = function () {
            readPages(rd.result).then(function (pages) {
                var any = pages.some(function (p) { return p.tokens.length > 0; });
                if (!any) { state.error = 'noText'; state.picks = []; renderResult(); return; }
                state.parsed = parseQpp(pages);
                state.pub = parsePublic(pages);
                state.picks = allAmounts(pages);
                renderResult();
            }).catch(function () { state.error = 'failed'; renderResult(); });
        };
        rd.readAsArrayBuffer(f);
        ev.target.value = '';   // forget the file handle; the PDF itself is not kept
    }

    function mount() {
        if (mounted) return; mounted = true;
        render();
        var lb = document.getElementById('langBtn');
        if (lb) lb.addEventListener('click', function () { setTimeout(render, 30); });
        var cm = document.getElementById('calcMode');
        if (cm) cm.addEventListener('change', function () { renderResult(); });
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount); else mount();

    window.QCRP_STMT = { parseQpp: parseQpp, parsePublic: parsePublic, tokenize: tokenize, parseAmount: parseAmount, render: render };
})();
