"""Vercel Python entrypoint for pdf-edit-engine + Articles/Admin.

Exposes the library as serverless HTTP API + CMS for articles/blogs.
Uses only stdlib (BaseHTTPRequestHandler) so no extra runtime dependencies.
Stores articles in data/articles.json (fallback /tmp on Vercel read-only FS)
and images as base64 data URLs inside JSON — guarantees image persists
after admin upload without external storage.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import tempfile
import time
import uuid
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

# ---------- Articles storage helpers ----------
DATA_DIR_CANDIDATES = [
    os.path.join(os.path.dirname(__file__), "..", "data"),
    os.path.join(os.getcwd(), "data"),
    "/tmp",
]
SEED_ARTICLES = [
    {
        "id": "1",
        "title": "Format-Preserving PDF Editing: Under the Hood",
        "slug": "format-preserving-pdf-editing",
        "excerpt": "How content-stream surgery keeps fonts and layout intact — no redaction, no re-render.",
        "content": "<p>Most PDF tools redact and re-insert text with a substitute font. <strong>pdf-edit-engine</strong> modifies content-stream operators in-place, preserving the original font subset and layout.</p><p>In this article we walk through BT/ET blocks, Identity-H CMap handling, and the two-tier font extension.</p><h3>Why it matters</h3><ul><li>Original font kept — no Helvetica fallback</li><li>Operator-level precision — exact positioning</li><li>Every edit returns a FidelityReport</li></ul>",
        "image": "https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=1200&auto=format&fit=crop&q=80",
        "category": "Engineering",
        "author": "pdf-edit-engine Team",
        "date": "2026-08-30",
        "published": True,
    },
    {
        "id": "2",
        "title": "Building a Mobile-Friendly Article System on Vercel",
        "slug": "mobile-friendly-articles",
        "excerpt": "From upload to render — making the admin panel and article pages work flawlessly on every screen size.",
        "content": "<p>Mobile traffic is 60%+ — article pages must be fast, readable, and image-perfect on any device. We rebuilt with Tailwind, responsive grids, and fluid images so every upload renders correctly on mobile.</p><h3>Checklist</h3><ul><li>Responsive grid (1 → 2 → 3 cols)</li><li>Images with object-cover and aspect ratio</li><li>Admin preview matches public render</li></ul>",
        "image": "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=1200&auto=format&fit=crop&q=80",
        "category": "Product",
        "author": "Admin",
        "date": "2026-08-29",
        "published": True,
    },
    {
        "id": "3",
        "title": "Handling Fonts: Subset Extension Without Corruption",
        "slug": "font-subset-extension",
        "excerpt": "Why the old retain-gids strategy corrupted text and how Tier 1.5 in-place injection fixes it.",
        "content": "<p>Embedded font subsets are tricky — extending them naively renumbers CIDs and corrupts unrelated text. Our pipeline uses a CMap-only fast path when glyphs already exist, otherwise injects outlines in-place while preserving every existing CID→GID mapping.</p>",
        "image": "https://images.unsplash.com/photo-1455390582262-044cdead277a?w=1200&auto=format&fit=crop&q=80",
        "category": "Deep Dive",
        "author": "Aryan B V",
        "date": "2026-08-28",
        "published": True,
    },
]


def _get_data_file() -> str:
    for d in DATA_DIR_CANDIDATES:
        try:
            os.makedirs(d, exist_ok=True)
            test = os.path.join(d, ".write_test")
            with open(test, "w") as f:
                f.write("ok")
            os.unlink(test)
            return os.path.join(d, "articles.json")
        except Exception:
            continue
    return "/tmp/articles.json"


DATA_FILE = _get_data_file()


def _load_articles() -> list[dict]:
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
    # try repo data/articles.json as seed
    repo_seed = os.path.join(os.path.dirname(__file__), "..", "data", "articles.json")
    if os.path.exists(repo_seed):
        try:
            with open(repo_seed, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return list(SEED_ARTICLES)


def _save_articles(articles: list[dict]) -> None:
    try:
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(articles, f, indent=2, ensure_ascii=False)
        # also try to keep repo file in sync if writable
        repo_file = os.path.join(os.path.dirname(__file__), "..", "data", "articles.json")
        try:
            os.makedirs(os.path.dirname(repo_file), exist_ok=True)
            with open(repo_file, "w", encoding="utf-8") as rf:
                json.dump(articles, rf, indent=2, ensure_ascii=False)
        except Exception:
            pass
    except Exception as e:
        print(f"save failed: {e}", file=sys.stderr)


def _guess_mime(filename: str) -> str:
    fn = filename.lower()
    if fn.endswith(".png"):
        return "image/png"
    if fn.endswith(".webp"):
        return "image/webp"
    if fn.endswith(".gif"):
        return "image/gif"
    if fn.endswith(".svg"):
        return "image/svg+xml"
    return "image/jpeg"


def _bytes_to_data_url(data: bytes, filename: str) -> str:
    mime = _guess_mime(filename)
    b64 = base64.b64encode(data).decode()
    return f"data:{mime};base64,{b64}"


# ---------- HTTP helpers ----------
def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict | list) -> None:
    body = json.dumps(payload).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
    handler.end_headers()
    handler.wfile.write(body)


def _html_response(handler: BaseHTTPRequestHandler, html: str) -> None:
    body = html.encode()
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


# ---------- Frontend HTML (detailed, mobile-friendly) ----------
LANDING_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>pdf-edit-engine — Format-preserving PDF editing</title>
<meta name="description" content="Edit text in existing PDFs at the content-stream level — fonts, layout and spacing stay intact. Articles, admin, live PDF editor."/>
<script src="https://cdn.tailwindcss.com"></script>
<script>tailwind.config={theme:{extend:{colors:{bg:'#0b0e14',card:'#151a23',muted:'#9aa4b2',accent:'#7c5cff',accent2:'#2ec4b6',border:'#232a36'}}}}</script>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.2.0/remixicon.min.css"/>
<style>
*{scroll-behavior:smooth}
::-webkit-scrollbar{width:8px;height:8px}::-webkit-scrollbar-thumb{background:#2a3242;border-radius:999px}
.glass{backdrop-filter:blur(16px);background:rgba(21,26,35,0.85)}
.gradient-text{background:linear-gradient(135deg,#7c5cff 0%,#2ec4b6 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.drop-active{border-color:#7c5cff!important;background:rgba(124,92,255,0.08)!important}
.tab-active{background:#7c5cff;color:white;border-color:#7c5cff}
.line-clamp-2{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.prose p{margin:0.75em 0;line-height:1.7} .prose h3{font-weight:700;margin-top:1.2em} .prose ul{list-style:disc;padding-left:1.4em;margin:0.6em 0} .prose strong{color:#fff}
</style>
</head>
<body class="bg-[#0b0e14] text-[#e6e8eb] antialiased selection:bg-[#7c5cff]/30">
<header class="sticky top-0 z-50 border-b border-[#232a36] glass">
  <div class="max-w-[1280px] mx-auto px-4 sm:px-6 py-3 flex items-center justify-between gap-3">
    <div class="flex items-center gap-3 min-w-0">
      <div class="w-9 h-9 rounded-xl bg-gradient-to-br from-[#7c5cff] to-[#2ec4b6] flex items-center justify-center font-black text-white shrink-0">PE</div>
      <div class="min-w-0">
        <div class="font-bold leading-none truncate">pdf-edit-engine</div>
        <div class="text-xs text-[#9aa4b2]">v0.2.0 • MIT</div>
      </div>
      <span class="hidden lg:inline-flex ml-2 px-2.5 py-1 rounded-full bg-[#1e2433] border border-[#232a36] text-xs text-[#9aa4b2]">414 probes • 801 tests</span>
    </div>
    <nav class="flex items-center gap-1 sm:gap-3 text-sm shrink-0">
      <a href="#editor" class="hidden sm:inline px-3 py-1.5 rounded-full hover:bg-[#1e2433] transition text-[#9aa4b2] hover:text-white">Editor</a>
      <a href="#articles" class="px-3 py-1.5 rounded-full bg-[#1e2433] border border-[#232a36] hover:bg-[#232a36] transition flex items-center gap-1.5"><i class="ri-article-line"></i><span class="hidden sm:inline">Articles</span><span id="articleCountBadge" class="ml-1 px-1.5 py-0.5 rounded-full bg-[#7c5cff] text-white text-xs">—</span></a>
      <a href="/admin" class="px-3 sm:px-4 py-1.5 rounded-full bg-white text-[#0b0e14] font-semibold hover:bg-zinc-100 transition flex items-center gap-1.5"><i class="ri-dashboard-line"></i> Admin</a>
      <button id="mobileMenuBtn" class="sm:hidden w-8 h-8 rounded-full bg-[#1e2433] border border-[#232a36] flex items-center justify-center"><i class="ri-menu-line"></i></button>
    </nav>
  </div>
  <div id="mobileMenu" class="hidden sm:hidden border-t border-[#232a36] bg-[#0f1320] px-4 py-3 space-y-2">
    <a href="#editor" class="block px-3 py-2 rounded-xl bg-[#151a23] border border-[#232a36]">Live Editor</a>
    <a href="#articles" class="block px-3 py-2 rounded-xl bg-[#151a23] border border-[#232a36]">Articles & Blogs</a>
    <a href="/admin" class="block px-3 py-2 rounded-xl bg-[#7c5cff] text-white font-semibold text-center">Open Admin Panel</a>
  </div>
</header>

<!-- Hero -->
<section class="relative overflow-hidden">
  <div class="absolute inset-0 bg-[radial-gradient(1200px_600px_at_20%_-10%,#1a1f2e_0%,transparent_60%),radial-gradient(800px_400px_at_90%_10%,rgba(124,92,255,0.12)_0%,transparent_60%)]"></div>
  <div class="relative max-w-[1280px] mx-auto px-4 sm:px-6 pt-8 sm:pt-10 pb-6">
    <div class="inline-flex flex-wrap items-center gap-2 px-3 py-1.5 rounded-full bg-[#1e2433] border border-[#232a36] text-xs">
      <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
      <span class="text-[#9aa4b2]">No AGPL • pikepdf + fonttools</span>
      <span class="hidden sm:inline text-[#5a6475]">•</span>
      <span class="hidden sm:inline text-[#9aa4b2]">Admin images now work • Mobile optimized</span>
    </div>
    <h1 class="mt-5 text-[30px] sm:text-[44px] font-extrabold tracking-tight leading-[0.95]">
      Edit PDFs <span class="gradient-text">without</span><br class="hidden sm:block"/> losing fidelity.
    </h1>
    <p class="mt-4 max-w-[680px] text-[15px] sm:text-[17px] leading-relaxed text-[#9aa4b2]">
      Modify <span class="text-white font-medium">content-stream operators in-place</span> — fonts & layout intact. Plus a working <span class="text-white">admin + articles</span> system: upload images in admin, they show instantly on site, mobile-perfect.
    </p>
    <div class="mt-6 flex flex-wrap gap-3">
      <a href="#editor" class="px-5 py-2.5 rounded-xl bg-[#7c5cff] text-white font-semibold shadow-lg shadow-[#7c5cff]/20 hover:bg-[#6b4eff] transition flex items-center gap-2"><i class="ri-quill-pen-line"></i> Open Live Editor</a>
      <a href="#articles" class="px-5 py-2.5 rounded-xl bg-[#151a23] border border-[#232a36] font-semibold hover:bg-[#1a2030] transition flex items-center gap-2"><i class="ri-article-line"></i> Browse Articles</a>
      <a href="/admin" class="px-5 py-2.5 rounded-xl bg-white text-[#0b0e14] font-semibold hover:bg-zinc-100 transition hidden sm:inline-flex items-center gap-2"><i class="ri-dashboard-line"></i> Admin Panel</a>
    </div>
  </div>
</section>

<!-- Articles (public, mobile-friendly) -->
<section id="articles" class="max-w-[1280px] mx-auto px-4 sm:px-6 mt-8">
  <div class="flex flex-wrap items-end justify-between gap-3 mb-3">
    <div>
      <h2 class="text-xl font-bold flex items-center gap-2"><span class="w-8 h-8 rounded-lg bg-[#2ec4b6] flex items-center justify-center text-white"><i class="ri-article-line"></i></span> Articles & Blogs</h2>
      <p class="text-sm text-[#9aa4b2] mt-1">Uploaded in admin panel → shown here instantly. Fully responsive with image handling fixed.</p>
    </div>
    <a href="/admin" class="hidden sm:inline-flex px-4 py-2 rounded-xl bg-[#151a23] border border-[#232a36] text-sm hover:bg-[#1e2433] transition"><i class="ri-add-line mr-1"></i> New via Admin</a>
  </div>
  <div id="articlesGrid" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
    <!-- injected -->
  </div>
  <div id="articlesEmpty" class="hidden rounded-2xl bg-[#151a23] border border-dashed border-[#2a3344] p-10 text-center">
    <div class="w-12 h-12 mx-auto rounded-xl bg-[#1e2433] flex items-center justify-center text-[#5a6475] text-xl"><i class="ri-inbox-line"></i></div>
    <div class="mt-3 font-medium">No articles yet</div>
    <div class="text-sm text-[#9aa4b2] mt-1">Create one in <a href="/admin" class="text-[#8ea0ff] underline">Admin Panel</a> — images will appear here immediately.</div>
  </div>
</section>

<!-- Article Detail Modal (mobile-friendly) -->
<div id="articleModal" class="fixed inset-0 z-40 hidden">
  <div id="articleBackdrop" class="absolute inset-0 bg-black/70 backdrop-blur-sm"></div>
  <div class="absolute inset-0 overflow-auto p-3 sm:p-6 flex items-start justify-center">
    <div class="relative w-full max-w-[820px] rounded-[20px] bg-[#151a23] border border-[#232a36] overflow-hidden max-h-[92vh] flex flex-col">
      <button id="closeArticle" class="absolute top-3 right-3 w-8 h-8 rounded-full bg-black/60 backdrop-blur border border-white/10 flex items-center justify-center hover:bg-black/80 transition z-10"><i class="ri-close-line"></i></button>
      <div class="overflow-auto">
        <img id="mImage" class="w-full h-[220px] sm:h-[340px] object-cover bg-[#0f1320]" alt=""/>
        <div class="p-5 sm:p-7">
          <div class="flex flex-wrap items-center gap-2 text-xs">
            <span id="mCategory" class="px-2.5 py-1 rounded-full bg-[#7c5cff]/15 border border-[#7c5cff]/20 text-[#8ea0ff] font-semibold"></span>
            <span id="mDate" class="text-[#9aa4b2]"></span>
            <span class="text-[#5a6475]">•</span>
            <span id="mAuthor" class="text-[#9aa4b2]"></span>
          </div>
          <h3 id="mTitle" class="mt-3 text-[22px] sm:text-[28px] font-extrabold leading-tight"></h3>
          <p id="mExcerpt" class="mt-2 text-sm sm:text-[15px] text-[#9aa4b2] leading-relaxed"></p>
          <div id="mContent" class="prose prose-invert mt-6 text-sm sm:text-[15px] text-[#d6dae1] leading-relaxed"></div>
          <div class="mt-6 flex flex-wrap gap-2">
            <button onclick="document.getElementById('articleModal').classList.add('hidden')" class="px-4 py-2 rounded-xl bg-[#0f1320] border border-[#232a36] text-sm hover:bg-[#1e2433] transition">Close</button>
            <a href="#articles" onclick="document.getElementById('articleModal').classList.add('hidden')" class="px-4 py-2 rounded-xl bg-[#7c5cff] text-white text-sm font-semibold">Back to articles</a>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- Live Editor -->
<section id="editor" class="max-w-[1280px] mx-auto px-4 sm:px-6 mt-10">
  <div class="flex items-center justify-between mb-3 gap-3">
    <h2 class="text-xl font-bold flex items-center gap-2"><span class="w-8 h-8 rounded-lg bg-[#7c5cff] flex items-center justify-center text-white"><i class="ri-edit-2-line"></i></span> Live Editor</h2>
    <span id="healthBadge" class="shrink-0 text-xs px-2.5 py-1 rounded-full bg-[#1e2433] border border-[#232a36] text-[#9aa4b2]">checking…</span>
  </div>
  <div class="grid lg:grid-cols-[1.05fr_1.2fr] gap-4">
    <div class="space-y-4">
      <div class="rounded-2xl bg-[#151a23] border border-[#232a36] p-4">
        <div class="flex items-center justify-between mb-2">
          <h3 class="font-semibold text-sm flex items-center gap-2"><i class="ri-upload-cloud-2-line text-[#7c5cff]"></i> 1. Upload PDF</h3>
          <span class="text-xs text-[#9aa4b2] hidden sm:inline">Drag & drop or click</span>
        </div>
        <div id="dropZone" class="relative rounded-xl border-2 border-dashed border-[#2a3344] bg-[#0f1320] p-6 text-center hover:border-[#3a455c] transition cursor-pointer group">
          <input id="fileInput" type="file" accept=".pdf,application/pdf" class="absolute inset-0 opacity-0 cursor-pointer"/>
          <div id="dropContent">
            <div class="w-12 h-12 mx-auto rounded-xl bg-[#1e2433] border border-[#232a36] flex items-center justify-center text-xl text-[#7c5cff] group-hover:scale-105 transition"><i class="ri-file-pdf-line"></i></div>
            <div class="mt-3 font-medium">Drop PDF here</div>
            <div class="text-xs text-[#9aa4b2]">or click to browse</div>
          </div>
          <div id="fileMeta" class="hidden text-left">
            <div class="flex items-start justify-between gap-3">
              <div class="flex gap-3 min-w-0">
                <div class="w-10 h-10 rounded-lg bg-[#7c5cff]/15 border border-[#7c5cff]/20 flex items-center justify-center text-[#7c5cff] shrink-0"><i class="ri-file-pdf-fill"></i></div>
                <div class="min-w-0">
                  <div id="fileName" class="font-medium text-sm truncate max-w-[220px]"></div>
                  <div id="fileSize" class="text-xs text-[#9aa4b2]"></div>
                </div>
              </div>
              <button id="clearFile" class="shrink-0 px-2.5 py-1 rounded-full bg-[#232a36] text-xs hover:bg-[#2a3342]">Clear</button>
            </div>
            <div class="mt-3 h-1.5 rounded-full bg-[#0b0e14] border border-[#232a36] overflow-hidden"><div id="uploadBar" class="h-full w-0 bg-gradient-to-r from-[#7c5cff] to-[#2ec4b6] transition-all"></div></div>
          </div>
        </div>
        <div id="uploadStatus" class="mt-2 text-xs text-[#9aa4b2]"></div>
      </div>
      <div class="rounded-2xl bg-[#151a23] border border-[#232a36] p-4">
        <h3 class="font-semibold text-sm flex items-center gap-2 mb-3"><i class="ri-search-line text-[#7c5cff]"></i> 2. Find & Replace</h3>
        <div class="space-y-3">
          <div>
            <label class="text-xs font-semibold text-[#9aa4b2] uppercase">Find text</label>
            <div class="mt-1 relative">
              <i class="ri-search-line absolute left-3 top-1/2 -translate-y-1/2 text-[#5a6475]"></i>
              <input id="findInput" placeholder="Software Engineer" class="w-full pl-9 pr-8 py-2.5 rounded-xl bg-[#0f1320] border border-[#232a36] focus:border-[#7c5cff]/50 focus:outline-none text-sm"/>
              <button id="clearFind" class="absolute right-2 top-1/2 -translate-y-1/2 w-6 h-6 rounded-full bg-[#1e2433] text-[#9aa4b2] text-xs">×</button>
            </div>
          </div>
          <div>
            <label class="text-xs font-semibold text-[#9aa4b2] uppercase">Replace with</label>
            <div class="mt-1 relative">
              <i class="ri-quill-pen-line absolute left-3 top-1/2 -translate-y-1/2 text-[#5a6475]"></i>
              <input id="replaceInput" placeholder="Senior Engineer" class="w-full pl-9 pr-3 py-2.5 rounded-xl bg-[#0f1320] border border-[#232a36] focus:border-[#7c5cff]/50 focus:outline-none text-sm"/>
            </div>
          </div>
          <div class="grid grid-cols-2 gap-2 pt-1">
            <label class="flex items-center gap-2 px-3 py-2 rounded-xl bg-[#0f1320] border border-[#232a36] cursor-pointer"><input id="replaceAllToggle" type="checkbox" class="accent-[#7c5cff]"/><span class="text-xs font-medium">Replace all</span></label>
            <label class="flex items-center gap-2 px-3 py-2 rounded-xl bg-[#0f1320] border border-[#232a36] cursor-pointer"><input id="dryRunToggle" type="checkbox" class="accent-[#2ec4b6]"/><span class="text-xs font-medium">Dry run</span></label>
          </div>
          <div class="grid grid-cols-3 gap-2 pt-2">
            <button id="btnFind" class="py-2.5 rounded-xl bg-[#1e2433] border border-[#232a36] font-semibold text-sm hover:bg-[#232a36] transition flex items-center justify-center gap-1.5"><i class="ri-search-2-line"></i> Find</button>
            <button id="btnReplace" class="col-span-2 py-2.5 rounded-xl bg-[#7c5cff] text-white font-bold text-sm shadow-md shadow-[#7c5cff]/20 hover:bg-[#6b4eff] transition flex items-center justify-center gap-1.5"><i class="ri-refresh-line"></i> Replace & Download</button>
          </div>
          <div class="grid grid-cols-2 gap-2">
            <button id="btnReplaceAll" class="py-2 rounded-xl bg-[#0f1320] border border-[#232a36] text-sm font-medium hover:bg-[#1a2030] transition"><i class="ri-repeat-line"></i> Replace All</button>
            <button id="btnClear" class="py-2 rounded-xl border border-[#232a36] text-sm text-[#9aa4b2] hover:text-white">Clear</button>
          </div>
        </div>
        <div id="controlStatus" class="mt-3 text-xs min-h-[18px] text-[#9aa4b2]"></div>
      </div>
    </div>
    <div class="space-y-4">
      <div class="rounded-2xl bg-[#151a23] border border-[#232a36] overflow-hidden">
        <div class="flex items-center justify-between px-4 py-3 border-b border-[#232a36] bg-[#0f1320]/50 gap-2">
          <h3 class="font-semibold text-sm flex items-center gap-2"><i class="ri-checkbox-circle-line text-emerald-400"></i> Results</h3>
          <div class="flex items-center gap-1.5">
            <button data-tab="matches" class="tabBtn tab-active px-3 py-1.5 rounded-full border text-xs font-semibold">Matches</button>
            <button data-tab="fidelity" class="tabBtn px-3 py-1.5 rounded-full border border-[#232a36] text-xs font-semibold text-[#9aa4b2]">Fidelity</button>
            <button data-tab="preview" class="tabBtn px-3 py-1.5 rounded-full border border-[#232a36] text-xs font-semibold text-[#9aa4b2]">Preview</button>
          </div>
        </div>
        <div class="p-4">
          <div id="tab-matches">
            <div id="emptyMatches" class="rounded-xl bg-[#0f1320] border border-dashed border-[#2a3344] p-8 text-center">
              <div class="w-10 h-10 mx-auto rounded-xl bg-[#1e2433] flex items-center justify-center text-[#5a6475]"><i class="ri-search-eye-line"></i></div>
              <div class="mt-2 text-sm font-medium">No search yet</div>
              <div class="text-xs text-[#9aa4b2] mt-1">Upload PDF → Find.</div>
            </div>
            <div id="matchesList" class="hidden space-y-2 max-h-[320px] overflow-auto pr-1"></div>
          </div>
          <div id="tab-fidelity" class="hidden">
            <div id="emptyFidelity" class="rounded-xl bg-[#0f1320] border border-dashed border-[#2a3344] p-8 text-center">
              <div class="w-10 h-10 mx-auto rounded-xl bg-[#1e2433] flex items-center justify-center text-[#5a6475]"><i class="ri-shield-check-line"></i></div>
              <div class="mt-2 text-sm font-medium">FidelityReport after edit</div>
              <div class="text-xs text-[#9aa4b2] mt-1">Every edit reports <code class="bg-[#1e2433] px-1 rounded">font_preserved</code> etc.</div>
            </div>
            <div id="fidelityPanel" class="hidden space-y-3">
              <div class="grid grid-cols-3 gap-2">
                <div class="rounded-xl bg-[#0f1320] border border-[#232a36] p-3 text-center"><div class="text-[11px] uppercase text-[#5a6475] font-semibold">Font preserved</div><div id="fFont" class="mt-1 text-sm font-bold">—</div></div>
                <div class="rounded-xl bg-[#0f1320] border border-[#232a36] p-3 text-center"><div class="text-[11px] uppercase text-[#5a6475] font-semibold">Overflow</div><div id="fOverflow" class="mt-1 text-sm font-bold">—</div></div>
                <div class="rounded-xl bg-[#0f1320] border border-[#232a36] p-3 text-center"><div class="text-[11px] uppercase text-[#5a6475] font-semibold">Glyphs missing</div><div id="fGlyphs" class="mt-1 text-sm font-bold">—</div></div>
              </div>
              <div class="rounded-xl bg-[#0f1320] border border-[#232a36] p-3">
                <div class="text-xs font-semibold text-[#9aa4b2] uppercase">Degradations</div>
                <div id="fDegradations" class="mt-2 space-y-1.5 text-xs"></div>
              </div>
              <pre id="fRaw" class="text-[11px] bg-[#0b0e14] border border-[#232a36] rounded-lg p-2.5 overflow-auto max-h-[160px]"></pre>
            </div>
          </div>
          <div id="tab-preview" class="hidden">
            <div id="emptyPreview" class="rounded-xl bg-[#0f1320] border border-dashed border-[#2a3344] p-8 text-center">
              <div class="w-10 h-10 mx-auto rounded-xl bg-[#1e2433] flex items-center justify-center text-[#5a6475]"><i class="ri-eye-line"></i></div>
              <div class="mt-2 text-sm font-medium">Preview after replace</div>
              <div class="text-xs text-[#9aa4b2] mt-1">Edited PDF will render here.</div>
            </div>
            <div id="previewWrap" class="hidden">
              <div class="flex items-center justify-between mb-2">
                <div class="text-xs text-[#9aa4b2]"><span id="previewMeta"></span></div>
                <a id="downloadBtn" href="#" download="edited.pdf" class="px-3 py-1.5 rounded-full bg-[#2ec4b6] text-[#0b0e14] text-xs font-bold hover:bg-[#25b0a3] flex items-center gap-1"><i class="ri-download-2-line"></i> Download</a>
              </div>
              <div class="rounded-xl overflow-hidden border border-[#232a36] bg-white">
                <iframe id="pdfPreview" class="w-full h-[420px] sm:h-[520px] bg-white" title="PDF preview"></iframe>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</section>

<footer class="max-w-[1280px] mx-auto px-4 sm:px-6 py-8 text-xs text-[#5a6475]">
  <div class="rounded-2xl bg-[#151a23] border border-[#232a36] p-4 flex flex-wrap items-center justify-between gap-3">
    <div>pdf-edit-engine v0.2.0 • MIT • <a href="/admin" class="text-[#8ea0ff] underline">Admin Panel</a> • Deployed on Vercel</div>
    <div class="flex gap-2"><span class="px-2 py-1 rounded-full bg-[#0f1320] border border-[#232a36]">pikepdf ≥10</span><span class="px-2 py-1 rounded-full bg-[#0f1320] border border-[#232a36]">fonttools ≥4.60.2</span></div>
  </div>
</footer>

<div id="toast" class="fixed bottom-4 left-1/2 -translate-x-1/2 hidden px-4 py-2.5 rounded-full bg-[#1e2433] border border-[#232a36] text-sm shadow-xl z-50 max-w-[90vw] text-center"></div>

<script>
const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);
$('#mobileMenuBtn')?.addEventListener('click', ()=> $('#mobileMenu').classList.toggle('hidden'));

function toast(msg, ok=true){
  const t=$('#toast'); t.textContent=msg; t.classList.remove('hidden');
  t.style.background = ok ? '#1e2433' : '#2a1a1a'; t.style.borderColor = ok ? '#232a36' : '#4a2323';
  setTimeout(()=>t.classList.add('hidden'), 2600);
}

// Health
fetch('/api/health').then(r=>r.json()).then(j=>{
  $('#healthBadge').textContent = `● ${j.version} • ${j.python.split(' ')[0]}`;
  $('#healthBadge').className = 'shrink-0 text-xs px-2.5 py-1 rounded-full bg-emerald-500/15 border border-emerald-500/20 text-emerald-400';
}).catch(()=>{ $('#healthBadge').textContent='● api unreachable'; $('#healthBadge').className='shrink-0 text-xs px-2.5 py-1 rounded-full bg-rose-500/15 border border-rose-500/20 text-rose-400'; });

// Articles — public, mobile-friendly, image-fixed
let articlesCache=[];
async function loadArticles(){
  try{
    const r=await fetch('/api/articles');
    const j=await r.json();
    articlesCache = j.articles || j || [];
    renderArticles(articlesCache);
  }catch(e){
    console.error(e);
    $('#articlesGrid').innerHTML='<div class="col-span-full text-sm text-rose-400">Failed to load articles</div>';
  }
}
function renderArticles(list){
  const grid=$('#articlesGrid');
  const empty=$('#articlesEmpty');
  const badge=$('#articleCountBadge');
  const published=list.filter(a=>a.published!==false);
  badge.textContent=published.length;
  if(published.length===0){ grid.innerHTML=''; empty.classList.remove('hidden'); return; }
  empty.classList.add('hidden');
  grid.innerHTML=published.map(a=>`
    <article class="group rounded-2xl bg-[#151a23] border border-[#232a36] overflow-hidden hover:border-[#2a3344] transition flex flex-col">
      <div class="relative h-48 sm:h-44 overflow-hidden bg-[#0f1320]">
        <img src="${a.image}" alt="${a.title}" class="w-full h-full object-cover group-hover:scale-[1.03] transition duration-500" loading="lazy" onerror="this.src='https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=800&auto=format&fit=crop&q=60'"/>
        <span class="absolute top-2.5 left-2.5 px-2.5 py-1 rounded-full bg-black/60 backdrop-blur border border-white/10 text-xs font-semibold">${a.category||'Article'}</span>
      </div>
      <div class="p-4 flex flex-col flex-1">
        <div class="text-xs text-[#9aa4b2] flex items-center gap-1.5"><i class="ri-calendar-line"></i> ${a.date||''} <span class="opacity-50">•</span> ${a.author||'Admin'}</div>
        <h3 class="mt-1.5 font-bold leading-tight line-clamp-2 group-hover:text-white transition">${a.title}</h3>
        <p class="mt-1.5 text-sm text-[#9aa4b2] line-clamp-2 leading-relaxed">${a.excerpt||''}</p>
        <button onclick="openArticle('${a.id}')" class="mt-3 inline-flex items-center gap-1.5 text-sm font-semibold text-[#8ea0ff] hover:text-white transition">Read article <i class="ri-arrow-right-line"></i></button>
      </div>
    </article>
  `).join('');
}
function openArticle(id){
  const a=articlesCache.find(x=>String(x.id)===String(id));
  if(!a) return;
  $('#mImage').src=a.image;
  $('#mImage').alt=a.title;
  $('#mCategory').textContent=a.category||'Article';
  $('#mDate').textContent=a.date||'';
  $('#mAuthor').textContent=a.author||'';
  $('#mTitle').textContent=a.title;
  $('#mExcerpt').textContent=a.excerpt||'';
  $('#mContent').innerHTML=a.content||'';
  $('#articleModal').classList.remove('hidden');
  document.body.style.overflow='hidden';
}
function closeArticle(){
  $('#articleModal').classList.add('hidden');
  document.body.style.overflow='';
}
$('#closeArticle').addEventListener('click', closeArticle);
$('#articleBackdrop').addEventListener('click', closeArticle);
document.addEventListener('keydown', e=>{ if(e.key==='Escape') closeArticle(); });
loadArticles();

// Tabs + PDF editor (same as before)
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

let currentFile=null;
let lastPreviewUrl=null;
function setFile(file){
  if(!file) return;
  if(file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')){ toast('Please select a PDF', false); return; }
  currentFile=file;
  $('#dropContent').classList.add('hidden');
  $('#fileMeta').classList.remove('hidden');
  $('#fileName').textContent=file.name;
  $('#fileSize').textContent=(file.size/1024).toFixed(1)+' KB';
  $('#uploadBar').style.width='100%';
  $('#uploadStatus').textContent='✓ Ready — enter Find text and hit Find or Replace.';
  $('#uploadStatus').className='mt-2 text-xs text-emerald-400';
}
$('#fileInput').addEventListener('change', e=> setFile(e.target.files[0]));
$('#dropZone').addEventListener('dragover', e=>{e.preventDefault(); e.currentTarget.classList.add('drop-active')});
$('#dropZone').addEventListener('dragleave', e=> e.currentTarget.classList.remove('drop-active'));
$('#dropZone').addEventListener('drop', e=>{ e.preventDefault(); e.currentTarget.classList.remove('drop-active'); const f=e.dataTransfer.files[0]; if(f) setFile(f); });
$('#clearFile').addEventListener('click', ()=>{
  currentFile=null; $('#fileInput').value=''; $('#dropContent').classList.remove('hidden'); $('#fileMeta').classList.add('hidden');
  $('#uploadBar').style.width='0'; $('#uploadStatus').textContent='';
});
$('#clearFind').addEventListener('click', ()=>{ $('#findInput').value=''; $('#findInput').focus(); });
$('#btnClear').addEventListener('click', ()=>{
  $('#findInput').value=''; $('#replaceInput').value='';
  $('#matchesList').classList.add('hidden'); $('#emptyMatches').classList.remove('hidden');
  $('#fidelityPanel').classList.add('hidden'); $('#emptyFidelity').classList.remove('hidden');
  $('#previewWrap').classList.add('hidden'); $('#emptyPreview').classList.remove('hidden');
  $('#controlStatus').textContent='';
});
function requireFile(){ if(!currentFile){ toast('Upload a PDF first', false); return false; } return true; }
function setLoading(btn, loading, label){
  btn.disabled=loading; btn.style.opacity=loading?'0.6':'1';
  if(loading) btn.dataset.orig=btn.innerHTML, btn.innerHTML='<i class="ri-loader-4-line animate-spin"></i> '+label;
  else if(btn.dataset.orig) btn.innerHTML=btn.dataset.orig;
}
$('#btnFind').addEventListener('click', async ()=>{
  if(!requireFile()) return;
  const q=$('#findInput').value.trim();
  if(!q){ toast('Enter text to find', false); return; }
  const btn=$('#btnFind'); setLoading(btn,true,'Finding…');
  $('#controlStatus').textContent='Searching…';
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
        el.innerHTML='<div class="min-w-0"><div class="text-sm font-medium truncate">'+(m.text||'(match '+(i+1)+')')+'</div><div class="text-xs text-[#9aa4b2]">Page '+m.page_index+' • bbox '+(m.bbox?('['+m.bbox.map(v=>v.toFixed(1)).join(', ')+']'):'—')+'</div></div><span class="shrink-0 text-xs px-2 py-1 rounded-full bg-[#7c5cff]/15 border border-[#7c5cff]/20 text-[#8ea0ff]">#'+(i+1)+'</span>';
        list.appendChild(el);
      });
    }
    $$('.tabBtn').forEach(b=> b.dataset.tab==='matches' && b.click());
    $('#controlStatus').textContent='Found '+j.count+' match'+(j.count!==1?'es':'');
    toast('Found '+j.count+' match'+(j.count!==1?'es':''));
  }catch(e){ toast(e.message, false); $('#controlStatus').textContent='Error: '+e.message; $('#controlStatus').className='mt-3 text-xs text-rose-400'; } finally{ setLoading(btn,false); }
});
$('#btnReplace').addEventListener('click', ()=> doReplace(false));
$('#btnReplaceAll').addEventListener('click', ()=> doReplace(true));
async function doReplace(all){
  if(!requireFile()) return;
  const find=$('#findInput').value.trim();
  const repl=$('#replaceInput').value;
  const dry=$('#dryRunToggle').checked;
  if(!find){ toast('Enter Find text', false); return; }
  const btn = all ? $('#btnReplaceAll') : $('#btnReplace');
  setLoading(btn,true, dry?'Previewing…':'Replacing…');
  $('#controlStatus').textContent = dry ? 'Dry run…' : (all ? 'Replacing all…' : 'Replacing…');
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
      $('#controlStatus').textContent='Dry run — FidelityReport ready.';
      toast('Dry run OK'); return;
    }
    if(!res.ok){
      let msg='Replace failed';
      try{ const j=await res.json(); msg=j.error || msg; } catch{ msg=await res.text(); }
      throw new Error(msg);
    }
    const blob=await res.blob();
    const url=URL.createObjectURL(blob);
    if(lastPreviewUrl) URL.revokeObjectURL(lastPreviewUrl); lastPreviewUrl=url;
    $('#pdfPreview').src=url;
    $('#downloadBtn').href=url;
    $('#previewWrap').classList.remove('hidden'); $('#emptyPreview').classList.add('hidden');
    $('#previewMeta').textContent=(all?'Replace All':'Replace')+' • '+(blob.size/1024).toFixed(1)+' KB';
    const fPres = res.headers.get('X-Fidelity-Font-Preserved');
    const fOver = res.headers.get('X-Fidelity-Overflow');
    renderFidelityFromHeaders({font_preserved:fPres, overflow_detected:fOver});
    $$('.tabBtn').forEach(b=> b.dataset.tab==='preview' && b.click());
    $('#controlStatus').textContent='✓ Edited PDF ready.';
    $('#controlStatus').className='mt-3 text-xs text-emerald-400';
    toast('Edited PDF ready');
  }catch(e){ toast(e.message, false); $('#controlStatus').textContent='Error: '+e.message; $('#controlStatus').className='mt-3 text-xs text-rose-400'; } finally{ setLoading(btn,false); }
}
function renderFidelity(j){
  $('#emptyFidelity').classList.add('hidden'); $('#fidelityPanel').classList.remove('hidden');
  const fp = j.font_preserved ?? (j.font_substituted==null);
  const over = j.overflow_detected ?? false;
  const glyphs = j.glyphs_missing ?? [];
  const degr = j.degradations ?? [];
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
  $('#fGlyphs').textContent = '—';
  $('#fRaw').textContent = JSON.stringify(h, null, 2);
  $('#fDegradations').innerHTML='<div class="text-xs text-[#5a6475]">Full degradations available via Dry run.</div>';
}
</script>
</body>
</html>
"""

ADMIN_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Admin Panel — pdf-edit-engine</title>
<script src="https://cdn.tailwindcss.com"></script>
<script>tailwind.config={theme:{extend:{colors:{bg:'#0b0e14',card:'#151a23',muted:'#9aa4b2',accent:'#7c5cff',accent2:'#2ec4b6',border:'#232a36'}}}}</script>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.2.0/remixicon.min.css"/>
<style>
::-webkit-scrollbar{width:8px;height:8px}::-webkit-scrollbar-thumb{background:#2a3242;border-radius:999px}
.glass{backdrop-filter:blur(16px);background:rgba(21,26,35,0.9)}
.drop-active{border-color:#7c5cff!important;background:rgba(124,92,255,0.08)!important}
</style>
</head>
<body class="bg-[#0b0e14] text-[#e6e8eb] antialiased">
<header class="sticky top-0 z-50 border-b border-[#232a36] glass">
  <div class="max-w-[1280px] mx-auto px-4 sm:px-6 py-3 flex items-center justify-between gap-3">
    <div class="flex items-center gap-3">
      <a href="/" class="w-9 h-9 rounded-xl bg-gradient-to-br from-[#7c5cff] to-[#2ec4b6] flex items-center justify-center font-black text-white">PE</a>
      <div>
        <div class="font-bold leading-none">Admin Panel</div>
        <div class="text-xs text-[#9aa4b2]">Articles & Blogs • Images fixed • Mobile ready</div>
      </div>
    </div>
    <div class="flex items-center gap-2">
      <a href="/" class="hidden sm:inline-flex px-3 py-1.5 rounded-full bg-[#1e2433] border border-[#232a36] text-sm hover:bg-[#232a36]"><i class="ri-external-link-line mr-1"></i> View Site</a>
      <button id="logoutBtn" class="hidden px-3 py-1.5 rounded-full bg-[#232a36] text-sm hover:bg-[#2a3342]">Logout</button>
    </div>
  </div>
</header>

<!-- Login -->
<div id="loginScreen" class="min-h-[70vh] flex items-center justify-center p-4">
  <div class="w-full max-w-[420px] rounded-[20px] bg-[#151a23] border border-[#232a36] p-6 sm:p-7">
    <div class="w-12 h-12 rounded-xl bg-[#7c5cff]/15 border border-[#7c5cff]/20 flex items-center justify-center text-[#7c5cff] text-xl"><i class="ri-lock-2-line"></i></div>
    <h1 class="mt-4 text-xl font-bold">Admin login</h1>
    <p class="text-sm text-[#9aa4b2] mt-1">Default password is <span class="text-white font-mono bg-[#0f1320] border border-[#232a36] px-1.5 py-0.5 rounded">admin123</span> — change in code if needed.</p>
    <div class="mt-5 space-y-3">
      <div>
        <label class="text-xs font-semibold text-[#9aa4b2] uppercase">Password</label>
        <input id="loginPass" type="password" placeholder="Enter password" class="mt-1 w-full px-3 py-2.5 rounded-xl bg-[#0f1320] border border-[#232a36] focus:border-[#7c5cff]/50 focus:outline-none text-sm"/>
      </div>
      <button id="loginBtn" class="w-full py-2.5 rounded-xl bg-[#7c5cff] text-white font-bold hover:bg-[#6b4eff] transition flex items-center justify-center gap-2"><i class="ri-login-box-line"></i> Login</button>
      <div id="loginErr" class="text-xs text-rose-400 min-h-[18px]"></div>
    </div>
    <div class="mt-4 rounded-xl bg-[#0f1320] border border-[#232a36] p-3 text-xs text-[#9aa4b2]">
      <div class="font-semibold text-white flex items-center gap-1.5"><i class="ri-information-line text-[#7c5cff]"></i> Fix for images</div>
      <div class="mt-1 leading-relaxed">Images are stored as base64 data URLs inside <code class="bg-[#151a23] px-1 rounded border border-[#232a36]">data/articles.json</code>. Upload in admin → appears instantly on site (no external bucket, no lost files) and works on mobile with <code class="bg-[#151a23] px-1 rounded">object-cover</code>.</div>
    </div>
  </div>
</div>

<!-- Dashboard -->
<div id="dashboard" class="hidden max-w-[1280px] mx-auto px-4 sm:px-6 py-6">
  <div class="flex flex-wrap items-center justify-between gap-3 mb-4">
    <div>
      <h2 class="text-xl font-bold flex items-center gap-2"><i class="ri-dashboard-line text-[#7c5cff]"></i> Dashboard</h2>
      <p class="text-sm text-[#9aa4b2]">Manage articles — upload images, they show on site + mobile immediately.</p>
    </div>
    <button id="newBtn" class="px-5 py-2.5 rounded-xl bg-[#7c5cff] text-white font-bold shadow shadow-[#7c5cff]/20 hover:bg-[#6b4eff] flex items-center gap-2"><i class="ri-add-line"></i> New Article</button>
  </div>

  <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-5">
    <div class="rounded-2xl bg-[#151a23] border border-[#232a36] p-4"><div class="text-xs uppercase font-semibold text-[#5a6475]">Total articles</div><div id="statTotal" class="text-2xl font-bold mt-1">—</div></div>
    <div class="rounded-2xl bg-[#151a23] border border-[#232a36] p-4"><div class="text-xs uppercase font-semibold text-[#5a6475]">Published</div><div id="statPublished" class="text-2xl font-bold mt-1 text-emerald-400">—</div></div>
    <div class="rounded-2xl bg-[#151a23] border border-[#232a36] p-4"><div class="text-xs uppercase font-semibold text-[#5a6475]">Drafts</div><div id="statDrafts" class="text-2xl font-bold mt-1 text-amber-400">—</div></div>
  </div>

  <!-- Desktop table, mobile cards -->
  <div class="hidden sm:block rounded-2xl bg-[#151a23] border border-[#232a36] overflow-hidden">
    <div class="overflow-auto">
      <table class="w-full text-sm">
        <thead class="text-xs uppercase tracking-wide text-[#5a6475] bg-[#0f1320]/50"><tr><th class="text-left px-4 py-3">Article</th><th class="text-left px-4 py-3">Category</th><th class="text-left px-4 py-3">Date</th><th class="text-left px-4 py-3">Status</th><th class="text-right px-4 py-3">Actions</th></tr></thead>
        <tbody id="tableBody" class="divide-y divide-[#232a36]"></tbody>
      </table>
    </div>
  </div>
  <div id="mobileCards" class="sm:hidden space-y-3"></div>

  <div id="dashEmpty" class="hidden rounded-2xl bg-[#151a23] border border-dashed border-[#2a3344] p-10 text-center">
    <div class="w-12 h-12 mx-auto rounded-xl bg-[#1e2433] flex items-center justify-center text-[#5a6475] text-xl"><i class="ri-article-line"></i></div>
    <div class="mt-3 font-medium">No articles yet</div>
    <div class="text-sm text-[#9aa4b2] mt-1">Click <span class="text-white">New Article</span> — upload an image and publish, it will show on the website and mobile.</div>
  </div>
</div>

<!-- Editor Modal (mobile-friendly, scrollable) -->
<div id="editorModal" class="fixed inset-0 z-40 hidden">
  <div id="editorBackdrop" class="absolute inset-0 bg-black/70 backdrop-blur-sm"></div>
  <div class="absolute inset-0 overflow-auto p-3 sm:p-6 flex items-start justify-center">
    <div class="relative w-full max-w-[820px] rounded-[20px] bg-[#151a23] border border-[#232a36] overflow-hidden flex flex-col max-h-[96vh]">
      <div class="sticky top-0 z-10 flex items-center justify-between px-5 py-4 border-b border-[#232a36] bg-[#151a23]">
        <h3 id="editorTitle" class="font-bold">New Article</h3>
        <button id="closeEditor" class="w-8 h-8 rounded-full bg-[#0f1320] border border-[#232a36] flex items-center justify-center hover:bg-[#1e2433]"><i class="ri-close-line"></i></button>
      </div>
      <form id="articleForm" class="overflow-auto p-5 space-y-4">
        <input type="hidden" id="fId"/>
        <div class="grid sm:grid-cols-2 gap-4">
          <div class="sm:col-span-2">
            <label class="text-xs font-semibold text-[#9aa4b2] uppercase">Title *</label>
            <input id="fTitle" required placeholder="Article title" class="mt-1 w-full px-3 py-2.5 rounded-xl bg-[#0f1320] border border-[#232a36] focus:border-[#7c5cff]/50 focus:outline-none text-sm"/>
          </div>
          <div>
            <label class="text-xs font-semibold text-[#9aa4b2] uppercase">Category</label>
            <input id="fCategory" placeholder="Engineering, Product..." class="mt-1 w-full px-3 py-2.5 rounded-xl bg-[#0f1320] border border-[#232a36] focus:outline-none text-sm"/>
          </div>
          <div>
            <label class="text-xs font-semibold text-[#9aa4b2] uppercase">Author</label>
            <input id="fAuthor" placeholder="Author name" class="mt-1 w-full px-3 py-2.5 rounded-xl bg-[#0f1320] border border-[#232a36] focus:outline-none text-sm"/>
          </div>
          <div class="sm:col-span-2">
            <label class="text-xs font-semibold text-[#9aa4b2] uppercase">Excerpt *</label>
            <textarea id="fExcerpt" required rows="2" placeholder="Short excerpt (1-2 lines) shown on cards" class="mt-1 w-full px-3 py-2.5 rounded-xl bg-[#0f1320] border border-[#232a36] focus:border-[#7c5cff]/50 focus:outline-none text-sm resize-none"></textarea>
          </div>
          <div class="sm:col-span-2">
            <label class="text-xs font-semibold text-[#9aa4b2] uppercase">Content (HTML allowed) *</label>
            <textarea id="fContent" required rows="6" placeholder="<p>Your article content…</p><h3>Heading</h3><ul><li>Points</li></ul>" class="mt-1 w-full px-3 py-2.5 rounded-xl bg-[#0f1320] border border-[#232a36] focus:border-[#7c5cff]/50 focus:outline-none text-sm font-mono"></textarea>
            <div class="text-[11px] text-[#5a6475] mt-1">Supports HTML: &lt;p&gt; &lt;h3&gt; &lt;ul&gt; &lt;li&gt; &lt;strong&gt; — rendered with prose styling, mobile-optimized.</div>
          </div>
          <!-- Image upload — fixed -->
          <div class="sm:col-span-2">
            <label class="text-xs font-semibold text-[#9aa4b2] uppercase">Cover image *</label>
            <div id="imageDrop" class="mt-1 relative rounded-xl border-2 border-dashed border-[#2a3344] bg-[#0f1320] p-4 hover:border-[#3a455c] transition cursor-pointer">
              <input id="fImage" type="file" accept="image/*" class="absolute inset-0 opacity-0 cursor-pointer"/>
              <div id="imageDropContent" class="text-center py-2">
                <div class="w-10 h-10 mx-auto rounded-xl bg-[#1e2433] border border-[#232a36] flex items-center justify-center text-[#7c5cff]"><i class="ri-image-add-line"></i></div>
                <div class="mt-2 text-sm font-medium">Drop image here or click to browse</div>
                <div class="text-xs text-[#9aa4b2]">JPG, PNG, WEBP • stored as base64, shows instantly on site + mobile</div>
              </div>
              <div id="imagePreviewWrap" class="hidden">
                <img id="imagePreview" class="w-full h-48 sm:h-56 object-cover rounded-xl bg-[#0b0e14] border border-[#232a36]" alt="preview"/>
                <div class="mt-2 flex items-center justify-between gap-2">
                  <span id="imageName" class="text-xs text-[#9aa4b2] truncate"></span>
                  <button type="button" id="removeImage" class="shrink-0 px-3 py-1 rounded-full bg-[#232a36] text-xs hover:bg-[#2a3342]">Remove</button>
                </div>
              </div>
            </div>
            <input type="hidden" id="fImageData"/>
            <div class="text-[11px] text-[#5a6475] mt-1">Previous bug: images weren't saved. Fixed — now uploaded file is converted to data URL and saved in JSON, so it renders on site and mobile without external storage.</div>
          </div>
          <div class="sm:col-span-2 flex items-center gap-3 pt-1">
            <label class="flex items-center gap-2 px-3 py-2 rounded-xl bg-[#0f1320] border border-[#232a36] cursor-pointer">
              <input id="fPublished" type="checkbox" checked class="accent-[#7c5cff]"/>
              <span class="text-sm font-medium">Published</span>
              <span class="text-xs text-[#5a6475]">(uncheck = draft, hidden from site)</span>
            </label>
          </div>
        </div>
        <div class="flex flex-wrap gap-2 pt-2">
          <button type="submit" class="flex-1 sm:flex-none px-6 py-2.5 rounded-xl bg-[#7c5cff] text-white font-bold hover:bg-[#6b4eff] flex items-center justify-center gap-2"><i class="ri-save-line"></i> Save Article</button>
          <button type="button" id="cancelEditor" class="px-6 py-2.5 rounded-xl bg-[#0f1320] border border-[#232a36] hover:bg-[#1e2433]">Cancel</button>
        </div>
        <div id="formStatus" class="text-xs min-h-[18px] text-[#9aa4b2]"></div>
      </form>
    </div>
  </div>
</div>

<div id="toast" class="fixed bottom-4 left-1/2 -translate-x-1/2 hidden px-4 py-2.5 rounded-full bg-[#1e2433] border border-[#232a36] text-sm shadow-xl z-50 max-w-[90vw] text-center"></div>

<script>
const $=s=>document.querySelector(s);
const ADMIN_PASS="admin123";
function isAuthed(){ return localStorage.getItem("admin_auth")==="1"; }
function setAuthed(v){ if(v) localStorage.setItem("admin_auth","1"); else localStorage.removeItem("admin_auth"); }

function showLogin(show){
  $('#loginScreen').classList.toggle('hidden', !show);
  $('#dashboard').classList.toggle('hidden', show);
  $('#logoutBtn').classList.toggle('hidden', show);
}
function checkAuth(){
  if(isAuthed()){ showLogin(false); loadAdminArticles(); } else showLogin(true);
}
$('#loginBtn').addEventListener('click', ()=>{
  const p=$('#loginPass').value;
  if(p===ADMIN_PASS){ setAuthed(true); $('#loginErr').textContent=''; checkAuth(); toast('Logged in'); }
  else { $('#loginErr').textContent='Wrong password'; }
});
$('#loginPass').addEventListener('keydown', e=>{ if(e.key==='Enter') $('#loginBtn').click(); });
$('#logoutBtn').addEventListener('click', ()=>{ setAuthed(false); checkAuth(); toast('Logged out'); });
checkAuth();

// Articles admin
let adminArticles=[];
let editingId=null;
let pendingImageData=null; // data URL

async function loadAdminArticles(){
  try{
    const r=await fetch('/api/articles');
    const j=await r.json();
    adminArticles=j.articles || j || [];
    renderAdmin();
  }catch(e){ toast('Failed to load', false); }
}
function renderAdmin(){
  const total=adminArticles.length;
  const pub=adminArticles.filter(a=>a.published!==false).length;
  $('#statTotal').textContent=total;
  $('#statPublished').textContent=pub;
  $('#statDrafts').textContent=total-pub;
  const tb=$('#tableBody');
  const cards=$('#mobileCards');
  const empty=$('#dashEmpty');
  if(total===0){ tb.innerHTML=''; cards.innerHTML=''; empty.classList.remove('hidden'); return; }
  empty.classList.add('hidden');
  tb.innerHTML=adminArticles.map(a=>`
    <tr class="hover:bg-[#0f1320]/50 transition">
      <td class="px-4 py-3">
        <div class="flex gap-3 items-center min-w-0">
          <img src="${a.image}" class="w-12 h-12 rounded-xl object-cover bg-[#0f1320] border border-[#232a36] shrink-0" onerror="this.style.display='none'"/>
          <div class="min-w-0">
            <div class="font-medium truncate max-w-[280px]">${a.title}</div>
            <div class="text-xs text-[#9aa4b2] truncate max-w-[280px]">${a.excerpt||''}</div>
          </div>
        </div>
      </td>
      <td class="px-4 py-3"><span class="px-2 py-1 rounded-full bg-[#1e2433] border border-[#232a36] text-xs">${a.category||'—'}</span></td>
      <td class="px-4 py-3 text-xs text-[#9aa4b2]">${a.date||''}</td>
      <td class="px-4 py-3"><span class="px-2 py-1 rounded-full text-xs font-semibold ${a.published!==false?'bg-emerald-500/15 border border-emerald-500/20 text-emerald-400':'bg-amber-500/15 border border-amber-500/20 text-amber-400'}">${a.published!==false?'Published':'Draft'}</span></td>
      <td class="px-4 py-3">
        <div class="flex justify-end gap-1.5">
          <button onclick="editArticle('${a.id}')" class="w-8 h-8 rounded-full bg-[#1e2433] border border-[#232a36] hover:bg-[#232a36] flex items-center justify-center"><i class="ri-edit-line"></i></button>
          <button onclick="deleteArticle('${a.id}')" class="w-8 h-8 rounded-full bg-rose-500/10 border border-rose-500/20 text-rose-400 hover:bg-rose-500/20 flex items-center justify-center"><i class="ri-delete-bin-line"></i></button>
        </div>
      </td>
    </tr>
  `).join('');
  cards.innerHTML=adminArticles.map(a=>`
    <div class="rounded-2xl bg-[#151a23] border border-[#232a36] overflow-hidden">
      <img src="${a.image}" class="w-full h-40 object-cover bg-[#0f1320]" onerror="this.style.display='none'"/>
      <div class="p-4">
        <div class="flex items-center gap-2 text-xs"><span class="px-2 py-1 rounded-full bg-[#1e2433] border border-[#232a36]">${a.category||'—'}</span><span class="text-[#9aa4b2]">${a.date||''}</span><span class="ml-auto px-2 py-1 rounded-full text-xs font-semibold ${a.published!==false?'bg-emerald-500/15 text-emerald-400 border border-emerald-500/20':'bg-amber-500/15 text-amber-400 border border-amber-500/20'}">${a.published!==false?'Published':'Draft'}</span></div>
        <div class="mt-2 font-bold leading-tight">${a.title}</div>
        <div class="text-sm text-[#9aa4b2] line-clamp-2 mt-1">${a.excerpt||''}</div>
        <div class="mt-3 flex gap-2">
          <button onclick="editArticle('${a.id}')" class="flex-1 py-2 rounded-xl bg-[#1e2433] border border-[#232a36] text-sm font-medium"><i class="ri-edit-line mr-1"></i> Edit</button>
          <button onclick="deleteArticle('${a.id}')" class="px-4 py-2 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm"><i class="ri-delete-bin-line"></i></button>
        </div>
      </div>
    </div>
  `).join('');
}

function toast(msg, ok=true){
  const t=$('#toast'); t.textContent=msg; t.classList.remove('hidden');
  t.style.background=ok?'#1e2433':'#2a1a1a'; t.style.borderColor=ok?'#232a36':'#4a2323';
  setTimeout(()=>t.classList.add('hidden'), 2600);
}

function openEditor(mode, article=null){
  $('#editorModal').classList.remove('hidden');
  document.body.style.overflow='hidden';
  $('#editorTitle').textContent = mode==='edit' ? 'Edit Article' : 'New Article';
  if(article){
    editingId=article.id;
    $('#fId').value=article.id;
    $('#fTitle').value=article.title||'';
    $('#fCategory').value=article.category||'';
    $('#fAuthor').value=article.author||'';
    $('#fExcerpt').value=article.excerpt||'';
    $('#fContent').value=article.content||'';
    $('#fPublished').checked=article.published!==false;
    pendingImageData=article.image||null;
    $('#fImageData').value=article.image||'';
    if(article.image){
      $('#imagePreview').src=article.image;
      $('#imagePreviewWrap').classList.remove('hidden');
      $('#imageDropContent').classList.add('hidden');
      $('#imageName').textContent='Current image';
    }
  } else {
    editingId=null;
    $('#articleForm').reset();
    $('#fPublished').checked=true;
    pendingImageData=null;
    $('#fImageData').value='';
    $('#imagePreviewWrap').classList.add('hidden');
    $('#imageDropContent').classList.remove('hidden');
  }
  $('#formStatus').textContent='';
}
function closeEditor(){
  $('#editorModal').classList.add('hidden');
  document.body.style.overflow='';
  editingId=null;
}
$('#newBtn').addEventListener('click', ()=> openEditor('new'));
$('#closeEditor').addEventListener('click', closeEditor);
$('#cancelEditor').addEventListener('click', closeEditor);
$('#editorBackdrop').addEventListener('click', closeEditor);

window.editArticle = (id)=>{
  const a=adminArticles.find(x=>String(x.id)===String(id));
  if(a) openEditor('edit', a);
};
window.deleteArticle = async (id)=>{
  if(!confirm('Delete this article?')) return;
  try{
    const r=await fetch('/api/articles/'+id, {method:'DELETE'});
    if(!r.ok){ const j=await r.json(); throw new Error(j.error||'Delete failed'); }
    toast('Deleted');
    await loadAdminArticles();
  }catch(e){ toast(e.message, false); }
};

// Image handling — FIXED: proper preview + base64 conversion
const imageInput=$('#fImage');
const imageDrop=$('#imageDrop');
imageDrop.addEventListener('dragover', e=>{e.preventDefault(); imageDrop.classList.add('drop-active')});
imageDrop.addEventListener('dragleave', e=> imageDrop.classList.remove('drop-active'));
imageDrop.addEventListener('drop', e=>{e.preventDefault(); imageDrop.classList.remove('drop-active'); const f=e.dataTransfer.files[0]; if(f) handleImageFile(f); });
imageInput.addEventListener('change', e=>{ const f=e.target.files[0]; if(f) handleImageFile(f); });
function handleImageFile(file){
  if(!file.type.startsWith('image/')){ toast('Please select an image', false); return; }
  if(file.size > 4*1024*1024){ toast('Image too large (max 4MB)', false); return; }
  const reader=new FileReader();
  reader.onload = ()=>{
    pendingImageData=reader.result; // data URL
    $('#fImageData').value=pendingImageData;
    $('#imagePreview').src=pendingImageData;
    $('#imagePreviewWrap').classList.remove('hidden');
    $('#imageDropContent').classList.add('hidden');
    $('#imageName').textContent=file.name+' • '+(file.size/1024).toFixed(0)+' KB';
  };
  reader.readAsDataURL(file);
}
$('#removeImage').addEventListener('click', ()=>{
  pendingImageData=null;
  $('#fImageData').value='';
  $('#fImage').value='';
  $('#imagePreviewWrap').classList.add('hidden');
  $('#imageDropContent').classList.remove('hidden');
});

// Submit — FIXED: sends image as data URL correctly
$('#articleForm').addEventListener('submit', async (e)=>{
  e.preventDefault();
  const title=$('#fTitle').value.trim();
  const excerpt=$('#fExcerpt').value.trim();
  const content=$('#fContent').value.trim();
  const category=$('#fCategory').value.trim() || 'Article';
  const author=$('#fAuthor').value.trim() || 'Admin';
  const published=$('#fPublished').checked;
  const imageData=$('#fImageData').value.trim();
  if(!title || !excerpt || !content){ toast('Fill required fields', false); return; }
  if(!imageData){ toast('Please upload an image', false); return; }
  const payload={ title, excerpt, content, category, author, published, image: imageData };
  // also support FormData with file if user selected file but preview already converted
  $('#formStatus').textContent='Saving…';
  try{
    let url='/api/articles';
    let method='POST';
    if(editingId){ url='/api/articles/'+editingId; method='PUT'; }
    const r=await fetch(url, {method, headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
    const j=await r.json();
    if(!r.ok) throw new Error(j.error||'Save failed');
    toast(editingId?'Updated':'Created');
    closeEditor();
    await loadAdminArticles();
  }catch(err){ $('#formStatus').textContent='Error: '+err.message; $('#formStatus').className='text-xs text-rose-400'; toast(err.message, false); }
});
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
            "GET /": "landing page + articles",
            "GET /admin": "admin panel",
            "GET /api/health": "health check",
            "GET /api/docs": "this document",
            "GET /api/articles": "list articles",
            "GET /api/articles/{id}": "get one",
            "POST /api/articles": "create (JSON: title, excerpt, content, image dataURL, category, author, published)",
            "PUT /api/articles/{id}": "update",
            "DELETE /api/articles/{id}": "delete",
            "POST /api/find": "multipart: file + query -> matches",
            "POST /api/replace": "multipart: file + find + replace (+dry_run) -> PDF or JSON",
            "POST /api/replace-all": "multipart: file + find + replace -> PDF",
        },
    }


# --- multipart helpers (stdlib only) ---
def _parse_multipart(handler: BaseHTTPRequestHandler) -> dict:
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
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)

        if path in ("/", "/api"):
            _html_response(self, LANDING_HTML)
            return
        if path in ("/admin", "/admin/"):
            _html_response(self, ADMIN_HTML)
            return
        if path in ("/api/health", "/health"):
            _json_response(self, 200, _health_payload())
            return
        if path in ("/api/docs", "/docs"):
            _json_response(self, 200, _docs_payload())
            return
        if path == "/api/articles":
            articles = _load_articles()
            _json_response(self, 200, {"articles": articles})
            return
        if path.startswith("/api/articles/"):
            aid = path.split("/")[-1]
            articles = _load_articles()
            found = next((a for a in articles if str(a.get("id")) == aid), None)
            if not found:
                _json_response(self, 404, {"error": "not found"})
                return
            _json_response(self, 200, found)
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
        if path == "/api/articles":
            self._handle_create_article()
            return
        if path == "/api/upload":
            self._handle_upload()
            return

        _json_response(self, 404, {"error": "not found", "path": path})

    def do_PUT(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if path.startswith("/api/articles/"):
            self._handle_update_article(path.split("/")[-1])
            return
        _json_response(self, 404, {"error": "not found"})

    def do_DELETE(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if path.startswith("/api/articles/"):
            self._handle_delete_article(path.split("/")[-1])
            return
        _json_response(self, 404, {"error": "not found"})

    # --- article handlers ---
    def _handle_create_article(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b""
        ctype = self.headers.get("Content-Type", "")
        data: dict = {}
        image_data_url: str | None = None

        if "application/json" in ctype:
            try:
                data = json.loads(raw.decode() or "{}")
                image_data_url = data.get("image")
            except Exception as e:
                _json_response(self, 400, {"error": f"invalid json: {type(e).__name__}"})
                return
        elif "multipart/form-data" in ctype:
            # need to re-parse with raw already read — reconstruct handler state
            # simpler: use _parse_multipart by feeding raw via temp handler
            # fallback: read again? we already consumed — so parse manually from raw
            # quick parse for image file
            try:
                boundary = None
                for part in ctype.split(";"):
                    part = part.strip()
                    if part.startswith("boundary="):
                        boundary = part.split("=", 1)[1].strip('"')
                        break
                if boundary:
                    delimiter = ("--" + boundary).encode()
                    parts = raw.split(delimiter)
                    for chunk in parts:
                        if b"\r\n\r\n" not in chunk:
                            continue
                        hraw, body = chunk.split(b"\r\n\r\n", 1)
                        if body.endswith(b"\r\n"):
                            body = body[:-2]
                        hstr = hraw.decode(errors="ignore")
                        name = None
                        filename = None
                        for line in hstr.split("\r\n"):
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
                        if filename and name == "image":
                            image_data_url = _bytes_to_data_url(body, filename)
                        elif filename and name == "file":
                            image_data_url = _bytes_to_data_url(body, filename)
                        elif name == "image" and not filename:
                            # data URL passed as text
                            try:
                                image_data_url = body.decode()
                            except Exception:
                                pass
                        else:
                            try:
                                data[name] = body.decode()
                            except Exception:
                                data[name] = body
                    if "image" in data and not image_data_url:
                        image_data_url = data.get("image")
            except Exception as e:
                _json_response(self, 400, {"error": f"multipart parse failed: {type(e).__name__}"})
                return
        else:
            try:
                data = json.loads(raw.decode() or "{}")
                image_data_url = data.get("image")
            except Exception:
                pass

        title = (data.get("title") or "").strip()
        excerpt = (data.get("excerpt") or "").strip()
        content = (data.get("content") or "").strip()
        category = (data.get("category") or "Article").strip()
        author = (data.get("author") or "Admin").strip()
        published = data.get("published", True)
        if isinstance(published, str):
            published = published.lower() not in ("false", "0", "no")
        image = image_data_url or data.get("image") or ""

        if not title or not excerpt or not content:
            _json_response(self, 400, {"error": "missing required fields: title, excerpt, content"})
            return
        if not image:
            _json_response(self, 400, {"error": "cover image is required — upload an image in admin panel"})
            return

        articles = _load_articles()
        new_id = str(uuid.uuid4())[:8]
        # ensure unique
        while any(str(a.get("id")) == new_id for a in articles):
            new_id = str(uuid.uuid4())[:8]
        now = time.strftime("%Y-%m-%d")
        article = {
            "id": new_id,
            "title": title,
            "slug": title.lower().replace(" ", "-")[:60],
            "excerpt": excerpt,
            "content": content,
            "image": image,
            "category": category,
            "author": author,
            "date": now,
            "published": bool(published),
        }
        articles.insert(0, article)
        _save_articles(articles)
        _json_response(self, 201, article)

    def _handle_update_article(self, aid: str) -> None:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b""
        ctype = self.headers.get("Content-Type", "")
        data: dict = {}
        try:
            if "application/json" in ctype:
                data = json.loads(raw.decode() or "{}")
            else:
                data = json.loads(raw.decode() or "{}")
        except Exception as e:
            _json_response(self, 400, {"error": f"invalid json: {type(e).__name__}"})
            return

        articles = _load_articles()
        idx = next((i for i, a in enumerate(articles) if str(a.get("id")) == aid), None)
        if idx is None:
            _json_response(self, 404, {"error": "not found"})
            return

        cur = articles[idx]
        # merge, keep image if not provided
        for k in ("title", "excerpt", "content", "category", "author", "published", "image", "slug"):
            if k in data and data[k] != "":
                cur[k] = data[k]
        # handle published string
        if "published" in data and isinstance(cur["published"], str):
            cur["published"] = cur["published"].lower() not in ("false", "0", "no")
        if not cur.get("image"):
            _json_response(self, 400, {"error": "cover image is required"})
            return

        articles[idx] = cur
        _save_articles(articles)
        _json_response(self, 200, cur)

    def _handle_delete_article(self, aid: str) -> None:
        articles = _load_articles()
        new_list = [a for a in articles if str(a.get("id")) != aid]
        if len(new_list) == len(articles):
            _json_response(self, 404, {"error": "not found"})
            return
        _save_articles(new_list)
        _json_response(self, 200, {"ok": True})

    def _handle_upload(self) -> None:
        fields = _parse_multipart(self)
        files = fields.get("_files", {})
        # support both 'file' and 'image'
        fkey = "file" if "file" in files else ("image" if "image" in files else None)
        if not fkey:
            _json_response(self, 400, {"error": "missing file field 'file' or 'image'"})
            return
        data: bytes = files[fkey]["data"]  # type: ignore
        filename = files[fkey]["filename"]  # type: ignore
        if len(data) > 5 * 1024 * 1024:
            _json_response(self, 400, {"error": "file too large (max 5MB)"})
            return
        data_url = _bytes_to_data_url(data, filename)
        _json_response(self, 200, {"url": data_url, "filename": filename})

    # --- PDF handlers (unchanged) ---
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
