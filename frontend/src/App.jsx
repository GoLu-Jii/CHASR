import { useEffect, useState } from 'react'

const API = import.meta.env.VITE_API_BASE || '/api'
const DEMO = import.meta.env.VITE_DEMO_BASE || '/demo'
const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === 'true'
const money = (v) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(Number(v || 0))
const dateFormat = new Intl.DateTimeFormat('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
const dateTimeFormat = new Intl.DateTimeFormat('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: true })
const formatDate = (value) => {
  if (!value) return 'Not stated'
  const [year, month, day] = String(value).slice(0, 10).split('-').map(Number)
  return dateFormat.format(new Date(year, month - 1, day))
}
const formatDateTime = (value) => {
  const match = String(value || '').match(/(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/)
  return match ? dateTimeFormat.format(new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]), Number(match[4]), Number(match[5]))) : formatDate(value)
}
const go = (path) => { window.history.pushState({}, '', path); window.dispatchEvent(new PopStateEvent('popstate')) }

function Metric({ title, value }) { return <div className="border border-stone-300 bg-white p-5"><div className="text-xs uppercase text-stone-500">{title}</div><strong className="mt-2 block text-2xl">{value}</strong></div> }
function Table({ invoices }) { return <div className="overflow-x-auto border border-stone-300 bg-white"><table className="w-full min-w-[720px] text-left text-sm"><thead className="bg-stone-100 text-xs uppercase text-stone-600"><tr><th>Invoice</th><th>Customer</th><th>Status</th><th>Stage</th><th>Overdue</th><th>Reliability</th><th className="text-right">Amount</th></tr></thead><tbody>{invoices.map(i => <tr key={i.id}><td><button className="font-mono underline" onClick={() => go(`/invoice/${i.id}`)}>#{i.id}</button></td><td>{i.customer_name}</td><td>{i.status.replace('_', ' ')}</td><td>{i.current_stage}</td><td>{i.days_overdue} days</td><td>{Number(i.reliability_score).toFixed(2)}</td><td className="text-right">{money(i.amount)}</td></tr>)}</tbody></table></div> }

function DemoBar({ refresh }) {
  const [clock, setClock] = useState('')
  useEffect(() => { fetch(`${DEMO}/clock`).then(r => r.json()).then(d => setClock(d.now)).catch(() => {}) }, [])
  if (!DEMO_MODE) return null
  const action = async (path, body) => { const r = await fetch(`${DEMO}/${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined }); const d = await r.json(); if (!r.ok) return alert(d.detail || 'Demo action failed'); setClock(d.now || ''); window.dispatchEvent(new Event('demo-clock-changed')); await refresh() }
  return <div className="mb-6 flex flex-wrap items-center gap-2 border border-stone-300 bg-stone-50 p-3 text-sm"><strong>Demo controls</strong><button onClick={() => action('seed')}>Seed data</button><button onClick={() => action('advance-clock', { days: 1 })}>Advance +1 day</button><button onClick={() => action('advance-clock', { days: 7 })}>Advance +7 days</button><button onClick={() => action('reset')}>Reset demo</button>{clock && <span className="ml-auto text-xs text-stone-500">Virtual time: {formatDateTime(clock)}</span>}</div>
}

function Dashboard({ invoices, metrics }) { return <><h1>Collections dashboard</h1><div className="grid gap-3 md:grid-cols-3"><Metric title="Total unpaid" value={money(metrics.total_unpaid_inr)} /><Metric title="Active invoices" value={metrics.active_unpaid_invoices} /><Metric title="Human review" value={metrics.human_review_required} /></div><h2 className="mt-8">Priority watchlist</h2><Table invoices={invoices} /></> }

function InvoiceDetail({ id, refresh }) {
  const [invoice, setInvoice] = useState(null), [audit, setAudit] = useState(null), [notice, setNotice] = useState('')
  const load = async () => { const [a, b] = await Promise.all([fetch(`${API}/invoices/${id}`), fetch(`${API}/invoices/${id}/ledger`)]); setInvoice(await a.json()); setAudit(await b.json()) }
  useEffect(() => { load() }, [id])
  useEffect(() => { window.addEventListener('demo-clock-changed', load); return () => window.removeEventListener('demo-clock-changed', load) }, [id])
  const verify = async () => { const d = await fetch(`${API}/invoices/${id}/verify`, { method: 'POST' }).then(r => r.json()); setNotice(d.chain_integrity_valid ? 'Integrity check passed: every hash and link verified.' : 'Integrity check failed.') }
  const sync = async () => { const r = await fetch(`${API}/invoices/${id}/sync-payment`, { method: 'POST' }); const d = await r.json(); setNotice(r.ok ? `Razorpay sync complete: ${money(d.amount_paid)} received.` : d.detail); await load(); await refresh() }
  const createRazorpay = async () => { const r = await fetch(`${API}/invoices/${id}/razorpay`, { method: 'POST' }); const d = await r.json(); setNotice(r.ok ? `${d.mocked ? 'Mock fallback' : 'Live Razorpay test object'} created: ${d.payment_link}` : d.detail); await load() }
  if (!invoice) return <p>Loading invoice…</p>
  return <><button className="mb-5 text-sm underline" onClick={() => go('/dashboard')}>← Dashboard</button><h1>Invoice #{invoice.id}: {invoice.customer_name}</h1><div className="mb-5 grid gap-3 md:grid-cols-4"><Metric title="Amount" value={money(invoice.amount)} /><Metric title="Status" value={invoice.status} /><Metric title="Reliability" value={Number(invoice.reliability_score).toFixed(2)} /><Metric title="Next action" value={invoice.next_action} /></div><div className="mb-5 flex flex-wrap gap-2"><button onClick={createRazorpay}>Create Razorpay test link</button><button onClick={verify}>Verify integrity</button><button onClick={sync}>Sync Razorpay payment</button></div>{notice && <p className="mb-4 border border-stone-300 bg-stone-50 p-3">{notice}</p>}<div className="mb-6 border border-stone-300 bg-white p-4"><h2>Razorpay test mode</h2><p className="mt-2">Invoice: {invoice.razorpay_invoice_id || 'Not created'}</p><p>Payment link: {invoice.razorpay_payment_link_id || 'Not created'}</p></div><h2>Extracted promises</h2><div className="mb-6 border border-stone-300 bg-white p-4">{invoice.promises?.length ? invoice.promises.map(p => <div className="border-b border-stone-200 py-3 last:border-0" key={p.id}><strong>{p.confidence} commitment</strong><div>{p.amount ? money(p.amount) : 'Amount not stated'} · {formatDate(p.promised_date)} · {p.status}</div><p className="mt-1 text-sm text-stone-600">{p.source_text}</p></div>) : <p>No promises extracted yet.</p>}</div><h2>Append-only audit timeline</h2><div className="border border-stone-300 bg-white">{audit?.ledger?.map(e => <div className="border-b border-stone-200 p-4" key={e.id}><div className="text-xs text-stone-500">{formatDateTime(e.timestamp)} · {e.event}</div><pre className="mt-2 whitespace-pre-wrap text-xs">{JSON.stringify(e.payload, null, 2)}</pre></div>)}</div></>
}

function Simulate({ invoices, refresh }) {
  const defaultReply = 'We are waiting on client disbursement and will clear 50% by Thursday and the rest by month-end.'
  const [id, setId] = useState(''), [text, setText] = useState(defaultReply), [result, setResult] = useState(null), [context, setContext] = useState(null)
  const loadContext = async (invoiceId) => { if (!invoiceId) return; const response = await fetch(`${API}/invoices/${invoiceId}`); if (response.ok) setContext(await response.json()) }
  useEffect(() => { if (!id && invoices[0]) setId(String(invoices[0].id)) }, [invoices, id])
  useEffect(() => { loadContext(id) }, [id])
  const changeInvoice = (invoiceId) => {
    const invoice = invoices.find(i => String(i.id) === invoiceId)
    setId(invoiceId)
    setText(invoice?.last_customer_reply || defaultReply)
    setResult(null)
  }
  const submit = async () => {
    const r = await fetch(`${API}/simulate/reply`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ invoice_id: Number(id), text }) })
    const data = await r.json(); setResult(data)
    if (r.ok) { await refresh(); await loadContext(id) }
  }
  return <><h1>Live promise extraction</h1><p className="mb-5 text-stone-600">The LLM only extracts the customer’s stated commitment. CHASR then applies a deterministic policy to the selected invoice.</p><label>Invoice<select value={id} onChange={e => changeInvoice(e.target.value)}>{invoices.map(i => <option key={i.id} value={i.id}>#{i.id} · {i.customer_name}</option>)}</select></label>{context && <div className="mb-5 grid gap-3 border border-stone-300 bg-white p-4 md:grid-cols-3"><div><span className="text-xs uppercase text-stone-500">Current stage</span><strong className="block">{context.current_stage}</strong></div><div><span className="text-xs uppercase text-stone-500">Reliability</span><strong className="block">{Number(context.reliability_score).toFixed(2)}</strong></div><div><span className="text-xs uppercase text-stone-500">CHASR policy decision</span><strong className="block">{context.next_action}</strong></div><div className="md:col-span-3"><span className="text-xs uppercase text-stone-500">Next outbound message / hold reason</span><p className="mt-1">{context.next_message || 'No automated message is due.'}</p></div></div>}<label>Customer reply<textarea rows="6" value={text} onChange={e => setText(e.target.value)} /></label><button disabled={!id} onClick={submit}>Extract commitment</button>{result && <div className="mt-6 grid gap-4 md:grid-cols-2"><div className="border border-stone-300 bg-white p-5"><h2>LLM structured output</h2>{result.extraction?.commitments?.length ? result.extraction.commitments.map((commitment, index) => <div className="mt-3 border-l-2 border-stone-400 pl-3" key={index}><strong>Commitment {index + 1}</strong><div>Amount: {commitment.amount ? money(commitment.amount) : 'Not stated'}</div><div>Promised date: {formatDate(commitment.promised_date)}</div><div>Confidence: {commitment.confidence || 'vague'}</div></div>) : <p className="mt-3">No clear payment commitment was found.</p>}</div><div className="border border-stone-300 bg-white p-5"><h2>{result.needs_review ? 'Human review required' : 'What CHASR does next'}</h2><p className="mt-3">{context?.next_action || 'Refreshing decision…'}</p><p className="mt-2 text-sm text-stone-600">{context?.next_message || (result.needs_review ? 'The commitment is incomplete, so automation is paused.' : 'The escalation scheduler will apply the policy.')}</p></div></div>}</>
}

function Results() { const [data, setData] = useState(null); useEffect(() => { fetch(`${API}/results`).then(r => r.json()).then(setData) }, []); if (!data) return <p>Loading evaluation…</p>; return <><h1>Held-out batch evaluation</h1><p className="mb-5 text-stone-600">{data.methodology}</p><div className="grid gap-3 md:grid-cols-5"><Metric title="Batch size" value={data.batch_size} /><Metric title="Observed recovered" value={money(data.observed_recovered_inr)} /><Metric title="Adaptive recovered" value={money(data.model_recovered_inr)} /><Metric title="Baseline recovered" value={money(data.baseline_recovered_inr)} /><Metric title="Targeting uplift" value={`${Number(data.improvement_pct || 0).toFixed(1)}%`} /></div><div className="mt-6 grid gap-3 md:grid-cols-2"><Metric title="Precision" value={data.precision} /><Metric title="Recall" value={data.recall} /></div><div className="mt-6 grid gap-4 md:grid-cols-2"><section className="border border-stone-300 bg-white p-5"><h2>Adaptive targets</h2><p>{data.adaptive_target_invoice_ids?.map(i => `#${i}`).join(', ') || 'None'}</p></section><section className="border border-stone-300 bg-white p-5"><h2>Fixed-schedule targets</h2><p>{data.baseline_target_invoice_ids?.map(i => `#${i}`).join(', ') || 'None'}</p></section></div><h2 className="mt-6">Honest exception list</h2><div className="border border-stone-300 bg-white">{data.exceptions?.length ? data.exceptions.map(e => <div className="border-b border-stone-200 p-3" key={e.invoice_id}>#{e.invoice_id} · {e.customer} · {money(e.amount)} — {e.reason}</div>) : <p className="p-3">No exceptions in this held-out batch.</p>}</div></> }

export default function App() {
  const [path, setPath] = useState(window.location.pathname === '/' ? '/dashboard' : window.location.pathname), [invoices, setInvoices] = useState([]), [metrics, setMetrics] = useState({})
  const refresh = async () => { const [i, m] = await Promise.all([fetch(`${API}/invoices`).then(r => r.json()), fetch(`${API}/dashboard`).then(r => r.json())]); setInvoices(i); setMetrics(m) }
  useEffect(() => { refresh(); const h = () => setPath(window.location.pathname); window.addEventListener('popstate', h); return () => window.removeEventListener('popstate', h) }, [])
  const content = path.startsWith('/invoice/') ? <InvoiceDetail id={path.split('/').pop()} refresh={refresh} /> : path === '/simulate' ? <Simulate invoices={invoices} refresh={refresh} /> : path === '/results' ? <Results /> : <Dashboard invoices={invoices} metrics={metrics} />
  return <div className="min-h-screen bg-stone-100 text-stone-900"><header className="border-b border-stone-300 bg-white"><div className="mx-auto flex max-w-6xl flex-wrap items-center gap-5 px-5 py-4"><button className="text-xl font-bold" onClick={() => go('/dashboard')}>CHASR</button><span className="text-sm text-stone-500">B2B revenue recovery</span><nav className="ml-auto flex gap-4 text-sm">{[['/dashboard', 'Dashboard'], ['/simulate', 'Simulate'], ['/results', 'Results']].map(([target, label]) => <button className="underline" key={target} onClick={() => go(target)}>{label}</button>)}</nav></div></header><main className="mx-auto max-w-6xl px-5 py-8"><DemoBar refresh={refresh} />{content}</main></div>
}
