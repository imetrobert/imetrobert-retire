pdf.js (pdfjs-dist) 3.11.174, Apache-2.0 (see LICENSE). Self-hosted so the planner never loads code from another site.
Only statements.js loads these two files, and only when a person picks a PDF.
To update: npm pack pdfjs-dist@<version>, copy build/pdf.min.js and build/pdf.worker.min.js here, run scripts/test_statements.py.
