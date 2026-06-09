import { useRef, useEffect, useState } from 'react'
import { ReferencesPanel } from './ReferencesPanel'

interface ParseData {
  sections: Array<{
    slug: string; title: string
    paragraphs: Array<{ en?: string; zh?: string; refs?: string[] }>
  }>
  figures: Array<{ id: string; caption: string; page: number }>
  references: string[]
  parse_time_ms?: number
  llm_used?: boolean
}

export function ReaderView({ data }: { data: ParseData }): JSX.Element {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [visibleFigs, setVisibleFigs] = useState<Map<string, { targetY: number }>>(new Map())
  const sections = data.sections || []
  const figures = data.figures || []
  const references = data.references || []

  // IntersectionObserver for figure tracking
  useEffect(() => {
    const container = scrollRef.current
    if (!container) return

    const active = new Map<string, { targetY: number }>()
    const obs = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const refId = (entry.target as HTMLElement).dataset.ref
          if (!refId) continue
          if (entry.isIntersecting) {
            const rect = entry.target.getBoundingClientRect()
            const containerRect = container.getBoundingClientRect()
            active.set(refId, {
              targetY: rect.top - containerRect.top + container.scrollTop,
            })
          } else {
            active.delete(refId)
          }
        }
        setVisibleFigs(new Map(active))
      },
      { root: container, rootMargin: '-10% 0px -10% 0px', threshold: [0.3, 0.5] },
    )

    const els = container.querySelectorAll('[data-ref]')
    els.forEach((el) => obs.observe(el))
    return () => obs.disconnect()
  }, [sections])

  const scrollTo = (slug: string) => {
    document.getElementById(`sec-${slug}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <div className="reader-layout-v2">
      {/* Left nav */}
      <nav className="section-nav">
        <div className="section-nav__title">目录</div>
        {sections.map((sec) => (
          <button key={sec.slug} className="section-nav__link" onClick={() => scrollTo(sec.slug)}>
            {sec.title}
          </button>
        ))}
      </nav>

      {/* Center text */}
      <div className="reader-scroll" ref={scrollRef}>
        <div className="reader-toolbar">
          <span>{sections.length} sections · {figures.length} figures · {references.length} refs</span>
          <span>{data.llm_used ? '🤖 LLM polished' : '📐 Rule-based'}</span>
        </div>

        <div className="reader-content-v2">
          {sections.map((sec) => (
            <section key={sec.slug} id={`sec-${sec.slug}`}>
              <h2 className="section-heading">{sec.title}</h2>
              {(sec.paragraphs || []).map((p, pi) => {
                const text = p.en || ''
                const refs = p.refs || []
                return (
                  <p
                    key={pi}
                    className={`content-paragraph ${refs.length ? 'content-paragraph--has-figure' : ''}`}
                    {...(refs.length ? { 'data-ref': refs[0] } : {})}
                  >
                    {text}
                    {p.zh && <span className="zh-block">{p.zh}</span>}
                    {refs.length > 0 && (
                      <span className="inline-ref-tag">
                        {refs.map((r) => <span key={r} className="ref-chip">📎 {r}</span>)}
                      </span>
                    )}
                  </p>
                )
              })}
            </section>
          ))}

          {references.length > 0 && (
            <>
              <div className="end-of-text">—— 正文结束 · 参考文献 ——</div>
              <ReferencesPanel references={references} />
            </>
          )}
        </div>
      </div>

      {/* Right figure panel */}
      <aside className="figure-tracker">
        <div className="figure-tracker__header">
          📊 图文同步 <span className="figure-tracker__count">{visibleFigs.size}/{figures.length}</span>
        </div>
        <div className="figure-tracker__canvas">
          {figures.map((fig) => {
            const vf = visibleFigs.get(fig.id)
            const active = !!vf
            return (
              <div
                key={fig.id}
                className={`figure-card-v2 ${active ? 'figure-card-v2--active' : ''}`}
                style={{
                  opacity: active ? 1 : 0.2,
                  transform: active && vf ? `translateY(${vf.targetY}px)` : 'none',
                  transition: 'all 0.4s cubic-bezier(0.22, 0.61, 0.36, 1)',
                }}
              >
                <div className="figure-card-v2__id">{fig.id} <span style={{fontSize:'.65rem',color:'#94a3b8'}}>p{fig.page}</span></div>
                <div className="figure-card-v2__body">
                  <span className="figure-card-v2__icon">🖼️</span>
                </div>
                <div className="figure-card-v2__caption">{fig.caption.slice(0, 120)}</div>
              </div>
            )
          })}
        </div>
      </aside>
    </div>
  )
}
