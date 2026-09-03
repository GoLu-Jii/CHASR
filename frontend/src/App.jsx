import { useEffect, useMemo, useState } from 'react'

const API_BASE = 'http://localhost:8000/api'
const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === 'true'

function formatCurrency(value) {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(Number(value || 0))
}

function StatCard({ label, value, tone = 'neutral' }) {
  const toneClass = tone === 'primary' ? 'text-cyan-400' : tone === 'warning' ? 'text-amber-400' : 'text-slate-400'

  return (
    <div className="rounded-lg bg-slate-800 p-5">
      <div className={`mb-3 text-xs font-medium uppercase tracking-widest ${toneClass}`}>{label}</div>
      <div className="text-3xl font-semibold text-slate-100">{value}</div>
    </div>
  )
}

function statusClass(status) {
  return {
    paid: 'bg-emerald-500/10 text-emerald-400 px-2.5 py-0.5 rounded-full text-xs font-medium',
    unpaid: 'bg-amber-500/10 text-amber-400 px-2.5 py-0.5 rounded-full text-xs font-medium',
    written_off: 'bg-slate-500/10 text-slate-400 px-2.5 py-0.5 rounded-full text-xs font-medium',
    partially_paid: 'bg-amber-500/10 text-amber-400 px-2.5 py-0.5 rounded-full text-xs font-medium',
    escalation_exhausted: 'bg-red-500/10 text-red-400 px-2.5 py-0.5 rounded-full text-xs font-medium',
  }[status] || 'bg-slate-500/10 text-slate-400 px-2.5 py-0.5 rounded-full text-xs font-medium'
}

function postureClass(stage) {
  return {
    nudge: 'bg-cyan-500/10 text-cyan-400 px-2 py-0.5 rounded-full text-xs font-medium',
    firm: 'bg-orange-500/10 text-orange-400 px-2 py-0.5 rounded-full text-xs font-medium',
    formal: 'bg-red-500/10 text-red-400 px-2 py-0.5 rounded-full text-xs font-medium',
  }[stage] || 'bg-slate-500/10 text-slate-400 px-2 py-0.5 rounded-full text-xs font-medium'
}

function reliabilityClass(score) {
  if (score > 0.75) return 'text-emerald-400'
  if (score >= 0.4) return 'text-amber-400'
  return 'text-red-400'
}

function Table({ invoices, onSelect }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[900px] text-left text-sm">
        <thead className="text-xs uppercase tracking-wider text-slate-400">
          <tr>
            <th className="px-6 py-4">Invoice</th>
            <th className="px-6 py-4">Customer</th>
            <th className="px-6 py-4">Status</th>
            <th className="px-6 py-4">Agent Posture</th>
            <th className="px-6 py-4">Days overdue</th>
            <th className="px-6 py-4 text-right">Amount</th>
            <th className="px-6 py-4 text-right">Reliability Score</th>
            <th className="px-6 py-4 text-right">Action</th>
          </tr>
        </thead>
        <tbody>
          {invoices.map((invoice) => {
            const score = Number(invoice.reliability_score ?? 0.5)
            return (
              <tr key={invoice.id} className="border-b border-slate-700/50">
                <td className="px-6 py-4 font-mono text-slate-100">#{invoice.id}</td>
                <td className="px-6 py-4 text-slate-300">{invoice.customer_name}</td>
                <td className="px-6 py-4"><span className={statusClass(invoice.status)}>{invoice.status}</span></td>
                <td className="px-6 py-4"><span className={postureClass(invoice.current_stage)}>{invoice.current_stage === 'formal' ? 'Legal' : invoice.current_stage === 'firm' ? 'Firm' : 'Nudge'}</span></td>
                <td className="px-6 py-4 text-slate-300">{invoice.days_overdue}</td>
                <td className="px-6 py-4 text-right font-mono text-slate-100">{formatCurrency(invoice.amount)}</td>
                <td className={`px-6 py-4 text-right font-mono ${reliabilityClass(score)}`}>{score.toFixed(2)}</td>
                <td className="px-6 py-4 text-right"><button className="rounded-md bg-cyan-600 px-3 py-2 text-xs font-medium text-slate-100 hover:bg-cyan-500" onClick={() => onSelect(invoice.id)}>View audit</button></td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function App() {
  const [view, setView] = useState('dashboard')
  const [dashboard, setDashboard] = useState({ total_unpaid_inr: 0, active_unpaid_invoices: 0, human_review_required: 0 })
  const [invoices, setInvoices] = useState([])
  const [selectedInvoiceId, setSelectedInvoiceId] = useState(null)
  const [ledger, setLedger] = useState([])
  const [lastCustomerReply, setLastCustomerReply] = useState('')
  const [replyText, setReplyText] = useState('We are waiting on client disbursement and will clear 50% by Thursday and the rest by month-end.')
  const [resultSummary, setResultSummary] = useState({ baseline_recovered_inr: 0, model_recovered_inr: 0, precision: 0, recall: 0, improvement_pct: 0, avg_days_to_recovery: 0 })
  const [statusMessage, setStatusMessage] = useState('')
  const [demoClock, setDemoClock] = useState(null)
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

  const extractedCommitment = useMemo(() => {
    const extraction = [...ledger].reverse().find((entry) => entry.event === 'promise_extracted')
    const raw = extraction?.payload?.raw || extraction?.payload
    const commitment = raw?.commitments?.[0] || raw
    return commitment || null
  }, [ledger])

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
    const latestReply = [...(data.ledger || [])].reverse().find((entry) => entry.event === 'reply_received')
    setLastCustomerReply(latestReply?.payload?.text || '')
  }

  const loadResults = async () => {
    const response = await fetch(`${API_BASE}/results`)
    const data = await response.json()
    setResultSummary(data)
  }

  const loadDemoClock = async () => {
    if (!DEMO_MODE) return
    const response = await fetch('http://127.0.0.1:8000/demo/clock')
    if (response.ok) setDemoClock((await response.json()).now)
  }

  const demoAction = async (path, body) => {
    try {
      const response = await fetch(`http://127.0.0.1:8000/demo/${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined,
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`)
      if (path === 'seed' || path === 'reset') setSelectedInvoiceId(null)
      setDemoClock(data.now)
      await Promise.all([loadDashboard(), loadInvoices(), loadResults()])
      if (selectedInvoiceId) await loadLedger(selectedInvoiceId)
      setStatusMessage(data.message)
    } catch (error) {
      alert(`Demo action failed: ${error.message || 'Unknown error'}`)
    }
  }

  useEffect(() => {
    loadDashboard()
    loadInvoices()
    loadResults()
    loadDemoClock()
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
    try {
      const response = await fetch(`${API_BASE}/invoices/${selectedInvoiceId}/simulate_reply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: replyText }),
      })

      const data = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(data.detail || `Request failed with status ${response.status}`)
      }

      setStatusMessage(data.message)
      loadDashboard()
      loadInvoices()
      loadLedger(selectedInvoiceId)
    } catch (error) {
      alert(`LLM Extraction Failed: ${error.message || 'Unknown error'}`)
    }
  }

  return (
    <div className="app-shell min-h-screen bg-slate-900 font-sans text-slate-100">
      <aside className="sidebar-shell sticky top-0 z-10 flex h-auto flex-col bg-slate-800 px-4 py-4 md:h-screen md:w-64 md:px-5 md:py-6">
        <div className="mb-8 flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-lg bg-cyan-600 text-lg font-bold text-slate-100">C</div>
          <div>
            <div className="text-xs uppercase tracking-widest text-slate-400">B2B Recovery</div>
            <h1 className="mt-1 text-2xl font-semibold text-slate-100">CHASR</h1>
          </div>
        </div>

        <nav className="flex flex-row gap-2 overflow-x-auto md:flex-col">
          {['dashboard', 'invoices', 'ledger', 'results'].map((item) => (
            <button key={item} className={`nav-item px-3 py-2 text-left capitalize ${view === item ? 'bg-cyan-600 text-slate-100' : 'text-slate-400 hover:bg-slate-700 hover:text-slate-100'}`} onClick={() => setView(item)}>{item === 'ledger' ? 'Audit Trail' : item}</button>
          ))}
        </nav>

        <div className="mt-4 bg-slate-900 p-4 md:mt-auto">
          <div className="mb-3 text-xs uppercase tracking-widest text-slate-400">Operations</div>
          <button className="w-full bg-cyan-600 px-3 py-2 text-sm font-medium text-slate-100 hover:bg-cyan-500" onClick={runCron}>Run midnight cron</button>
        </div>
      </aside>

      <main className="main-shell min-h-screen px-4 pb-8 pt-6 md:p-8">
        <div className="topbar mb-8 flex items-center justify-between border-b border-slate-700 pb-4">
          <div>
            <div className="text-xs uppercase tracking-widest text-cyan-400">CHASR / Operations</div>
            <div className="mt-1 text-sm font-medium text-slate-100">{view === 'ledger' ? 'Audit trail' : view === 'results' ? 'Recovery results' : view === 'invoices' ? 'Invoice operations' : 'Collections overview'}</div>
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-400"><span className="h-2 w-2 bg-emerald-600" /> API connected</div>
        </div>
        {DEMO_MODE && (
          <div className="mb-6 flex flex-wrap items-center gap-2 border border-slate-700 bg-slate-800 p-3">
            <span className="mr-2 text-xs font-semibold uppercase tracking-widest text-slate-400">Demo controls</span>
            <button className="bg-cyan-600 px-3 py-2 text-xs font-medium text-slate-100 hover:bg-cyan-500" onClick={() => demoAction('seed')}>Seed Data</button>
            <button className="bg-cyan-600 px-3 py-2 text-xs font-medium text-slate-100 hover:bg-cyan-500" onClick={() => demoAction('advance-clock', { days: 1 })}>Advance +1 Day</button>
            <button className="bg-cyan-600 px-3 py-2 text-xs font-medium text-slate-100 hover:bg-cyan-500" onClick={() => demoAction('advance-clock', { days: 7 })}>Advance +7 Days</button>
            <button className="bg-slate-900 px-3 py-2 text-xs font-medium text-slate-100" onClick={() => demoAction('reset')}>Reset Demo</button>
            {demoClock && <span className="ml-auto font-mono text-xs text-slate-400">Virtual time: {new Date(demoClock).toLocaleString()}</span>}
          </div>
        )}
        {view === 'dashboard' && (
          <>
            <div className="mb-6 flex items-center justify-between border-b border-slate-700 pb-5">
              <div>
                <div className="text-xs uppercase tracking-widest text-cyan-400">Recovery intelligence</div>
                <h2 className="mt-2 text-2xl font-semibold text-slate-100">Collections dashboard</h2>
              </div>
              <button className="rounded-md bg-cyan-600 px-3 py-2 text-sm font-medium text-slate-100 hover:bg-cyan-500" onClick={loadDashboard}>Refresh</button>
            </div>

            <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-3">
              <StatCard label="Total unpaid" value={formatCurrency(dashboard.total_unpaid_inr)} tone="primary" />
              <StatCard label="Active invoices" value={dashboard.active_unpaid_invoices} tone="neutral" />
              <StatCard label="Needs human review" value={dashboard.human_review_required} tone="warning" />
            </div>

            {lastCronSummary && (
              <div className="mb-5 bg-slate-800 p-5">
                <div className="mb-3 flex items-center justify-between">
                  <h3 className="font-semibold text-slate-100">Last cron summary</h3>
                  <span className="rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-xs font-medium text-emerald-400">{lastCronSummary.processed || 0} processed</span>
                </div>
                <div className="flex justify-between border-b border-slate-700/50 py-3 text-sm"><span className="text-slate-400">Run at</span><strong className="text-slate-100">{new Date(lastCronSummary.run_at).toLocaleString()}</strong></div>
                <div className="flex justify-between border-b border-slate-700/50 py-3 text-sm"><span className="text-slate-400">Message</span><strong className="text-slate-100">{lastCronSummary.message}</strong></div>
                <div className="flex justify-between border-b border-slate-700/50 py-3 text-sm"><span className="text-slate-400">Updated invoices</span><strong className="text-slate-100">{(lastCronSummary.updated_invoices || []).length}</strong></div>
                {(lastCronSummary.updated_invoices || []).slice(0, 5).map((item) => (
                  <div key={item.invoice_id} className="flex justify-between border-b border-slate-700/50 py-3 text-sm">
                    <span className="text-slate-400">Invoice #{item.invoice_id}</span>
                    <strong className="text-slate-100">{item.previous_stage} -&gt; {item.new_stage}</strong>
                  </div>
                ))}
              </div>
            )}

            <div className="bg-slate-800 p-2">
              <h3 className="px-4 py-3 font-semibold text-slate-100">Priority watchlist</h3>
              <Table invoices={invoices.slice(0, 5)} onSelect={(id) => { setSelectedInvoiceId(id); setView('ledger') }} />
            </div>
          </>
        )}

        {view === 'invoices' && (
          <>
            <div className="mb-6 border-b border-slate-700 pb-5">
              <div>
                <div className="text-xs uppercase tracking-widest text-cyan-400">Invoice operations</div>
                <h2 className="mt-2 text-2xl font-semibold text-slate-100">Invoice ledger</h2>
              </div>
            </div>

            <div className="bg-slate-800 p-2">
              <Table invoices={invoices} onSelect={(id) => { setSelectedInvoiceId(id); setView('ledger') }} />
            </div>
          </>
        )}

        {view === 'ledger' && (
          <>
            <div className="mb-6 border-b border-slate-700 pb-5">
              <div>
                <div className="text-xs uppercase tracking-widest text-cyan-400">Audit integrity</div>
                <h2 className="mt-2 text-2xl font-semibold text-slate-100">Cryptographic ledger</h2>
              </div>
            </div>

            <div className="mb-5 bg-slate-800 p-4">
              <label className="mb-2 block text-sm text-slate-400" htmlFor="invoice-selector">Invoice</label>
              <select className="mb-4 w-full rounded-md bg-slate-900 px-3 py-2 text-slate-100" id="invoice-selector" value={selectedInvoiceId ?? ''} onChange={(event) => setSelectedInvoiceId(Number(event.target.value))}>
                {invoices.map((invoice) => (
                  <option key={invoice.id} value={invoice.id}>#{invoice.id} · {invoice.customer_name}</option>
                ))}
              </select>

              <div className="mb-2 text-xs uppercase tracking-widest text-cyan-400">Simulated customer reply</div>
              <p className="mb-3 text-sm text-slate-400">This is the inbound message CHASR reads. The outbound recovery action is decided below.</p>
              <textarea
                className="mb-4 w-full rounded-md bg-slate-900 p-3 text-slate-100"
                value={replyText}
                onChange={(event) => setReplyText(event.target.value)}
                rows={4}
                placeholder="Paste a customer reply"
              />
              <button className="rounded-md bg-cyan-600 px-3 py-2 text-sm font-medium text-slate-100 hover:bg-cyan-500" onClick={simulateReply}>Simulate customer reply</button>
            </div>

            {selectedInvoice && (
              <div className="mb-5 flex flex-col gap-4 md:flex-row">
                <div className="flex-1 rounded-lg bg-slate-800 p-4 italic text-slate-300">{lastCustomerReply || 'No customer reply recorded yet.'}</div>
                <div className="flex-1 rounded-lg border border-cyan-500/30 bg-slate-900 p-4">
                  <h3 className="mb-3 font-semibold text-slate-100">Extracted Commitment</h3>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between"><span className="text-slate-400">Promised Amount</span><strong className="text-slate-100">{extractedCommitment?.amount ? formatCurrency(extractedCommitment.amount) : 'Not stated'}</strong></div>
                    <div className="flex justify-between"><span className="text-slate-400">Expected Date</span><strong className="text-slate-100">{extractedCommitment?.promised_date || 'Not stated'}</strong></div>
                    <div className="flex justify-between"><span className="text-slate-400">AI Confidence Score</span><strong className="text-cyan-400">{extractedCommitment?.confidence || 'Pending'}</strong></div>
                  </div>
                </div>
              </div>
            )}

            {selectedInvoice && (
              <div className="mb-5 bg-slate-800 p-4">
                <div className="mb-2 text-xs uppercase tracking-widest text-cyan-400">CHASR next step</div>
                <div className="text-lg font-semibold text-slate-100">{selectedInvoice.next_action || 'Evaluate invoice'}</div>
                {selectedInvoice.next_message && <div className="mt-2 text-sm text-slate-400">{selectedInvoice.next_message}</div>}
              </div>
            )}

            <div className="rounded-md border border-slate-800 bg-slate-950 p-4 font-mono text-sm">
              <div className="mb-4 flex items-center justify-between">
                <h3 className="text-slate-100">Transaction chain</h3>
                <span className={ledger.length && ledger.every((entry) => entry.hash) ? 'text-xs text-emerald-500' : 'text-xs text-slate-400'}>
                  {ledger.length ? 'Chain valid' : 'No ledger entries'}
                </span>
              </div>
              {ledger.length === 0 ? (
                <p className="empty-state">No ledger events for this invoice yet.</p>
              ) : (
                <div className="ledger-list">
                  {ledger.map((entry) => (
                    <div key={entry.id} className="border-b border-slate-800 py-3 last:border-0">
                      <div className="flex items-center gap-2 text-xs text-slate-400">
                        <svg className="h-3.5 w-3.5 text-emerald-500" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2a7 7 0 0 0-7 7v3.1A4 4 0 0 0 3 15.5V18a4 4 0 0 0 4 4h10a4 4 0 0 0 4-4v-2.5a4 4 0 0 0-2-3.4V9a7 7 0 0 0-7-7Zm-5 7a5 5 0 0 1 10 0v3H7V9Zm4 8a1 1 0 1 1 2 0v2a1 1 0 1 1-2 0v-2Z" /></svg>
                        <span className="text-emerald-500">{new Date(entry.timestamp).toLocaleString()} verified</span>
                      </div>
                      <div className="my-2 text-slate-100">{entry.event}</div>
                      <div className="whitespace-pre-wrap break-words text-slate-400">{Object.entries(entry.payload || {}).map(([key, value]) => <div key={key}><span className="text-cyan-400">{key}</span>: <span className="text-emerald-300">{JSON.stringify(value)}</span></div>)}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}

        {view === 'results' && (
          <>
            <div className="mb-6 border-b border-slate-700 pb-5">
              <div>
                <div className="text-xs uppercase tracking-widest text-cyan-400">Offline benchmark</div>
                <h2 className="mt-2 text-2xl font-semibold text-slate-100">Recovery comparison</h2>
                <p className="mt-2 text-sm text-slate-400">Synthetic holdout benchmark against a fixed reminder baseline.</p>
              </div>
            </div>

            <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-3">
              <StatCard label="Model recovered" value={formatCurrency(resultSummary.model_recovered_inr)} tone="primary" />
              <StatCard label="Baseline recovered" value={formatCurrency(resultSummary.baseline_recovered_inr)} tone="neutral" />
              <StatCard label="Improvement" value={`${resultSummary.improvement_pct}%`} tone="warning" />
            </div>

            <div className="bg-slate-800 p-5">
              <div className="flex justify-between border-b border-slate-700/50 py-3"><span className="text-slate-400">Precision</span><strong className="text-slate-100">{resultSummary.precision}</strong></div>
              <div className="flex justify-between border-b border-slate-700/50 py-3"><span className="text-slate-400">Recall</span><strong className="text-slate-100">{resultSummary.recall}</strong></div>
              <div className="flex justify-between py-3"><span className="text-slate-400">Avg. time to recovery</span><strong className="text-slate-100">{resultSummary.avg_days_to_recovery} days</strong></div>
            </div>
          </>
        )}

        <footer className="footer-bar mt-10 flex flex-col gap-2 border-t border-slate-700 pt-4 text-xs text-slate-500 md:flex-row md:items-center md:justify-between">
          <span>CHASR · AI-assisted receivables operations</span>
          <span>Inbound reply → policy decision → auditable action</span>
        </footer>
        {statusMessage && <div className="toast">{statusMessage}</div>}
      </main>
    </div>
  )
}

export default App
