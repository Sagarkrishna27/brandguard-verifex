import { useEffect, useRef, useState } from 'react'

function PosterCorrectionEditor({ imageUrl, onExport, onClose }) {
  const canvasRef = useRef(null)
  const imageRef = useRef(null)
  const [text, setText] = useState('')
  const [x, setX] = useState(8)
  const [y, setY] = useState(82)
  const [fontSize, setFontSize] = useState(34)
  const [textColor, setTextColor] = useState('#111827')
  const [backgroundColor, setBackgroundColor] = useState('#ffffff')
  const [layers, setLayers] = useState([])
  const [error, setError] = useState('')

  function draw(currentLayers, image) {
    const canvas = canvasRef.current
    if (!canvas || !image) return
    const scale = Math.min(1, 1600 / Math.max(image.naturalWidth, image.naturalHeight))
    canvas.width = Math.max(1, Math.round(image.naturalWidth * scale))
    canvas.height = Math.max(1, Math.round(image.naturalHeight * scale))
    const context = canvas.getContext('2d')
    context.clearRect(0, 0, canvas.width, canvas.height)
    context.drawImage(image, 0, 0, canvas.width, canvas.height)
    currentLayers.forEach((layer) => {
      const px = canvas.width * layer.x / 100
      const py = canvas.height * layer.y / 100
      const size = Math.max(12, layer.fontSize * scale)
      context.font = "700 " + size + "px Arial, sans-serif"
      context.textBaseline = 'middle'
      const lines = String(layer.text).split('\n')
      const lineHeight = size * 1.25
      const width = Math.min(canvas.width - px - 12, Math.max(...lines.map((line) => context.measureText(line).width)) + 28)
      const height = lines.length * lineHeight + 18
      context.fillStyle = layer.backgroundColor
      context.fillRect(px, py, Math.max(0, width), height)
      context.fillStyle = layer.textColor
      lines.forEach((line, index) => context.fillText(line, px + 12, py + 9 + index * lineHeight + lineHeight / 2, Math.max(10, width - 24)))
    })
  }


  useEffect(() => {
    const image = new Image()
    image.onload = () => {
      imageRef.current = image
      draw(layers, image)
    }
    image.onerror = () => setError('Could not load the original poster image.')
    image.src = imageUrl
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [imageUrl])

  useEffect(() => {
    if (imageRef.current) draw(layers, imageRef.current)
  }, [layers])


  function addCorrection(event) {
    event.preventDefault()
    if (!text.trim()) {
      setError('Enter the correction text first.')
      return
    }
    setError('')
    setLayers((current) => [...current, { text: text.trim(), x, y, fontSize, textColor, backgroundColor }])
    setText('')
  }

  function exportPoster() {
    const canvas = canvasRef.current
    if (!canvas) return
    canvas.toBlob((blob) => {
      if (!blob) {
        setError('Could not export the corrected poster. Try again.')
        return
      }
      onExport(new File([blob], 'brandguard-corrected-poster.png', { type: 'image/png' }))
    }, 'image/png')
  }

  return (
    <section className="evaluator-card poster-correction-editor">
      <div className="analysis-module-heading">
        <div><span className="ocr-region-kicker">POSTER CORRECTION WORKSPACE</span><h2>Edit the advertisement</h2></div>
        <button type="button" className="text-button" onClick={onClose}>Close editor</button>
      </div>
      <p>Add corrected text or disclaimers over the original poster. Set the placement and styling, preview each change, then export and re-analyse. This editor overlays text; it does not erase or reconstruct the original artwork.</p>
      <div className="poster-editor-layout">
        <div className="poster-editor-preview"><canvas ref={canvasRef} aria-label="Poster correction preview" /></div>
        <form className="poster-editor-controls" onSubmit={addCorrection}>
          <label>Correction text<textarea rows="3" value={text} onChange={(event) => setText(event.target.value)} placeholder="Enter corrected claim, offer condition or disclaimer" /></label>
          <label>Horizontal position: {x}%<input type="range" min="0" max="90" value={x} onChange={(event) => setX(Number(event.target.value))} /></label>
          <label>Vertical position: {y}%<input type="range" min="0" max="95" value={y} onChange={(event) => setY(Number(event.target.value))} /></label>
          <label>Text size: {fontSize}px<input type="range" min="14" max="72" value={fontSize} onChange={(event) => setFontSize(Number(event.target.value))} /></label>
          <label>Text colour<input type="color" value={textColor} onChange={(event) => setTextColor(event.target.value)} /></label>
          <label>Text background<input type="color" value={backgroundColor} onChange={(event) => setBackgroundColor(event.target.value)} /></label>
          <button type="submit" className="primary-button">Add correction to preview</button>
          {layers.length > 0 && <div><strong>Added corrections</strong><ol>{layers.map((layer, index) => <li key={index}>{layer.text} <button type="button" className="text-button" onClick={() => setLayers((items) => items.filter((_, itemIndex) => itemIndex !== index))}>Remove</button></li>)}</ol></div>}
          {error && <p className="upload-error" role="alert">{error}</p>}
          <button type="button" className="primary-button" disabled={!layers.length} onClick={exportPoster}>Export corrected poster PNG</button>
        </form>
      </div>
    </section>
  )
}

export default PosterCorrectionEditor
