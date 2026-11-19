import { useRef, useState } from 'react'
import { apiRequest, apiUrl } from '../lib/api.js'

const API_URL = apiUrl('/api/ocr')
const CLAIMS_URL = apiUrl('/api/analyze-claims')

const ACCEPTED_TYPES = '.png,.jpg,.jpeg,image/png,image/jpeg'

function getDefaultOcrLanguage() {
  try {
    const settings = JSON.parse(localStorage.getItem('brandguard-settings') || '{}')
    return typeof settings.defaultLanguage === 'string' && settings.defaultLanguage
      ? [settings.defaultLanguage]
      : ['eng']
  } catch {
    return ['eng']
  }
}

const LANGUAGE_OPTIONS = [
  { value: 'eng', label: 'English' },
  { value: 'kan', label: 'Kannada' },
  { value: 'hin', label: 'Hindi' },
  { value: 'tam', label: 'Tamil' },
  { value: 'tel', label: 'Telugu' },
  { value: 'mal', label: 'Malayalam' },
  { value: 'ben', label: 'Bengali' },
  { value: 'guj', label: 'Gujarati' },
  { value: 'mar', label: 'Marathi' },
  { value: 'pan', label: 'Punjabi' },
  { value: 'ori', label: 'Odia' },
  { value: 'asm', label: 'Assamese' },
  { value: 'urd', label: 'Urdu' },
  { value: 'san', label: 'Sanskrit' },
]

function confidenceBand(value) {
  const confidence = Number(value) || 0
  if (confidence >= 75) return { label: 'High confidence', className: 'confidence-high' }
  if (confidence >= 45) return { label: 'Review recommended', className: 'confidence-medium' }
  if (confidence > 0) return { label: 'Low confidence', className: 'confidence-low' }
  return { label: 'Uncertain', className: 'confidence-unknown' }
}

function regionTitle(region) {
  return region.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function getRegionLines(data) {
  if (Array.isArray(data.line_groups) && data.line_groups.length > 0) {
    return data.line_groups
  }

  return (data.lines || data.text?.split('\n') || [])
    .filter(Boolean)
    .map((text) => ({ text }))
}

function RegionAnalysis({ result }) {
  return (
    <section className="ocr-region-analysis" aria-labelledby="ocr-region-heading">
      <h3 id="ocr-region-heading">OCR Region Analysis</h3>
      <p className="ocr-region-intro">
        Regional OCR is supporting evidence. Lines are grouped from the
        engine&apos;s word coordinates and hierarchy; disagreements with the
        primary OCR remain visible for human verification.
      </p>

      <div className="ocr-region-list">
        {Object.entries(result.region_ocr || {}).map(([region, data]) => {
          const band = confidenceBand(data.average_confidence)
          const lines = getRegionLines(data)

          return (
            <article className="ocr-region-card" key={region}>
              <div className="ocr-region-heading">
                <div>
                  <span className="ocr-region-kicker">OCR REGION</span>
                  <h4>{regionTitle(region)}</h4>
                </div>
                <span className={`confidence-badge ${band.className}`}>
                  {band.label} · {data.average_confidence}%
                </span>
              </div>

              <div className="ocr-region-meta">
                <span>Method: regional Tesseract</span>
                <span>PSM: {data.best_psm_mode}</span>
                <span>{data.word_count || 0} words grouped</span>
              </div>

              {Number(data.average_confidence) < 45 && (
                <p className="ocr-confidence-warning" role="status">
                  Low-confidence reading. Review the image and raw OCR before
                  relying on this region.
                </p>
              )}

              <div className="ocr-line-list" aria-label={`${regionTitle(region)} grouped lines`}>
                {lines.length > 0 ? lines.map((line, index) => (
                  <div className="ocr-line-box" key={`${region}-${index}`}>
                    <span>{line.text || 'Uncertain text'}</span>
                    {line.confidence != null && (
                      <small>{Number(line.confidence).toFixed(1)}%</small>
                    )}
                  </div>
                )) : (
                  <div className="ocr-line-box ocr-line-empty">No text detected.</div>
                )}
              </div>

              <details className="ocr-raw-details">
                <summary>Show raw OCR evidence and bounding boxes</summary>
                <pre>{data.raw_text || data.text || 'No raw text detected.'}</pre>
                {Array.isArray(data.words) && data.words.length > 0 && (
                  <ul className="ocr-box-list">
                    {data.words.map((word, index) => (
                      <li key={`${region}-word-${index}`}>
                        <code>{word.text}</code> · x {Math.round(word.x)}, y {Math.round(word.y)}, w {Math.round(word.width)}, h {Math.round(word.height)} · {Number(word.confidence).toFixed(1)}%
                      </li>
                    ))}
                  </ul>
                )}
              </details>
            </article>
          )
        })}
      </div>
    </section>
  )
}

function PosterEvaluator({ onNavigate }) {
  const [selectedImage, setSelectedImage] = useState(null)
  const [selectedFile, setSelectedFile] = useState(null)
  const [fileName, setFileName] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [selectedLanguages, setSelectedLanguages] = useState(getDefaultOcrLanguage)
  const [claimResult, setClaimResult] = useState(null)
  const [claimLoading, setClaimLoading] = useState(false)
  const [claimError, setClaimError] = useState('')
  const [riskAlert, setRiskAlert] = useState(null)

  const fileInputRef = useRef(null)
  const requestInFlightRef = useRef(false)
  const claimsRequestInFlightRef = useRef(false)

  const handleFileChange = (event) => {
    const file = event.target.files[0]
    setError('')
    setResult(null)
    setClaimResult(null)
    setClaimError('')
    setRiskAlert(null)

    if (!file) return

    if (!['image/png', 'image/jpeg'].includes(file.type)) {
      setError('Please choose a PNG, JPG or JPEG image.')
      return
    }

    if (file.size > 15 * 1024 * 1024) {
      setError('Image size must be below 15 MB.')
      return
    }

    if (selectedImage) {
      URL.revokeObjectURL(selectedImage)
    }

    setSelectedImage(URL.createObjectURL(file))
    setSelectedFile(file)
    setFileName(file.name)
    setClaimResult(null)
  }

  const handleLanguageChange = (event) => {
    const { checked, value } = event.target
    setSelectedLanguages((languages) => (
      checked
        ? [...languages, value]
        : languages.filter((language) => language !== value)
    ))
  }

  const handleAnalyze = async () => {
    if (requestInFlightRef.current) return

    if (!selectedFile) {
      setError('Please upload a poster first.')
      return
    }

    if (selectedLanguages.length === 0) {
      setError('Please select at least one language.')
      return
    }

    requestInFlightRef.current = true
    setLoading(true)
    setError('')

    try {
      const formData = new FormData()
      formData.append('file', selectedFile)
      formData.append('languages', selectedLanguages.join('+'))

      const data = await apiRequest(API_URL, {
        method: 'POST',
        body: formData,
      }, {
        timeoutMs: 120_000,
        fallbackMessage: 'OCR analysis failed. Please try again.',
      })

      setResult(data)
      setClaimResult(null)
      setClaimError('')
      setRiskAlert(null)
    } catch (err) {
      setError(err.message || 'Cannot connect to BrandGuard backend.')
    } finally {
      requestInFlightRef.current = false
      setLoading(false)
    }
  }

  const handleClaimAnalysis = async () => {
    if (claimsRequestInFlightRef.current) return

    const text = result?.original_extracted_text?.trim()
    if (!text) {
      setClaimError('Run OCR and confirm the extracted text before analyzing claims.')
      return
    }

    claimsRequestInFlightRef.current = true
    setClaimLoading(true)
    setClaimError('')

    try {
      const data = await apiRequest(CLAIMS_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      }, {
        timeoutMs: 30_000,
        fallbackMessage: 'Claim analysis failed. Please try again.',
      })
      setClaimResult(data)
    } catch (err) {
      setClaimError(err.message || 'Claim analysis failed.')
    } finally {
      claimsRequestInFlightRef.current = false
      setClaimLoading(false)
    }
  }

  const handleRemove = () => {
    if (selectedImage) {
      URL.revokeObjectURL(selectedImage)
    }

    setSelectedImage(null)
    setSelectedFile(null)
    setFileName('')
    setResult(null)
    setClaimResult(null)
    setClaimError('')
    setRiskAlert(null)
    setError('')

    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  return (
    <>
      <header className="page-header">
        <button
          className="back-button"
          onClick={() => onNavigate('dashboard')}
        >
          ← Back to Dashboard
        </button>

        <h1>Evaluate Poster</h1>
      </header>

      <p className="page-intro">
        Upload an advertisement to extract its text and inspect important
        advertising values using BrandGuard multilingual OCR.
        Human verification is required for every final decision.
      </p>

      <div className="evaluator-layout">

        {/* UPLOAD */}
        <section className="evaluator-card" aria-label="Poster upload">
          <h2>1. Upload a poster image</h2>

          <label className="upload-area" htmlFor="posterUpload">
            <span className="upload-icon" aria-hidden="true">⬆</span>
            <span className="upload-title">Choose a poster image</span>
            <span className="upload-hint">
              PNG, JPG or JPEG · Maximum 15 MB
            </span>

            <input
              id="posterUpload"
              ref={fileInputRef}
              type="file"
              accept={ACCEPTED_TYPES}
              onChange={handleFileChange}
            />
          </label>

          {fileName && (
            <p className="upload-file-name">
              Selected: <strong>{fileName}</strong>
            </p>
          )}

          {error && (
            <p className="upload-error" role="alert">
              {error}
            </p>
          )}

          <div style={{ marginTop: '20px' }}>
            <h3>Select OCR languages</h3>

            <p style={{ fontSize: '13px', color: '#777' }}>
              Select every language that appears in your poster.
            </p>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(125px, 1fr))',
                gap: '10px',
                marginTop: '12px',
              }}
            >
              {LANGUAGE_OPTIONS.map((language) => (
                <label
                  key={language.value}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '7px',
                    fontSize: '13px',
                    cursor: 'pointer',
                  }}
                >
                  <input
                    type="checkbox"
                    value={language.value}
                    checked={selectedLanguages.includes(language.value)}
                    onChange={handleLanguageChange}
                  />
                  {language.label}
                </label>
              ))}
            </div>
          </div>

          <button
            className="primary-button"
            onClick={handleAnalyze}
            disabled={!selectedFile || loading}
            style={{ marginTop: '20px', width: '100%' }}
          >
            {loading ? 'Analyzing poster...' : 'Analyze Poster'}
          </button>

          {selectedFile && (
            <button
              className="secondary-button"
              onClick={handleRemove}
              disabled={loading}
              style={{ marginTop: '10px', width: '100%' }}
            >
              Remove Poster
            </button>
          )}
        </section>

        {/* PREVIEW */}
        <section className="evaluator-card" aria-label="Poster preview">
          <h2>2. Preview</h2>

          {selectedImage ? (
            <img
              className="evaluator-preview"
              src={selectedImage}
              alt={`Poster preview: ${fileName}`}
            />
          ) : (
            <div className="preview-placeholder">
              <p>No image selected yet.</p>
              <p>Your uploaded poster will appear here.</p>
            </div>
          )}
        </section>
      </div>

      {/* LOADING */}
      {loading && (
        <section className="evaluator-card" style={{ marginTop: '20px' }}>
          <h2>⏳ Analyzing advertisement</h2>
          <p>
            BrandGuard is processing the image using Tesseract OCR.
            Please wait.
          </p>
        </section>
      )}

      {/* OCR RESULTS */}
      {result && (
        <section
          className="evaluator-card"
          style={{ marginTop: '20px' }}
        >
          <h2>3. OCR Analysis Results</h2>

          <p style={{ color: 'green', fontWeight: 'bold' }}>
            ✓ {result.status}
          </p>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
              gap: '12px',
              margin: '20px 0',
            }}
          >
            <div>
              <strong>Version</strong>
              <p>{result.version}</p>
            </div>

            <div>
              <strong>OCR Confidence</strong>
              <p>{result.ocr_confidence}%</p>
            </div>

            <div>
              <strong>OCR Passes</strong>
              <p>{result.total_ocr_passes}</p>
            </div>

            <div>
              <strong>Best OCR Method</strong>
              <p>{result.best_ocr_pass}</p>
            </div>
          </div>

          <h3>Selected Languages</h3>
          <p>
            {result.selected_languages?.language_names?.join(', ')}
          </p>

          <hr />

          <h3>Extracted Advertisement Text</h3>

          <pre
            style={{
              whiteSpace: 'pre-wrap',
              overflowWrap: 'anywhere',
              background: '#f5f6fa',
              padding: '15px',
              borderRadius: '8px',
              fontFamily: 'inherit',
              fontSize: '14px',
            }}
          >
            {result.original_extracted_text || 'No text detected.'}
          </pre>

          <hr />

          <h3>Critical Values Detected</h3>

          {Object.entries(result.primary_critical_values || {}).map(
            ([category, values]) => (
              <div key={category} style={{ marginBottom: '12px' }}>
                <strong>
                  {category.replaceAll('_', ' ').toUpperCase()}
                </strong>
                <p>
                  {values.length > 0
                    ? values.join(', ')
                    : 'No values detected'}
                </p>
              </div>
            )
          )}

          <hr />

          <RegionAnalysis result={result} />

          <div className="legacy-ocr-output">
            <h3>OCR Region Analysis</h3>

          {Object.entries(result.region_ocr || {}).map(
            ([region, data]) => (
              <div key={region} style={{ marginBottom: '18px' }}>
                <strong>
                  {region.replaceAll('_', ' ').toUpperCase()}
                </strong>

                <pre
                  style={{
                    whiteSpace: 'pre-wrap',
                    overflowWrap: 'anywhere',
                    background: '#f5f6fa',
                    padding: '12px',
                    borderRadius: '8px',
                    fontFamily: 'inherit',
                    fontSize: '13px',
                  }}
                >
                  {data.text || 'No text detected'}
                </pre>

                <small>
                  Confidence: {data.average_confidence}%
                  {' · '}
                  PSM: {data.best_psm_mode}
                </small>
              </div>
            )
          )}

          </div>

          <hr />

          <h3>Critical Value Review</h3>

          {result.critical_value_review?.has_conflicts ? (
            <p style={{ color: '#b45309' }}>
              ⚠ Conflicting readings detected. Human verification required.
            </p>
          ) : (
            <p>No conflicting readings detected across OCR passes.</p>
          )}

          {result.critical_value_review?.uncorroborated_values?.length > 0 && (
            <>
              <strong>Values needing additional verification:</strong>
              <ul>
                {result.critical_value_review.uncorroborated_values.map(
                  (item, index) => (
                    <li key={index}>
                      {item.category}: {item.value}
                    </li>
                  )
                )}
              </ul>
            </>
          )}

          <hr />

          {/* ---- REAL-TIME RISK ALERT (feature 10) ---- */}
          {riskAlert && (
            <>
              <h3>Real-Time Risk Alert</h3>

              <div
                style={{
                  background:
                    riskAlert.alert_level === 'CRITICAL_ALERT' ? '#fdecea'
                    : riskAlert.alert_level === 'WARNING' ? '#fff4e0'
                    : riskAlert.alert_level === 'MINOR_NOTICES' ? '#fffbe6'
                    : '#e9f7ef',
                  border: '1px solid #e5eaf2',
                  borderRadius: '10px',
                  padding: '14px',
                }}
              >
                <p style={{ margin: '0 0 6px', fontWeight: 700 }}>
                  {riskAlert.alert_level.replaceAll('_', ' ')} · Score {riskAlert.risk_score}/100
                </p>
                {riskAlert.reasons.length === 0 ? (
                  <p style={{ margin: 0 }}>No review flags were raised for this poster.</p>
                ) : (
                  <ul style={{ margin: 0, paddingLeft: '18px' }}>
                    {riskAlert.reasons.map((reason, index) => (
                      <li key={index}>{reason}</li>
                    ))}
                  </ul>
                )}
                <p className="tool-note" style={{ marginTop: '8px' }}>{riskAlert.note}</p>
              </div>

              <hr />
            </>
          )}

          {/* ---- CLAIM ANALYSIS (from /api/analyze-claims) ---- */}
          <h3>Intelligent Claim Analysis</h3>
          <button
            className="secondary-button"
            onClick={handleClaimAnalysis}
            disabled={claimLoading || !result.original_extracted_text?.trim()}
          >
            {claimLoading ? 'Analyzing claims…' : 'Analyze extracted claims'}
          </button>
          {claimError && <p className="upload-error" role="alert">{claimError}</p>}

          {claimResult === null ? null : claimResult.error ? (
            <p className="upload-error" role="alert">
              {claimResult.error}
            </p>
          ) : (
            <>
              <p>
                {claimResult.total_claims === 0
                  ? 'No potential advertising claims were detected in the extracted text. This does not confirm the advertisement is compliant — human review is still required.'
                  : `${claimResult.total_claims} potential advertising claim${claimResult.total_claims === 1 ? '' : 's'} detected. Each one needs supporting evidence before approval.`}
              </p>

              {claimResult.claims?.map((claim, index) => (
                <div
                  key={index}
                  style={{
                    border: '1px solid #e5eaf2',
                    borderLeft: `5px solid ${
                      claim.risk_level === 'HIGH' ? '#dc3545'
                      : claim.risk_level === 'MEDIUM' ? '#e59b22'
                      : '#e59b22'
                    }`,
                    borderRadius: '8px',
                    padding: '14px',
                    marginBottom: '12px',
                    background: '#fbfcfe',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      gap: '8px',
                      flexWrap: 'wrap',
                      alignItems: 'center',
                      marginBottom: '8px',
                    }}
                  >
                    <strong>{claim.category.replaceAll('_', ' ')}</strong>
                    <span
                      style={{
                        background:
                          claim.risk_level === 'HIGH' ? '#fdecea'
                          : '#fff4e0',
                        color:
                          claim.risk_level === 'HIGH' ? '#b02a37'
                          : '#8a6100',
                        borderRadius: '999px',
                        padding: '2px 10px',
                        fontSize: '12px',
                        fontWeight: 600,
                      }}
                    >
                      {claim.risk_level === 'REVIEW'
                        ? 'CONTEXT REVIEW'
                        : claim.risk_level}
                    </span>
                    <span style={{ fontSize: '12px', color: '#718096' }}>
                      {claim.status.replaceAll('_', ' ')}
                    </span>
                  </div>

                  <p style={{ margin: '4px 0' }}>
                    <strong>Statement:</strong> {claim.text}
                  </p>
                  <p style={{ margin: '4px 0' }}>
                    <strong>Why it needs review:</strong> {claim.explanation}
                  </p>
                  <p style={{ margin: '4px 0 0' }}>
                    <strong>Evidence required:</strong> {claim.evidence_required}
                  </p>
                </div>
              ))}

              <p style={{ fontSize: '12px', color: '#718096' }}>
                {claimResult.message}
              </p>
            </>
          )}

          <div
            style={{
              background: '#fff7e6',
              padding: '15px',
              borderRadius: '8px',
              marginTop: '20px',
            }}
          >
            <strong>⚠ Human verification required</strong>
            <p>{result.important_note}</p>
            <p>
              OCR results are machine-generated. They do not establish
              whether an advertisement is truthful or legally compliant.
            </p>
          </div>
        </section>
      )}

      <footer className="footer">
        <p>BrandGuard © 2026 · Built by Team Verifex</p>
        <span>Human review is required for final approval.</span>
      </footer>
    </>
  )
}

export default PosterEvaluator
