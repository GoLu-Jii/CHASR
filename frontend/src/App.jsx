import { useEffect, useMemo, useState } from 'react'
import './App.css'

const API_BASE = 'http://localhost:8000/api'

function formatCurrency(value) {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(Number(value || 0))
}

function StatCard({ label, value, tone = 'neutral' }) {
  return (
    <div className="panel stat-card">
      <div className={`badge badge-${tone}`}>{label}</div>
      <div className="stat-value">{value}</div>
    </div>
  )
}

function App() {
  const [view, setView] = useState('dashboard')
  const [dashboard, setDashboard] = useState({ total_unpaid_inr: 0, active_unpaid_invoices: 0, human_review_required: 0 })
  const [invoices, setInvoices] = useState([])
  const [selectedInvoiceId, setSelectedInvoiceId] = useState(null)
  const [ledger, setLedger] = useState([])
  const [replyText, setReplyText] = useState('We are waiting on client disbursement and will clear 50% by Thursday and the rest by month-end.')
  const [resultSummary, setResultSummary] = useState({ baseline_recovered_inr: 0, model_recovered_inr: 0, precision: 0, recall: 0, improvement_pct: 0, avg_days_to_recovery: 0 })
  const [statusMessage, setStatusMessage] = useState('')
  const [lastCronSummary, setLastCronSummary] = useState(() => {
    if (typeof window === 'undefined') return null
    try {
      return JSON.parse(localStorage.getItem('lastCronSummary')) || null
    } catch {
      return null
    }
  })

  const selectedInvoice = useMemo(
    () => invoices.find((invoice) => invoice.id === selectedInvoiceId) || null,
    [invoices, selectedInvoiceId],
  )

  const loadDashboard = async () => {
    const response = await fetch(`${API_BASE}/dashboard`)
    const data = await response.json()
    setDashboard(data)
  }

  const loadInvoices = async () => {
    const response = await fetch(`${API_BASE}/invoices`)
    const data = await response.json()
    setInvoices(data)
    if (!selectedInvoiceId && data[0]) {
      setSelectedInvoiceId(data[0].id)
    }
  }

  const loadLedger = async (invoiceId) => {
    if (!invoiceId) return
    const response = await fetch(`${API_BASE}/invoices/${invoiceId}/ledger`)
    const data = await response.json()
    setLedger(data.ledger || [])
  }

  const loadResults = async () => {
    const response = await fetch(`${API_BASE}/results`)
    const data = await response.json()
    setResultSummary(data)
  }

  useEffect(() => {
    loadDashboard()
    loadInvoices()
    loadResults()
  }, [])

  useEffect(() => {
    if (selectedInvoiceId) {
      loadLedger(selectedInvoiceId)
    }
  }, [selectedInvoiceId])

  useEffect(() => {
    if (lastCronSummary) {
      localStorage.setItem('lastCronSummary', JSON.stringify(lastCronSummary))
    }
  }, [lastCronSummary])

  const runCron = async () => {
    try {
      const response = await fetch('http://127.0.0.1:8000/api/jobs/run_escalations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })

      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`)
      }

      const data = await response.json()
      const message = data.message || 'Cron job completed successfully.'
      setLastCronSummary(data)
      alert(message)
      window.location.reload()
    } catch (error) {
      alert(error.message || 'Failed to run cron job.')
    }
  }

  const simulateReply = async () => {
    if (!selectedInvoiceId) return
    const response = await fetch(`${API_BASE}/invoices/${selectedInvoiceId}/simulate_reply`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: replyText }),
    })
    const data = await response.json()
    setStatusMessage(data.message)
    loadDashboard()
    loadInvoices()
    loadLedger(selectedInvoiceId)
  }

  return (
    <div className="app-shell">
      <aside className="sidebar panel">
        <div className="brand-block">
          <div className="brand-mark">C</div>
          <div>
            <div className="eyebrow">B2B Recovery</div>
            <h1>CHASR</h1>
          </div>
        </div>

        <nav className="nav">
          <button className={view === 'dashboard' ? 'nav-link active' : 'nav-link'} onClick={() => setView('dashboard')}>Dashboard</button>
          <button className={view === 'invoices' ? 'nav-link active' : 'nav-link'} onClick={() => setView('invoices')}>Invoices</button>
          <button className={view === 'ledger' ? 'nav-link active' : 'nav-link'} onClick={() => setView('ledger')}>Audit Trail</button>
          <button className={view === 'results' ? 'nav-link active' : 'nav-link'} onClick={() => setView('results')}>Results</button>
        </nav>

        <div className="sidebar-card">
          <div className="eyebrow">Operations</div>
          <button className="primary-button" onClick={runCron}>Run midnight cron</button>
        </div>
      </aside>

      <main className="content">
        {view === 'dashboard' && (
          <>
            <div className="page-header">
              <div>
                <div className="eyebrow">Recovery intelligence</div>
                <h2>Collections dashboard</h2>
              </div>
              <button className="secondary-button" onClick={loadDashboard}>Refresh</button>
            </div>

            <div className="stats-grid">
              <StatCard label="Total unpaid" value={formatCurrency(dashboard.total_unpaid_inr)} tone="primary" />
              <StatCard label="Active invoices" value={dashboard.active_unpaid_invoices} tone="neutral" />
              <StatCard label="Needs human review" value={dashboard.human_review_required} tone="warning" />
            </div>

            {lastCronSummary && (
              <div className="panel metrics-panel" style={{ marginBottom: '18px' }}>
                <div className="timeline-header">
                  <h3>Last cron summary</h3>
                  <span className="status-pill ok">{lastCronSummary.processed || 0} processed</span>
                </div>
                <div className="metric-row"><span>Run at</span><strong>{new Date(lastCronSummary.run_at).toLocaleString()}</strong></div>
                <div className="metric-row"><span>Message</span><strong>{lastCronSummary.message}</strong></div>
                <div className="metric-row"><span>Updated invoices</span><strong>{(lastCronSummary.updated_invoices || []).length}</strong></div>
                {(lastCronSummary.updated_invoices || []).slice(0, 5).map((item) => (
                  <div key={item.invoice_id} className="metric-row">
                    <span>Invoice #{item.invoice_id}</span>
                    <strong>{item.previous_stage} → {item.new_stage}</strong>
                  </div>
                ))}
              </div>
            )}

            <div className="panel table-panel">
              <div className="table-header">
                <h3>Priority watchlist</h3>
              </div>
              <table>
                <thead>
                  <tr>
                    <th>Customer</th>
                    <th>Status</th>
                    <th>Days overdue</th>
                    <th>Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {invoices.slice(0, 5).map((invoice) => (
                    <tr key={invoice.id}>
                      <td>{invoice.customer_name}</td>
                      <td>{invoice.status}</td>
                      <td>{invoice.days_overdue}</td>
                      <td>{formatCurrency(invoice.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {view === 'invoices' && (
          <>
            <div className="page-header">
              <div>
                <div className="eyebrow">Invoice operations</div>
                <h2>Invoice ledger</h2>
              </div>
            </div>

            <div className="panel table-panel">
              <table>
                <thead>
                  <tr>
                    <th>Invoice</th>
                    <th>Customer</th>
                    <th>Status</th>
                    <th>Days overdue</th>
                    <th>Amount</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {invoices.map((invoice) => (
                    <tr key={invoice.id}>
                      <td>#{invoice.id}</td>
                      <td>{invoice.customer_name}</td>
                      <td>{invoice.status}</td>
                      <td>{invoice.days_overdue}</td>
                      <td>{formatCurrency(invoice.amount)}</td>
                      <td>
                        <button className="inline-button" onClick={() => { setSelectedInvoiceId(invoice.id); setView('ledger'); }}>
                          View ledger
                        </button>
                        <button className="inline-button secondary" onClick={() => { setSelectedInvoiceId(invoice.id); setReplyText('We are waiting on client disbursement and will clear 50% by Thursday and the rest by month-end.'); setView('ledger'); }}>
                          Simulate reply
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {view === 'ledger' && (
          <>
            <div className="page-header">
              <div>
                <div className="eyebrow">Audit integrity</div>
                <h2>Cryptographic ledger</h2>
              </div>
            </div>

            <div className="panel form-panel">
              <label className="field-label" htmlFor="invoice-selector">Invoice</label>
              <select id="invoice-selector" value={selectedInvoiceId ?? ''} onChange={(event) => setSelectedInvoiceId(Number(event.target.value))}>
                {invoices.map((invoice) => (
                  <option key={invoice.id} value={invoice.id}>#{invoice.id} · {invoice.customer_name}</option>
                ))}
              </select>

              <textarea
                value={replyText}
                onChange={(event) => setReplyText(event.target.value)}
                rows={4}
                placeholder="Paste a customer reply"
              />
              <button className="primary-button" onClick={simulateReply}>Simulate customer reply</button>
            </div>

            <div className="panel timeline-panel">
              <div className="timeline-header">
                <h3>Transaction chain</h3>
                <span className={ledger.length && ledger.every((entry) => entry.hash) ? 'status-pill ok' : 'status-pill'}>
                  {ledger.length ? 'Chain valid' : 'No ledger entries'}
                </span>
              </div>
              {ledger.length === 0 ? (
                <p className="empty-state">No ledger events for this invoice yet.</p>
              ) : (
                <div className="ledger-list">
                  {ledger.map((entry) => (
                    <div key={entry.id} className="ledger-entry">
                      <div className="ledger-time">{new Date(entry.timestamp).toLocaleString()}</div>
                      <div className="ledger-event">{entry.event}</div>
                      <pre>{JSON.stringify(entry.payload, null, 2)}</pre>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}

        {view === 'results' && (
          <>
            <div className="page-header">
              <div>
                <div className="eyebrow">Model vs baseline</div>
                <h2>Recovery comparison</h2>
              </div>
            </div>

            <div className="stats-grid">
              <StatCard label="Model recovered" value={formatCurrency(resultSummary.model_recovered_inr)} tone="primary" />
              <StatCard label="Baseline recovered" value={formatCurrency(resultSummary.baseline_recovered_inr)} tone="neutral" />
              <StatCard label="Improvement" value={`${resultSummary.improvement_pct}%`} tone="warning" />
            </div>

            <div className="panel metrics-panel">
              <div className="metric-row"><span>Precision</span><strong>{resultSummary.precision}</strong></div>
              <div className="metric-row"><span>Recall</span><strong>{resultSummary.recall}</strong></div>
              <div className="metric-row"><span>Avg. time to recovery</span><strong>{resultSummary.avg_days_to_recovery} days</strong></div>
            </div>
          </>
        )}

        {statusMessage && <div className="toast">{statusMessage}</div>}
      </main>
    </div>
  )
}

export default App
