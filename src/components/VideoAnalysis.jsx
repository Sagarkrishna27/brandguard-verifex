import { useState } from 'react'
import { apiUrl } from '../lib/api.js'

function VideoAnalysis({ onNavigate }) {
  const [file, setFile] = useState(null); const [result, setResult] = useState(null); const [error, setError] = useState(''); const [loading, setLoading] = useState(false)
  async function analyze() {
    if (!file) return setError('Choose a video advertisement first.')
    setLoading(true); setError(''); setResult(null)
    try { const body = new FormData(); body.append('file', file); const response = await fetch(apiUrl('/api/analyze-video'), { method: 'POST', body }); const data = await response.json(); if (!response.ok) throw new Error(data.detail || 'Video analysis failed.'); setResult(data) } catch (err) { setError(err.message) } finally { setLoading(false) }
  }
  return <>
    <header className="page-header"><button className="back-button" onClick={() => onNavigate('dashboard')}>← Back</button><h1>Full Video Advertisement Analysis</h1></header>
    <p className="page-intro">Samples the complete video timeline, runs OCR on frames, extracts claim/disclaimer findings with timestamps, and reports audio availability honestly.</p>
    <section className="evaluator-card round3-form"><label className="upload-area"><span className="upload-title">Choose a video advertisement</span><span className="upload-hint">MP4, MOV, WebM · maximum 200 MB</span><input type="file" accept="video/*" onChange={(e) => { setFile(e.target.files[0]); setResult(null); setError('') }} /></label>{file && <p className="upload-file-name">Selected: <strong>{file.name}</strong></p>}<button className="primary-button" onClick={analyze} disabled={loading}>{loading ? 'Analyzing timeline…' : 'Analyze complete video'}</button></section>
    {error && <p className="upload-error" role="alert">{error}</p>}
    {result && <section className="tool-result video-results"><div className="result-summary"><strong>{result.status}</strong><span>{result.duration_seconds}s · {result.frames_analyzed} frames · Audio: {result.audio.status}</span></div><p>{result.audio.explanation}</p>{result.findings.length ? result.findings.map((item, i) => <article className="claim-card" key={`${item.timestamp_seconds}-${i}`}><strong>{item.timestamp_label} · {item.type}</strong><p>{item.text}</p><small>{item.explanation}</small></article>) : <p className="tool-note">No claim or disclaimer text was detected in sampled frames. This is not proof that the video is compliant.</p>}</section>}
  </>
}

export default VideoAnalysis
