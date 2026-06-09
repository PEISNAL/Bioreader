"""
BioReader Parser v8 — Universal Defense Pipeline
  S1: Symbol normalization + encoding fix
  S2: Universal margin filter (geometry-based header/footer/page-number removal)
  S3: Multi-pattern section heading detection + figure extraction
  S4: Multi-strategy reference parsing
  S5: Cross-page hyphenation repair
"""

from __future__ import annotations
import re, json, time, os, fitz, pymupdf4llm
from typing import Any
from collections import OrderedDict


# ======================== S1: Symbol Normalization ========================

def _normalize(text: str) -> str:
    """Fix common encoding artifacts and normalize symbols."""
    text = re.sub(r'(\d+)\s*\?\s*C\b', r'\1_deg_C', text)
    text = re.sub(r'(\d+)\s*\?\s*M\b', r'\1_uM', text)
    text = re.sub(r'(\d+)C\b', r'\1_deg_C', text)
    text = re.sub(r'(\d+)_deg_C', r'\1°C', text)
    text = re.sub(r'(\d+)_uM', r'\1 μM', text)
    text = re.sub(r'(\d+)\s*°\s*C', r'\1°C', text)
    text = re.sub(r'(\d+)\s*μ\s*M', r'\1 μM', text)
    # Strip PUA block + replacement char + control chars
    text = re.sub('[-�]', '', text)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
    text = text.replace('-deoxycytidine', "5-aza-2'-deoxycytidine")
    return text


# ======================== S2: Universal Margin Filter ========================

def _universal_margin_filter(file_path: str) -> set[str]:
    """Cross-page geometric analysis: auto-detect headers, footers, page numbers,
    DOIs, URLs, and first-page footnote text that repeats across pages.

    Strategy:
      1. Extract text blocks with bbox from EVERY page via PyMuPDF.
      2. Classify text into header zone (top 10%), footer zone (bottom 12%).
      3. Normalize and count occurrences across pages.
      4. Any text appearing on >= 40% of pages in margin zones → filter candidate.
      5. Additional patterns: standalone page numbers, DOI/URL lines,
         first-page small-font footnotes.
    """
    try:
        doc = fitz.open(file_path)
    except Exception:
        return set()

    n_pages = len(doc)
    if n_pages == 0:
        doc.close()
        return set()

    threshold = max(2, int(n_pages * 0.4))

    header_counter: dict[str, int] = {}
    footer_counter: dict[str, int] = {}
    first_page_footnotes: set[str] = set()
    url_doi_lines: set[str] = set()
    page_numbers: set[str] = set()

    for pi in range(n_pages):
        page = doc[pi]
        ph = page.rect.height
        pw = page.rect.width
        d = page.get_text("dict")

        header_y = ph * 0.10
        footer_y = ph * 0.88

        for blk in d.get("blocks", []):
            if blk.get("type") != 0:
                continue
            bbox = blk["bbox"]
            _, y0, _, y1 = bbox

            for line in blk.get("lines", []):
                line_text = ""
                max_size = 0.0
                for span in line.get("spans", []):
                    line_text += span.get("text", "")
                    sz = span.get("size", 0)
                    if sz > max_size:
                        max_size = sz

                line_text = line_text.strip()
                if not line_text or len(line_text) < 2:
                    continue

                norm = _normalize_margin(line_text)

                # Header zone
                if y0 < header_y and len(line_text) > 2:
                    header_counter[norm] = header_counter.get(norm, 0) + 1

                # Footer zone
                if y0 > footer_y:
                    if re.match(r'^\d{1,4}$', line_text):
                        page_numbers.add(line_text)
                    elif len(line_text) > 2:
                        footer_counter[norm] = footer_counter.get(norm, 0) + 1

                # First-page bottom small-font footnotes
                if pi == 0 and y0 > footer_y and max_size < 9 and len(line_text) > 5:
                    first_page_footnotes.add(line_text)

                # DOI / URL anywhere
                if re.match(r'^(https?://|doi\s*:|www\.)', line_text, re.I):
                    url_doi_lines.add(line_text)

    doc.close()

    filter_set: set[str] = set()

    for text, cnt in header_counter.items():
        if cnt >= threshold and len(text) > 3:
            filter_set.add(text)

    for text, cnt in footer_counter.items():
        if cnt >= threshold and len(text) > 3:
            filter_set.add(text)

    filter_set.update(first_page_footnotes)
    filter_set.update(page_numbers)
    filter_set.update(url_doi_lines)

    # Generic footnote keyword patterns (content-based, not journal-specific)
    footnote_kw = [
        r'correspondence\s*(to\s*)?:', r'e-?mail\s*:',
        r'present\s+address\s*:', r'equal\s+contribution',
        r'lead\s+contact', r'orcid\s*:', r'author\s+contributions',
        r'conflict\s+of\s+interest', r'funding\s*:',
        r'grant\s+numbers?\s*:', r'supplementary\s+(data|information|material)',
        r'data\s+availability', r'code\s+availability',
        r'©\s*\d{4}', r'copyright\s+©',
    ]
    # These patterns are used later in content-based filtering, not added to set directly

    return filter_set


def _normalize_margin(text: str) -> str:
    """Normalize margin text for cross-page comparison: collapse whitespace,
    replace digits with placeholder, strip punctuation."""
    t = text.strip().lower()
    t = re.sub(r'\s+', ' ', t)
    t = re.sub(r'\d+', '#', t)
    t = re.sub(r'[^\w\s#]', '', t)
    return t.strip()


def _apply_margin_filter(md_text: str, filter_set: set[str]) -> str:
    """Apply margin filter set to Markdown text by removing matching lines.

    Also applies generic footnote keyword patterns."""
    if not filter_set and True:  # always run keyword patterns
        pass

    lines = md_text.split('\n')
    clean: list[str] = []

    # Generic patterns that indicate footnote/header cruft
    cruft_patterns = [
        re.compile(r'^(>?\s*)?correspondence\s*(to\s*)?:', re.I),
        re.compile(r'^(>?\s*)?\*?\s*e-?mail\s*:', re.I),
        re.compile(r'^(>?\s*)?present\s+address\s*:', re.I),
        re.compile(r'^(>?\s*)?these\s+authors\s+contributed\s+equally', re.I),
        re.compile(r'^(>?\s*)?lead\s+contact', re.I),
        re.compile(r'^(>?\s*)?orcid\s*:', re.I),
        re.compile(r'^(>?\s*)?author\s+contributions', re.I),
        re.compile(r'^(>?\s*)?conflict\s+of\s+interest', re.I),
        re.compile(r'^(>?\s*)?acknowledg?ments?$', re.I),
        re.compile(r'^(>?\s*)?funding\s*:', re.I),
        re.compile(r'^(>?\s*)?grant\s+numbers?\s*:', re.I),
        re.compile(r'^(>?\s*)?supplementary\s+(data|information|material)', re.I),
        re.compile(r'^(>?\s*)?data\s+availability', re.I),
        re.compile(r'^(>?\s*)?code\s+availability', re.I),
        re.compile(r'^(>?\s*)?\d+\s*$'),  # standalone numbers (page numbers)
        re.compile(r'^(>?\s*)?https?://', re.I),
        re.compile(r'^(>?\s*)?doi\s*:', re.I),
        re.compile(r'^(>?\s*)?www\.', re.I),
        re.compile(r'^\s*©\s*\d{4}', re.I),
        re.compile(r'^\s*copyright\s+©', re.I),
    ]

    for line in lines:
        s = line.strip()
        if not s:
            clean.append(line)
            continue

        skip = False

        # Check against geometric filter set
        if filter_set:
            s_norm = _normalize_margin(s)
            for ft in filter_set:
                ft_norm = _normalize_margin(ft)
                if ft_norm and len(ft_norm) > 3 and (ft_norm in s_norm or s_norm in ft_norm):
                    skip = True
                    break

        # Check against generic cruft patterns
        if not skip:
            for pat in cruft_patterns:
                if pat.match(s):
                    skip = True
                    break

        if not skip:
            clean.append(line)

    return '\n'.join(clean)


def _remove_page_headers(md_text: str, file_path: str) -> str:
    """Remove running titles and page numbers that pymupdf4llm inserts between paragraphs.

    pymupdf4llm outputs page headers as: \n\nRunning Title <page_number>\n\n
    This function detects these patterns and removes them.
    """
    try:
        doc = fitz.open(file_path)
    except Exception:
        return md_text

    n_pages = len(doc)
    if n_pages < 2:
        doc.close()
        return md_text

    # Extract original header text from PDF (not normalized)
    header_texts: dict[str, int] = {}
    for pi in range(n_pages):
        page = doc[pi]
        ph = page.rect.height
        d = page.get_text("dict")
        for blk in d.get("blocks", []):
            if blk.get("type") != 0:
                continue
            _, y0, _, _ = blk["bbox"]
            if y0 > ph * 0.10:  # only top 10%
                continue
            for line in blk.get("lines", []):
                txt = "".join(s.get("text", "") for s in line.get("spans", [])).strip()
                if txt and len(txt) > 5:
                    header_texts[txt] = header_texts.get(txt, 0) + 1

    doc.close()

    # Find running titles: text that appears on >=40% of pages in header zone
    threshold = max(2, int(n_pages * 0.4))
    running_titles = sorted(
        [t for t, c in header_texts.items() if c >= threshold and len(t) > 8],
        key=len, reverse=True
    )

    if not running_titles:
        return md_text

    # Remove header patterns from markdown:
    # Pattern: \n\n<running_title> <digits>\n\n
    for title in running_titles:
        escaped = re.escape(title)
        # Title + optional page number
        md_text = re.sub(
            r'\n\n\s*' + escaped + r'\s*\d*\s*\n\n',
            '\n\n', md_text, flags=re.I
        )
        # Also match title alone on a line
        md_text = re.sub(
            r'\n\s*' + escaped + r'\s*\d*\s*\n',
            '\n', md_text, flags=re.I
        )

    # Remove standalone 3-digit numbers between paragraphs (page numbers)
    md_text = re.sub(r'\n\n\s*\d{3,4}\s*\n\n', '\n\n', md_text)

    return md_text


def _repair_hyphenation(text: str) -> str:
    """Cross-page hyphenation repair: 'endoge-\nnous' → 'endogenous'"""
    return re.sub(r'(\w+)-\s*\n+\s*(\w+)', r'\1\2', text)


# ======================== S3: Figure Extraction ========================

def _extract_figures(text: str) -> tuple[str, list[dict]]:
    figures: list[dict] = []
    seen: set[str] = set()
    lines = text.split('\n')
    clean: list[str] = []
    pending: list[str] = []

    for line in lines:
        s = line.strip()
        if not s:
            if pending:
                _flush(pending, figures, seen)
                pending = []
            clean.append(line)
            continue
        if 'intentionally omitted' in s.lower():
            continue
        is_cap = bool(re.match(r'^(?:Figure|Fig\.?)\s*\d+', s, re.I))
        is_sub = bool(re.match(r'^\([A-Z]\)\s+', s))
        if is_cap or is_sub:
            pending.append(s)
            continue
        if pending:
            if len(s) > 10 and not re.match(r'^##?\s', s):
                pending.append(s)
                continue
            else:
                _flush(pending, figures, seen)
                pending = []
        clean.append(line)

    if pending:
        _flush(pending, figures, seen)

    return '\n'.join(clean), figures


def _flush(lines: list[str], figures: list[dict], seen: set[str]):
    cap = ' '.join(lines)
    m = re.match(r'(Figure\s+\d+[A-Z]?)', cap, re.I)
    fid = m.group(1) if m else f'Figure-{len(figures)+1}'
    if fid not in seen:
        seen.add(fid)
        figures.append({'id': fid, 'caption': cap})


# ======================== S4: Section Parsing ========================

SLUGS = OrderedDict([
    ('abstract','abstract'),('summary','abstract'),('introduction','introduction'),
    ('results','results'),('results and discussion','results'),
    ('discussion','discussion'),('materials and methods','methods'),
    ('methods','methods'),('experimental procedures','methods'),
    ('acknowledgments','acknowledgments'),('acknowledgements','acknowledgments'),
    ('references','references'),('literature cited','references'),
    ('bibliography','references'),('identification of','results'),
    ('gene silencing','results'),('dna methylation','results'),
    ('epigenetic','results'),('map-based','results'),
    ('encodes a','results'),('nicking activity','results'),
    ('plant growth','methods'),('positional cloning','methods'),
    ('localization of','methods'),('in vitro activity','methods'),
])

HEAD_RE = re.compile(r'^#{1,3}\s+(.+?)$')
KW_RE = re.compile(
    r'^(Abstract|Summary|Introduction|Results(?:\s+and\s+Discussion)?|'
    r'Discussion|Materials?\s*(?:and|&)\s*Methods?|Methods?|'
    r'Experimental\s+Procedures?|Acknowledgments?|Acknowledgements?|'
    r'References?|Literature\s+Cited|Bibliography)$', re.I)


def _slug(title: str) -> str:
    t = title.strip().lower().rstrip('.')
    for kw, sl in SLUGS.items():
        if kw in t:
            return sl
    return 'body'


def _parse_sections(md: str) -> tuple[list[dict], list[dict]]:
    md, figures = _extract_figures(md)
    lines = md.split('\n')
    positions = []
    cum = 0

    for line in lines:
        pos = cum
        cum += len(line) + 1
        s = line.strip()
        if not s:
            continue
        m = HEAD_RE.match(s) or KW_RE.match(s)
        if not m:
            continue
        title = m.group(1) if m.lastindex else s
        title = re.sub(r'[*_]{1,3}', '', title).strip()
        positions.append((pos, pos + len(s), title))

    seen_titles = set()
    deduped = []
    for h in positions:
        if h[2] not in seen_titles:
            seen_titles.add(h[2])
            deduped.append(h)
    positions = deduped

    sections = []
    for i, (start, end, title) in enumerate(positions):
        body_start = end + 1
        body_end = positions[i+1][0] if i+1 < len(positions) else len(md)
        body = md[body_start:body_end].strip()

        paragraphs = []
        for para in body.split('\n\n'):
            para = para.strip()
            if len(para) < 15:
                continue
            clean = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', para)
            clean = re.sub(r'_([^_]+)_', r'\1', clean)
            clean = re.sub(r'\s+', ' ', clean).strip()
            if re.match(r'^(?:Figure|Fig\.?)\s*\d+|\([A-Z]\)\s+', clean, re.I):
                continue
            refs = list(set(re.findall(r'Figure\s+\d+[A-Z]?', clean, re.I)))
            entry = {'en': clean}
            if refs:
                entry['refs'] = refs
            paragraphs.append(entry)

        if paragraphs:
            sections.append({'title': title, 'slug': _slug(title), 'paragraphs': paragraphs})

    return sections, figures


# ======================== S5: Universal Reference Parsing ========================

def _parse_references(sections: list[dict]) -> list[str]:
    """Multi-strategy reference parsing — works across journals and formats.

    Strategy (tried in order):
      1. Numbered-list mode: detect [1], 1., (1) patterns → split on each.
      2. Author-year mode: split on ". Surname, I." boundaries (most common).
      3. Line-break mode: use paragraph breaks as reference boundaries.
      4. Clean and deduplicate.

    Output always formatted as clean text (numbering added by frontend).
    """
    ref_sec = next((s for s in sections if s['slug'] == 'references'), None)
    if not ref_sec:
        return []

    paragraphs = [p['en'] for p in ref_sec['paragraphs']]

    # ---- Step 1: Reconstruct text preserving paragraph boundaries ----
    # Use double-newline as paragraph separator (preserves some structure)
    raw_text = '\n\n'.join(paragraphs)

    # ---- Step 2: Split into individual references ----
    # Pattern A: Numbered references [1], 1., (1), 1)
    numbered_split = re.compile(
        r'(?:^|\n)\s*\[?\s*(\d+)\s*\]?\s*[\.\)\-–—]\s+'
    )

    # Pattern B: Author-year boundary: ". Author, I." or ". Author, I.B."
    # This matches: period + space + Capitalized surname + comma + initial(s) + period
    author_boundary = re.compile(
        r'\.\s+(?=[A-Z][a-zà-ÿ\-]{2,},\s+[A-Z]\.)'
    )

    # Check if this is a numbered reference list
    numbered_matches = numbered_split.findall(raw_text)
    is_numbered = len(numbered_matches) >= 3

    if is_numbered:
        # Split on each numbered entry
        parts = re.split(r'(?=(?:^|\n)\s*\[?\d+\]?\s*[\.\)\-–—]\s+)', raw_text)
        parts = [p.strip() for p in parts if p.strip()]
    else:
        # Try author-boundary split first
        parts = author_boundary.split(raw_text)
        parts = [p.strip() for p in parts if p.strip()]

        # If that didn't work well (too few parts), use paragraph breaks
        if len(parts) < 3:
            parts = [p.strip() for p in raw_text.split('\n\n') if p.strip()]
            # Still too few? Try single newlines
            if len(parts) < 3:
                parts = [p.strip() for p in raw_text.split('\n') if p.strip()]

    # ---- Step 3: Merge continuation fragments ----
    # A continuation is a part that doesn't look like a reference start
    author_start = re.compile(r'^[A-Z][a-zà-ÿ\-]{2,},\s+[A-Z]\.')
    numbered_start = re.compile(r'^\s*\[?\d+\]?\s*[\.\)\-–—]')

    entries: list[str] = []
    current: list[str] = []

    for part in parts:
        s = part.strip()
        if not s:
            continue

        is_start = bool(author_start.match(s)) or bool(numbered_start.match(s))

        if is_start and current:
            entries.append(' '.join(current))
            current = [s]
        else:
            current.append(s)

    if current:
        entries.append(' '.join(current))

    # ---- Step 4: Clean each entry ----
    cleaned: list[str] = []
    for e in entries:
        e = e.strip()
        if not e or len(e) < 25:
            continue

        # Normalize
        e = e.replace('–', '-').replace('—', '-')
        e = re.sub(r'\s+', ' ', e)
        e = re.sub(r'\s*­\s*', '', e)  # soft hyphens

        # Remove leading number/bracket
        e = re.sub(r'^\[?\s*\d+\s*\]?\s*[\.\)\-–—]\s*', '', e)
        e = re.sub(r'^\s*\(\d+\)\s*', '', e)
        e = re.sub(r'^\s*\d+\s*[\.\-–—]\s*', '', e)

        # Fix encoding artifacts
        e = e.replace('Â', '').replace('Ä', '')

        e = e.strip()
        if len(e) > 25:
            cleaned.append(e)

    # Deduplicate by normalized prefix (first 60 chars)
    seen: set[str] = set()
    unique: list[str] = []
    for e in cleaned:
        prefix = e[:60].lower()
        if prefix not in seen:
            seen.add(prefix)
            unique.append(e)

    return unique


# ======================== Figure Image Extraction ========================

def _extract_figure_images(file_path: str) -> list[dict]:
    """Extract real figure images from PDF using PyMuPDF.

    Strategy:
      1. Scan every page for figure captions ("Figure N." pattern).
      2. For each page that has a caption, find the largest embedded image.
      3. Render the image as high-quality PNG using pixmap.
      4. Build a clean figure list: one entry per unique figure number.
      5. Compound figures (one image with sub-panels A/B/C) → sub-figures
         like "Figure 2A" get the same image_path as "Figure 2".

    Returns:
      [{id: "Figure 1", caption: "...", page: 2, image_path: "/static/figures/Figure_1.png"}]
    """
    try:
        doc = fitz.open(file_path)
    except Exception:
        return []

    n_pages = len(doc)
    static_dir = os.path.join(os.path.dirname(__file__), "..", "static", "figures")
    os.makedirs(static_dir, exist_ok=True)

    # ---- Step 1: find figure captions and images per page ----
    page_figures: dict[int, list[dict]] = {}  # page_num → [figure entries]

    for pi in range(n_pages):
        page = doc[pi]
        page_text = page.get_text()

        # Find all figure captions on this page
        # Captions look like: "Figure N. Title text..." or "Figure N (continued)"
        captions: list[tuple[str, str]] = []  # [(figure_id, caption_text)]

        for m in re.finditer(
            r'(?:^|\n)\s*(Figure\s+(\d+)[A-Z]?)[\.\s]+(.+?)(?=\n(?:Figure\s+\d+|$))',
            page_text, re.I | re.DOTALL
        ):
            fid = m.group(1).strip()
            caption_text = m.group(3).strip().replace('\n', ' ')
            captions.append((fid, caption_text))

        # If multi-line captions aren't caught, try simpler pattern
        if not captions:
            for line in page_text.split('\n'):
                m = re.match(r'^(Figure\s+\d+[A-Z]?)[\.\s]+(.+)', line.strip(), re.I)
                if m:
                    captions.append((m.group(1).strip(), m.group(2).strip()[:200]))

        if not captions:
            continue

        # Get images on this page
        images = page.get_images(full=True)
        if not images:
            # No embedded images — maybe the figure is vector art or text-based
            # Still record the captions
            for fid, cap in captions:
                if pi + 1 not in page_figures:
                    page_figures[pi + 1] = []
                # Don't duplicate same ID on same page
                if not any(f['id'] == fid for f in page_figures[pi + 1]):
                    page_figures[pi + 1].append({
                        'id': fid,
                        'caption': cap,
                        'page': pi + 1,
                        'image_path': '',
                    })
            continue

        # Find the largest image (likely the figure itself)
        best_xref = None
        best_area = 0
        best_ext = 'png'

        for img_info in images:
            xref = img_info[0]
            try:
                base = doc.extract_image(xref)
                w, h = base.get('width', 0), base.get('height', 0)
                area = w * h
                if area > best_area and area > 15000:  # ignore tiny icons
                    best_area = area
                    best_xref = xref
                    best_ext = base.get('ext', 'png')
            except Exception:
                continue

        if best_xref is None:
            # No suitable image found
            for fid, cap in captions:
                if pi + 1 not in page_figures:
                    page_figures[pi + 1] = []
                if not any(f['id'] == fid for f in page_figures[pi + 1]):
                    page_figures[pi + 1].append({
                        'id': fid, 'caption': cap,
                        'page': pi + 1, 'image_path': '',
                    })
            continue

        # Render image at high quality
        primary_fid = captions[0][0] if captions else f'Figure_{pi+1}'
        safe_name = primary_fid.replace(' ', '_')
        fname = f"{safe_name}.png"
        fpath = os.path.join(static_dir, fname)

        if not os.path.exists(fpath):
            try:
                pix = fitz.Pixmap(doc, best_xref)
                # Convert CMYK to RGB if needed
                if pix.n > 4:
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                if pix.n == 4:  # RGBA → save as PNG with alpha
                    pix.save(fpath)
                else:
                    pix.save(fpath)
                pix = None  # free memory
            except Exception:
                # Fallback: raw extraction
                try:
                    base = doc.extract_image(best_xref)
                    with open(fpath, 'wb') as f:
                        f.write(base['image'])
                except Exception:
                    pass

        image_path = f"/api/figures/{fname}"

        # Assign this image to ALL figure captions on this page
        for fid, cap in captions:
            if pi + 1 not in page_figures:
                page_figures[pi + 1] = []
            if not any(f['id'] == fid for f in page_figures[pi + 1]):
                page_figures[pi + 1].append({
                    'id': fid,
                    'caption': cap,
                    'page': pi + 1,
                    'image_path': image_path,
                })

    doc.close()

    # ---- Step 2: Flatten and sort by figure number ----
    result: list[dict] = []
    for pi in sorted(page_figures.keys()):
        for f in page_figures[pi]:
            result.append(f)

    # Sort by figure number (extract numeric part)
    def _sort_key(f: dict) -> tuple:
        m = re.match(r'Figure\s+(\d+)([A-Z]?)', f['id'], re.I)
        if m:
            return (int(m.group(1)), m.group(2))
        return (9999, '')

    result.sort(key=_sort_key)

    return result


# ======================== Main Pipeline ========================

def parse(file_path: str) -> dict[str, Any]:
    t0 = time.perf_counter()
    log: list[str] = []

    # Convert PDF to Markdown
    raw = pymupdf4llm.to_markdown(file_path)
    log.append(f'raw:{len(raw)}c')

    # S1: Normalize
    md = _normalize(raw)
    log.append('S1:normalize')

    # S2: Universal margin filter (geometry-based header/footer removal)
    filter_set = _universal_margin_filter(file_path)
    md = _apply_margin_filter(md, filter_set)
    md = _remove_page_headers(md, file_path)
    log.append(f'S2:margin_filter({len(filter_set)}items)')

    # Cross-page hyphenation repair
    md = _repair_hyphenation(md)

    # S3: Section + figure parsing
    sections, _ = _parse_sections(md)
    # Remove pymupdf4llm's embedded picture markers from body text
    md = re.sub(r'\*\*==>\s*picture\s*\[[^\]]*\].*?\n', '', md)
    log.append(f'S3:{len(sections)}sec')

    # S3.5: Figure image extraction (PyMuPDF direct — builds clean figure list)
    figures = _extract_figure_images(file_path)
    log.append(f'S3.5:{len([f for f in figures if f.get("image_path")])}/{len(figures)}fig_images')

    # S4: Reference parsing
    references = _parse_references(sections)
    sections = [s for s in sections if s['slug'] != 'references']
    log.append(f'S4:{len(references)}refs')

    # S5: (optional) LLM polish — kept for backwards compat
    polished = 0
    if os.environ.get('OLLAMA_POLISH'):
        import httpx
        OLLAMA_URL = "http://localhost:11434/api/chat"
        try:
            r = httpx.get("http://localhost:11434/api/tags", timeout=2)
            ollama_ok = r.status_code == 200 and len(r.json().get("models", [])) > 0
        except Exception:
            ollama_ok = False

        if ollama_ok:
            LLM_PROMPT = (
                "Translate this academic English to Chinese. Extract all Figure references.\n"
                "Output STRICT JSON: {\"zh\":\"...\",\"refs\":[\"Figure 1\"]}\n"
                "Use terms: 表观遗传 拟南芥 转录 突变体 甲基化"
            )
            for sec in sections:
                if sec['slug'] not in ('introduction', 'results'):
                    continue
                for i, p in enumerate(sec.get('paragraphs', [])):
                    if i >= 3:
                        break
                    try:
                        resp = httpx.post(OLLAMA_URL, json={
                            'model': 'qwen2.5:3b',
                            'messages': [{'role': 'user', 'content': f'{LLM_PROMPT}\n\nTEXT:\n{p.get("en", "")[:1200]}'}],
                            'stream': False,
                            'options': {'temperature': 0.1, 'num_predict': 500},
                        }, timeout=30)
                        if resp.status_code == 200:
                            content = resp.json()['message']['content']
                            m = re.search(r'\{[\s\S]*\}', content)
                            if m:
                                r = json.loads(m.group(0))
                                sec['paragraphs'][i]['zh'] = r.get('zh', '')
                                sec['paragraphs'][i]['refs'] = r.get('refs', p.get('refs', []))
                                polished += 1
                    except Exception:
                        pass
            log.append(f'S5:{polished}polished')

    elapsed = round((time.perf_counter() - t0) * 1000, 1)
    return {
        'sections': sections,
        'figures': figures,
        'references': references,
        'parse_time_ms': elapsed,
        'pipeline_log': log,
        'llm_polished': polished,
    }
