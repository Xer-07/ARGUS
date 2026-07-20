import { useState } from 'react'

function ThreadInput({ onAnalyze, loading }) {
  const [urlText, setUrlText] = useState('')

  function handleSubmit() {
    if(!urlText.trim()) return
    onAnalyze(urlText)
  }
  return (
    <div>
      <input
        type="text"
        value={urlText}
        onChange={(e) => setUrlText(e.target.value)}
        placeholder="Paste Reddit thread URL"
      />
      <button onClick={handleSubmit} disabled={loading}>
        {loading ? 'Analyzing...' : 'Analyze'}
        </button>
    </div>
  )
}

export default ThreadInput