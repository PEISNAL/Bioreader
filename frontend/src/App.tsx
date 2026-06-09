import { useState, useEffect, useCallback, useRef, DragEvent } from 'react'

// All /api requests are proxied by Vite to http://127.0.0.1:18000
const API = ''

// ======================== Types ========================
interface Para { en: string; zh?: string; refs?: string[] }
interface Section { slug: string; title: string; paragraphs: Para[] }
interface Figure { id: string; caption: string; page?: number; image_path?: string }
interface ParseData { sections: Section[]; figures: Figure[]; references: string[]; parse_time_ms: number; filename?: string }
interface VocabEntry { word: string; context: string; translation: string; section: string; timestamp: string; phonetic: string; meanings: DictMeaning[] }
interface DictMeaning { pos: string; defs: string[]; examples: string[]; synonyms: string[] }
interface TranslateResult { text: string; translation: string; phonetic: string; source: string; meanings: DictMeaning[] }

// ======================== Selection Toolbar ========================
function SelectionToolbar({ x, y, text, context, onClose }: {
  x: number; y: number; text: string; context: string; onClose: () => void
}) {
  const [trl, setTrl] = useState<TranslateResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [toast, setToast] = useState('')

  const isLong = text.length > 80
  const toolbarWidth = Math.min(isLong ? 420 : 260, window.innerWidth - 40)

  const translate = async () => {
    setLoading(true)
    const res = await fetch(`${API}/api/translate`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, context }),
    })
    setTrl(await res.json())
    setLoading(false)
  }

  const addVocab = async () => {
    const section = document.querySelector('.section-heading')?.textContent || ''
    await fetch(`${API}/api/vocabulary`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        word: isLong ? text.slice(0, 80) : text,
        context_sentence: context,
        translation: trl?.translation || '',
        section_title: section,
        phonetic: trl?.phonetic || '',
        meanings: trl?.meanings || [],
      }),
    })
    setToast('✅ 已加入生词本')
    setTimeout(() => setToast(''), 2000)
  }

  return (
    <div style={{ position: 'fixed', left: Math.min(x, window.innerWidth - toolbarWidth - 20), top: Math.min(y + 12, window.innerHeight - 300), zIndex: 9999, background: '#fff', border: '1px solid #e2e8f0', borderRadius: 12, padding: 14, boxShadow: '0 8px 32px rgba(0,0,0,.12)', width: toolbarWidth, fontSize: 13, maxHeight: '80vh', display: 'flex', flexDirection: 'column' }}>
      <div style={{ marginBottom: 8, fontWeight: 600, color: '#1e293b', maxHeight: 48, overflow: 'hidden', lineHeight: 1.3 }}>
        {isLong ? text.slice(0, 80) + '…' : text}
        {isLong && <span style={{ fontSize: 10, color: '#94a3b8', marginLeft: 6 }}>({text.length} 字符)</span>}
      </div>
      {trl && (
        <div style={{ marginBottom: 8, padding: '8px 10px', background: '#f0f9ff', borderRadius: 8, color: '#1e40af', fontSize: 12, maxHeight: 260, overflowY: 'auto', lineHeight: 1.6 }}>
          {/* Phonetic */}
          {trl.phonetic && <div style={{ color: '#64748b', marginBottom: 4, fontSize: 11 }}>🔊 {trl.phonetic}</div>}

          {/* Rich dictionary display (for words) */}
          {trl.meanings && trl.meanings.length > 0 ? (
            trl.meanings.map((m, mi) => (
              <div key={mi} style={{ marginBottom: mi < trl.meanings.length - 1 ? 6 : 0 }}>
                {m.pos && (
                  <span style={{ display: 'inline-block', background: '#dbeafe', color: '#1e40af', borderRadius: 4, padding: '1px 6px', fontSize: 10, fontWeight: 600, marginBottom: 3, marginRight: 4 }}>
                    {m.pos}
                  </span>
                )}
                {m.synonyms.length > 0 && (
                  <span style={{ fontSize: 10, color: '#94a3b8' }}>syn: {m.synonyms.slice(0, 3).join(', ')}</span>
                )}
                {m.defs.map((d, di) => (
                  <div key={di} style={{ marginTop: 2, paddingLeft: 4 }}>
                    <span style={{ color: '#475569', fontSize: 11 }}>{di + 1}. {d}</span>
                  </div>
                ))}
                {m.examples.length > 0 && (
                  <div style={{ marginTop: 2, paddingLeft: 8, fontSize: 10, color: '#64748b', fontStyle: 'italic' }}>
                    {m.examples.slice(0, 2).map((ex, ei) => (
                      <div key={ei}>"{ex}"</div>
                    ))}
                  </div>
                )}
              </div>
            ))
          ) : (
            /* Simple translation display (for sentences) */
            <div>{trl.translation}</div>
          )}

          {/* Source label */}
          {trl.source && trl.source !== 'fallback' && (
            <div style={{ marginTop: 4, fontSize: 10, color: '#94a3b8' }}>
              {trl.source === 'dictionary' ? '📖 词典' : trl.source === 'mymemory' ? '🌐 在线翻译' : trl.source === 'ollama' ? '🤖 AI' : trl.source}
            </div>
          )}
        </div>
      )}
      <div style={{ display: 'flex', gap: 8 }}>
        <button onClick={translate} disabled={loading} style={btnStyle}>{loading ? '⏳' : '🌐 翻译'}</button>
        <button onClick={addVocab} style={btnStyle}>📖 生词本</button>
      </div>
      {toast && <div style={{ marginTop: 6, fontSize: 11, color: '#16a34a' }}>{toast}</div>}
    </div>
  )
}

const btnStyle: React.CSSProperties = {
  flex: 1, border: '1px solid #e2e8f0', borderRadius: 8, padding: '6px 0', fontSize: 12, cursor: 'pointer', background: '#f8fafc',
}

// ======================== Figure Panel ========================
function FigurePanel({ figures, activeRef, onFigureClick, panelRef }: {
  figures: Figure[]; activeRef: string | null; onFigureClick: (f: Figure) => void
  panelRef: React.RefObject<HTMLDivElement>
}) {
  const imgCount = figures.filter(f => f.image_path).length

  return (
    <aside ref={panelRef} style={{ flex: '1 1 300px', maxWidth: 420, background: '#fafbfc', borderLeft: '1px solid #e2e8f0', overflow: 'auto', padding: 14 }}>
      <div style={{ fontWeight: 700, fontSize: 11, color: '#64748b', textTransform: 'uppercase', letterSpacing: '.5px', marginBottom: 12, position: 'sticky', top: 0, background: '#fafbfc', padding: '4px 0', zIndex: 1 }}>
        📊 Figures ({imgCount}/{figures.length})
      </div>
      {figures.map(f => {
        const active = activeRef === f.id
        const imgSrc = f.image_path || null

        return (
          <div key={f.id} id={`fig-${f.id}`} style={{
            background: '#fff',
            border: active ? '3px solid #2563eb' : '1px solid #e2e8f0',
            borderRadius: 12, padding: 14, marginBottom: 14,
            opacity: active ? 1 : .7, transition: 'all .25s ease',
            boxShadow: active
              ? '0 0 0 4px rgba(37,99,235,.15), 0 8px 24px rgba(37,99,235,.1)'
              : '0 1px 3px rgba(0,0,0,.04)',
            animation: active ? 'pulse-border 1.5s ease-in-out' : 'none',
            cursor: 'pointer',
          }}
            onClick={() => onFigureClick(f)}
          >
            <div style={{ fontWeight: 700, fontSize: 13, color: '#2563eb', marginBottom: 6, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span>{f.id}</span>
              {f.page && <span style={{ fontSize: 10, color: '#94a3b8' }}>p.{f.page}</span>}
            </div>

            {imgSrc ? (
              <img src={imgSrc} alt={f.caption || f.id}
                style={{ width: '100%', borderRadius: 6, background: '#f1f5f9', minHeight: 80, display: 'block' }} />
            ) : (
              <div style={{ width: '100%', minHeight: 60, background: '#f1f5f9', borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <span style={{ color: '#94a3b8', fontSize: 12 }}>No image</span>
              </div>
            )}

            <div style={{ fontSize: 11, color: '#64748b', marginTop: 8, lineHeight: 1.4 }}>
              {f.caption ? f.caption.slice(0, 180) : ''}
            </div>
          </div>
        )
      })}
      {figures.length === 0 && (
        <div style={{ textAlign: 'center', color: '#94a3b8', marginTop: 40, fontSize: 12 }}>No figures detected</div>
      )}
      <style>{`@keyframes pulse-border { 0%,100%{box-shadow:0 0 0 4px rgba(37,99,235,.15)} 50%{box-shadow:0 0 0 10px rgba(37,99,235,.05)} }`}</style>
    </aside>
  )
}


// ======================== Figure Enlarged Modal ========================
function FigureModal({ figure, onClose }: { figure: Figure; onClose: () => void }) {
  const imgSrc = figure.image_path || null
  return (
    <div onClick={onClose} style={{
      position: 'fixed', inset: 0, zIndex: 10000, background: 'rgba(0,0,0,.75)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 40, cursor: 'pointer',
    }}>
      <div onClick={e => e.stopPropagation()} style={{
        maxWidth: '90vw', maxHeight: '90vh', background: '#fff',
        borderRadius: 16, overflow: 'hidden', boxShadow: '0 20px 60px rgba(0,0,0,.3)',
      }}>
        <div style={{ padding: '12px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #e2e8f0' }}>
          <span style={{ fontWeight: 700, fontSize: 15, color: '#1e293b' }}>{figure.id}</span>
          <button onClick={onClose} style={{ border: 'none', background: 'none', fontSize: 22, cursor: 'pointer', color: '#94a3b8' }}>✕</button>
        </div>
        {imgSrc ? (
          <img src={imgSrc} style={{ maxWidth: '85vw', maxHeight: '75vh', display: 'block' }} alt={figure.caption} />
        ) : (
          <div style={{ padding: 60, textAlign: 'center', color: '#94a3b8' }}>No image available</div>
        )}
        <div style={{ padding: '10px 20px', fontSize: 12, color: '#64748b', borderTop: '1px solid #e2e8f0', lineHeight: 1.5 }}>
          {figure.caption}
        </div>
      </div>
    </div>
  )
}

// ======================== Vocab Full Page ========================
function VocabPage({ onBack }: { onBack: () => void }) {
  const [words, setWords] = useState<VocabEntry[]>([])
  const [expanded, setExpanded] = useState<string | null>(null)

  useEffect(() => { fetch(`/api/vocabulary`).then(r => r.json()).then(d => setWords(d.words || [])) }, [])

  const del = async (word: string) => {
    await fetch(`/api/vocabulary/${encodeURIComponent(word)}`, { method: 'DELETE' })
    setWords(w => w.filter(e => e.word !== word))
  }

  return (
    <div style={{ minHeight: '100vh', fontFamily: 'system-ui', background: '#f8fafc' }}>
      <header style={{ display: 'flex', alignItems: 'center', padding: '0 24px', height: 56, background: '#fff', borderBottom: '1px solid #e2e8f0', position: 'sticky', top: 0, zIndex: 100, gap: 16 }}>
        <button onClick={onBack} style={{ border: 'none', background: 'none', color: '#0071e3', cursor: 'pointer', fontSize: 14, fontWeight: 600 }}>← 返回阅读</button>
        <span style={{ fontWeight: 700, fontSize: 18 }}>📖 生词本</span>
        <span style={{ fontSize: 13, color: '#94a3b8' }}>{words.length} 个词汇</span>
      </header>
      <div style={{ maxWidth: 720, margin: '0 auto', padding: '24px 20px' }}>
        {words.length === 0 ? (
          <div style={{ textAlign: 'center', color: '#94a3b8', marginTop: 80, fontSize: 14 }}>
            <div style={{ fontSize: 48, marginBottom: 16 }}>📖</div>
            暂无生词<br/>在阅读中划词翻译后，点击"生词本"即可保存
          </div>
        ) : (
          words.map(w => (
            <div key={w.word} style={{ marginBottom: 12, background: '#fff', borderRadius: 12, padding: 18, border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,.04)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <span style={{ fontWeight: 700, fontSize: 17, color: '#1e293b' }}>{w.word}</span>
                  {w.phonetic && <span style={{ fontSize: 12, color: '#94a3b8', marginLeft: 10 }}>🔊 {w.phonetic}</span>}
                </div>
                <button onClick={() => del(w.word)} style={{ border: 'none', background: 'none', cursor: 'pointer', color: '#94a3b8', fontSize: 16 }}>🗑️</button>
              </div>
              {w.meanings && w.meanings.length > 0 && (
                <div style={{ marginTop: 8 }}>
                  {w.meanings.map((m, mi) => (
                    <div key={mi} style={{ marginBottom: 6 }}>
                      {m.pos && <span style={{ display: 'inline-block', background: '#dbeafe', color: '#1e40af', borderRadius: 4, padding: '1px 8px', fontSize: 11, fontWeight: 600, marginRight: 6 }}>{m.pos}</span>}
                      {m.synonyms && m.synonyms.length > 0 && <span style={{ fontSize: 11, color: '#94a3b8' }}>syn: {m.synonyms.slice(0, 4).join(', ')}</span>}
                      {m.defs && m.defs.slice(0, 4).map((d, di) => (
                        <div key={di} style={{ fontSize: 12, color: '#475569', paddingLeft: 6, lineHeight: 1.6, marginTop: 2 }}>{di + 1}. {d}</div>
                      ))}
                      {m.examples && m.examples.length > 0 && (
                        <div style={{ fontSize: 11, color: '#94a3b8', fontStyle: 'italic', paddingLeft: 12, marginTop: 2 }}>
                          e.g. "{m.examples[0]}"
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
              {w.translation && (!w.meanings || w.meanings.length === 0) && (
                <div style={{ fontSize: 14, color: '#2563eb', marginTop: 6 }}>{w.translation}</div>
              )}
              <div style={{ fontSize: 10, color: '#94a3b8', marginTop: 8, display: 'flex', gap: 12 }}>
                {w.section && <span>📑 {w.section}</span>}
                <span>{w.timestamp}</span>
              </div>
              {w.context && (
                <div onClick={() => setExpanded(expanded === w.word ? null : w.word)} style={{ marginTop: 6, fontSize: 11, color: '#94a3b8', cursor: 'pointer', fontStyle: 'italic', lineHeight: 1.4 }}>
                  {expanded === w.word ? w.context : '📝 ' + w.context.slice(0, 100) + '...'}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}

// ======================== Main App ========================
export default function App() {
  const [data, setData] = useState<ParseData | null>(null)
  const [loading, setLoading] = useState(false)
  const [filename, setFilename] = useState('')
  const [dragOver, setDragOver] = useState(false)
  const [view, setView] = useState<'home' | 'reader' | 'vocab'>('home')
  const [sel, setSel] = useState<{ text: string; x: number; y: number; context: string } | null>(null)
  const [activeRef, setActiveRef] = useState<string | null>(null)
  const [enlargedFigure, setEnlargedFigure] = useState<Figure | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const figurePanelRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Upload PDF
  const uploadPDF = async (file: File) => {
    setLoading(true)
    const fd = new FormData()
    fd.append('file', file)
    const res = await fetch(`${API}/api/upload`, { method: 'POST', body: fd })
    const result = await res.json()
    setFilename(result.filename || file.name)
    setData(result)
    setView('reader')
    setLoading(false)
  }

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) uploadPDF(file)
  }

  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files?.[0]
    if (file && file.name.toLowerCase().endsWith('.pdf')) uploadPDF(file)
  }

  // Selection handler — supports word → phrase → sentence → paragraph (up to 2000 chars)
  useEffect(() => {
    const onMouseUp = (e: MouseEvent) => {
      setTimeout(() => {
        const s = window.getSelection()
        if (!s || s.isCollapsed || !s.toString().trim()) { setSel(null); return }
        const text = s.toString().trim()
        if (text.length < 2 || text.length > 2000) { setSel(null); return }
        const node = s.anchorNode
        const para = node?.parentElement?.closest('p')
        const context = para?.textContent || text
        setSel({ text, x: e.clientX, y: e.clientY, context })
      }, 50)
    }
    document.addEventListener('mouseup', onMouseUp)
    return () => document.removeEventListener('mouseup', onMouseUp)
  }, [])

  // IntersectionObserver for figure tracking
  useEffect(() => {
    if (!data || !scrollRef.current) return
    const obs = new IntersectionObserver((entries) => {
      for (const e of entries) {
        if (e.isIntersecting) {
          const ref = (e.target as HTMLElement).dataset.ref
          if (ref) setActiveRef(ref)
        }
      }
    }, { root: scrollRef.current, rootMargin: '-15% 0px', threshold: 0.3 })
    const els = scrollRef.current.querySelectorAll('[data-ref]')
    els.forEach(el => obs.observe(el))
    return () => obs.disconnect()
  }, [data])

  // Click outside to close selection
  useEffect(() => {
    const onClick = () => { if (!window.getSelection()?.toString()) setSel(null) }
    document.addEventListener('click', onClick)
    return () => document.removeEventListener('click', onClick)
  }, [])

  // ---- Vocab Full Page ----
  if (view === 'vocab') {
    return <VocabPage onBack={() => setView('reader')} />
  }

  // ---- Splash (Upload) ----
  if (view === 'home') {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', fontFamily: 'system-ui', background: '#f5f5f7' }}>
        <div style={{ textAlign: 'center', maxWidth: 480 }}>
          <h1 style={{ fontSize: '2.2rem', marginBottom: 8 }}>🧬 BioReader</h1>
          <p style={{ color: '#86868b', marginBottom: 24 }}>pymupdf4llm 视觉引擎 · 划词翻译 · 生词本</p>

          {/* Drop zone */}
          <div
            onDragOver={e => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
            onClick={() => fileInputRef.current?.click()}
            style={{
              border: `2px dashed ${dragOver ? '#0071e3' : '#d1d5db'}`,
              borderRadius: 16,
              padding: '40px 24px',
              background: dragOver ? '#eff6ff' : '#fafafa',
              cursor: 'pointer',
              transition: 'all .2s',
              marginBottom: 16,
            }}
          >
            <div style={{ fontSize: 40, marginBottom: 12 }}>📄</div>
            <div style={{ fontWeight: 600, fontSize: 15, color: '#374151', marginBottom: 4 }}>
              {dragOver ? '松开以上传' : '拖拽 PDF 到此处'}
            </div>
            <div style={{ fontSize: 12, color: '#9ca3af' }}>或点击选择文件</div>
          </div>

          <input ref={fileInputRef} type="file" accept=".pdf" onChange={onFileChange} style={{ display: 'none' }} />

          {loading && (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10, color: '#0071e3', fontSize: 14 }}>
              <div style={{ width: 18, height: 18, border: '2px solid #e2e8f0', borderTopColor: '#0071e3', borderRadius: '50%', animation: 'spin .8s linear infinite' }} />
              ⏳ 解析中...
            </div>
          )}
        </div>
        <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
      </div>
    )
  }

  // ---- Reader ----
  if (!data) return null
  const secs = data.sections || []
  const figs = data.figures || []
  const refs = data.references || []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', fontFamily: 'system-ui' }}>
      {/* Topbar */}
      <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 20px', height: 48, background: 'rgba(255,255,255,.85)', backdropFilter: 'blur(20px)', borderBottom: '1px solid #e5e5e5', position: 'sticky', top: 0, zIndex: 100 }}>
        <button onClick={() => setView('home')} style={{ border: 'none', background: 'none', color: '#0071e3', cursor: 'pointer', fontSize: 13 }}>← 返回</button>
        <span style={{ fontWeight: 600, fontSize: 13, color: '#374151', maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={filename}>
          📄 {filename}
        </span>
        <div style={{ display: 'flex', gap: 10 }}>
          <button onClick={() => setView('vocab')} style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: '5px 14px', fontSize: 12, cursor: 'pointer', background: '#fff' }}>📖 生词本</button>
          <span style={{ fontSize: 11, color: '#86868b', alignSelf: 'center' }}>{data.parse_time_ms}ms</span>
        </div>
      </header>

      {/* Body */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* Left nav */}
        <nav style={{ width: 170, flexShrink: 0, background: '#f8fafc', borderRight: '1px solid #e2e8f0', overflow: 'auto', padding: '12px 8px' }}>
          {secs.map(s => (
            <button key={s.slug} onClick={() => document.getElementById(`sec-${s.slug}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
              style={{ display: 'block', width: '100%', padding: '7px 10px', border: 'none', background: 'none', textAlign: 'left', fontSize: 12, color: '#475569', cursor: 'pointer', borderRadius: 6, marginBottom: 1 }}>
              {s.title.length > 22 ? s.title.slice(0, 22) + '…' : s.title}
            </button>
          ))}
        </nav>

        {/* Center scroll */}
        <div ref={scrollRef} style={{ flex: '0 1 720px', overflow: 'auto', padding: '24px 32px' }}>
          {secs.map(s => (
            <section key={s.slug} id={`sec-${s.slug}`}>
              <h2 style={{ fontSize: 18, fontWeight: 700, borderBottom: '1px solid #e5e5e5', paddingBottom: 6, margin: '24px 0 12px' }}>{s.title}</h2>
              {s.paragraphs.map((p, i) => {
                const handleFigureRefClick = (figId: string) => {
                  setActiveRef(figId)
                  setTimeout(() => {
                    const figEl = document.getElementById(`fig-${figId}`)
                    if (figEl && figurePanelRef.current) {
                      figEl.scrollIntoView({ behavior: 'smooth', block: 'center' })
                    }
                  }, 100)
                }

                // Build figure ID set for inline detection
                const figIds = new Set(p.refs || [])

                return (
                <p key={i} {...(p.refs?.length ? { 'data-ref': p.refs[0] } : {})}
                  style={{ fontSize: 14, lineHeight: 1.7, textAlign: 'justify', textIndent: '1.8em', marginBottom: 14, whiteSpace: 'pre-line', color: '#333', borderLeft: p.refs?.length ? '3px solid #93c5fd' : 'none', paddingLeft: p.refs?.length ? 12 : 0 }}>
                  {/* Split text at Figure/Fig N and insert inline buttons */}
                  {p.en.split(/((?:Figure|Fig\.?)\s+\d+)/gi).map((part, j) => {
                    const m = part.match(/^(?:Figure|Fig\.?)\s+(\d+)$/i)
                    if (m) {
                      const figId = `Figure ${m[1]}`
                      if (figIds.has(figId)) {
                        return (
                          <span key={j} onClick={() => handleFigureRefClick(figId)}
                            style={{ fontSize: 11, background: '#eff6ff', color: '#2563eb', padding: '2px 8px', borderRadius: 5, cursor: 'pointer', fontWeight: 600, border: '1px solid #bfdbfe', display: 'inline', margin: '0 2px', whiteSpace: 'nowrap', transition: 'all .15s' }}
                            onMouseEnter={e => { (e.target as HTMLElement).style.background = '#2563eb'; (e.target as HTMLElement).style.color = '#fff' }}
                            onMouseLeave={e => { (e.target as HTMLElement).style.background = '#eff6ff'; (e.target as HTMLElement).style.color = '#2563eb' }}
                            title={`Click to view ${figId} in side panel`}>
                            📊 {figId}
                          </span>
                        )
                      }
                    }
                    return <span key={j}>{part}</span>
                  })}
                  {p.zh && <span style={{ display: 'block', marginTop: 6, padding: '8px 12px', background: '#f0f9ff', borderLeft: '3px solid #0071e3', borderRadius: '0 6px 6px 0', fontSize: 13, color: '#1e40af' }}>{p.zh}</span>}
                </p>
                )
              })}
            </section>
          ))}
          {refs.length > 0 && (
            <section>
              <h2 style={{ fontSize: 18, fontWeight: 700, borderBottom: '1px solid #e5e5e5', paddingBottom: 6, margin: '32px 0 16px' }}>📚 References ({refs.length})</h2>
              <ol style={{ fontSize: 12, lineHeight: 1.8, color: '#444', paddingLeft: 0, listStyle: 'none' }}>
                {refs.map((r, i) => (
                  <li key={i} style={{
                    marginBottom: 14, padding: '10px 14px',
                    background: i % 2 === 0 ? '#f8fafc' : '#fff',
                    borderRadius: 8, border: '1px solid #e2e8f0',
                    borderLeft: '3px solid #93c5fd',
                  }}>
                    <span style={{ fontWeight: 700, color: '#2563eb', marginRight: 10, fontSize: 12, fontFamily: 'monospace' }}>[{i + 1}]</span>
                    <span style={{ color: '#334155' }}>{r}</span>
                  </li>
                ))}
              </ol>
            </section>
          )}
        </div>

        {/* Right figure panel */}
        <FigurePanel figures={figs} activeRef={activeRef} onFigureClick={f => setEnlargedFigure(f)} panelRef={figurePanelRef} />
      </div>

      {/* Selection toolbar */}
      {sel && <SelectionToolbar {...sel} onClose={() => setSel(null)} />}

      {/* Figure enlarged modal */}
      {enlargedFigure && <FigureModal figure={enlargedFigure} onClose={() => setEnlargedFigure(null)} />}
    </div>
  )
}
