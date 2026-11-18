import { useEffect, useState } from 'react'
import { apiUrl } from '../lib/api.js'

function PublicReport({ reportId }) {
  const [report, setReport] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    fetch(apiUrl(`/api/analysis-reports/${encodeURIComponent(reportId)}`))
      .then(async (response) => {
        const data = await response.json()
        if (!response.ok) throw new Error(data.detail || 'The report is not available.')
        if (active) setReport(data)
      })
      .catch((requestError) => { if (active) setError(requestError.message) })
    return () => { active = false }
  }, [reportId])

  return (
    <main className="public-report-page">
      <header className="page-header"><h1>Verifix Advertisement Analysis Record</h1></header>
      {error && <p className="upload-error" role="alert">{error}</p>}
      {!report && !error && <p role="status">Loading the public report…</p>}
      {report && (
        <>
          <section className="evaluator-card">
            <p><strong>Verification ID:</strong> <code>{report.verification_id}</code></p>
            <p><strong>Created:</strong> {new Date(report.created_at).toLocaleString()}</p>
            <p><strong>Media:</strong> {report.media_type}</p>
            <p><strong>Analysis result:</strong> {report.overall_status}</p>
            {report.risk_summary && <p><strong>Risk signal:</strong> {report.risk_summary}</p>}
            <p className="tool-note">This QR identifies a saved analysis report. It does not prove that an advertisement claim is true or legally compliant.</p>
          </section>
          <section className="analysis-module-list public-report-modules">
            {report.modules.map((module) => (
              <article className="analysis-module-card" key={module.id}>
                <div className="analysis-module-heading"><h2>{module.label}</h2><span className={`analysis-status analysis-status-${String(module.status).toLowerCase().replaceAll('_', '-')}`}>{module.status.replaceAll('_', ' ')}</span></div>
                <p>{module.message}</p>
                {module.result && <details className="analysis-module-details"><summary>Details</summary><pre>{JSON.stringify(module.result, null, 2)}</pre></details>}
              </article>
            ))}
          </section>
          <section className="evaluator-card">
            <h2>Limitations</h2>
            <ul>{report.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
          </section>
        </>
      )}
      <a className="text-button" href="/">Return to BrandGuard</a>
    </main>
  )
}

export default PublicReport
