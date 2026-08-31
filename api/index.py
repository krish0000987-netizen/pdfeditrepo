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
from urllib.parse import urlparse


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
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


LANDING_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>pdf-edit-engine — Format-preserving PDF editing</title>
<meta name="description" content="Edit text in existing PDFs at the content-stream level — fonts, layout and spacing stay intact. No AGPL, with FidelityReport on every edit."/>
<script src="https://cdn.tailwindcss.com"></script>
<script>
tailwind.config={theme:{extend:{colors:{bg:'#0b0e14',card:'#151a23',muted:'#9aa4b2',accent:'#7c5cff',accent2:'#2ec4b6',border:'#232a36'}}}}
</script>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.2.0/remixicon.min.css"/>
<style>
*{scroll-behavior:smooth}
::-webkit-scrollbar{width:8px;height:8px}::-webkit-scrollbar-thumb{background:#2a3242;border-radius:999px}
.glass{backdrop-filter:blur(16px);background:rgba(21,26,35,0.7)}
.gradient-text{background:linear-gradient(135deg,#7c5cff 0%,#2ec4b6 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.drop-active{border-color:#7c5cff!important;background:rgba(124,92,255,0.08)!important}
.tab-active{background:#7c5cff;color:white;border-color:#7c5cff}
</style>
</head>
<body class="bg-[#0b0e14] text-[#e6e8eb] antialiased selection:bg-[#7c5cff]/30">
<!-- Header -->
<header class="sticky top-0 z-50 border-b border-[#232a36] glass">
  <div class="max-w-[1280px] mx-auto px-4 sm:px-6 py-3 flex items-center justify-between">
    <div class="flex items-center gap-3">
      <div class="w-9 h-9 rounded-xl bg-gradient-to-br from-[#7c5cff] to-[#2ec4b6] flex items-center justify-center font-black text-white">PE</div>
      <div>
        <div class="font-bold leading-none">pdf-edit-engine</div>
        <div class="text-xs text-[#9aa4b2] -mt-0.5">v0.2.0 • Python 3.12+ • MIT</div>
      </div>
      <span class="hidden md:inline-flex ml-3 px-2.5 py-1 rounded-full bg-[#1e2433] border border-[#232a36] text-xs text-[#9aa4b2]">✦ 414 probes • 801 tests</span>
    </div>
    <nav class="hidden md:flex items-center gap-6 text-sm text-[#9aa4b2]">
      <a href="#editor" class="hover:text-white transition">Editor</a>
      <a href="#features" class="hover:text-white transition">Features</a>
      <a href="#api" class="hover:text-white transition">API</a>
      <a href="https://github.com/krish0000987-netizen/pdfeditrepo" target="_blank" class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white text-[#0b0e14] font-semibold hover:bg-zinc-100 transition"><i class="ri-github-fill"></i> GitHub</a>
    </nav>
  </div>
</header>

<!-- Hero -->
<section class="relative overflow-hidden">
  <div class="absolute inset-0 bg-[radial-gradient(1200px_600px_at_20%_-10%,#1a1f2e_0%,transparent_60%),radial-gradient(800px_400px_at_90%_10%,rgba(124,92,255,0.12)_0%,transparent_60%)]"></div>
  <div class="relative max-w-[1280px] mx-auto px-4 sm:px-6 pt-10 pb-8">
    <div class="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-[#1e2433] border border-[#232a36] text-xs">
      <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
      <span class="text-[#9aa4b2]">No AGPL • pikepdf + fonttools • Content-stream surgery</span>
      <span class="hidden sm:inline text-[#5a6475]">•</span>
      <a href="#editor" class="hidden sm:inline text-[#8ea0ff] hover:underline">Try live editor ↓</a>
    </div>
    <h1 class="mt-5 text-[32px] sm:text-[44px] font-extrabold tracking-tight leading-[0.95]">
      Edit PDFs <span class="gradient-text">without</span><br/>losing fidelity.
    </h1>
    <p class="mt-4 max-w-[680px] text-[15px] sm:text-[17px] leading-relaxed text-[#9aa4b2]">
      Modify <span class="text-white font-medium">content-stream operators in-place</span> — original fonts, layout and spacing stay intact. Unlike redact-and-replace, every edit returns a <span class="text-white font-mono text-sm bg-[#1e2433] border border-[#232a36] px-1.5 py-0.5 rounded">FidelityReport</span> for programmatic quality gates.
    </p>
    <div class="mt-6 flex flex-wrap gap-3">
      <a href="#editor" class="px-5 py-2.5 rounded-xl bg-[#7c5cff] text-white font-semibold shadow-lg shadow-[#7c5cff]/20 hover:bg-[#6b4eff] transition flex items-center gap-2"><i class="ri-quill-pen-line"></i> Open Live Editor</a>
      <a href="#api" class="px-5 py-2.5 rounded-xl bg-[#151a23] border border-[#232a36] font-semibold hover:bg-[#1a2030] transition flex items-center gap-2"><i class="ri-code-s-slash-line"></i> API Docs</a>
      <button onclick="document.getElementById('quickstart').scrollIntoView()" class="hidden sm:inline-flex px-5 py-2.5 rounded-xl bg-transparent border border-[#232a36] text-[#9aa4b2] hover:text-white transition">Quick start</button>
    </div>
    <!-- stats -->
    <div class="mt-8 grid grid-cols-2 sm:grid-cols-4 gap-3 max-w-[760px]">
      <div class="rounded-2xl bg-[#151a23] border border-[#232a36] p-4"><div class="text-2xl font-bold">In-place</div><div class="text-xs text-[#9aa4b2]">Operator splice, not overlay</div></div>
      <div class="rounded-2xl bg-[#151a23] border border-[#232a36] p-4"><div class="text-2xl font-bold">Original font</div><div class="text-xs text-[#9aa4b2]">Kept + subset extended</div></div>
      <div class="rounded-2xl bg-[#151a23] border border-[#232a36] p-4"><div class="text-2xl font-bold">30 kinds</div><div class="text-xs text-[#9aa4b2]">Typed Degradations</div></div>
      <div class="rounded-2xl bg-[#151a23] border border-[#232a36] p-4"><div class="text-2xl font-bold">15 ops</div><div class="text-xs text-[#9aa4b2]">Merge, split, encrypt…</div></div>
    </div>
  </div>
</section>

<!-- Live Editor -->
<section id="editor" class="max-w-[1280px] mx-auto px-4 sm:px-6 mt-8">
  <div class="flex items-center justify-between mb-3">
    <h2 class="text-xl font-bold flex items-center gap-2"><span class="w-8 h-8 rounded-lg bg-[#7c5cff] flex items-center justify-center text-white"><i class="ri-edit-2-line"></i></span> Live Editor <span class="text-xs font-normal text-[#9aa4b2] ml-2">PDF → Find → Replace → Download</span></h2>
    <span id="healthBadge" class="text-xs px-2.5 py-1 rounded-full bg-[#1e2433] border border-[#232a36] text-[#9aa4b2]">checking health…</span>
  </div>

  <div class="grid lg:grid-cols-[1.05fr_1.2fr] gap-4">
    <!-- Left: Upload + Controls -->
    <div class="space-y-4">
      <!-- Upload -->
      <div class="rounded-2xl bg-[#151a23] border border-[#232a36] p-4">
        <div class="flex items-center justify-between mb-2">
          <h3 class="font-semibold text-sm flex items-center gap-2"><i class="ri-upload-cloud-2-line text-[#7c5cff]"></i> 1. Upload PDF</h3>
          <span class="text-xs text-[#9aa4b2]">Drag & drop or click</span>
        </div>
        <div id="dropZone" class="relative rounded-xl border-2 border-dashed border-[#2a3344] bg-[#0f1320] p-6 text-center hover:border-[#3a455c] transition cursor-pointer group">
          <input id="fileInput" type="file" accept=".pdf,application/pdf" class="absolute inset-0 opacity-0 cursor-pointer"/>
          <div id="dropContent">
            <div class="w-12 h-12 mx-auto rounded-xl bg-[#1e2433] border border-[#232a36] flex items-center justify-center text-xl text-[#7c5cff] group-hover:scale-105 transition"><i class="ri-file-pdf-line"></i></div>
            <div class="mt-3 font-medium">Drop PDF here</div>
            <div class="text-xs text-[#9aa4b2]">or click to browse • max ~10MB recommended</div>
            <div class="mt-3 inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full bg-[#0b0e14] border border-[#232a36] text-[#9aa4b2]"><i class="ri-shield-check-line"></i> Processed server-side, not stored</div>
          </div>
          <div id="fileMeta" class="hidden text-left">
            <div class="flex items-start justify-between gap-3">
              <div class="flex gap-3">
                <div class="w-10 h-10 rounded-lg bg-[#7c5cff]/15 border border-[#7c5cff]/20 flex items-center justify-center text-[#7c5cff]"><i class="ri-file-pdf-fill"></i></div>
                <div>
                  <div id="fileName" class="font-medium text-sm leading-tight truncate max-w-[220px]"></div>
                  <div id="fileSize" class="text-xs text-[#9aa4b2]"></div>
                  <div id="filePages" class="text-xs text-[#2ec4b6]"></div>
                </div>
              </div>
              <button id="clearFile" class="px-2.5 py-1 rounded-full bg-[#232a36] text-xs hover:bg-[#2a3342] transition">Clear</button>
            </div>
            <div class="mt-3 h-1.5 rounded-full bg-[#0b0e14] border border-[#232a36] overflow-hidden"><div id="uploadBar" class="h-full w-0 bg-gradient-to-r from-[#7c5cff] to-[#2ec4b6] transition-all"></div></div>
          </div>
        </div>
        <div id="uploadStatus" class="mt-2 text-xs text-[#9aa4b2]"></div>
      </div>

      <!-- Controls -->
      <div class="rounded-2xl bg-[#151a23] border border-[#232a36] p-4">
        <h3 class="font-semibold text-sm flex items-center gap-2 mb-3"><i class="ri-search-line text-[#7c5cff]"></i> 2. Find & Replace</h3>
        <div class="space-y-3">
          <div>
            <label class="text-xs font-semibold text-[#9aa4b2] tracking-wide uppercase">Find text</label>
            <div class="mt-1 relative">
              <i class="ri-search-line absolute left-3 top-1/2 -translate-y-1/2 text-[#5a6475]"></i>
              <input id="findInput" placeholder="e.g.  Software Engineer" class="w-full pl-9 pr-8 py-2.5 rounded-xl bg-[#0f1320] border border-[#232a36] focus:border-[#7c5cff]/50 focus:outline-none text-sm placeholder:text-[#5a6475]"/>
              <button id="clearFind" class="absolute right-2 top-1/2 -translate-y-1/2 w-6 h-6 rounded-full bg-[#1e2433] text-[#9aa4b2] hover:text-white text-xs">×</button>
            </div>
          </div>
          <div>
            <label class="text-xs font-semibold text-[#9aa4b2] tracking-wide uppercase">Replace with</label>
            <div class="mt-1 relative">
              <i class="ri-quill-pen-line absolute left-3 top-1/2 -translate-y-1/2 text-[#5a6475]"></i>
              <input id="replaceInput" placeholder="e.g.  Senior Engineer" class="w-full pl-9 pr-3 py-2.5 rounded-xl bg-[#0f1320] border border-[#232a36] focus:border-[#7c5cff]/50 focus:outline-none text-sm placeholder:text-[#5a6475]"/>
            </div>
            <div class="mt-1.5 text-[11px] text-[#5a6475]">Empty = deletion. Longer text triggers reflow + Tz kerning.</div>
          </div>

          <div class="grid grid-cols-2 gap-2 pt-1">
            <label class="flex items-center gap-2 px-3 py-2 rounded-xl bg-[#0f1320] border border-[#232a36] cursor-pointer hover:border-[#2a3344] transition">
              <input id="replaceAllToggle" type="checkbox" class="accent-[#7c5cff]"/>
              <span class="text-xs font-medium">Replace all <span class="text-[#5a6475]">(batch)</span></span>
            </label>
            <label class="flex items-center gap-2 px-3 py-2 rounded-xl bg-[#0f1320] border border-[#232a36] cursor-pointer hover:border-[#2a3344] transition">
              <input id="dryRunToggle" type="checkbox" class="accent-[#2ec4b6]"/>
              <span class="text-xs font-medium">Dry run <span class="text-[#5a6475]">(preview)</span></span>
            </label>
          </div>

          <div class="grid grid-cols-3 gap-2 pt-2">
            <button id="btnFind" class="col-span-1 py-2.5 rounded-xl bg-[#1e2433] border border-[#232a36] font-semibold text-sm hover:bg-[#232a36] transition flex items-center justify-center gap-1.5"><i class="ri-search-2-line"></i> Find</button>
            <button id="btnReplace" class="col-span-2 py-2.5 rounded-xl bg-[#7c5cff] text-white font-bold text-sm shadow-md shadow-[#7c5cff]/20 hover:bg-[#6b4eff] transition flex items-center justify-center gap-1.5"><i class="ri-refresh-line"></i> Replace & Download</button>
          </div>
          <div class="grid grid-cols-2 gap-2">
            <button id="btnReplaceAll" class="py-2 rounded-xl bg-[#0f1320] border border-[#232a36] text-sm font-medium hover:bg-[#1a2030] transition flex items-center justify-center gap-1.5"><i class="ri-repeat-line"></i> Replace All</button>
            <button id="btnClear" class="py-2 rounded-xl bg-transparent border border-[#232a36] text-sm text-[#9aa4b2] hover:text-white transition">Clear</button>
          </div>
        </div>
        <div id="controlStatus" class="mt-3 text-xs min-h-[18px] text-[#9aa4b2]"></div>
      </div>

      <!-- Tips -->
      <div class="rounded-2xl bg-gradient-to-br from-[#7c5cff]/15 to-[#2ec4b6]/10 border border-[#7c5cff]/20 p-4">
        <div class="text-sm font-semibold flex items-center gap-2"><i class="ri-lightbulb-line text-[#7c5cff]"></i> Tips</div>
        <ul class="mt-2 space-y-1.5 text-xs text-[#9aa4b2] leading-relaxed">
          <li>• Try <span class="text-white font-mono bg-[#0b0e14]/60 px-1 rounded">Find</span> first to verify match count & bbox.</li>
          <li>• Use <span class="text-white">Dry run</span> to preview <code class="bg-[#0b0e14] px-1 rounded border border-white/10">FidelityReport</code> without downloading.</li>
          <li>• Long replacements auto-reflow paragraphs with greedy line breaking.</li>
        </ul>
      </div>
    </div>

    <!-- Right: Results + Preview -->
    <div class="space-y-4">
      <div class="rounded-2xl bg-[#151a23] border border-[#232a36] overflow-hidden">
        <div class="flex items-center justify-between px-4 py-3 border-b border-[#232a36] bg-[#0f1320]/50">
          <div class="flex items-center gap-2">
            <h3 class="font-semibold text-sm flex items-center gap-2"><i class="ri-checkbox-circle-line text-emerald-400"></i> Results</h3>
            <span id="resultBadge" class="hidden text-xs px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/20">0 matches</span>
          </div>
          <div class="flex items-center gap-1.5">
            <button data-tab="matches" class="tabBtn tab-active px-3 py-1.5 rounded-full border text-xs font-semibold transition">Matches</button>
            <button data-tab="fidelity" class="tabBtn px-3 py-1.5 rounded-full border border-[#232a36] text-xs font-semibold text-[#9aa4b2] hover:text-white transition">Fidelity</button>
            <button data-tab="preview" class="tabBtn px-3 py-1.5 rounded-full border border-[#232a36] text-xs font-semibold text-[#9aa4b2] hover:text-white transition">Preview</button>
          </div>
        </div>

        <div class="p-4">
          <!-- Matches tab -->
          <div id="tab-matches">
            <div id="emptyMatches" class="rounded-xl bg-[#0f1320] border border-dashed border-[#2a3344] p-8 text-center">
              <div class="w-10 h-10 mx-auto rounded-xl bg-[#1e2433] flex items-center justify-center text-[#5a6475]"><i class="ri-search-eye-line"></i></div>
              <div class="mt-2 text-sm font-medium">No search yet</div>
              <div class="text-xs text-[#9aa4b2] mt-1">Upload a PDF and click <span class="text-white">Find</span> to see operator-level matches.</div>
            </div>
            <div id="matchesList" class="hidden space-y-2 max-h-[320px] overflow-auto pr-1"></div>
          </div>

          <!-- Fidelity tab -->
          <div id="tab-fidelity" class="hidden">
            <div id="emptyFidelity" class="rounded-xl bg-[#0f1320] border border-dashed border-[#2a3344] p-8 text-center">
              <div class="w-10 h-10 mx-auto rounded-xl bg-[#1e2433] flex items-center justify-center text-[#5a6475]"><i class="ri-shield-check-line"></i></div>
              <div class="mt-2 text-sm font-medium">FidelityReport appears after edit</div>
              <div class="text-xs text-[#9aa4b2] mt-1">Every edit reports <code class="bg-[#1e2433] px-1 rounded">font_preserved</code>, <code class="bg-[#1e2433] px-1 rounded">overflow</code> and degradations.</div>
            </div>
            <div id="fidelityPanel" class="hidden space-y-3">
              <div class="grid grid-cols-3 gap-2">
                <div class="rounded-xl bg-[#0f1320] border border-[#232a36] p-3 text-center"><div class="text-[11px] tracking-wide uppercase text-[#5a6475] font-semibold">Font preserved</div><div id="fFont" class="mt-1 text-sm font-bold">—</div></div>
                <div class="rounded-xl bg-[#0f1320] border border-[#232a36] p-3 text-center"><div class="text-[11px] tracking-wide uppercase text-[#5a6475] font-semibold">Overflow</div><div id="fOverflow" class="mt-1 text-sm font-bold">—</div></div>
                <div class="rounded-xl bg-[#0f1320] border border-[#232a36] p-3 text-center"><div class="text-[11px] tracking-wide uppercase text-[#5a6475] font-semibold">Glyphs missing</div><div id="fGlyphs" class="mt-1 text-sm font-bold">—</div></div>
              </div>
              <div class="rounded-xl bg-[#0f1320] border border-[#232a36] p-3">
                <div class="text-xs font-semibold text-[#9aa4b2] uppercase tracking-wide">Degradations (typed)</div>
                <div id="fDegradations" class="mt-2 space-y-1.5 text-xs"></div>
              </div>
              <div class="rounded-xl bg-[#0f1320] border border-[#232a36] p-3">
                <div class="text-xs font-semibold text-[#9aa4b2] uppercase tracking-wide">Raw JSON</div>
                <pre id="fRaw" class="mt-2 text-[11px] bg-[#0b0e14] border border-[#232a36] rounded-lg p-2.5 overflow-auto max-h-[160px]"></pre>
              </div>
            </div>
          </div>

          <!-- Preview tab -->
          <div id="tab-preview" class="hidden">
            <div id="emptyPreview" class="rounded-xl bg-[#0f1320] border border-dashed border-[#2a3344] p-8 text-center">
              <div class="w-10 h-10 mx-auto rounded-xl bg-[#1e2433] flex items-center justify-center text-[#5a6475]"><i class="ri-eye-line"></i></div>
              <div class="mt-2 text-sm font-medium">Preview appears after replace</div>
              <div class="text-xs text-[#9aa4b2] mt-1">Edited PDF will render here + download button.</div>
            </div>
            <div id="previewWrap" class="hidden">
              <div class="flex items-center justify-between mb-2">
                <div class="text-xs text-[#9aa4b2]"><span id="previewMeta"></span></div>
                <a id="downloadBtn" href="#" download="edited.pdf" class="px-3 py-1.5 rounded-full bg-[#2ec4b6] text-[#0b0e14] text-xs font-bold hover:bg-[#25b0a3] transition flex items-center gap-1"><i class="ri-download-2-line"></i> Download PDF</a>
              </div>
              <div class="rounded-xl overflow-hidden border border-[#232a36] bg-white">
                <iframe id="pdfPreview" class="w-full h-[520px] bg-white" title="PDF preview"></iframe>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Fidelity explainer -->
      <div class="rounded-2xl bg-[#151a23] border border-[#232a36] p-4">
        <h4 class="text-sm font-semibold flex items-center gap-2"><i class="ri-information-line text-[#7c5cff]"></i> FidelityReport — what to gate on</h4>
        <div class="mt-2 grid sm:grid-cols-3 gap-2 text-xs">
          <div class="rounded-xl bg-[#0f1320] border border-[#232a36] p-2.5"><div class="font-semibold text-white">font_preserved</div><div class="text-[#9aa4b2]">True iff no <code class="bg-white/10 px-1 rounded">FONT_AFFECTING</code> degradation</div></div>
          <div class="rounded-xl bg-[#0f1320] border border-[#232a36] p-2.5"><div class="font-semibold text-white">overflow_detected</div><div class="text-[#9aa4b2]">Text wider than original slot</div></div>
          <div class="rounded-xl bg-[#0f1320] border border-[#232a36] p-2.5"><div class="font-semibold text-white">degradations[]</div><div class="text-[#9aa4b2]">Gate on this, not <code class="bg-white/10 px-1 rounded">font_preserved</code></div></div>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- Features -->
<section id="features" class="max-w-[1280px] mx-auto px-4 sm:px-6 mt-10">
  <h2 class="text-xl font-bold">Everything the engine can do</h2>
  <p class="text-sm text-[#9aa4b2] mt-1">Same library powers the HTTP API and the Python package.</p>
  <div class="mt-4 grid md:grid-cols-3 gap-4">
    <div class="rounded-2xl bg-[#151a23] border border-[#232a36] p-5">
      <div class="w-9 h-9 rounded-xl bg-[#7c5cff]/15 border border-[#7c5cff]/20 flex items-center justify-center text-[#7c5cff]"><i class="ri-search-line"></i></div>
      <h3 class="mt-3 font-semibold">Search & Locate</h3>
      <p class="mt-1 text-sm text-[#9aa4b2]">Position-aware <code class="bg-[#0f1320] border border-[#232a36] px-1 rounded">find()</code> across split operators, bbox-aware <code class="bg-[#0f1320] border px-1 rounded">get_text_layout</code>, <code class="bg-[#0f1320] border px-1 rounded">extract_bbox_text</code>.</p>
      <div class="mt-3 flex flex-wrap gap-1.5 text-[11px]"><span class="px-2 py-1 rounded-full bg-[#0f1320] border border-[#232a36]">find</span><span class="px-2 py-1 rounded-full bg-[#0f1320] border border-[#232a36]">get_text</span><span class="px-2 py-1 rounded-full bg-[#0f1320] border border-[#232a36]">get_fonts</span></div>
    </div>
    <div class="rounded-2xl bg-[#151a23] border border-[#232a36] p-5">
      <div class="w-9 h-9 rounded-xl bg-emerald-500/15 border border-emerald-500/20 flex items-center justify-center text-emerald-400"><i class="ri-quill-pen-line"></i></div>
      <h3 class="mt-3 font-semibold">Replace (preserving)</h3>
      <p class="mt-1 text-sm text-[#9aa4b2]"><code class="bg-[#0f1320] border px-1 rounded">replace</code> / <code class="bg-[#0f1320] border px-1 rounded">replace_all</code> / <code class="bg-[#0f1320] border px-1 rounded">batch_replace</code> with kerning via <code class="bg-[#0f1320] border px-1 rounded">Tz</code> and subset extension.</p>
      <div class="mt-3 flex flex-wrap gap-1.5 text-[11px]"><span class="px-2 py-1 rounded-full bg-[#0f1320] border border-[#232a36]">Tz kerning</span><span class="px-2 py-1 rounded-full bg-[#0f1320] border border-[#232a36]">CMap fast-path</span><span class="px-2 py-1 rounded-full bg-[#0f1320] border border-[#232a36]">Tier 1.5 injection</span></div>
    </div>
    <div class="rounded-2xl bg-[#151a23] border border-[#232a36] p-5">
      <div class="w-9 h-9 rounded-xl bg-amber-500/15 border border-amber-500/20 flex items-center justify-center text-amber-400"><i class="ri-layout-line"></i></div>
      <h3 class="mt-3 font-semibold">Structural & Reflow</h3>
      <p class="mt-1 text-sm text-[#9aa4b2]"><code class="bg-[#0f1320] border px-1 rounded">replace_block</code>, <code class="bg-[#0f1320] border px-1 rounded">delete_block</code>, <code class="bg-[#0f1320] border px-1 rounded">insert_text_block</code>, <code class="bg-[#0f1320] border px-1 rounded">reflow_paragraph</code> greedy line-break.</p>
      <div class="mt-3 flex flex-wrap gap-1.5 text-[11px]"><span class="px-2 py-1 rounded-full bg-[#0f1320] border border-[#232a36]">bbox edits</span><span class="px-2 py-1 rounded-full bg-[#0f1320] border border-[#232a36]">reflow</span><span class="px-2 py-1 rounded-full bg-[#0f1320] border border-[#232a36]">detect_paragraphs</span></div>
    </div>
    <div class="rounded-2xl bg-[#151a23] border border-[#232a36] p-5">
      <div class="w-9 h-9 rounded-xl bg-sky-500/15 border border-sky-500/20 flex items-center justify-center text-sky-400"><i class="ri-font-size"></i></div>
      <h3 class="mt-3 font-semibold">Fonts</h3>
      <p class="mt-1 text-sm text-[#9aa4b2]">Analyze subsets, <code class="bg-[#0f1320] border px-1 rounded">can_render</code> check, 2-tier extension (CMap-only + in-place glyph injection).</p>
      <div class="mt-3 flex flex-wrap gap-1.5 text-[11px]"><span class="px-2 py-1 rounded-full bg-[#0f1320] border border-[#232a36]">analyze_subset</span><span class="px-2 py-1 rounded-full bg-[#0f1320] border border-[#232a36]">extend_subset</span></div>
    </div>
    <div class="rounded-2xl bg-[#151a23] border border-[#232a36] p-5">
      <div class="w-9 h-9 rounded-xl bg-violet-500/15 border border-violet-500/20 flex items-center justify-center text-violet-400"><i class="ri-file-copy-line"></i></div>
      <h3 class="mt-3 font-semibold">PDF Ops (15)</h3>
      <p class="mt-1 text-sm text-[#9aa4b2]">Merge, split, rotate, encrypt, crop, watermark, Bookmarks, hyperlinks…</p>
      <div class="mt-3 flex flex-wrap gap-1.5 text-[11px]"><span class="px-2 py-1 rounded-full bg-[#0f1320] border border-[#232a36]">merge_pdfs</span><span class="px-2 py-1 rounded-full bg-[#0f1320] border border-[#232a36]">encrypt_pdf</span><span class="px-2 py-1 rounded-full bg-[#0f1320] border border-[#232a36]">rotate_pages</span></div>
    </div>
    <div class="rounded-2xl bg-[#151a23] border border-[#232a36] p-5">
      <div class="w-9 h-9 rounded-xl bg-rose-500/15 border border-rose-500/20 flex items-center justify-center text-rose-400"><i class="ri-annotation-line"></i></div>
      <h3 class="mt-3 font-semibold">Annotations</h3>
      <p class="mt-1 text-sm text-[#9aa4b2]">Read, create, move, update URIs, delete — with annotation shift on edits.</p>
      <div class="mt-3 flex flex-wrap gap-1.5 text-[11px]"><span class="px-2 py-1 rounded-full bg-[#0f1320] border border-[#232a36]">get_annotations</span><span class="px-2 py-1 rounded-full bg-[#0f1320] border border-[#232a36]">add_annotation</span></div>
    </div>
  </div>

  <!-- Comparison -->
  <div class="mt-6 rounded-2xl bg-[#151a23] border border-[#232a36] overflow-hidden">
    <div class="px-5 py-4 border-b border-[#232a36] flex items-center justify-between">
      <h3 class="font-semibold">Why not redact-and-replace?</h3>
      <span class="text-xs px-2 py-1 rounded-full bg-[#0f1320] border border-[#232a36] text-[#9aa4b2]">Operator-level precision</span>
    </div>
    <div class="overflow-auto">
      <table class="w-full text-sm">
        <thead class="text-xs tracking-wide uppercase text-[#5a6475] bg-[#0f1320]/50"><tr><th class="text-left px-5 py-2 font-semibold">Approach</th><th class="text-left px-5 py-2 font-semibold">Font</th><th class="text-left px-5 py-2 font-semibold">Layout</th><th class="text-left px-5 py-2 font-semibold">Verification</th></tr></thead>
        <tbody class="divide-y divide-[#232a36]">
          <tr class="bg-[#0f1320]/30"><td class="px-5 py-3"><span class="inline-flex items-center gap-1.5"><span class="w-2 h-2 rounded-full bg-amber-400"></span> PyMuPDF (redact)</span></td><td class="px-5 py-3 text-[#9aa4b2]">Substituted (Helvetica)</td><td class="px-5 py-3 text-[#9aa4b2]">Re-calculated</td><td class="px-5 py-3 text-[#9aa4b2]">None — silent</td></tr>
          <tr><td class="px-5 py-3 font-semibold text-white"><span class="inline-flex items-center gap-1.5"><span class="w-2 h-2 rounded-full bg-emerald-400"></span> pdf-edit-engine</span></td><td class="px-5 py-3 text-white">Original preserved</td><td class="px-5 py-3 text-white">Exact positioning</td><td class="px-5 py-3"><span class="px-2 py-1 rounded-full bg-emerald-500/15 border border-emerald-500/20 text-emerald-400 text-xs">FidelityReport</span></td></tr>
        </tbody>
      </table>
    </div>
  </div>
</section>

<!-- How it works + Quickstart -->
<section id="quickstart" class="max-w-[1280px] mx-auto px-4 sm:px-6 mt-8 grid lg:grid-cols-[1.1fr_0.9fr] gap-4">
  <div class="rounded-2xl bg-[#151a23] border border-[#232a36] p-5">
    <h3 class="font-bold flex items-center gap-2"><i class="ri-flow-chart text-[#7c5cff]"></i> How it works</h3>
    <ol class="mt-3 space-y-2.5 text-sm">
      <li class="flex gap-3"><span class="w-6 h-6 rounded-full bg-[#1e2433] border border-[#232a36] flex items-center justify-center text-xs font-bold">1</span><span><span class="font-semibold">Index</span> — <span class="text-[#9aa4b2]">Interpret BT/ET blocks, track graphics state per page</span></span></li>
      <li class="flex gap-3"><span class="w-6 h-6 rounded-full bg-[#1e2433] border flex items-center justify-center text-xs font-bold">2</span><span><span class="font-semibold">Match</span> — <span class="text-[#9aa4b2]">Assemble characters, position-aware matching across split operators</span></span></li>
      <li class="flex gap-3"><span class="w-6 h-6 rounded-full bg-[#1e2433] border flex items-center justify-center text-xs font-bold">3</span><span><span class="font-semibold">Encode</span> — <span class="text-[#9aa4b2]">CID (Identity-H) or WinAnsi, micro-kerning via Tz</span></span></li>
      <li class="flex gap-3"><span class="w-6 h-6 rounded-full bg-[#1e2433] border flex items-center justify-center text-xs font-bold">4</span><span><span class="font-semibold">Extend</span> — <span class="text-[#9aa4b2]">CMap fast-path or Tier 1.5 in-place glyph injection</span></span></li>
      <li class="flex gap-3"><span class="w-6 h-6 rounded-full bg-[#1e2433] border flex items-center justify-center text-xs font-bold">5</span><span><span class="font-semibold">Reflow</span> — <span class="text-[#9aa4b2]">Greedy line-break if wider, else in-place splice</span></span></li>
      <li class="flex gap-3"><span class="w-6 h-6 rounded-full bg-[#1e2433] border flex items-center justify-center text-xs font-bold">6</span><span><span class="font-semibold">Serialize</span> — <span class="text-[#9aa4b2]">pikepdf.unparse_content_stream() + save</span></span></li>
    </ol>
  </div>
  <div class="rounded-2xl bg-[#151a23] border border-[#232a36] p-5">
    <h3 class="font-bold flex items-center gap-2"><i class="ri-terminal-box-line text-[#2ec4b6]"></i> Quick start</h3>
    <div class="mt-3 rounded-xl bg-[#0b0e14] border border-[#232a36] overflow-hidden">
      <div class="flex items-center justify-between px-3 py-2 border-b border-[#232a36] bg-[#0f1320]">
        <span class="text-xs font-mono text-[#9aa4b2]">python</span>
        <button onclick="navigator.clipboard.writeText(document.getElementById('qs').innerText)" class="text-xs px-2 py-1 rounded-full bg-[#1e2433] border border-[#232a36] hover:bg-[#232a36] transition">Copy</button>
      </div>
      <pre id="qs" class="p-3 text-[12.5px] leading-relaxed overflow-auto"><code>pip install pdf-edit-engine

from pdf_edit_engine import find, replace

matches = find("document.pdf", "Software Engineer")
result = replace("document.pdf", matches[0], "Senior Engineer", "output.pdf")

report = result.fidelity_report
assert report.font_preserved          # original font kept
assert not report.overflow_detected   # fits in original slot
# every edit is explainable:
for d in report.degradations:
    print(d.kind, d.severity, d.detail)</code></pre>
    </div>
    <div class="mt-3 rounded-xl bg-[#0f1320] border border-[#232a36] p-3 text-xs text-[#9aa4b2]">
      Batch: <code class="bg-[#151a23] border border-[#232a36] px-1.5 py-0.5 rounded">batch_replace("in.pdf", [Edit(find="John", replace="Jane")], "out.pdf")</code> • Structural: <code class="bg-[#151a23] border px-1.5 py-0.5 rounded">replace_block(...)</code> • Dry run: <code class="bg-[#151a23] border px-1.5 py-0.5 rounded">replace(..., dry_run=True)</code>
    </div>
  </div>
</section>

<!-- API -->
<section id="api" class="max-w-[1280px] mx-auto px-4 sm:px-6 mt-8">
  <div class="rounded-2xl bg-[#151a23] border border-[#232a36] overflow-hidden">
    <div class="px-5 py-4 border-b border-[#232a36] flex flex-wrap items-center justify-between gap-3">
      <h2 class="font-bold flex items-center gap-2"><i class="ri-code-s-slash-line text-[#7c5cff]"></i> HTTP API</h2>
      <div class="flex items-center gap-2 text-xs">
        <span class="px-2.5 py-1 rounded-full bg-[#0f1320] border border-[#232a36] text-[#9aa4b2]">Base: <span class="text-white font-mono" id="apiBase">/api</span></span>
        <a href="/api/health" target="_blank" class="px-3 py-1.5 rounded-full bg-white text-[#0b0e14] font-semibold">/health</a>
        <a href="/api/docs" target="_blank" class="px-3 py-1.5 rounded-full bg-[#1e2433] border border-[#232a36]">/docs</a>
      </div>
    </div>
    <div class="grid lg:grid-cols-2 gap-0 divide-y lg:divide-y-0 lg:divide-x divide-[#232a36]">
      <div class="p-5">
        <h3 class="font-semibold text-sm">Endpoints</h3>
        <dl class="mt-3 space-y-3 text-sm">
          <div class="rounded-xl bg-[#0f1320] border border-[#232a36] p-3"><dt class="font-mono text-xs font-bold text-emerald-400">GET /api/health</dt><dd class="text-xs text-[#9aa4b2] mt-1">Version, python, entrypoint</dd></div>
          <div class="rounded-xl bg-[#0f1320] border border-[#232a36] p-3"><dt class="font-mono text-xs font-bold text-sky-400">POST /api/find</dt><dd class="text-xs text-[#9aa4b2] mt-1">multipart: <code class="bg-[#151a23] px-1 rounded">file</code> + <code class="bg-[#151a23] px-1 rounded">query</code> → <code class="bg-[#151a23] px-1 rounded">{count,matches:[{text,page_index,bbox}]}</code></dd></div>
          <div class="rounded-xl bg-[#0f1320] border border-[#232a36] p-3"><dt class="font-mono text-xs font-bold text-[#7c5cff]">POST /api/replace</dt><dd class="text-xs text-[#9aa4b2] mt-1">multipart: <code class="bg-[#151a23] px-1 rounded">file</code> + <code class="bg-[#151a23] px-1 rounded">find</code> + <code class="bg-[#151a23] px-1 rounded">replace</code> → <code class="bg-[#151a23] px-1 rounded">application/pdf</code> + <code class="bg-[#151a23] px-1 rounded">X-Fidelity-*</code> headers</dd></div>
          <div class="rounded-xl bg-[#0f1320] border border-[#232a36] p-3"><dt class="font-mono text-xs font-bold text-[#7c5cff]">POST /api/replace-all</dt><dd class="text-xs text-[#9aa4b2] mt-1">Same as above, but batch replaces all occurrences</dd></div>
        </dl>
      </div>
      <div class="p-5">
        <h3 class="font-semibold text-sm">Curl examples</h3>
        <div class="mt-3 space-y-3">
          <div class="rounded-xl bg-[#0b0e14] border border-[#232a36] p-3">
            <div class="text-[11px] tracking-wide uppercase font-semibold text-[#5a6475]">Find</div>
            <pre class="mt-1 text-[11.5px] overflow-auto"><code>curl -X POST https://your-app.vercel.app/api/find \
  -F file=@document.pdf -F query="Software Engineer"</code></pre>
          </div>
          <div class="rounded-xl bg-[#0b0e14] border border-[#232a36] p-3">
            <div class="text-[11px] tracking-wide uppercase font-semibold text-[#5a6475]">Replace (single)</div>
            <pre class="mt-1 text-[11.5px] overflow-auto"><code>curl -X POST https://your-app.vercel.app/api/replace \
  -F file=@document.pdf -F find="Software Engineer" \
  -F replace="Senior Engineer" -o edited.pdf</code></pre>
          </div>
          <div class="rounded-xl bg-[#0b0e14] border border-[#232a36] p-3">
            <div class="text-[11px] tracking-wide uppercase font-semibold text-[#5a6475]">Dry run (preview FidelityReport)</div>
            <pre class="mt-1 text-[11.5px] overflow-auto"><code>curl -X POST https://your-app.vercel.app/api/replace \
  -F file=@document.pdf -F find="John Doe" \
  -F replace="Jane Smith" -F dry_run=true</code></pre>
          </div>
        </div>
      </div>
    </div>
  </div>
</section>

<footer class="max-w-[1280px] mx-auto px-4 sm:px-6 py-8 text-xs text-[#5a6475]">
  <div class="rounded-2xl bg-[#151a23] border border-[#232a36] p-4 flex flex-wrap items-center justify-between gap-3">
    <div>pdf-edit-engine v0.2.0 • MIT • Built from <a href="https://github.com/AryanBV/pdf-edit-engine" class="text-[#8ea0ff] hover:underline">AryanBV/pdf-edit-engine</a> • Deployed on Vercel (Python 3.12)</div>
    <div class="flex items-center gap-2"><span class="px-2 py-1 rounded-full bg-[#0f1320] border border-[#232a36]">pikepdf ≥10</span><span class="px-2 py-1 rounded-full bg-[#0f1320] border border-[#232a36]">fonttools ≥4.60.2</span><span class="px-2 py-1 rounded-full bg-[#0f1320] border border-[#232a36]">pdfminer.six</span></div>
  </div>
</footer>

<div id="toast" class="fixed bottom-4 left-1/2 -translate-x-1/2 hidden px-4 py-2.5 rounded-full bg-[#1e2433] border border-[#232a36] text-sm shadow-xl z-50"></div>

<script>
const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);
const apiBase = location.origin;
$('#apiBase').textContent = apiBase + '/api';

// Health
fetch('/api/health').then(r=>r.json()).then(j=>{
  $('#healthBadge').textContent = `● ${j.version} • ${j.python.split(' ')[0]}`;
  $('#healthBadge').className = 'text-xs px-2.5 py-1 rounded-full bg-emerald-500/15 border border-emerald-500/20 text-emerald-400';
}).catch(()=>{
  $('#healthBadge').textContent = '● api unreachable';
  $('#healthBadge').className = 'text-xs px-2.5 py-1 rounded-full bg-rose-500/15 border border-rose-500/20 text-rose-400';
});

// Tabs
$$('.tabBtn').forEach(b=>{
  b.addEventListener('click',()=>{
    $$('.tabBtn').forEach(x=>{x.classList.remove('tab-active'); x.classList.add('border-[#232a36]','text-[#9aa4b2]')});
    b.classList.add('tab-active'); b.classList.remove('border-[#232a36]','text-[#9aa4b2]');
    const t=b.dataset.tab;
    $('#tab-matches').classList.toggle('hidden', t!=='matches');
    $('#tab-fidelity').classList.toggle('hidden', t!=='fidelity');
    $('#tab-preview').classList.toggle('hidden', t!=='preview');
  });
});
function toast(msg, ok=true){
  const t=$('#toast'); t.textContent=msg; t.classList.remove('hidden');
  t.style.background = ok ? '#1e2433' : '#2a1a1a'; t.style.borderColor = ok ? '#232a36' : '#4a2323';
  setTimeout(()=>t.classList.add('hidden'), 2600);
}

// File state
let currentFile=null;
let lastPreviewUrl=null;

function setFile(file){
  if(!file) return;
  if(file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')){
    toast('Please select a PDF file', false); return;
  }
  currentFile=file;
  $('#dropContent').classList.add('hidden');
  $('#fileMeta').classList.remove('hidden');
  $('#fileName').textContent=file.name;
  $('#fileSize').textContent=(file.size/1024).toFixed(1)+' KB • '+file.type;
  $('#filePages').textContent='Ready to edit';
  $('#uploadBar').style.width='100%';
  $('#uploadStatus').textContent='✓ Ready — now enter Find text and hit Find or Replace.';
  $('#uploadStatus').className='mt-2 text-xs text-emerald-400';
}

$('#fileInput').addEventListener('change', e=> setFile(e.target.files[0]));
$('#dropZone').addEventListener('dragover', e=>{e.preventDefault(); e.currentTarget.classList.add('drop-active')});
$('#dropZone').addEventListener('dragleave', e=> e.currentTarget.classList.remove('drop-active'));
$('#dropZone').addEventListener('drop', e=>{
  e.preventDefault(); e.currentTarget.classList.remove('drop-active');
  const f=e.dataTransfer.files[0]; if(f) setFile(f);
});
$('#clearFile').addEventListener('click', ()=>{
  currentFile=null; $('#fileInput').value=''; $('#dropContent').classList.remove('hidden'); $('#fileMeta').classList.add('hidden');
  $('#uploadBar').style.width='0'; $('#uploadStatus').textContent=''; $('#matchesList').classList.add('hidden'); $('#emptyMatches').classList.remove('hidden');
  $('#resultBadge').classList.add('hidden'); if(lastPreviewUrl) URL.revokeObjectURL(lastPreviewUrl);
});
$('#clearFind').addEventListener('click', ()=>{ $('#findInput').value=''; $('#findInput').focus(); });
$('#btnClear').addEventListener('click', ()=>{
  $('#findInput').value=''; $('#replaceInput').value='';
  $('#matchesList').classList.add('hidden'); $('#emptyMatches').classList.remove('hidden');
  $('#fidelityPanel').classList.add('hidden'); $('#emptyFidelity').classList.remove('hidden');
  $('#previewWrap').classList.add('hidden'); $('#emptyPreview').classList.remove('hidden');
  $('#resultBadge').classList.add('hidden'); $('#controlStatus').textContent='';
});

function requireFile(){
  if(!currentFile){ toast('Upload a PDF first', false); return false; }
  return true;
}
function setLoading(btn, loading, label){
  btn.disabled=loading; btn.style.opacity=loading?'0.6':'1';
  if(loading) btn.dataset.orig=btn.innerHTML, btn.innerHTML='<i class="ri-loader-4-line animate-spin"></i> '+label;
  else if(btn.dataset.orig) btn.innerHTML=btn.dataset.orig;
}

// Find
$('#btnFind').addEventListener('click', async ()=>{
  if(!requireFile()) return;
  const q=$('#findInput').value.trim();
  if(!q){ toast('Enter text to find', false); return; }
  const btn=$('#btnFind'); setLoading(btn,true,'Finding…');
  $('#controlStatus').textContent='Searching operator stream…';
  try{
    const fd=new FormData(); fd.append('file', currentFile); fd.append('query', q);
    const res=await fetch('/api/find', {method:'POST', body: fd});
    const j=await res.json();
    if(!res.ok) throw new Error(j.error || 'Find failed');
    const list=$('#matchesList'); list.innerHTML='';
    if(j.count===0){
      list.classList.remove('hidden'); $('#emptyMatches').classList.add('hidden');
      list.innerHTML='<div class="rounded-xl bg-[#0f1320] border border-[#232a36] p-4 text-sm text-center text-[#9aa4b2]">No matches for <span class="text-white font-mono">'+q+'</span></div>';
    } else {
      $('#emptyMatches').classList.add('hidden'); list.classList.remove('hidden');
      j.matches.forEach((m,i)=>{
        const el=document.createElement('div');
        el.className='rounded-xl bg-[#0f1320] border border-[#232a36] p-3 flex items-center justify-between gap-3';
        el.innerHTML='<div class="min-w-0"><div class="text-sm font-medium truncate">'+(m.text||'(match '+(i+1)+')')+'</div><div class="text-xs text-[#9aa4b2]">Page '+m.page_index+' • bbox '+ (m.bbox?('['+m.bbox.map(v=>v.toFixed(1)).join(', ')+']'):'—') +'</div></div><span class="shrink-0 text-xs px-2 py-1 rounded-full bg-[#7c5cff]/15 border border-[#7c5cff]/20 text-[#8ea0ff]">#'+(i+1)+'</span>';
        list.appendChild(el);
      });
    }
    $('#resultBadge').textContent=j.count+' match'+(j.count!==1?'es':''); $('#resultBadge').classList.remove('hidden');
    // switch to matches tab
    $$('.tabBtn').forEach(b=> b.dataset.tab==='matches' && b.click());
    $('#controlStatus').textContent='Found '+j.count+' match'+(j.count!==1?'es':'')+' for "'+q+'".';
    toast('Found '+j.count+' match'+(j.count!==1?'es':''));
  }catch(e){
    toast(e.message, false); $('#controlStatus').textContent='Error: '+e.message; $('#controlStatus').className='mt-3 text-xs text-rose-400';
  } finally{ setLoading(btn,false); }
});

// Replace (single)
$('#btnReplace').addEventListener('click', ()=> doReplace(false));
$('#btnReplaceAll').addEventListener('click', ()=> doReplace(true));

async function doReplace(all){
  if(!requireFile()) return;
  const find=$('#findInput').value.trim();
  const repl=$('#replaceInput').value; // may be empty
  const dry=$('#dryRunToggle').checked;
  if(!find){ toast('Enter Find text', false); return; }
  const btn = all ? $('#btnReplaceAll') : $('#btnReplace');
  setLoading(btn,true, dry?'Previewing…':'Replacing…');
  $('#controlStatus').textContent = dry ? 'Dry run — previewing FidelityReport…' : (all ? 'Replacing all occurrences…' : 'Replacing…');
  try{
    const fd=new FormData(); fd.append('file', currentFile); fd.append('find', find); fd.append('replace', repl);
    if(dry) fd.append('dry_run','true');
    const endpoint = all ? '/api/replace-all' : '/api/replace';
    const res=await fetch(endpoint, {method:'POST', body: fd});
    if(dry){
      const j=await res.json();
      if(!res.ok) throw new Error(j.error || 'Dry run failed');
      renderFidelity(j.fidelity || j.fidelity_report || j);
      $$('.tabBtn').forEach(b=> b.dataset.tab==='fidelity' && b.click());
      $('#controlStatus').textContent='Dry run — FidelityReport ready (no file written).';
      toast('Dry run OK');
      return;
    }
    if(!res.ok){
      let msg='Replace failed';
      try{ const j=await res.json(); msg=j.error || msg; } catch{ msg=await res.text(); }
      throw new Error(msg);
    }
    // binary PDF
    const blob=await res.blob();
    const url=URL.createObjectURL(blob);
    if(lastPreviewUrl) URL.revokeObjectURL(lastPreviewUrl); lastPreviewUrl=url;
    $('#pdfPreview').src=url;
    $('#downloadBtn').href=url;
    $('#downloadBtn').download='edited-'+(currentFile.name||'document.pdf');
    $('#previewWrap').classList.remove('hidden'); $('#emptyPreview').classList.add('hidden');
    $('#previewMeta').textContent=(all?'Replace All':'Replace')+' • '+(blob.size/1024).toFixed(1)+' KB';
    // fidelity from headers
    const fPres = res.headers.get('X-Fidelity-Font-Preserved');
    const fOver = res.headers.get('X-Fidelity-Overflow');
    const fGlyph = res.headers.get('X-Fidelity-Glyphs-Missing');
    const fDegr = res.headers.get('X-Fidelity-Degradations');
    // try to render fidelity from headers + fallback
    renderFidelityFromHeaders({font_preserved:fPres, overflow_detected:fOver, glyphs_missing:fGlyph, degradations:fDegr});
    $$('.tabBtn').forEach(b=> b.dataset.tab==='preview' && b.click());
    $('#controlStatus').textContent='✓ Edited PDF ready — preview + download below.';
    $('#controlStatus').className='mt-3 text-xs text-emerald-400';
    toast('Edited PDF ready');
  }catch(e){
    toast(e.message, false); $('#controlStatus').textContent='Error: '+e.message; $('#controlStatus').className='mt-3 text-xs text-rose-400';
  } finally{ setLoading(btn,false); }
}

function renderFidelity(j){
  $('#emptyFidelity').classList.add('hidden'); $('#fidelityPanel').classList.remove('hidden');
  const fp = j.font_preserved ?? j.fontPreserved ?? (j.font_substituted==null);
  const over = j.overflow_detected ?? j.overflow ?? false;
  const glyphs = j.glyphs_missing ?? j.glyphsMissing ?? [];
  const degr = j.degradations ?? j.degradation ?? [];
  $('#fFont').textContent = fp ? '✓ Yes' : '✗ No';
  $('#fFont').className = 'mt-1 text-sm font-bold ' + (fp?'text-emerald-400':'text-amber-400');
  $('#fOverflow').textContent = over ? '⚠ Yes' : '— No';
  $('#fOverflow').className = 'mt-1 text-sm font-bold ' + (over?'text-amber-400':'text-[#9aa4b2]');
  $('#fGlyphs').textContent = glyphs.length ? glyphs.join(', ') : '—';
  $('#fRaw').textContent = JSON.stringify(j, null, 2);
  const box=$('#fDegradations'); box.innerHTML='';
  if(!degr || degr.length===0) box.innerHTML='<div class="text-xs text-[#5a6475]">No degradations — ideal edit.</div>';
  else degr.forEach(d=>{
    const sev = (d.severity||'info');
    const color = sev==='warning'?'bg-amber-500/15 border-amber-500/20 text-amber-300' : sev==='error'?'bg-rose-500/15 border-rose-500/20 text-rose-300' : 'bg-sky-500/15 border-sky-500/20 text-sky-300';
    const row=document.createElement('div'); row.className='rounded-lg border p-2 flex gap-2 '+color;
    row.innerHTML='<span class="shrink-0 px-1.5 py-0.5 rounded-full bg-black/20 text-[10px] font-bold uppercase">'+sev+'</span><span class="min-w-0"><span class="font-mono font-semibold">'+(d.kind||'unknown')+'</span><span class="opacity-80"> — '+(d.detail||'')+'</span></span>';
    box.appendChild(row);
  });
}
function renderFidelityFromHeaders(h){
  $('#emptyFidelity').classList.add('hidden'); $('#fidelityPanel').classList.remove('hidden');
  $('#fFont').textContent = h.font_preserved==='True' ? '✓ Yes' : h.font_preserved==='False' ? '✗ No' : '—';
  $('#fOverflow').textContent = h.overflow_detected==='True' ? '⚠ Yes' : '— No';
  $('#fGlyphs').textContent = h.glyphs_missing || '—';
  $('#fRaw').textContent = JSON.stringify(h, null, 2);
  $('#fDegradations').innerHTML='<div class="text-xs text-[#5a6475]">Degradations list available via dry_run preview (headers are summary). For full list, enable <span class="text-white">Dry run</span>.</div>';
}
</script>
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
                "fields": {"file": "PDF", "find": "text", "replace": "text", "dry_run": "true|false"},
                "returns": "application/pdf (edited file) + X-Fidelity headers, or JSON if dry_run=true",
            },
            "POST /api/replace-all": {
                "contentType": "multipart/form-data",
                "fields": {"file": "PDF", "find": "text", "replace": "text", "dry_run": "true|false"},
                "returns": "application/pdf or JSON",
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
        if body.endswith(b"\r\n"):
            body = body[:-2]
        header_str = header_raw.decode(errors="ignore")
        name = None
        filename = None
        for line in header_str.split("\r\n"):
            low = line.lower()
            if "content-disposition" in low:
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
        dry_run = str(fields.get("dry_run") or "").lower() in ("1", "true", "yes")
        if not find_text:
            _json_response(self, 400, {"error": "missing field 'find'"})
            return
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

            if dry_run:
                # dry_run: return JSON fidelity without writing PDF
                if all_occurrences:
                    results = pdf_replace_all(
                        in_path, str(find_text), str(replace_text), out_path, dry_run=True
                    )
                    report = results[0].fidelity_report if results else None
                    payload = {
                        "dry_run": True,
                        "mode": "replace_all",
                        "count": len(results),
                        "fidelity": {
                            "font_preserved": getattr(report, "font_preserved", None),
                            "font_substituted": getattr(report, "font_substituted", None),
                            "overflow_detected": getattr(report, "overflow_detected", None),
                            "reflow_applied": getattr(report, "reflow_applied", None),
                            "glyphs_missing": getattr(report, "glyphs_missing", None),
                            "degradations": [
                                {"kind": d.kind, "severity": d.severity, "detail": d.detail}
                                for d in getattr(report, "degradations", [])
                            ]
                            if report
                            else [],
                        },
                    }
                else:
                    result = pdf_replace(in_path, matches[0], str(replace_text), out_path, dry_run=True)
                    report = result.fidelity_report
                    payload = {
                        "dry_run": True,
                        "mode": "replace",
                        "fidelity": {
                            "font_preserved": getattr(report, "font_preserved", None),
                            "font_substituted": getattr(report, "font_substituted", None),
                            "overflow_detected": getattr(report, "overflow_detected", None),
                            "reflow_applied": getattr(report, "reflow_applied", None),
                            "glyphs_missing": getattr(report, "glyphs_missing", None),
                            "degradations": [
                                {"kind": d.kind, "severity": d.severity, "detail": d.detail}
                                for d in getattr(report, "degradations", [])
                            ],
                        },
                        "success": getattr(result, "success", None),
                    }
                _json_response(self, 200, payload)
                return

            if all_occurrences:
                results = pdf_replace_all(in_path, str(find_text), str(replace_text), out_path)
                report = results[0].fidelity_report if results else None
            else:
                result = pdf_replace(in_path, matches[0], str(replace_text), out_path)
                report = result.fidelity_report

            with open(out_path, "rb") as f:
                pdf_bytes = f.read()

            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Length", str(len(pdf_bytes)))
            self.send_header("Content-Disposition", 'attachment; filename="edited.pdf"')
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header(
                "Access-Control-Expose-Headers",
                "X-Fidelity-Font-Preserved, X-Fidelity-Overflow, X-Fidelity-Glyphs-Missing, X-Fidelity-Degradations",
            )
            if report is not None:
                try:
                    self.send_header(
                        "X-Fidelity-Font-Preserved", str(getattr(report, "font_preserved", ""))
                    )
                    self.send_header(
                        "X-Fidelity-Overflow", str(getattr(report, "overflow_detected", ""))
                    )
                    gm = getattr(report, "glyphs_missing", [])
                    self.send_header("X-Fidelity-Glyphs-Missing", ",".join(gm) if gm else "")
                    degrs = getattr(report, "degradations", [])
                    if degrs:
                        self.send_header(
                            "X-Fidelity-Degradations",
                            "; ".join(f"{d.kind}:{d.severity}" for d in degrs[:5]),
                        )
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
        sys.stderr.write(f"{self.client_address[0]} - - [{self.log_date_time_string()}] {format % args}\n")
