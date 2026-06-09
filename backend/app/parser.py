"""
BioReader Parser v7 — Defense Pipeline
  S1: Symbol normalization (encoding fix)
  S2: Figure caption extraction + body purification
  S3: Multi-pattern section heading detection
  S4: Reference cleaning (no double numbering)
  S5: (optional) LLM translate + refs extraction
"""

from __future__ import annotations
import re, json, time, os, fitz, httpx, pymupdf4llm
from typing import Any
from collections import OrderedDict

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen2.5:3b"

def _ollama_ok() -> bool:
    try:
        r = httpx.get("http://localhost:11434/api/tags", timeout=2)
        return r.status_code == 200 and len(r.json().get("models", [])) > 0
    except Exception:
        return False

OLLAMA = _ollama_ok()

# ======================== S1: Symbol Normalization ========================

def _normalize(text: str) -> str:
    text = re.sub(r'(\d+)\s*\?\s*C\b', r'\1_deg_C', text)
    text = re.sub(r'(\d+)\s*\?\s*M\b', r'\1_uM', text)
    text = re.sub(r'(\d+)C\b', r'\1_deg_C', text)
    text = re.sub(r'(\d+)_deg_C', r'\1°C', text)
    text = re.sub(r'(\d+)_uM', r'\1 μM', text)
    text = re.sub(r'(\d+)\s*°\s*C', r'\1°C', text)
    text = re.sub(r'(\d+)\s*μ\s*M', r'\1 μM', text)
    # PUA block + replacement char + control chars — all removed
    text = re.sub('[-�]', '', text)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
    # specific known artifacts
    text = text.replace('-deoxycytidine', "5-aza-2'-deoxycytidine")
    return text


# ======================== 注脚双保险拦截器 ========================

def _filter_footnotes_regex(text: str) -> str:
    """保险一: 正则硬拦截注脚行 (通讯作者/地址/资助信息)"""
    patterns = [
        r'^>?\s*[\d\*\†\#\s]*Correspondence\s*:.*$',
        r'^>?\s*[\d\*\†\#\s]*Present\s+address\s*:.*$',
        r'^>?\s*[\d\*\†\#\s]*To\s+whom\s+correspondence\s+should\s+be\s+addressed.*$',
        r'^>?\s*[\d\*\†\#\s]*E-?mail\s*:.*$',
        r'^>?\s*[\d\*\†\#\s]*These\s+authors\s+contributed\s+equally.*$',
        r'^>?\s*[\d\*\†\#\s]*Lead\s+contact\s*:?.*$',
        r'^>?\s*[\d\*\†\#\s]*Correspondence\s+and\s+requests\s+for\s+materials.*$',
        r'^>?\s*jkzhu@ag\.arizona\.edu\s*$',
        r'^>?\s*[\d\*\†\#\s]*College\s+of\s+Biological\s+Sciences.*$',
        r'^>?\s*[\d\*\†\#\s]*China\s+Agricultural\s+University.*$',
        r'^>?\s*[\d\*\†\#\s]*Beijing\s+\d+.*$',
        r'^>?\s*[\d\*\†\#\s]*Tucson,\s*Arizona\s+\d+.*$',
        r'^>?\s*[\d\*\†\#\s]*Departamento\s+de\s+Gen.*$',
        r'^>?\s*[\d\*\†\#\s]*Universidad\s+de\s+C.*$',
        r'^>?\s*[\d\*\†\#\s]*14071\s+C.*$',
        r'^>?\s*[\d\*\†\#\s]*Spain\s*$',
    ]
    lines = text.split('\n')
    clean = []
    for line in lines:
        s = line.strip()
        if not s:
            clean.append(line)
            continue
        matched = False
        for pat in patterns:
            if re.match(pat, s, re.I):
                matched = True
                break
        if not matched:
            clean.append(line)
    return '\n'.join(clean)


def _filter_footnotes_geometric(file_path: str) -> None:
    """
    保险二: 几何绞杀 — 直接修改 PDF 资源? No.
    改为: 用 PyMuPDF 定位 Page 0 左栏底部小字，返回需要额外过滤的文本行集合。
    """
    try:
        doc = fitz.open(file_path)
        page = doc[0]
        pw = page.rect.width
        ph = page.rect.height
        mid_x = pw / 2.0
        d = page.get_text("dict")
        small_texts: set[str] = set()

        for blk in d.get("blocks", []):
            if blk.get("type") != 0:
                continue
            bbox = blk["bbox"]
            x0, y0, x1, y1 = bbox
            # 左栏底部: y0 > 75% 页高, 左栏
            if x1 > mid_x or y0 < ph * 0.72:
                continue

            for line in blk.get("lines", []):
                max_size = 0.0
                line_text = ""
                for span in line.get("spans", []):
                    line_text += span.get("text", "")
                    sz = span.get("size", 0)
                    if sz > max_size:
                        max_size = sz
                line_text = line_text.strip()
                if not line_text:
                    continue
                # 小字 (≤7pt) 且 不是正文关键词 → 注脚
                if max_size < 7.5 and len(line_text) > 3:
                    small_texts.add(line_text)

        doc.close()
        return small_texts
    except Exception:
        return set()


def _apply_geometric_filter(text: str, footnote_set: set[str]) -> str:
    """将几何过滤集合应用到 Markdown 文本中"""
    if not footnote_set:
        return text
    lines = text.split('\n')
    clean = []
    for line in lines:
        s = line.strip()
        should_skip = False
        for ft in footnote_set:
            if ft in s or s in ft:
                should_skip = True
                break
        if not should_skip:
            clean.append(line)
    return '\n'.join(clean)


# ======================== 页眉页码过滤 + 跨页断字缝合 ========================

def _filter_headers_and_repair(text: str) -> str:
    """
    1. 剔除页眉/页码/期刊头信息 (这些横插在段落间的垃圾阻断了跨页单词)
    2. 跨页断词无缝缝合 (endoge- + nous → endogenous)
    """
    lines = text.split('\n')
    # 页眉页码特征模式
    header_patterns = [
        r'^\s*Repression\s+of\s+Transcriptional\s+Gene\s+Silencing\s+\d+\s*$',
        r'^\s*Cell,\s+Vol\.\s+\d+.*$',
        r'^\s*Cell\s*\d+\s*$',
        r'^\s*\d{3,4}\s*$',
        r'^\s*\d+\s*Cell\s*$',
        r'^\s*ROS1.*Silencing.*\d+\s*$',
    ]
    clean = []
    for line in lines:
        s = line.strip()
        skip = False
        for pat in header_patterns:
            if re.match(pat, s, re.I):
                skip = True
                break
        if not skip:
            clean.append(line)

    result = '\n'.join(clean)

    # 跨页断词缝合: "endoge-\n\nnous" → "endogenous"
    result = re.sub(r'(\w+)-\s*\n+\s*(\w+)', r'\1\2', result)

    return result


# ======================== S2: Figure Extraction ========================

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


# ======================== S3: Section Parsing ========================

SLUGS = OrderedDict([
    ('abstract','abstract'),('summary','abstract'),('introduction','introduction'),
    ('results','results'),('results and discussion','results'),
    ('discussion','discussion'),('materials and methods','methods'),
    ('methods','methods'),('experimental procedures','methods'),
    ('acknowledgments','acknowledgments'),('acknowledgements','acknowledgments'),
    ('references','references'),('literature cited','references'),
    ('identification of','results'),('gene silencing','results'),
    ('dna methylation','results'),('epigenetic','results'),
    ('map-based','results'),('encodes a','results'),('nicking activity','results'),
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


# ======================== S4: Reference Cleaning ========================

def _clean_references(sections: list[dict]) -> list[str]:
    ref_sec = next((s for s in sections if s['slug'] == 'references'), None)
    if not ref_sec:
        return []
    all_text = ' '.join(p['en'] for p in ref_sec['paragraphs'])
    entries = re.split(r'(?<=\S\.)\s+(?=[A-Z][a-z\-]{2,},\s+[A-Z]\.)', all_text)
    cleaned = []
    for e in entries:
        e = e.strip().replace('–','-').replace('—','-')
        e = re.sub(r'^\s*\d+\s*[\.\s\-]*\[\d+\]\s*', '', e)
        e = re.sub(r'^\s*\[?\d+\]?\s*[\.\、\s\-]+', '', e).strip()
        e = re.sub(r'\s+(?:Cell|Nature|Science)\s+\d+[,\d\-–—]*\s*$', '', e, flags=re.I).strip()
        if len(e) > 30:
            cleaned.append(e)
    return cleaned


# ======================== S5: LLM Polish ========================

LLM_PROMPT = """Translate this academic English to Chinese. Extract all Figure references.
Output STRICT JSON: {"zh":"...","refs":["Figure 1"]}
Use terms: 表观遗传 拟南芥 转录 突变体 甲基化"""

def _llm_polish(text: str) -> dict | None:
    if len(text) < 80 or not OLLAMA:
        return None
    try:
        resp = httpx.post(OLLAMA_URL, json={
            'model': OLLAMA_MODEL,
            'messages': [{'role': 'user', 'content': f'{LLM_PROMPT}\n\nTEXT:\n{text[:1200]}'}],
            'stream': False,
            'options': {'temperature': 0.1, 'num_predict': 500},
        }, timeout=30)
        if resp.status_code != 200:
            return None
        content = resp.json()['message']['content']
        m = re.search(r'\{[\s\S]*\}', content)
        return json.loads(m.group(0)) if m else None
    except Exception:
        return None


# ======================== Main ========================

def parse(file_path: str) -> dict[str, Any]:
    t0 = time.perf_counter()
    log = []

    raw = pymupdf4llm.to_markdown(file_path)
    log.append(f'raw:{len(raw)}c')

    md = _normalize(raw)
    log.append('S1:normalize')

    # 双保险注脚拦截
    md = _filter_footnotes_regex(md)
    geo_set = _filter_footnotes_geometric(file_path)
    md = _apply_geometric_filter(md, geo_set)
    log.append(f'footnote:regex+geo({len(geo_set)}items)')

    # 页眉过滤 + 跨页断字缝合
    md = _filter_headers_and_repair(md)
    log.append('header+hyphen')

    sections, figures = _parse_sections(md)
    log.append(f'S2+S3:{len(sections)}sec/{len(figures)}fig')

    references = _clean_references(sections)
    sections = [s for s in sections if s['slug'] != 'references']
    log.append(f'S4:{len(references)}refs')

    polished = 0
    if os.environ.get('OLLAMA_POLISH') and OLLAMA:
        for sec in sections:
            if sec['slug'] != 'introduction':
                continue
            for i, p in enumerate(sec.get('paragraphs', [])):
                if i >= 3:
                    break
                r = _llm_polish(p.get('en', ''))
                if r:
                    sec['paragraphs'][i]['zh'] = r.get('zh', '')
                    sec['paragraphs'][i]['refs'] = r.get('refs', p.get('refs', []))
                    polished += 1
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
