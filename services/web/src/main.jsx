import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  ClipboardCheck,
  Database,
  Download,
  Eye,
  EyeOff,
  FileText,
  History,
  Loader2,
  LogOut,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  Upload,
  User,
  Users,
  Zap,
} from "lucide-react";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const SESSION_KEY = "neurodocops.session";
const THEME_KEY = "neurodocops.theme";

const THEMES = [
  { id: "graphite", label: "Graphite", note: "Neutral dark operations console" },
  { id: "ocean", label: "Ocean", note: "Cool blue evidence console" },
  { id: "primer", label: "Primer", note: "Semantic product color system" },
  { id: "spotify", label: "Spotify", note: "Deep black green operations theme" },
];

const ROLES = {
  admin: {
    label: "Admin",
    email: "admin@neurodocops.local",
    password: "Admin@123",
    summary: "Full system access, export approval, audit visibility, and operations control.",
    permissions: ["packet:create", "packet:read", "document:upload", "packet:process", "review:complete", "export:packet", "audit:read", "job:read"],
  },
  manager: {
    label: "Manager",
    email: "manager@neurodocops.local",
    password: "Manager@123",
    summary: "Owns operational queue, approval flow, export release, and team throughput.",
    permissions: ["packet:create", "packet:read", "document:upload", "packet:process", "review:complete", "export:packet", "audit:read", "job:read"],
  },
  reviewer: {
    label: "Reviewer",
    email: "reviewer@neurodocops.local",
    password: "Reviewer@123",
    summary: "Processes evidence, resolves review exceptions, and approves packets without export release.",
    permissions: ["packet:create", "packet:read", "document:upload", "packet:process", "review:complete", "audit:read", "job:read"],
  },
  auditor: {
    label: "Auditor",
    email: "auditor@neurodocops.local",
    password: "Auditor@123",
    summary: "Read-only evidence, decisions, audit trail, and job status visibility.",
    permissions: ["packet:read", "audit:read", "job:read"],
  },
  integration: {
    label: "Integration",
    email: "integration@neurodocops.local",
    password: "Integration@123",
    summary: "Service-account style intake, processing, export, and job polling.",
    permissions: ["packet:create", "packet:read", "packet:process", "export:packet", "job:read"],
  },
};

const PERSONAS = {
  admin: { title: "Control Room Admin", initials: "AD", bg: "#121826", accent: "#ef4444", soft: "#7f1d1d" },
  manager: { title: "Claims Ops Manager", initials: "MG", bg: "#0f1b2d", accent: "#38bdf8", soft: "#1d4ed8" },
  reviewer: { title: "Evidence Reviewer", initials: "RV", bg: "#0d2119", accent: "#34d399", soft: "#047857" },
  auditor: { title: "Audit Observer", initials: "AU", bg: "#21190f", accent: "#f59e0b", soft: "#92400e" },
  integration: { title: "API Integration", initials: "IN", bg: "#1a1230", accent: "#c084fc", soft: "#6d28d9" },
};

function personaAvatar(role) {
  const persona = PERSONAS[role] || PERSONAS.manager;
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="96" height="96" viewBox="0 0 96 96">
      <rect width="96" height="96" fill="${persona.bg}"/>
      <path d="M0 72 L96 30 L96 96 L0 96 Z" fill="${persona.soft}" opacity="0.42"/>
      <rect x="12" y="12" width="72" height="72" fill="none" stroke="${persona.accent}" stroke-width="2" opacity="0.72"/>
      <rect x="22" y="22" width="18" height="18" fill="${persona.accent}" opacity="0.92"/>
      <rect x="56" y="22" width="18" height="18" fill="${persona.accent}" opacity="0.28"/>
      <rect x="22" y="56" width="18" height="18" fill="${persona.accent}" opacity="0.28"/>
      <rect x="56" y="56" width="18" height="18" fill="${persona.accent}" opacity="0.92"/>
      <path d="M40 31 H56 M31 40 V56 M56 65 H40 M65 56 V40" stroke="#ffffff" stroke-width="2" opacity="0.36"/>
      <text x="48" y="53" text-anchor="middle" font-family="monospace" font-size="17" font-weight="900" fill="#ffffff">${persona.initials}</text>
    </svg>`;
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

const sampleDocuments = [
  { filename: "claim-form.pdf", text: "Claim form for claim number CLM-1001 and policy number POL-42. Loss date 2026-05-01." },
  { filename: "incident-report.pdf", text: "Incident report for accident with loss date 2026-05-01 at North Bridge Road." },
  { filename: "repair-invoice.pdf", text: "Repair invoice for vehicle damage. Amount due 1250 USD." },
  { filename: "identity.pdf", text: "Passport identity document for claimant Amina Rahman." },
];

async function api(path, options = {}) {
  const isFormData = options.body instanceof FormData;
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { ...(isFormData ? {} : { "Content-Type": "application/json" }), ...(options.headers || {}) },
  });
  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const detail = typeof body === "object" && body !== null ? body.detail : body;
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  return body;
}

function authHeaders(session) {
  return { "X-Actor": session.email, "X-Role": session.role };
}

function can(session, permission) {
  return Boolean(session && ROLES[session.role]?.permissions.includes(permission));
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
  useEffect(() => { reload(); }, deps);
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
  const [session, setSession] = useState(() => {
    try { return JSON.parse(localStorage.getItem(SESSION_KEY)); } catch { return null; }
  });
  const [theme, setTheme] = useState(() => {
    const savedTheme = localStorage.getItem(THEME_KEY);
    if (savedTheme === "paper") return "spotify";
    return THEMES.some((item) => item.id === savedTheme) ? savedTheme : THEMES[0].id;
  });

  useEffect(() => {
    const onHash = () => setRoute(window.location.hash.slice(1) || "/");
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

  const navigate = (nextRoute) => { window.location.hash = nextRoute; };
  const cycleTheme = () => {
    const currentIndex = THEMES.findIndex((item) => item.id === theme);
    setTheme(THEMES[((currentIndex < 0 ? 0 : currentIndex) + 1) % THEMES.length].id);
  };
  const signIn = (nextSession) => {
    localStorage.setItem(SESSION_KEY, JSON.stringify(nextSession));
    setSession(nextSession);
    navigate("/");
  };
  const signOut = () => {
    localStorage.removeItem(SESSION_KEY);
    setSession(null);
    navigate("/");
  };

  if (!session) return <SignInPage onSignIn={signIn} theme={theme} onCycleTheme={cycleTheme} />;

  const packetMatch = route.match(/^\/packets\/([^/]+)$/);
  return (
    <div className="app-shell">
      <Nav route={route} navigate={navigate} session={session} onSignOut={signOut} theme={theme} onCycleTheme={cycleTheme} />
      <main className="content">
        {route === "/" && <Dashboard navigate={navigate} session={session} />}
        {route === "/system" && <SystemPage session={session} />}
        {route === "/packets" && <PacketsPage navigate={navigate} session={session} />}
        {route === "/packets/new" && <NewPacketPage navigate={navigate} session={session} />}
        {packetMatch && <PacketDetail packetId={packetMatch[1]} navigate={navigate} session={session} />}
      </main>
    </div>
  );
}

function SignInPage({ onSignIn, theme, onCycleTheme }) {
  const [email, setEmail] = useState(ROLES.manager.email);
  const [password, setPassword] = useState(ROLES.manager.password);
  const [selectedRole, setSelectedRole] = useState("manager");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const selectRole = (role) => {
    setSelectedRole(role);
    setEmail(ROLES[role].email);
    setPassword(ROLES[role].password);
    setError(null);
  };

  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    await new Promise((resolve) => setTimeout(resolve, 180));
    const role = Object.keys(ROLES).find((key) => ROLES[key].email === email.trim().toLowerCase());
    if (!role || password !== ROLES[role].password) {
      setLoading(false);
      setError("Use one of the local-dev demo identities. This is wired to API RBAC headers, not production auth.");
      return;
    }
    onSignIn({ email: ROLES[role].email, role, name: ROLES[role].label });
  };

  return (
    <main className="signin-shell">
      <section className="signin-copy">
        <button className="theme-switch theme-switch-login" type="button" onClick={onCycleTheme}>
          <Zap size={14} /> Theme: {THEMES.find((item) => item.id === theme)?.label}
        </button>
        <div className="brand large"><div className="brand-mark"><Database size={20} /></div><div><strong>NeuroDocOps</strong><span>Evidence operations console</span></div></div>
        <h1>Sign in by responsibility, not by decoration.</h1>
        <p>Local-dev RBAC session for claim packet operations. The selected identity is sent as <code>X-Actor</code> and <code>X-Role</code> to the real FastAPI backend.</p>
        <div className="trust-grid">
          <div><ShieldCheck size={18} /><strong>Permission-gated</strong><span>Actions render from the active role matrix.</span></div>
          <div><History size={18} /><strong>Auditable</strong><span>Review and export calls carry actor identity.</span></div>
          <div><Zap size={18} /><strong>Operational</strong><span>No paid OCR/model calls are enabled by this login.</span></div>
        </div>
      </section>
      <section className="signin-card">
        <p className="eyebrow">Local Dev Login</p>
        <h2>Choose a workspace role</h2>
        <div className="role-grid">
          {Object.entries(ROLES).map(([role, details]) => (
            <button key={role} type="button" className={selectedRole === role ? "role-card active" : "role-card"} onClick={() => selectRole(role)}>
              <strong>{details.label}</strong><span>{details.summary}</span>
            </button>
          ))}
        </div>
        <form onSubmit={submit} className="login-form">
          <label>Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
          <label>Password<div className="password-field"><input type={showPassword ? "text" : "password"} value={password} onChange={(event) => setPassword(event.target.value)} required /><button type="button" onClick={() => setShowPassword(!showPassword)}>{showPassword ? <EyeOff size={15} /> : <Eye size={15} />}</button></div></label>
          <ErrorBanner error={error} />
          <button className="primary full" type="submit" disabled={loading}>{loading ? <Loader2 className="spin" size={16} /> : <User size={16} />} Sign In</button>
        </form>
      </section>
    </main>
  );
}

function Nav({ route, navigate, session, onSignOut, theme, onCycleTheme }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const persona = PERSONAS[session.role] || PERSONAS.manager;
  useEffect(() => {
    const handler = (event) => { if (ref.current && !ref.current.contains(event.target)) setOpen(false); };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);
  const links = [
    ["/", "Dashboard"],
    ["/system", "System"],
    ["/packets", "Claims"],
    ...(can(session, "packet:create") ? [["/packets/new", "New Packet"]] : []),
  ];
  return (
    <header className="topnav">
      <button className="brand nav-brand" onClick={() => navigate("/")}><div className="brand-mark"><Database size={16} /></div><div><strong>NeuroDocOps</strong><span>by Neurosformer</span></div></button>
      <nav className="nav-center">{links.map(([href, label]) => <button key={href} className={route === href ? "active" : ""} onClick={() => navigate(href)}>{label}</button>)}</nav>
      <div className="nav-actions">
        <button className="theme-switch" type="button" onClick={onCycleTheme} title={THEMES.find((item) => item.id === theme)?.note}>
          <Zap size={14} /> {THEMES.find((item) => item.id === theme)?.label}
        </button>
        <div className="account" ref={ref}>
          <button className="account-button" onClick={() => setOpen(!open)}>
            <img className="persona-avatar" src={personaAvatar(session.role)} alt={`${session.name} profile`} />
            <span className="account-copy"><strong>{session.name}</strong><small>{persona.title}</small></span>
            <span className="role-pill">{session.role}</span>
            <ChevronDown size={14} />
          </button>
          {open && (
            <div className="account-menu">
              <div className="account-menu-head">
                <img className="persona-avatar large" src={personaAvatar(session.role)} alt={`${session.name} profile`} />
                <section>
                  <strong>{session.name}</strong>
                  <small>{session.email}</small>
                  <span>{persona.title}</span>
                </section>
              </div>
              <button onClick={onSignOut}><LogOut size={14} /> Sign out</button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

function Dashboard({ navigate, session }) {
  const { data: packets, loading, error, reload } = useAsyncData(() => api("/claim-packets", { headers: authHeaders(session) }), [session.email, session.role]);
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
      <PageHeader eyebrow={`${session.name} workspace`} title="Operations Dashboard" description={ROLES[session.role].summary} action={can(session, "packet:create") && <button className="primary" onClick={() => navigate("/packets/new")}><Plus size={16} /> Intake Packet</button>} />
      <ErrorBanner error={error} />
      <RoleConsole session={session} stats={stats} />
      <div className="metric-grid">
        <Metric label="Total Packets" value={loading ? "..." : stats.total} icon={FileText} />
        <Metric label="Needs Review" value={loading ? "..." : stats.needsReview} icon={AlertTriangle} tone="warn" />
        <Metric label="Open Tasks" value={loading ? "..." : stats.openTasks} icon={ClipboardCheck} tone="warn" />
        <Metric label="Approved" value={loading ? "..." : stats.approved} icon={CheckCircle2} tone="good" />
        <Metric label="Exported" value={loading ? "..." : stats.exported} icon={Download} tone="info" />
      </div>
      <PermissionMatrix session={session} />
      <section className="panel"><div className="panel-title"><h2>Recent Evidence Packets</h2><button className="ghost" onClick={reload}><RefreshCw size={14} /> Refresh</button></div><PacketTable packets={(packets || []).slice(-8).reverse()} navigate={navigate} loading={loading} /></section>
    </section>
  );
}

function SystemPage({ session }) {
  const { data: readiness, loading, error, reload } = useAsyncData(() => api("/ready"), []);
  return (
    <section>
      <PageHeader eyebrow="Control plane" title="Live System Status" description={`Standalone infrastructure readiness for ${session.name}. This page reads the live /ready endpoint and provider registry.`} />
      <SystemStatus readiness={readiness} loading={loading} error={error} reload={reload} standalone />
    </section>
  );
}

function SystemStatus({ readiness, loading, error, reload, standalone = false }) {
  const providers = readiness?.providers || [];
  const implemented = providers.filter((provider) => provider.implemented).length;
  const paidEnabled = providers.filter((provider) => provider.paid && provider.live_enabled).length;
  const summary = [
    ["API Readiness", loading ? "checking" : readiness?.status || "unknown", CheckCircle2],
    ["Service", readiness?.service || "api", Database],
    ["Implemented Providers", loading ? "..." : `${implemented}/${providers.length}`, ClipboardCheck],
    ["Paid Live Providers", loading ? "..." : paidEnabled, AlertTriangle],
  ];
  return (
    <section className={standalone ? "panel system-panel system-panel-standalone" : "panel system-panel"}>
      <div className="panel-title">
        <h2><Database size={16} /> {standalone ? "Readiness And Providers" : "Live System Status"}</h2>
        <button className="ghost" onClick={reload}><RefreshCw size={14} /> Refresh</button>
      </div>
      {error && <ErrorBanner error={error} />}
      <div className="system-summary">
        {summary.map(([label, value, Icon]) => <div key={label}><span className="summary-icon"><Icon size={16} /></span><span>{label}</span><strong>{value}</strong></div>)}
      </div>
      <div className="provider-list">
        {loading && <p className="muted">Checking repository, queue, object store, and provider registry.</p>}
        {!loading && providers.map((provider) => (
          <div className="provider-row" key={`${provider.kind}-${provider.name}`}>
            <span className="provider-icon"><ProviderIcon provider={provider} /></span>
            <div><strong>{provider.kind}</strong><span>{provider.name}{provider.adapter ? ` · ${provider.adapter}` : ""}</span></div>
            <StatusBadge status={provider.implemented ? "ready" : "open"} />
            <span className={provider.paid ? "provider-flag warn" : "provider-flag good"}>{provider.tier}</span>
            <span className={provider.live_enabled ? "provider-flag warn" : "provider-flag"}>{provider.live_enabled ? "live" : "local"}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function ProviderIcon({ provider }) {
  const icons = {
    ocr: Eye,
    extraction: FileText,
    reasoning: Zap,
    search: Search,
    auth: ShieldCheck,
    telemetry: History,
    secrets: Database,
  };
  const Icon = icons[provider.kind] || Database;
  return <Icon size={16} />;
}

function PermissionMatrix({ session }) {
  const permissions = ROLES[session.role]?.permissions || [];
  return (
    <section className="panel permissions-panel">
      <div className="panel-title"><h2><ShieldCheck size={16} /> Active RBAC Contract</h2></div>
      <p className="muted">These are the exact permissions sent through <code>X-Role: {session.role}</code>. Disabled buttons in the app follow this list and the API enforces it again server-side.</p>
      <div className="permission-chips">
        {permissions.map((permission) => <span key={permission}><CheckCircle2 size={12} /> {permission}</span>)}
      </div>
    </section>
  );
}

function RoleConsole({ session, stats }) {
  const cards = [
    can(session, "export:packet") ? ["Export Authority", "Can release approved packets", ShieldCheck, "good"] : ["Export Locked", "This role cannot release packets", ShieldCheck, "warn"],
    can(session, "review:complete") ? ["Review Actions", "Can approve or request changes", ClipboardCheck, "info"] : ["Read-only Review", "Can inspect decisions only", Eye, "neutral"],
    can(session, "packet:create") ? ["Intake Access", "Can create evidence packets", Upload, "info"] : ["Intake Locked", "Cannot create packets", Upload, "warn"],
    ["Current Workload", `${stats.openTasks || 0} open review tasks`, Users, "neutral"],
  ];
  return <section className="role-console">{cards.map(([title, text, Icon, tone]) => <div className={`role-tile role-${tone}`} key={title}><span className="icon-cell"><Icon size={18} /></span><strong>{title}</strong><span>{text}</span></div>)}</section>;
}

function PacketsPage({ navigate, session }) {
  const [search, setSearch] = useState("");
  const { data: packets, loading, error, reload } = useAsyncData(() => api("/claim-packets", { headers: authHeaders(session) }), [session.email, session.role]);
  const filtered = (packets || []).filter((packet) => `${packet.claim_reference} ${packet.claimant_name} ${packet.loss_type}`.toLowerCase().includes(search.toLowerCase()));
  return <section><PageHeader eyebrow="Queue" title="Evidence Packets" description="Role-filtered operations queue for intake, review, audit, and export readiness." action={can(session, "packet:create") && <button className="primary" onClick={() => navigate("/packets/new")}><Plus size={16} /> Create Packet</button>} /><ErrorBanner error={error} /><div className="toolbar"><div className="searchbox"><Search size={16} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search claim, claimant, or loss type" /></div><button className="ghost" onClick={reload}><RefreshCw size={14} /> Refresh</button></div><section className="panel"><PacketTable packets={filtered} navigate={navigate} loading={loading} /></section></section>;
}

function NewPacketPage({ navigate, session }) {
  const [claimReference, setClaimReference] = useState("CLM-1001");
  const [claimantName, setClaimantName] = useState("Amina Rahman");
  const [lossType, setLossType] = useState("auto");
  const [documents, setDocuments] = useState(sampleDocuments);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  if (!can(session, "packet:create")) return <Forbidden navigate={navigate} title="Packet intake is not available" message="Your role can inspect evidence but cannot create new claim packets." />;
  const updateDocument = (index, key, value) => setDocuments((current) => current.map((document, documentIndex) => documentIndex === index ? { ...document, [key]: value } : document));
  const createPacket = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const packet = await api("/claim-packets", { method: "POST", headers: authHeaders(session), body: JSON.stringify({ claim_reference: claimReference, claimant_name: claimantName, loss_type: lossType, documents }) });
      navigate(`/packets/${packet.id}`);
    } catch (apiError) { setError(apiError.message); } finally { setSubmitting(false); }
  };
  return <section><button className="back" onClick={() => navigate("/packets")}><ArrowLeft size={16} /> Back to packets</button><PageHeader eyebrow="Intake" title="Create Evidence Packet" description="Text-payload intake backed by the live API. Multipart source upload remains backend-only for now." /><ErrorBanner error={error} /><form className="panel form" onSubmit={createPacket}><div className="form-grid"><label>Claim Reference<input value={claimReference} onChange={(event) => setClaimReference(event.target.value)} required /></label><label>Claimant Name<input value={claimantName} onChange={(event) => setClaimantName(event.target.value)} required /></label><label>Loss Type<input value={lossType} onChange={(event) => setLossType(event.target.value)} required /></label></div><div className="panel-subtitle"><Upload size={16} /> Document Text Payloads</div>{documents.map((document, index) => <div className="document-editor" key={index}><input value={document.filename} onChange={(event) => updateDocument(index, "filename", event.target.value)} placeholder="filename.pdf" required /><textarea value={document.text} onChange={(event) => updateDocument(index, "text", event.target.value)} rows={3} required /></div>)}<div className="form-actions"><button type="button" className="ghost" onClick={() => setDocuments([...documents, { filename: "document.pdf", text: "" }])}><Plus size={14} /> Add Document</button><button type="submit" className="primary" disabled={submitting}>{submitting ? <Loader2 className="spin" size={16} /> : <Plus size={16} />} Create Packet</button></div></form></section>;
}

function PacketDetail({ packetId, navigate, session }) {
  const [exportPayload, setExportPayload] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [jobStatus, setJobStatus] = useState(null);
  const requestHeaders = authHeaders(session);
  const { data: packet, loading, error, reload } = useAsyncData(() => api(`/claim-packets/${packetId}`, { headers: requestHeaders }), [packetId, session.email, session.role]);
  const { data: audit, reload: reloadAudit } = useAsyncData(() => api(`/claim-packets/${packetId}/audit`, { headers: requestHeaders }), [packetId, session.email, session.role]);
  const runAction = async (label, permission, action) => {
    if (!can(session, permission)) { setActionError(`Your ${session.role} role lacks ${permission}.`); return; }
    setActionError(null);
    try { const result = await action(); if (label === "export") setExportPayload(result); await reload(); await reloadAudit(); } catch (apiError) { setActionError(apiError.message); }
  };
  const runQueuedProcess = async () => {
    if (!can(session, "packet:process")) { setActionError(`Your ${session.role} role lacks packet:process.`); return; }
    setActionError(null);
    setJobStatus("queued");
    try {
      const job = await api(`/claim-packets/${packetId}/process`, { method: "POST", headers: requestHeaders, body: JSON.stringify({ steps: ["classify", "extract", "checklist"] }) });
      let current = job;
      while (["queued", "running"].includes(current.status)) {
        setJobStatus(current.status);
        await new Promise((resolve) => setTimeout(resolve, 1000));
        current = await api(`/jobs/${job.id}`, { headers: requestHeaders });
      }
      setJobStatus(current.status);
      if (current.status === "failed") throw new Error(current.error || "Packet processing job failed.");
      await reload();
      await reloadAudit();
    } catch (apiError) { setActionError(apiError.message); }
  };
  if (loading) return <Loading />;
  if (error) return <ErrorBanner error={error} />;
  if (!packet) return null;
  const openTasks = packet.review_tasks.filter((task) => task.status === "open");
  const canExportPacket = packet.status === "approved" && openTasks.length === 0 && can(session, "export:packet");
  return (
    <section>
      <button className="back" onClick={() => navigate("/packets")}><ArrowLeft size={16} /> Back to packets</button>
      <PageHeader eyebrow={packet.claim_reference} title={packet.claimant_name} description={`${packet.loss_type} claim · ${packet.documents.length} documents · ${openTasks.length} open review tasks`} action={<StatusBadge status={packet.status} />} />
      <ErrorBanner error={actionError} />
      <div className="workflow-actions">
        <button className="primary" onClick={runQueuedProcess} disabled={!can(session, "packet:process") || jobStatus === "queued" || jobStatus === "running"}>{jobStatus === "queued" || jobStatus === "running" ? <Loader2 className="spin" size={14} /> : <RefreshCw size={14} />} Run Processing Job</button>
        <button disabled={!can(session, "packet:process")} onClick={() => runAction("classify", "packet:process", () => api(`/claim-packets/${packetId}/classify`, { method: "POST", headers: requestHeaders }))}>Classify</button>
        <button disabled={!can(session, "packet:process")} onClick={() => runAction("extract", "packet:process", () => api(`/claim-packets/${packetId}/extract`, { method: "POST", headers: requestHeaders }))}>Extract</button>
        <button disabled={!can(session, "packet:process")} onClick={() => runAction("checklist", "packet:process", () => api(`/claim-packets/${packetId}/checklist`, { method: "POST", headers: requestHeaders }))}>Checklist</button>
        <button disabled={!can(session, "review:complete")} onClick={() => runAction("review", "review:complete", () => api(`/claim-packets/${packetId}/review`, { method: "POST", headers: requestHeaders, body: JSON.stringify({ decision: "request_changes", reviewer: session.email, notes: "Needs more evidence." }) }))}>Request Changes</button>
        <button disabled={!can(session, "review:complete")} onClick={() => runAction("review", "review:complete", () => api(`/claim-packets/${packetId}/review`, { method: "POST", headers: requestHeaders, body: JSON.stringify({ decision: "approve", reviewer: session.email, notes: "Validated for export." }) }))}>Approve</button>
        <button className="primary" disabled={!canExportPacket} onClick={() => runAction("export", "export:packet", () => api(`/claim-packets/${packetId}/export`, { method: "POST", headers: requestHeaders }))}>Export</button>
      </div>
      {jobStatus && <div className="guardrail"><RefreshCw size={16} /> Last worker job status: {statusLabel(jobStatus)}</div>}
      {!canExportPacket && <div className="guardrail"><ShieldCheck size={16} /> Export requires approved status, no open review tasks, and an export-capable role.</div>}
      <div className="detail-grid">
        <section className="panel wide"><h2>Evidence Documents & Fields</h2><Documents packetId={packetId} documents={packet.documents} session={session} onChanged={async () => { await reload(); await reloadAudit(); }} /></section>
        <section className="panel"><h2>Evidence Checklist</h2><Checklist items={packet.checklist} /></section>
        <section className="panel"><h2>Review Exceptions</h2><ReviewTasks tasks={packet.review_tasks} /></section>
        <section className="panel"><h2><History size={16} /> Decision Timeline</h2><Audit events={audit || []} /></section>
      </div>
      {exportPayload && <section className="panel"><h2>Approved Export Payload</h2><pre>{JSON.stringify(exportPayload, null, 2)}</pre></section>}
    </section>
  );
}

function Forbidden({ navigate, title, message }) {
  return <section className="forbidden"><ShieldCheck size={34} /><h1>{title}</h1><p>{message}</p><button className="primary" onClick={() => navigate("/")}><ArrowRight size={16} /> Back to dashboard</button></section>;
}

function Documents({ packetId, documents, session, onChanged }) {
  const [error, setError] = useState(null);
  const openSource = async (document) => {
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/claim-packets/${packetId}/documents/${document.id}/source`, { headers: authHeaders(session) });
      if (!response.ok) throw new Error(await response.text() || `Source request failed: ${response.status}`);
      const blob = await response.blob();
      window.open(URL.createObjectURL(blob), "_blank", "noopener,noreferrer");
    } catch (sourceError) { setError(sourceError.message); }
  };
  return <div className="documents"><ErrorBanner error={error} />{documents.map((document) => <article className="document-card" key={document.id}><div className="document-head"><FileText size={18} /><div><strong>{document.filename}</strong><span>{statusLabel(document.document_type)} · {document.ocr_provider || "not parsed"}</span></div>{document.source_object && <button className="source-action" onClick={() => openSource(document)}><Eye size={14} /> Open Source</button>}</div><div className="field-table">{document.extracted_fields.length === 0 ? <p className="muted">No fields extracted yet.</p> : document.extracted_fields.map((field) => <FieldRow key={`${document.id}-${field.name}`} packetId={packetId} document={document} field={field} session={session} onChanged={onChanged} />)}</div></article>)}</div>;
}

function FieldRow({ packetId, document, field, session, onChanged }) {
  const [value, setValue] = useState(field.value);
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const canCorrect = can(session, "review:complete");
  const changed = value !== field.value;
  const saveCorrection = async () => {
    setSaving(true);
    setError(null);
    try {
      await api(`/claim-packets/${packetId}/documents/${document.id}/fields/${encodeURIComponent(field.name)}/correct`, { method: "POST", headers: authHeaders(session), body: JSON.stringify({ value, reviewer: session.email, notes: notes || null }) });
      setNotes("");
      await onChanged();
    } catch (apiError) { setError(apiError.message); } finally { setSaving(false); }
  };
  return <div className="field-row"><span>{field.name}</span><input value={value} onChange={(event) => setValue(event.target.value)} disabled={!canCorrect} aria-label={`Correct ${field.name}`} /><em>Confidence {Math.round(field.confidence * 100)}%</em>{field.citation?.snippet && <small>Citation: {field.citation.snippet}</small>}{canCorrect && <div className="field-correction"><input value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Correction note for audit trail" /><button onClick={saveCorrection} disabled={!changed || saving}>{saving ? <Loader2 className="spin" size={14} /> : <CheckCircle2 size={14} />} Save Correction</button></div>}<ErrorBanner error={error} /></div>;
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
  return <div className={`metric metric-${tone}`}><span className="icon-cell"><Icon size={20} /></span><span>{label}</span><strong>{value}</strong></div>;
}

function ErrorBanner({ error }) {
  if (!error) return null;
  return <div className="error"><AlertTriangle size={16} /> {error}</div>;
}

function Loading() {
  return <div className="loading"><Loader2 className="spin" size={18} /> Loading...</div>;
}

createRoot(document.getElementById("root")).render(<App />);
