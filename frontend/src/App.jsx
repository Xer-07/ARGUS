import { useState } from 'react'
import ThreadInput from './components/ThreadInput'
// TODO: import ThreadVerdict, ArgumentClusters, OutlierCard once you build them

function App() {
  const [analysisResult, setAnalysisResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function handleAnalyze(url) {
    setLoading(true)
    setError(null)

    try {
      const response = await fetch('http://localhost:8000/analyze', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ url })
      })

      if(!response.ok) {
        throw new Error(`Server error: ${response.status}`)
      }
      const data = await response.json()
      setAnalysisResult(data)

    } catch (err) {
      setError(err.message)
    } finally {
    setLoading(false)
  }
  }

  return (
    <div>
      <h1>ARGUS</h1>
      <ThreadInput onAnalyze={handleAnalyze} loading={loading} />

      {error && <p style={{color: 'red'}}>{error}</p>}

      {analysisResult && (<pre>{JSON.stringify(analysisResult, null, 2)}</pre>)}
    </div>
  )
}

export default App