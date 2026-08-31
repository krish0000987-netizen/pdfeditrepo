"""Vercel Python entrypoint for pdf-edit-engine.

Exposes the library as a serverless HTTP API while keeping the
original package intact. Uses only stdlib (BaseHTTPRequestHandler)
so no extra runtime dependencies are needed.
"""

from __future__ import annotations

import json
import sys
import tempfile
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    # CORS
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.end_headers()
    handler.wfile.write(body)


def _html_response(handler: BaseHTTPRequestHandler, html: str) -> None:
    body = html.encode()
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


LANDING_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>pdf-edit-engine — API</title>
<style>
  :root{--bg:#0b0e14;--card:#151a23;--muted:#9aa4b2;--fg:#e6e8eb;--accent:#7c5cff;--accent2:#2ec4b6;--border:#232a36}
  *{box-sizing:border-box} body{margin:0;font-family:ui-sans,system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial;background:radial-gradient(1200px 600px at 20% -10%,#1a1f2e 0%,#0b0e14 60%);color:var(--fg);line-height:1.6}
  header{max-width:960px;margin:0 auto;padding:48px 24px 12px}
  h1{font-size:42px;margin:0 0 8px;letter-spacing:-0.02em} h1 span{color:var(--accent)}
  .sub{color:var(--muted);font-size:18px;max-width:680px}
  .grid{max-width:960px;margin:24px auto;display:grid;grid-template-columns:1.2fr 0.8fr;gap:16px;padding:0 24px}
  .card{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:20px}
  .badge{display:inline-block;font-size:12px;letter-spacing:0.08em;text-transform:uppercase;color:#cbd5e1;background:#1e2433;border:1px solid var(--border);padding:6px 10px;border-radius:999px;margin-right:8px}
  code,pre{background:#0f1320;border:1px solid var(--border);border-radius:10px}
  code{padding:2px 6px;font-size:13px} pre{padding:14px;overflow:auto;font-size:13px;line-height:1.5}
  a{color:#8ea0ff;text-decoration:none} a:hover{text-decoration:underline}
  .endpoints dt{font-weight:700;margin-top:12px} .endpoints dd{margin:4px 0 0 0;color:var(--muted)} 
  .cta{display:inline-block;margin-top:16px;background:var(--accent);color:white;padding:10px 16px;border-radius:10px;font-weight:600}
  .cta.secondary{background:transparent;border:1px solid var(--border);color:var(--fg);margin-left:8px}
  footer{max-width:960px;margin:32px auto;padding:0 24px;color:var(--muted);font-size:13px}
  @media(max-width:820px){.grid{grid-template-columns:1fr}}
</style>
</head>
<body>
<header>
  <div><span class="badge">Python 3.12+ &bull; MIT</span><span class="badge">pikepdf &bull; fonttools &bull; pdfminer.six</span></div>
  <h1>pdf-edit<span>-engine</span></h1>
  <p class="sub">Format-preserving PDF text editing. Modify content-stream operators in-place — original fonts, layout and spacing stay intact. No AGPL. Every edit returns a <code>FidelityReport</code>.</p>
  <a class="cta" href="#api">View API</a>
  <a class="cta secondary" href="https://github.com/krish0000987-netizen/pdfeditrepo" target="_blank">GitHub</a>
</header>

<div class="grid">
  <div class="card">
    <h3 style="margin-top:0">Quick start (library)</h3>
<pre>pip install pdf-edit-engine

from pdf_edit_engine import find, replace

matches = find("document.pdf", "Software Engineer")
result = replace("document.pdf", matches[0], "Senior Engineer", "output.pdf")

report = result.fidelity_report
report.font_preserved      # True — original font kept
report.overflow_detected   # False — fits in original space
report.glyphs_missing      # [] — all glyphs rendered</pre>
    <p style="color:var(--muted);font-size:14px">Full docs in <code>README.md</code> — search, replace, structural <code>replace_block</code>, 15 PDF ops, annotations.</p>
  </div>

  <div class="card" id="api">
    <h3 style="margin-top:0">HTTP API (Vercel)</h3>
    <dl class="endpoints">
      <dt>GET /</dt><dd>this landing page</dd>
      <dt>GET /api/health</dt><dd>version + runtime check</dd>
      <dt>GET /api/docs</dt><dd>JSON API spec</dd>
      <dt>POST /api/find</dt><dd>multipart: <code>file</code> + <code>query</code> — returns matches</dd>
      <dt>POST /api/replace</dt><dd>multipart: <code>file</code> + <code>find</code> + <code>replace</code> — returns edited PDF</dd>
      <dt>POST /api/replace-all</dt><dd>multipart: <code>file</code> + <code>find</code> + <code>replace</code> — replace all occurrences</dd>
    </dl>
    <p style="margin-top:14px"><code>curl https://your-deployment.vercel.app/api/health</code></p>
  </div>
</div>

<div class="grid">
  <div class="card">
    <h3 style="margin-top:0">Why this engine vs redact-and-replace?</h3>
    <table style="width:100%;font-size:14px;border-collapse:collapse">
      <tr style="color:var(--muted)"><th align="left">Method</th><th align="left">Font</th><th align="left">Layout</th></tr>
      <tr><td>Redact + re-insert</td><td>Substituted (Helvetica)</td><td>Re-calculated</td></tr>
      <tr><td><b>pdf-edit-engine</b></td><td><b>Original preserved</b></td><td><b>Operator-level precision</b></td></tr>
    </table>
    <p style="color:var(--muted);font-size:13px;margin-bottom:0">Every edit reports <code>font_preserved</code>, <code>overflow_detected</code>, <code>glyphs_missing</code> and typed <code>Degradation</code> events for programmatic quality gates.</p>
  </div>
  <div class="card">
    <h3 style="margin-top:0">Deploy</h3>
    <p style="color:var(--muted);font-size:14px">This repo is deployed on Vercel as a Python serverless function. The library itself has no web dependencies — the wrapper is <code>api/index.py</code> (~200 lines, stdlib only).</p>
    <pre>vercel --prod
# or push to main → auto-deploy</pre>
  </div>
</div>

<footer>
  pdf-edit-engine v0.2.0 &bull; MIT &bull; Built from <a href="https://github.com/AryanBV/pdf-edit-engine">AryanBV/pdf-edit-engine</a>
</footer>
</body>
</html>
"""


def _health_payload() -> dict:
    try:
        import pdf_edit_engine  # type: ignore

        version = getattr(pdf_edit_engine, "__version__", "0.2.0")
    except Exception as e:  # pragma: no cover
        version = f"import-error: {type(e).__name__}"
    return {
        "status": "ok",
        "service": "pdf-edit-engine",
        "version": version,
        "python": sys.version,
        "entrypoint": "api/index.py",
    }


def _docs_payload() -> dict:
    return {
        "service": "pdf-edit-engine",
        "docs": "https://github.com/krish0000987-netizen/pdfeditrepo#readme",
        "endpoints": {
            "GET /": "landing page (HTML)",
            "GET /api/health": "health check",
            "GET /api/docs": "this document",
            "POST /api/find": {
                "contentType": "multipart/form-data",
                "fields": {"file": "PDF file", "query": "text to find"},
                "returns": "JSON {matches: [...]}",
            },
            "POST /api/replace": {
                "contentType": "multipart/form-data",
                "fields": {"file": "PDF", "find": "text", "replace": "text"},
                "returns": "application/pdf (edited file) + X-Fidelity headers",
            },
            "POST /api/replace-all": {
                "contentType": "multipart/form-data",
                "fields": {"file": "PDF", "find": "text", "replace": "text"},
                "returns": "application/pdf",
            },
        },
    }


# --- multipart helpers (stdlib only) ---------------------------------------

def _parse_multipart(handler: BaseHTTPRequestHandler) -> dict:
    """Very small multipart parser for file uploads; returns {field: value}."""
    ctype = handler.headers.get("Content-Type", "")
    if "multipart/form-data" not in ctype:
        return {}
    boundary = None
    for part in ctype.split(";"):
        part = part.strip()
        if part.startswith("boundary="):
            boundary = part.split("=", 1)[1].strip('"')
            break
    if not boundary:
        return {}
    length = int(handler.headers.get("Content-Length", 0))
    raw = handler.rfile.read(length)
    delimiter = ("--" + boundary).encode()
    fields: dict = {}
    files: dict = {}
    parts = raw.split(delimiter)
    for chunk in parts:
        if not chunk or chunk in (b"--\r\n", b"--", b"\r\n"):
            continue
        if b"\r\n\r\n" not in chunk:
            continue
        header_raw, body = chunk.split(b"\r\n\r\n", 1)
        # strip trailing \r\n
        if body.endswith(b"\r\n"):
            body = body[:-2]
        header_str = header_raw.decode(errors="ignore")
        # extract name and filename
        name = None
        filename = None
        for line in header_str.split("\r\n"):
            low = line.lower()
            if "content-disposition" in low:
                # form-data; name="file"; filename="doc.pdf"
                for seg in line.split(";"):
                    seg = seg.strip()
                    if seg.startswith("name="):
                        name = seg.split("=", 1)[1].strip('"')
                    if seg.startswith("filename="):
                        filename = seg.split("=", 1)[1].strip('"')
        if not name:
            continue
        if filename:
            files[name] = {"filename": filename, "data": body}
            fields[name] = body
            fields[name + "_filename"] = filename
        else:
            try:
                fields[name] = body.decode()
            except Exception:
                fields[name] = body
    # merge files for convenience
    fields["_files"] = files
    return fields


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path in ("/", "/api"):
            _html_response(self, LANDING_HTML)
            return
        if path in ("/api/health", "/health"):
            _json_response(self, 200, _health_payload())
            return
        if path in ("/api/docs", "/docs"):
            _json_response(self, 200, _docs_payload())
            return

        _json_response(self, 404, {"error": "not found", "path": path})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/api/find":
            self._handle_find()
            return
        if path in ("/api/replace", "/api/replace-all"):
            self._handle_replace(all_occurrences=(path == "/api/replace-all"))
            return

        _json_response(self, 404, {"error": "not found", "path": path})

    # --- handlers ----------------------------------------------------------

    def _handle_find(self) -> None:
        fields = _parse_multipart(self)
        files = fields.get("_files", {})
        if "file" not in files:
            _json_response(self, 400, {"error": "missing file field 'file'"})
            return
        query = fields.get("query") or fields.get("find") or ""
        if not query:
            _json_response(self, 400, {"error": "missing field 'query' (text to find)"})
            return
        data: bytes = files["file"]["data"]  # type: ignore
        try:
            from pdf_edit_engine import find as pdf_find
        except Exception as e:
            _json_response(self, 500, {"error": f"import failed: {type(e).__name__}"})
            return

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name

        try:
            matches = pdf_find(tmp_path, str(query))
            payload = {
                "query": str(query),
                "count": len(matches),
                "matches": [
                    {
                        "text": m.text,  # type: ignore
                        "page_index": m.page_index,  # type: ignore
                        "bbox": list(m.bbox) if hasattr(m, "bbox") else None,  # type: ignore
                    }
                    for m in matches
                ],
            }
            _json_response(self, 200, payload)
        except Exception as e:
            _json_response(self, 500, {"error": f"{type(e).__name__}: {e}"})
        finally:
            try:
                import os

                os.unlink(tmp_path)
            except Exception:
                pass

    def _handle_replace(self, *, all_occurrences: bool) -> None:
        fields = _parse_multipart(self)
        files = fields.get("_files", {})
        if "file" not in files:
            _json_response(self, 400, {"error": "missing file field 'file'"})
            return
        find_text = fields.get("find") or fields.get("query") or ""
        replace_text = fields.get("replace") or ""
        if not find_text:
            _json_response(self, 400, {"error": "missing field 'find'"})
            return
        # replace may be empty (deletion)
        data: bytes = files["file"]["data"]  # type: ignore
        try:
            from pdf_edit_engine import find as pdf_find
            from pdf_edit_engine import replace as pdf_replace
            from pdf_edit_engine import replace_all as pdf_replace_all
        except Exception as e:
            _json_response(self, 500, {"error": f"import failed: {type(e).__name__}"})
            return

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_in:
            tmp_in.write(data)
            in_path = tmp_in.name
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_out:
            out_path = tmp_out.name

        try:
            matches = pdf_find(in_path, str(find_text))
            if not matches:
                _json_response(self, 404, {"error": f"text not found: {find_text!r}", "count": 0})
                return

            if all_occurrences:
                results = pdf_replace_all(in_path, str(find_text), str(replace_text), out_path)
                # use first fidelity for headers if available
                report = results[0].fidelity_report if results else None
            else:
                result = pdf_replace(in_path, matches[0], str(replace_text), out_path)
                report = result.fidelity_report

            with open(out_path, "rb") as f:
                pdf_bytes = f.read()

            # send PDF with fidelity headers
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Length", str(len(pdf_bytes)))
            self.send_header("Content-Disposition", 'attachment; filename="edited.pdf"')
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Expose-Headers", "X-Fidelity-Font-Preserved, X-Fidelity-Overflow, X-Fidelity-Glyphs-Missing")
            if report is not None:
                try:
                    self.send_header("X-Fidelity-Font-Preserved", str(getattr(report, "font_preserved", "")))
                    self.send_header("X-Fidelity-Overflow", str(getattr(report, "overflow_detected", "")))
                    gm = getattr(report, "glyphs_missing", [])
                    self.send_header("X-Fidelity-Glyphs-Missing", ",".join(gm) if gm else "")
                except Exception:
                    pass
            self.end_headers()
            self.wfile.write(pdf_bytes)

        except Exception as e:
            _json_response(self, 500, {"error": f"{type(e).__name__}: {e}"})
        finally:
            for p in (in_path, out_path):
                try:
                    import os

                    os.unlink(p)
                except Exception:
                    pass

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        # quieter logs on Vercel
        sys.stderr.write(f"{self.client_address[0]} - - [{self.log_date_time_string()}] {format % args}\n")
