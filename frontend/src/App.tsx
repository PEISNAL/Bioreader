import { useState } from 'react'

const API = 'http://127.0.0.1:18000'

export default function App() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    const res = await fetch(`${API}/api/parse`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_path: 'D:/YNU/AI_PROJ/test.pdf' }),
    })
    setData(await res.json())
    setLoading(false)
  }

  if (data) {
    const secs = data.sections || []
    const refs = data.references || []
    return (
      <div style={{ fontFamily: 'system-ui', maxWidth: 800, margin: '0 auto', padding: 24 }}>
        <button onClick={() => setData(null)}
          style={{ border: 'none', background: '#0071e3', color: '#fff', borderRadius: 20, padding: '8px 20px', cursor: 'pointer', marginBottom: 20 }}>
          ← 返回
        </button>
        <p style={{ color: '#86868b', fontSize: 13, marginBottom: 8 }}>
          {data.parse_time_ms}ms · {secs.length} sections · {refs.length} refs
        </p>

        {secs.map((s: any) => (
          <section key={s.slug} style={{ marginBottom: 28 }}>
            <h2 style={{ fontSize: 20, fontWeight: 700, borderBottom: '1px solid #e5e5e5', paddingBottom: 6, marginBottom: 14 }}>
              {s.title}
            </h2>
            {(s.paragraphs || []).map((p: any, i: number) => (
              <div key={i} style={{ marginBottom: 16 }}>
                <p style={{ fontSize: 15, lineHeight: 1.7, textAlign: 'justify', textIndent: '2em', whiteSpace: 'pre-line', color: '#333' }}>
                  {p.en}
                  {p.refs?.map((r: string) => (
                    <span key={r} style={{ fontSize: 12, background: '#e8f4fd', color: '#0071e3', padding: '2px 8px', borderRadius: 6, marginLeft: 6, fontWeight: 600 }}>📎 {r}</span>
                  ))}
                </p>
                {p.zh && (
                  <p style={{ fontSize: 14, lineHeight: 1.6, background: '#f0f9ff', borderLeft: '3px solid #0071e3', padding: '10px 14px', borderRadius: '0 8px 8px 0', marginTop: 6, color: '#1e40af' }}>
                    {p.zh}
                  </p>
                )}
              </div>
            ))}
          </section>
        ))}

        {refs.length > 0 && (
          <section>
            <h2 style={{ fontSize: 20, fontWeight: 700, borderBottom: '1px solid #e5e5e5', paddingBottom: 6, marginBottom: 14 }}>
              References ({refs.length})
            </h2>
            <ol style={{ fontSize: 13, lineHeight: 1.6, color: '#555', paddingLeft: 20 }}>
              {refs.map((r: string, i: number) => <li key={i} style={{ marginBottom: 4 }}>{r}</li>)}
            </ol>
          </section>
        )}
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', fontFamily: 'system-ui' }}>
      <div style={{ textAlign: 'center' }}>
        <h1 style={{ fontSize: '2rem', marginBottom: 8 }}>🧬 BioReader</h1>
        <p style={{ color: '#86868b', marginBottom: 24 }}>pymupdf4llm 视觉引擎 + Ollama 本地大模型</p>
        <button onClick={load} disabled={loading}
          style={{ border: 'none', borderRadius: 24, padding: '12px 36px', fontSize: 16, fontWeight: 600, background: loading ? '#999' : '#0071e3', color: '#fff', cursor: loading ? 'not-allowed' : 'pointer' }}>
          {loading ? '⏳ 解析中...' : '📖 打开 test.pdf'}
        </button>
      </div>
    </div>
  )
}
