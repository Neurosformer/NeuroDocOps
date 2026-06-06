import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  ClipboardCheck,
  Download,
  FileText,
  History,
  Loader2,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  Upload,
} from "lucide-react";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const sampleDocuments = [
  {
    filename: "claim-form.pdf",
    text: "Claim form for claim number CLM-1001 and policy number POL-42. Loss date 2026-05-01.",
  },
  {
    filename: "incident-report.pdf",
    text: "Incident report for accident with loss date 2026-05-01 at North Bridge Road.",
  },
  {
    filename: "repair-invoice.pdf",
    text: "Repair invoice for vehicle damage. Amount due 1250 USD.",
  },
  {
    filename: "identity.pdf",
    text: "Passport identity document for claimant Amina Rahman.",
  },
];

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const detail = typeof body === "object" && body !== null ? body.detail : body;
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  return body;
}

function useAsyncData(loader, deps) {
  const [state, setState] = useState({ loading: true, error: null, data: null });
  const reload = async () => {
    setState((current) => ({ ...current, loading: true, error: null }));
    try {
      setState({ loading: false, error: null, data: await loader() });
    } catch (error) {
      setState((current) => ({ ...current, loading: false, error: error.message }));
    }
  };
  useEffect(() => {
    reload();
  }, deps);
  return { ...state, reload };
}

function statusLabel(status) {
  return status.replaceAll("_", " ");
}

function StatusBadge({ status }) {
  return <span className={`status status-${status}`}>{statusLabel(status)}</span>;
}

function App() {
  const [route, setRoute] = useState(() => window.location.hash.slice(1) || "/");

  useEffect(() => {
    const onHash = () => setRoute(window.location.hash.slice(1) || "/");
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const navigate = (nextRoute) => {
    window.location.hash = nextRoute;
  };

  const packetMatch = route.match(/^\/packets\/([^/]+)$/);
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">N</div>
          <div>
            <strong>NeuroDocOps</strong>
            <span>Claims Packet Ops</span>
          </div>
        </div>
        <nav>
          <button className={route === "/" ? "active" : ""} onClick={() => navigate("/")}>Dashboard</button>
          <button className={route === "/packets" ? "active" : ""} onClick={() => navigate("/packets")}>Packets</button>
          <button className={route === "/packets/new" ? "active" : ""} onClick={() => navigate("/packets/new")}>New Packet</button>
        </nav>
        <div className="sidebar-note">
          <ShieldCheck size={16} />
          Human approval is required before export.
        </div>
      </aside>
      <main className="content">
        {route === "/" && <Dashboard navigate={navigate} />}
        {route === "/packets" && <PacketsPage navigate={navigate} />}
        {route === "/packets/new" && <NewPacketPage navigate={navigate} />}
        {packetMatch && <PacketDetail packetId={packetMatch[1]} navigate={navigate} />}
      </main>
    </div>
  );
}

function Dashboard({ navigate }) {
  const { data: packets, loading, error, reload } = useAsyncData(() => api("/claim-packets"), []);
  const stats = useMemo(() => {
    const items = packets || [];
    return {
      total: items.length,
      needsReview: items.filter((packet) => packet.status === "needs_review").length,
      approved: items.filter((packet) => packet.status === "approved").length,
      exported: items.filter((packet) => packet.status === "exported").length,
      openTasks: items.reduce((sum, packet) => sum + packet.review_tasks.filter((task) => task.status === "open").length, 0),
    };
  }, [packets]);

  return (
    <section>
      <PageHeader
        eyebrow="Reviewer workspace"
        title="Claims Packet Dashboard"
        description="Classify packets, review evidence, approve exports, and keep an audit trail."
        action={<button className="primary" onClick={() => navigate("/packets/new")}><Plus size={16} /> New Packet</button>}
      />
      <ErrorBanner error={error} />
      <div className="metric-grid">
        <Metric label="Total Packets" value={loading ? "..." : stats.total} icon={FileText} />
        <Metric label="Needs Review" value={loading ? "..." : stats.needsReview} icon={AlertTriangle} tone="warn" />
        <Metric label="Open Tasks" value={loading ? "..." : stats.openTasks} icon={ClipboardCheck} tone="warn" />
        <Metric label="Approved" value={loading ? "..." : stats.approved} icon={CheckCircle2} tone="good" />
        <Metric label="Exported" value={loading ? "..." : stats.exported} icon={Download} tone="info" />
      </div>
      <section className="panel">
        <div className="panel-title">
          <h2>Recent Packets</h2>
          <button className="ghost" onClick={reload}><RefreshCw size={14} /> Refresh</button>
        </div>
        <PacketTable packets={(packets || []).slice(-8).reverse()} navigate={navigate} loading={loading} />
      </section>
    </section>
  );
}

function PacketsPage({ navigate }) {
  const [search, setSearch] = useState("");
  const { data: packets, loading, error, reload } = useAsyncData(() => api("/claim-packets"), []);
  const filtered = (packets || []).filter((packet) => {
    const haystack = `${packet.claim_reference} ${packet.claimant_name} ${packet.loss_type}`.toLowerCase();
    return haystack.includes(search.toLowerCase());
  });
  return (
    <section>
      <PageHeader
        eyebrow="Queue"
        title="Claim Packets"
        description="Packet-first operations view for claim intake, review, and export readiness."
        action={<button className="primary" onClick={() => navigate("/packets/new")}><Plus size={16} /> New Packet</button>}
      />
      <ErrorBanner error={error} />
      <div className="toolbar">
        <div className="searchbox"><Search size={16} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search claim, claimant, or loss type" /></div>
        <button className="ghost" onClick={reload}><RefreshCw size={14} /> Refresh</button>
      </div>
      <section className="panel"><PacketTable packets={filtered} navigate={navigate} loading={loading} /></section>
    </section>
  );
}

function NewPacketPage({ navigate }) {
  const [claimReference, setClaimReference] = useState("CLM-1001");
  const [claimantName, setClaimantName] = useState("Amina Rahman");
  const [lossType, setLossType] = useState("auto");
  const [documents, setDocuments] = useState(sampleDocuments);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const updateDocument = (index, key, value) => {
    setDocuments((current) => current.map((document, documentIndex) => documentIndex === index ? { ...document, [key]: value } : document));
  };
  const createPacket = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const packet = await api("/claim-packets", {
        method: "POST",
        body: JSON.stringify({ claim_reference: claimReference, claimant_name: claimantName, loss_type: lossType, documents }),
      });
      navigate(`/packets/${packet.id}`);
    } catch (apiError) {
      setError(apiError.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section>
      <button className="back" onClick={() => navigate("/packets")}><ArrowLeft size={16} /> Back to packets</button>
      <PageHeader eyebrow="Intake" title="Create Claim Packet" description="The current backend accepts text-based document input. Real multipart upload is a later milestone." />
      <ErrorBanner error={error} />
      <form className="panel form" onSubmit={createPacket}>
        <div className="form-grid">
          <label>Claim Reference<input value={claimReference} onChange={(event) => setClaimReference(event.target.value)} required /></label>
          <label>Claimant Name<input value={claimantName} onChange={(event) => setClaimantName(event.target.value)} required /></label>
          <label>Loss Type<input value={lossType} onChange={(event) => setLossType(event.target.value)} required /></label>
        </div>
        <div className="panel-subtitle"><Upload size={16} /> Documents as OCR/Text Payloads</div>
        {documents.map((document, index) => (
          <div className="document-editor" key={index}>
            <input value={document.filename} onChange={(event) => updateDocument(index, "filename", event.target.value)} placeholder="filename.pdf" required />
            <textarea value={document.text} onChange={(event) => updateDocument(index, "text", event.target.value)} rows={3} required />
          </div>
        ))}
        <div className="form-actions">
          <button type="button" className="ghost" onClick={() => setDocuments([...documents, { filename: "document.pdf", text: "" }])}><Plus size={14} /> Add Document</button>
          <button type="submit" className="primary" disabled={submitting}>{submitting ? <Loader2 className="spin" size={16} /> : <Plus size={16} />} Create Packet</button>
        </div>
      </form>
    </section>
  );
}

function PacketDetail({ packetId, navigate }) {
  const [exportPayload, setExportPayload] = useState(null);
  const [actionError, setActionError] = useState(null);
  const { data: packet, loading, error, reload } = useAsyncData(() => api(`/claim-packets/${packetId}`), [packetId]);
  const { data: audit, reload: reloadAudit } = useAsyncData(() => api(`/claim-packets/${packetId}/audit`), [packetId]);

  const runAction = async (label, action) => {
    setActionError(null);
    try {
      const result = await action();
      if (label === "export") setExportPayload(result);
      await reload();
      await reloadAudit();
    } catch (apiError) {
      setActionError(apiError.message);
    }
  };

  if (loading) return <Loading />;
  if (error) return <ErrorBanner error={error} />;
  if (!packet) return null;

  const openTasks = packet.review_tasks.filter((task) => task.status === "open");
  const canExport = packet.status === "approved" && openTasks.length === 0;

  return (
    <section>
      <button className="back" onClick={() => navigate("/packets")}><ArrowLeft size={16} /> Back to packets</button>
      <PageHeader
        eyebrow={packet.claim_reference}
        title={packet.claimant_name}
        description={`${packet.loss_type} claim · ${packet.documents.length} documents · ${openTasks.length} open review tasks`}
        action={<StatusBadge status={packet.status} />}
      />
      <ErrorBanner error={actionError} />
      <div className="workflow-actions">
        <button onClick={() => runAction("classify", () => api(`/claim-packets/${packetId}/classify`, { method: "POST" }))}>Classify</button>
        <button onClick={() => runAction("extract", () => api(`/claim-packets/${packetId}/extract`, { method: "POST" }))}>Extract</button>
        <button onClick={() => runAction("checklist", () => api(`/claim-packets/${packetId}/checklist`, { method: "POST" }))}>Checklist</button>
        <button onClick={() => runAction("review", () => api(`/claim-packets/${packetId}/review`, { method: "POST", body: JSON.stringify({ decision: "request_changes", reviewer: "claims.ops@example.com", notes: "Needs more evidence." }) }))}>Request Changes</button>
        <button onClick={() => runAction("review", () => api(`/claim-packets/${packetId}/review`, { method: "POST", body: JSON.stringify({ decision: "approve", reviewer: "claims.ops@example.com", notes: "Validated for export." }) }))}>Approve</button>
        <button className="primary" disabled={!canExport} onClick={() => runAction("export", () => api(`/claim-packets/${packetId}/export`, { method: "POST" }))}>Export</button>
      </div>
      {!canExport && <div className="guardrail"><ShieldCheck size={16} /> Export stays disabled until the backend reports approved status and no open review tasks.</div>}
      <div className="detail-grid">
        <section className="panel wide"><h2>Documents And Fields</h2><Documents documents={packet.documents} /></section>
        <section className="panel"><h2>Checklist</h2><Checklist items={packet.checklist} /></section>
        <section className="panel"><h2>Review Tasks</h2><ReviewTasks tasks={packet.review_tasks} /></section>
        <section className="panel"><h2><History size={16} /> Audit Timeline</h2><Audit events={audit || []} /></section>
      </div>
      {exportPayload && <section className="panel"><h2>Export Payload</h2><pre>{JSON.stringify(exportPayload, null, 2)}</pre></section>}
    </section>
  );
}

function Documents({ documents }) {
  return <div className="documents">{documents.map((document) => <article className="document-card" key={document.id}><div className="document-head"><FileText size={18} /><div><strong>{document.filename}</strong><span>{statusLabel(document.document_type)} · {document.ocr_provider || "not parsed"}</span></div></div><div className="field-table">{document.extracted_fields.length === 0 ? <p className="muted">No fields extracted yet.</p> : document.extracted_fields.map((field) => <div className="field-row" key={`${document.id}-${field.name}`}><span>{field.name}</span><strong>{field.value}</strong><em>{Math.round(field.confidence * 100)}%</em><small>{field.citation?.snippet}</small></div>)}</div></article>)}</div>;
}

function Checklist({ items }) {
  if (!items.length) return <p className="muted">Run checklist to evaluate evidence completeness.</p>;
  return <div className="list-stack">{items.map((item) => <div className="list-item" key={item.name}><StatusBadge status={item.status} /><strong>{item.name}</strong><span>{item.detail}</span></div>)}</div>;
}

function ReviewTasks({ tasks }) {
  if (!tasks.length) return <p className="muted">No review tasks yet.</p>;
  return <div className="list-stack">{tasks.map((task) => <div className="list-item" key={task.id}><StatusBadge status={task.status} /><strong>{task.reason}</strong><span>{task.reviewer || "Unassigned"}{task.notes ? ` · ${task.notes}` : ""}</span></div>)}</div>;
}

function Audit({ events }) {
  if (!events.length) return <p className="muted">No audit events yet.</p>;
  return <div className="list-stack">{events.map((event) => <div className="list-item" key={event.id}><strong>{event.action}</strong><span>{event.actor} · {new Date(event.created_at).toLocaleString()}</span></div>)}</div>;
}

function PacketTable({ packets, navigate, loading }) {
  if (loading) return <Loading />;
  if (!packets.length) return <div className="empty"><FileText size={32} /><strong>No packets yet</strong><span>Create a sample claim packet to start the workflow.</span></div>;
  return <div className="table-wrap"><table><thead><tr><th>Claim</th><th>Claimant</th><th>Loss Type</th><th>Documents</th><th>Open Tasks</th><th>Status</th></tr></thead><tbody>{packets.map((packet) => <tr key={packet.id} onClick={() => navigate(`/packets/${packet.id}`)}><td>{packet.claim_reference}</td><td>{packet.claimant_name}</td><td>{packet.loss_type}</td><td>{packet.documents.length}</td><td>{packet.review_tasks.filter((task) => task.status === "open").length}</td><td><StatusBadge status={packet.status} /></td></tr>)}</tbody></table></div>;
}

function PageHeader({ eyebrow, title, description, action }) {
  return <header className="page-header"><div><p>{eyebrow}</p><h1>{title}</h1><span>{description}</span></div>{action}</header>;
}

function Metric({ label, value, icon: Icon, tone = "neutral" }) {
  return <div className={`metric metric-${tone}`}><Icon size={20} /><span>{label}</span><strong>{value}</strong></div>;
}

function ErrorBanner({ error }) {
  if (!error) return null;
  return <div className="error"><AlertTriangle size={16} /> {error}</div>;
}

function Loading() {
  return <div className="loading"><Loader2 className="spin" size={18} /> Loading...</div>;
}

createRoot(document.getElementById("root")).render(<App />);
