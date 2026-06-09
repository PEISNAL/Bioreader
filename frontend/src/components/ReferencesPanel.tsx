/** ReferencesPanel — Clean placeholder for future use. */
export function ReferencesPanel({ references }: { references: string[] }): JSX.Element {
  return (
    <div className="refs-panel-v2">
      <h2 className="section-heading">References ({references.length})</h2>
      <ul className="refs-list-v2">
        {references.map((ref, idx) => (
          <li key={idx} className="refs-item-v2">
            <span className="refs-index">[{idx + 1}]</span>
            <span className="refs-text">{ref}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
