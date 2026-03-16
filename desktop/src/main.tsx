import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import StageApp from './StageApp'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <StageApp />
  </StrictMode>
)
