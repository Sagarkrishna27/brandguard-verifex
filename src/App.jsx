/*
  App.jsx
  -------
  The "traffic controller" of BrandGuard.

  It keeps ONE piece of state: `page` — the id of the page currently open.
  The Sidebar calls onNavigate(id) when you click a nav button, and App
  decides which component to show below. That is all routing we need
  without adding a router package.
*/

import { useState } from 'react'
import './App.css'
import Sidebar from './components/Sidebar.jsx'
import Dashboard from './components/Dashboard.jsx'
import PosterEvaluator from './components/PosterEvaluator.jsx'
import TrustPassport from './components/TrustPassport.jsx'
import Tools from './components/Tools.jsx'
import PosterGenerator from './components/PosterGenerator.jsx'
import ClaimEvidence from './components/ClaimEvidence.jsx'
import VideoAnalysis from './components/VideoAnalysis.jsx'
import Settings from './components/Settings.jsx'
import UnifiedAnalysis from './components/UnifiedAnalysis.jsx'
import PublicReport from './components/PublicReport.jsx'

function App() {
  // Which page is open. Starts on the dashboard.
  const [page, setPage] = useState('dashboard')
  const [publicReportId] = useState(() => window.location.hash.match(/^#\/verify\/([A-Za-z0-9_-]+)$/)?.[1] || '')
  if (publicReportId) return <PublicReport reportId={publicReportId} />

  // Sidebar highlights the active page
  const handleNavigate = (id) => setPage(id)

  // Chooses which page content to render
  const renderPage = () => {
    switch (page) {
      case 'evidence':
        return <ClaimEvidence onNavigate={setPage} />
      case 'video':
        return <VideoAnalysis onNavigate={setPage} />
      case 'evaluate':
        return <PosterEvaluator onNavigate={setPage} />
      case 'passport':
        return <TrustPassport onNavigate={setPage} />
      case 'tools':
        return <Tools onNavigate={setPage} />
      case 'generator':
        return <PosterGenerator onNavigate={setPage} />
      case 'settings':
        return <Settings onNavigate={setPage} />
      case 'unified':
        return <UnifiedAnalysis onNavigate={setPage} />
      default:
        return <Dashboard onNavigate={setPage} />
    }
  }

  return (
    <div className="app-container">
      <Sidebar activePage={page} onNavigate={handleNavigate} />
      <main className="main-content">{renderPage()}</main>
    </div>
  )
}

export default App
