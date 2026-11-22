#!/usr/bin/env python3
"""Makes the FAKE statement PDFs used by scripts/test_statements.py (tests/fixtures/*.pdf).
They imitate the layout of Retraite Québec's public example statement (section A: two scenarios,
age 60 and 65 monthly amounts). All names and numbers are invented. Needs: pip install reportlab.
Run: python3 scripts/make_fake_statements.py"""
import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

OUT = os.path.join(os.path.dirname(__file__), '..', 'tests', 'fixtures')
os.makedirs(OUT, exist_ok=True)

def build(name, lang, split_dollar=False, extra_noise=True):
    c = canvas.Canvas(os.path.join(OUT, name), pagesize=letter)
    W, H = letter
    en = lang == 'en'
    c.setFont('Helvetica-Bold', 16); c.drawString(300, H - 60, 'Statement of Participation' if en else 'Relevé de participation')
    c.setFont('Helvetica', 9); c.drawString(300, H - 76, 'FAKE EXAMPLE - NOT A REAL PERSON')
    if extra_noise:
        c.drawString(60, H - 140, 'Your age: 55 - Years contributed: 30 - Earnings: 52 400 $' if en else 'Votre âge : 55 - Années cotisées : 30 - Revenus : 52 400 $')
    c.setFont('Helvetica-Bold', 12)
    c.drawString(60, H - 200, 'Estimate of the amount of your retirement pension (monthly)' if en else 'Estimation du montant de votre rente de retraite (mensuelle)')
    rows = [
        (H - 270, 'If you continue to', 'make contributions', (311, 468)) if en else (H - 270, 'Si vous continuez de', 'cotiser', (311, 468)),
        (H - 370, 'If you stopped', 'making contributions today', (205, 266)) if en else (H - 370, 'Si vous cessiez de cotiser', 'aujourd\'hui', (205, 266)),
    ]
    for y, l1, l2, (a60, a65) in rows:
        c.setFont('Helvetica', 9)
        c.drawString(70, y + 4, l1); c.drawString(70, y - 8, l2)
        for x, amt, age in ((250, a60, 60), (310, a65, 65)):
            c.setFillColorRGB(0, 0, 0); c.rect(x, y - 20, 40, 14 + (amt // 40), fill=1)
            c.setFillColorRGB(0, 0, 0); c.setFont('Helvetica-Bold', 10)
            if split_dollar:
                c.drawString(x, y + 12 + (amt // 40), str(amt)); c.drawString(x + 24, y + 12 + (amt // 40), '$')
            else:
                c.drawString(x, y + 12 + (amt // 40), '%d $' % amt)
            c.setFont('Helvetica', 8); c.drawString(x, y - 32, ('Age %d' % age) if en else ('%d ans' % age))
        c.setFont('Helvetica', 8)
        d = ['This is an estimate of the amount of the pension you could receive at the age indicated.',
             'if, as of today, you do not make any more contributions. Earnings no longer exceed',
             '3 500 $ a year until you retire.'] if en else \
            ['Il s\'agit d\'une estimation de la rente que vous pourriez recevoir à l\'âge indiqué.',
             'Vos revenus ne dépassent plus',
             '3 500 $ par année jusqu\'à votre retraite.']
        for i, line in enumerate(d):
            c.drawString(400, y + 12 - i * 11, line[:48])
    c.setFont('Helvetica-Bold', 12)
    c.drawString(60, H - 470, 'Pensionable earnings' if en else 'Revenus de travail admissibles')
    c.setFont('Helvetica', 9)
    for i, (yr, v) in enumerate(((2023, '52 400'), (2024, '53 100'), (2025, '54 000'))):
        c.drawString(60, H - 490 - i * 12, '%d   %s' % (yr, v))
    c.showPage(); c.save()

def blank(name):   # a PDF with no text layer at all
    c = canvas.Canvas(os.path.join(OUT, name), pagesize=letter); c.rect(100, 100, 200, 200, fill=1); c.showPage(); c.save()

def other(name):   # a PDF of a different document: dollar amounts but no section A
    c = canvas.Canvas(os.path.join(OUT, name), pagesize=letter)
    c.setFont('Helvetica', 11); c.drawString(72, 700, 'Some other letter'); c.drawString(72, 680, 'Monthly benefit now: 612 $'); c.drawString(72, 660, 'Annual total: 7 344 $')
    c.showPage(); c.save()

build('fake-qpp-en.pdf', 'en')
build('fake-qpp-fr.pdf', 'fr')
build('fake-qpp-split-dollar.pdf', 'en', split_dollar=True)
blank('fake-no-text.pdf')
other('fake-other-document.pdf')
print('written to', os.path.abspath(OUT))
