import { useRef, useState } from 'react'
import { apiRequest, apiUrl } from '../lib/api.js'

function VideoAnalysis({ onNavigate }) {
  const [file, setFile] = useState(null)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const requestInFlightRef = useRef(false)

  async function analyze() {
    if (requestInFlightRef.current) return
    if (!file) return setError('Choose a video advertisement first.')
    if (!file.type.startsWith('video/')) return setError('Choose a supported video file.')
    if (file.size > 200 * 1024 * 1024) return setError('Video size must be below 200 MB.')

    requestInFlightRef.current = true
    setLoading(true)
    setError('')

    try {
      const body = new FormData()
      body.append('file', file)

      const data = await apiRequest(apiUrl('/api/analyze-video'), {
        method: 'POST',
        body,
      }, {
        timeoutMs: 120_000,
        fallbackMessage: 'Video analysis failed.',
      })

      setResult(data)
    } catch (err) {
      setError(err.message || 'Video analysis failed.')
    } finally {
      requestInFlightRef.current = false
      setLoading(false)
    }
  }

  const triage = result?.media_forensics?.manipulation_triage
  const signals = triage?.observable_signals
  const audioForensics = result?.media_forensics?.audio

  return <>
    <header className="page-header">
      <button className="back-button" onClick={() => onNavigate('dashboard')}>← Back</button>
      <h1>Full Video Advertisement Analysis</h1>
    </header>

    <p className="page-intro">
      Samples the complete video timeline, runs OCR on frames, extracts claim/disclaimer findings with timestamps, and reports audio availability honestly.
    </p>

    <section className="evaluator-card round3-form">
      <label className="upload-area">
        <span className="upload-title">Choose a video advertisement</span>
        <span className="upload-hint">MP4, MOV, WebM · maximum 200 MB</span>
        <input
          type="file"
          accept="video/*"
          onChange={(e) => {
            setFile(e.target.files[0] || null)
            setResult(null)
            setError('')
          }}
        />
      </label>

      {file && <p className="upload-file-name">Selected: <strong>{file.name}</strong></p>}

      <button className="primary-button" onClick={analyze} disabled={!file || loading}>
        {loading ? 'Analyzing timeline…' : 'Analyze complete video'}
      </button>
    </section>

    {error && <p className="upload-error" role="alert">{error}</p>}

    {result && <>
      <section className="tool-result video-results">
        <div className="result-summary">
          <strong>{result.status}</strong>
          <span>{result.duration_seconds}s · {result.frames_analyzed} frames · Audio: {result.audio.status}</span>
        </div>

        <p>{result.audio.explanation}</p>

        {result.findings.length ? result.findings.map((item, i) => (
          <article className="claim-card" key={`${item.timestamp_seconds}-${i}`}>
            <strong>{item.timestamp_label} · {item.type}</strong>
            <p>{item.text}</p>
            <small>{item.explanation}</small>
          </article>
        )) : (
          <p className="tool-note">
            No claim or disclaimer text was detected in sampled frames. This is not proof that the video is compliant.
          </p>
        )}
      </section>

      <section className="tool-result video-results">
        <h2>Multimodal Manipulation Triage</h2>
        <p className="tool-note">
          Observable forensic signals are summarized below for human review. They do not prove manipulation or authenticity.
        </p>

        {triage && signals ? <>
          <div className="result-summary">
            <strong>{triage.status || 'PARTIAL'}</strong>
            <span>Human review required</span>
          </div>

          <article className="claim-card">
            <strong>Visual analysis signals</strong>
            <p>Frames sampled: {signals.frames_sampled ?? 'Not available'}</p>
            <p>Heuristic findings: {signals.heuristic_finding_count ?? 'Not available'}</p>
            <p>Face-like regions across samples: {signals.face_like_regions_across_samples ?? 'Not available'}</p>
            <p>Repeated sampled frames: {signals.repeated_sampled_frames ?? 'Not available'}</p>
            <p>Large visual changes: {signals.large_visual_changes ?? 'Not available'}</p>
          </article>

          <article className="claim-card">
            <strong>Audio stream inspection</strong>
            <p>Status: {signals.audio_stream_status ?? audioForensics?.status ?? 'Not available'}</p>
            <p>Audio stream present: {signals.audio_stream_present == null ? 'Not available' : signals.audio_stream_present ? 'Yes' : 'No'}</p>
            {audioForensics?.codec && <p>Audio codec: {audioForensics.codec}</p>}
          </article>

          <article className="claim-card">
            <strong>AI detection capabilities</strong>
            <p>AI deepfake detection: {triage.ai_deepfake_detection || 'NOT_CONFIGURED'}</p>
            <p>Voice-clone detection: {triage.voice_clone_detection || 'NOT_CONFIGURED'}</p>
            <p>Verdict: Not available</p>
          </article>

          <p className="tool-note">
            {triage.interpretation || 'These signals are not a deepfake verdict. Manual verification is required.'}
          </p>
        </> : (
          <p className="tool-note">
            Forensic triage data was not returned by the server. Existing video analysis results are still available above.
          </p>
        )}
      </section>
    </>}
  </>
}

export default VideoAnalysis
