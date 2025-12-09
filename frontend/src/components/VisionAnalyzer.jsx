import React, { useState } from 'react'
import { analyzeImage } from '../services/api'
import './Card.css'

function VisionAnalyzer() {
  const [file, setFile] = useState(null)
  const [imageUrl, setImageUrl] = useState('')
  const [symbol, setSymbol] = useState('')
  const [loading, setLoading] = useState(false)
  const [analysis, setAnalysis] = useState(null)
  const [error, setError] = useState(null)
  const [preview, setPreview] = useState(null)

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0]
    if (selectedFile) {
      setFile(selectedFile)
      setImageUrl('')
      
      // Create preview
      const reader = new FileReader()
      reader.onloadend = () => {
        setPreview(reader.result)
      }
      reader.readAsDataURL(selectedFile)
    }
  }

  const handleUrlChange = (e) => {
    setImageUrl(e.target.value)
    setFile(null)
    if (e.target.value) {
      setPreview(e.target.value)
    } else {
      setPreview(null)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setAnalysis(null)

    try {
      const result = await analyzeImage(file, imageUrl, symbol)
      setAnalysis(result.analysis)
    } catch (err) {
      setError(err.message || 'Failed to analyze image')
    } finally {
      setLoading(false)
    }
  }

  const handleReset = () => {
    setFile(null)
    setImageUrl('')
    setSymbol('')
    setAnalysis(null)
    setError(null)
    setPreview(null)
  }

  return (
    <div className="card">
      <h2>📊 AI Vision Chart Analysis</h2>
      
      <form onSubmit={handleSubmit} style={{ marginBottom: '20px' }}>
        <div style={{ marginBottom: '15px' }}>
          <label style={{ display: 'block', color: '#9ca3af', marginBottom: '5px', fontSize: '14px' }}>
            Stock Symbol (optional)
          </label>
          <input
            type="text"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            placeholder="e.g., AAPL"
            style={{
              width: '100%',
              padding: '10px',
              background: '#2a2f4a',
              border: '1px solid #2a2f4a',
              borderRadius: '5px',
              color: '#e0e0e0',
              fontSize: '14px'
            }}
          />
        </div>

        <div style={{ marginBottom: '15px' }}>
          <label style={{ display: 'block', color: '#9ca3af', marginBottom: '5px', fontSize: '14px' }}>
            Upload Chart Image
          </label>
          <input
            type="file"
            accept="image/*"
            onChange={handleFileChange}
            style={{
              width: '100%',
              padding: '10px',
              background: '#2a2f4a',
              border: '1px solid #2a2f4a',
              borderRadius: '5px',
              color: '#e0e0e0',
              fontSize: '14px'
            }}
          />
        </div>

        <div style={{ marginBottom: '15px', textAlign: 'center', color: '#9ca3af' }}>
          OR
        </div>

        <div style={{ marginBottom: '15px' }}>
          <label style={{ display: 'block', color: '#9ca3af', marginBottom: '5px', fontSize: '14px' }}>
            Image URL
          </label>
          <input
            type="url"
            value={imageUrl}
            onChange={handleUrlChange}
            placeholder="https://example.com/chart.png"
            style={{
              width: '100%',
              padding: '10px',
              background: '#2a2f4a',
              border: '1px solid #2a2f4a',
              borderRadius: '5px',
              color: '#e0e0e0',
              fontSize: '14px'
            }}
          />
        </div>

        {preview && (
          <div style={{ marginBottom: '15px', textAlign: 'center' }}>
            <img
              src={preview}
              alt="Preview"
              style={{
                maxWidth: '100%',
                maxHeight: '300px',
                borderRadius: '5px',
                border: '1px solid #2a2f4a'
              }}
            />
          </div>
        )}

        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            type="submit"
            disabled={loading || (!file && !imageUrl)}
            className="btn"
            style={{
              flex: 1,
              padding: '12px',
              opacity: loading ? 0.5 : 1,
              cursor: loading ? 'not-allowed' : 'pointer',
              fontSize: '14px',
              fontWeight: 'bold'
            }}
            disabled={loading || (!file && !imageUrl)}
          >
            {loading ? 'Analyzing...' : '🔍 Analyze Chart'}
          </button>
          
          {(file || imageUrl || analysis) && (
            <button
              type="button"
              onClick={handleReset}
              className="btn"
              style={{
                padding: '12px 20px',
                background: '#2a2f4a',
                fontSize: '14px'
              }}
            >
              Reset
            </button>
          )}
        </div>
      </form>

      {error && (
        <div style={{
          padding: '15px',
          background: '#2a1f1f',
          border: '1px solid #ef4444',
          borderRadius: '5px',
          color: '#fca5a5',
          marginBottom: '15px'
        }}>
          <strong>Error:</strong> {error}
        </div>
      )}

      {analysis && (
        <div className="analysis-results" style={{
          background: '#2a2f4a',
          padding: '20px',
          borderRadius: '10px',
          border: '1px solid #2a2f4a',
          marginTop: '20px'
        }}>
          <h3 style={{ color: '#667eea', marginBottom: '15px', fontSize: '18px' }}>
            AI Analysis Results
          </h3>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '15px', marginBottom: '20px' }}>
            <div style={{ background: '#1a1f3a', padding: '15px', borderRadius: '5px' }}>
              <div style={{ color: '#9ca3af', fontSize: '12px', marginBottom: '5px' }}>Action</div>
              <div style={{
                color: analysis.action === 'BUY' ? '#10b981' : analysis.action === 'SELL' ? '#ef4444' : '#9ca3af',
                fontSize: '18px',
                fontWeight: 'bold'
              }}>
                {analysis.action}
              </div>
            </div>

            <div style={{ background: '#1a1f3a', padding: '15px', borderRadius: '5px' }}>
              <div style={{ color: '#9ca3af', fontSize: '12px', marginBottom: '5px' }}>Confidence</div>
              <div style={{ color: '#e0e0e0', fontSize: '18px', fontWeight: 'bold' }}>
                {(analysis.confidence * 100).toFixed(1)}%
              </div>
            </div>

            <div style={{ background: '#1a1f3a', padding: '15px', borderRadius: '5px' }}>
              <div style={{ color: '#9ca3af', fontSize: '12px', marginBottom: '5px' }}>Entry</div>
              <div style={{ color: '#e0e0e0', fontSize: '18px', fontWeight: 'bold' }}>
                ${analysis.entry?.toFixed(2) || 'N/A'}
              </div>
            </div>

            <div style={{ background: '#1a1f3a', padding: '15px', borderRadius: '5px' }}>
              <div style={{ color: '#9ca3af', fontSize: '12px', marginBottom: '5px' }}>Stop Loss</div>
              <div style={{ color: '#ef4444', fontSize: '18px', fontWeight: 'bold' }}>
                ${analysis.stop?.toFixed(2) || 'N/A'}
              </div>
            </div>

            <div style={{ background: '#1a1f3a', padding: '15px', borderRadius: '5px' }}>
              <div style={{ color: '#9ca3af', fontSize: '12px', marginBottom: '5px' }}>Take Profit</div>
              <div style={{ color: '#10b981', fontSize: '18px', fontWeight: 'bold' }}>
                ${analysis.target?.toFixed(2) || 'N/A'}
              </div>
            </div>

            {analysis.risk_reward_ratio && (
              <div style={{ background: '#1a1f3a', padding: '15px', borderRadius: '5px' }}>
                <div style={{ color: '#9ca3af', fontSize: '12px', marginBottom: '5px' }}>Risk/Reward</div>
                <div style={{ color: '#e0e0e0', fontSize: '18px', fontWeight: 'bold' }}>
                  1:{analysis.risk_reward_ratio.toFixed(2)}
                </div>
              </div>
            )}
          </div>

          {analysis.setup_type && (
            <div style={{ marginBottom: '15px' }}>
              <div style={{ color: '#9ca3af', fontSize: '12px', marginBottom: '5px' }}>Setup Type</div>
              <div style={{ color: '#667eea', fontSize: '16px', fontWeight: 'bold' }}>
                {analysis.setup_type}
              </div>
            </div>
          )}

          {analysis.pattern_identified && (
            <div style={{ marginBottom: '15px' }}>
              <div style={{ color: '#9ca3af', fontSize: '12px', marginBottom: '5px' }}>Pattern Identified</div>
              <div style={{ color: '#e0e0e0', fontSize: '14px' }}>
                {analysis.pattern_identified}
              </div>
            </div>
          )}

          {analysis.chart_observations && (
            <div style={{ marginBottom: '15px' }}>
              <div style={{ color: '#9ca3af', fontSize: '12px', marginBottom: '5px' }}>Chart Observations</div>
              <div style={{ color: '#e0e0e0', fontSize: '14px', lineHeight: '1.6' }}>
                {analysis.chart_observations}
              </div>
            </div>
          )}

          {analysis.reasoning && (
            <div style={{
              background: '#1a1f3a',
              padding: '15px',
              borderRadius: '5px',
              marginTop: '15px'
            }}>
              <div style={{ color: '#9ca3af', fontSize: '12px', marginBottom: '5px' }}>AI Reasoning</div>
              <div style={{ color: '#e0e0e0', fontSize: '14px', lineHeight: '1.6' }}>
                {analysis.reasoning}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default VisionAnalyzer

