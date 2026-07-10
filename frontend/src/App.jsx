import { useEffect } from 'react'

function App() {

  useEffect(() => {
    async function testFetch() {
      try {
        const response = await fetch('http://localhost:8000/analyze', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
           body: JSON.stringify({ url: 'https://www.reddit.com/r/reactjs/comments/11cyejn/what_is_cors_and_why_is_it_so_annoying/' })
        })

        // 
        const data = await response.json()

        console.log('ARGUS response:', data)
      } catch (err) {
        console.error('Fetch failed:', err)
      }
    }

    testFetch()
  }, []) // empty dependency array = run once on mount, don't touch this yet

  return (
    <div>
      <h1>ARGUS Test</h1>
    </div>
  )
}

export default App