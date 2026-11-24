import { useEffect, useState } from 'react'
import { apiRequest, apiUrl } from '../lib/api.js'

function PublicReport({ reportId, slowRequestCount = 0 }) {
  const [report, setReport] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    apiRequest(apiUrl(`/api/analysis-reports/${encodeURIComponent(reportId)}`), {}, {
      timeoutMs: 120_000,
      fallbackMessage: 'The report is not available.',
    })
      .then((data) => {
        if (active) setReport(data)
      })
      .catch((requestError) => { if (active) setError(requestError.message) })
    return () => { active = false }
  }, [reportId])

  return (
    <main className="public-report-page">
      <header className="page-header"><h1>Verifix Advertisement Analysis Record</h1></header>
      {slowRequestCount > 0 && (
        <p className="page-intro" role="status">
          Server may be waking up (first request can take up to 90 seconds).
        </p>
      )}
      {error && <p className="upload-error" role="alert">{error}</p>}
      {!report && !error && <p role="status">Loading the public report…</p>}
      {report && (
        <>
          <section className="evaluator-card">
            <p><strong>Verification ID:</strong> <code>{report.verification_id}</code></p>
            <p><strong>Created:</strong> {new Date(report.created_at).toLocaleString()}</p>
            <p><strong>Media:</strong> {report.media_type}</p>
            <p><strong>Revision:</strong> {report.revision_number || 1}{report.revision_of ? ` · Corrected version of ${report.revision_of}` : " · Original submission"}</p>
            {report.revision_of && <p><a href={`/#/verify/${encodeURIComponent(report.revision_of)}`}>View original advertisement report</a></p>}
            <p><strong>Analysis result:</strong> {report.overall_status}</p>
            {report.risk_summary && <p><strong>Risk signal:</strong> {report.risk_summary}</p>}
            <p className="tool-note">This QR identifies a saved analysis report. It does not prove that an advertisement claim is true or legally compliant.</p>
          </section>

          {report.poster_data_url && (
            <section className="evaluator-card">
              <h2>{report.revision_of ? 'Corrected advertisement' : 'Submitted advertisement'}</h2>
              <img src={report.poster_data_url} alt="Advertisement associated with this BrandGuard report" style={{ display: 'block', width: '100%', maxWidth: '720px', height: 'auto', margin: '16px auto', borderRadius: '12px' }} />
            </section>
          )}
          {report.improvement_report && (
            <section className="evaluator-card">
              <h2>{report.improvement_report.title}</h2>
              <p>{report.improvement_report.summary}</p>
              {report.improvement_report.risk_summary && <p><strong>Risk signal:</strong> {report.improvement_report.risk_summary}</p>}
              {report.improvement_report.sections?.map((section) => (
                <section key={section.title}>
                  <h3>{section.title}</h3>
                  {section.checks.map((check) => (
                    <article className="analysis-module-card" key={check.feature}>
                      <div className="analysis-module-heading"><strong>{check.feature}</strong><span className="analysis-status">{check.status}</span></div>
                      {check.message && <p>{check.message}</p>}
                      {check.findings?.length > 0 && <ul>{check.findings.map((finding, index) => <li key={index}>{finding}</li>)}</ul>}
                    </article>
                  ))}
                </section>
              ))}
              {report.improvement_report.action_plan?.length > 0 && <section><h3>Action plan</h3><ol>{report.improvement_report.action_plan.map((item, index) => <li key={index}><strong>{item.priority}: {item.action}</strong><p>{item.reason}</p><small>Source: {item.source}</small></li>)}</ol></section>}
              <p className="tool-note">{report.improvement_report.disclaimer}</p>
            </section>
          )}
\n          <section className="analysis-module-list public-report-modules">
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
