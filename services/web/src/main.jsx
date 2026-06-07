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
    permissions: ["packet:create", "packet:read", "document:upload", "packet:process", "review:complete", "review_task:read", "review_task:update", "export:packet", "audit:read", "job:read"],
  },
  manager: {
    label: "Manager",
    email: "manager@neurodocops.local",
    password: "Manager@123",
    summary: "Owns operational queue, approval flow, export release, and team throughput.",
    permissions: ["packet:create", "packet:read", "document:upload", "packet:process", "review:complete", "review_task:read", "review_task:update", "export:packet", "audit:read", "job:read"],
  },
  reviewer: {
    label: "Reviewer",
    email: "reviewer@neurodocops.local",
    password: "Reviewer@123",
    summary: "Processes evidence, resolves review exceptions, and approves packets without export release.",
    permissions: ["packet:create", "packet:read", "document:upload", "packet:process", "review:complete", "review_task:read", "review_task:update", "audit:read", "job:read"],
  },
  auditor: {
    label: "Auditor",
    email: "auditor@neurodocops.local",
    password: "Auditor@123",
    summary: "Read-only evidence, decisions, audit trail, and job status visibility.",
    permissions: ["packet:read", "review_task:read", "audit:read", "job:read"],
  },
  integration: {
    label: "Integration",
    email: "integration@neurodocops.local",
    password: "Integration@123",
    summary: "Service-account style intake, processing, export, and job polling.",
    permissions: ["packet:create", "packet:read", "document:upload", "packet:process", "export:packet", "job:read"],
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
    throw new Error(formatApiError(body, response.status));
  }
  return body;
}

function formatApiError(body, status) {
  if (!body) return `Request failed: ${status}`;
  if (typeof body === "string") {
    try { return formatApiError(JSON.parse(body), status); } catch { return body; }
  }
  if (Array.isArray(body)) return body.map((item) => formatApiErrorItem(item)).join("; ");
  if (typeof body === "object") {
    if (body.detail) return formatApiError(body.detail, status);
    if (body.message) return String(body.message);
    if (body.msg) return String(body.msg);
    return JSON.stringify(body);
  }
  return String(body);
}

function formatApiErrorItem(item) {
  if (typeof item === "string") return item;
  if (item && typeof item === "object") {
    const location = Array.isArray(item.loc) ? item.loc.filter((part) => part !== "body").join(".") : null;
    const message = item.msg || item.message || "Invalid value";
    return location ? `${location}: ${message}` : message;
  }
  return String(item);
}

function authHeaders(session) {
  return { "X-Actor": session.email, "X-Role": session.role };
}

function can(session, permission) {
  return Boolean(session && ROLES[session.role]?.permissions.includes(permission));
}

function toLocalDateTimeValue(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

function fromLocalDateTimeValue(value) {
  return value ? new Date(value).toISOString() : null;
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

  const packetMatch = route === "/packets/new" ? null : route.match(/^\/packets\/([^/]+)$/);
  return (
    <div className="app-shell">
      <Nav route={route} navigate={navigate} session={session} onSignOut={signOut} theme={theme} onCycleTheme={cycleTheme} />
      <main className="content">
        {route === "/" && <Dashboard navigate={navigate} session={session} />}
        {route === "/review" && <ReviewQueuePage navigate={navigate} session={session} />}
        {route === "/system" && <SystemPage session={session} />}
        {route === "/plugins" && <PluginConfigPage session={session} />}
        {route === "/packets" && <PacketsPage navigate={navigate} session={session} />}
        {route === "/packets/new" && <SourceUploadPacketPage navigate={navigate} session={session} />}
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
    ...(can(session, "review_task:read") ? [["/review", "Review Queue"]] : []),
    ["/system", "System"],
    ...(session.role === "admin" ? [["/plugins", "Plugins"]] : []),
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

function ReviewQueuePage({ navigate, session }) {
  const [assignee, setAssignee] = useState(session.email);
  const [statusFilter, setStatusFilter] = useState("open");
  const [priority, setPriority] = useState("");
  const [unassigned, setUnassigned] = useState(false);
  const [savingTaskId, setSavingTaskId] = useState(null);
  const [error, setError] = useState(null);
  const query = new URLSearchParams();
  if (assignee && !unassigned) query.set("assignee", assignee);
  if (statusFilter !== "all") query.set("status", statusFilter);
  if (priority) query.set("priority", priority);
  if (unassigned) query.set("unassigned", "true");
  const { data: items, loading, error: loadError, reload } = useAsyncData(
    () => api(`/review-tasks${query.toString() ? `?${query.toString()}` : ""}`, { headers: authHeaders(session) }),
    [session.email, session.role, assignee, statusFilter, priority, unassigned]
  );

  const updateTask = async (item, updates) => {
    setSavingTaskId(item.task.id);
    setError(null);
    try {
      await api(`/claim-packets/${item.packet_id}/review-tasks/${item.task.id}`, {
        method: "PATCH",
        headers: authHeaders(session),
        body: JSON.stringify(updates),
      });
      await reload();
    } catch (apiError) {
      setError(apiError.message);
    } finally {
      setSavingTaskId(null);
    }
  };

  const rows = items || [];
  return (
    <section>
      <PageHeader eyebrow="Human review" title="Reviewer Work Queue" description="Live queue backed by review-task assignment metadata, priority, due dates, and RBAC. SLA escalation and saved views remain roadmap." action={<button className="ghost" onClick={reload}><RefreshCw size={14} /> Refresh</button>} />
      <ErrorBanner error={loadError || error} title="Review queue blocked" />
      <section className="panel queue-controls">
        <label><span>Assignee</span><input value={assignee} onChange={(event) => setAssignee(event.target.value)} disabled={unassigned} placeholder="reviewer@example.com" /></label>
        <label><span>Status</span><select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="open">Open</option><option value="resolved">Resolved</option><option value="all">All</option></select></label>
        <label><span>Priority</span><select value={priority} onChange={(event) => setPriority(event.target.value)}><option value="">All</option><option value="urgent">Urgent</option><option value="high">High</option><option value="normal">Normal</option><option value="low">Low</option></select></label>
        <label className="checkline"><input type="checkbox" checked={unassigned} onChange={(event) => setUnassigned(event.target.checked)} /> Unassigned only</label>
      </section>
      <section className="panel">
        <div className="panel-title"><h2>Queue Items</h2><span className="provider-flag">{loading ? "Loading" : `${rows.length} tasks`}</span></div>
        {loading ? <Loading /> : rows.length === 0 ? <p className="muted">No review tasks match this queue filter.</p> : <div className="review-queue-list">{rows.map((item) => <ReviewQueueItem key={`${item.packet_id}-${item.task.id}`} item={item} session={session} navigate={navigate} saving={savingTaskId === item.task.id} onUpdate={updateTask} />)}</div>}
      </section>
    </section>
  );
}

function ReviewQueueItem({ item, session, navigate, saving, onUpdate }) {
  const task = item.task;
  const [assignee, setAssignee] = useState(task.assignee || session.email);
  const [priority, setPriority] = useState(task.priority || "normal");
  const [dueAt, setDueAt] = useState(toLocalDateTimeValue(task.due_at));
  const [notes, setNotes] = useState(task.notes || "");
  useEffect(() => {
    setAssignee(task.assignee || session.email);
    setPriority(task.priority || "normal");
    setDueAt(toLocalDateTimeValue(task.due_at));
    setNotes(task.notes || "");
  }, [task.id, task.assignee, task.priority, task.due_at, task.notes, session.email]);
  const canUpdate = can(session, "review_task:update");
  const submit = () => onUpdate(item, { assignee: assignee || null, priority, due_at: fromLocalDateTimeValue(dueAt), notes: notes || null });
  return (
    <article className={`review-queue-item priority-${task.priority || "normal"}`}>
      <div className="review-queue-main">
        <div><StatusBadge status={task.status} /> <strong>{item.claim_reference}</strong> <span className="muted">{item.claimant_name}</span></div>
        <p>{task.reason}</p>
        <div className="review-task-meta"><span>Packet: {statusLabel(item.packet_status)}</span><span>Loss: {item.loss_type}</span><span>Assignee: {task.assignee || "Unassigned"}</span><span>Priority: {task.priority}</span>{task.due_at && <span>Due {new Date(task.due_at).toLocaleString()}</span>}</div>
      </div>
      <div className="review-queue-actions">
        <button className="ghost" onClick={() => navigate(`/packets/${item.packet_id}`)}><ArrowRight size={14} /> Open Packet</button>
        {canUpdate ? <div className="queue-edit-grid"><input value={assignee} onChange={(event) => setAssignee(event.target.value)} placeholder="assignee@example.com" /><select value={priority} onChange={(event) => setPriority(event.target.value)}><option value="urgent">Urgent</option><option value="high">High</option><option value="normal">Normal</option><option value="low">Low</option></select><input type="datetime-local" value={dueAt} onChange={(event) => setDueAt(event.target.value)} /><input value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Queue note" /><button className="primary" onClick={submit} disabled={saving}>{saving ? <Loader2 className="spin" size={14} /> : <CheckCircle2 size={14} />} Save Queue Metadata</button></div> : <span className="review-rbac-note">Read-only queue access. Requires review_task:update.</span>}
      </div>
    </article>
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

function PluginConfigPage({ session }) {
  const { data: config, loading, error, reload } = useAsyncData(() => api("/system/provider-configuration", { headers: authHeaders(session) }), [session.email, session.role]);
  if (session.role !== "admin") return <Forbidden navigate={() => { window.location.hash = "/"; }} title="Plugin configuration is admin-only" message="Provider configuration controls are restricted to system administrators." />;
  return (
    <section>
      <PageHeader eyebrow="Admin" title="Plugin Configuration" description="Read-only provider/plugin configuration from the live API. Provider changes are made through deployment environment variables, not unsafe browser-side secret forms." action={<button className="ghost" onClick={reload}><RefreshCw size={14} /> Refresh</button>} />
      <ErrorBanner error={error} />
      <section className="panel plugin-safety">
        <div className="panel-title"><h2><ShieldCheck size={16} /> Configuration Safety Contract</h2></div>
        <div className="system-summary">
          <div><span className="summary-icon"><CheckCircle2 size={16} /></span><span>Mode</span><strong>{loading ? "..." : statusLabel(config?.mode || "unknown")}</strong></div>
          <div><span className="summary-icon"><ShieldCheck size={16} /></span><span>Runtime Mutation</span><strong>{config?.safety?.runtime_mutation_supported ? "enabled" : "disabled"}</strong></div>
          <div><span className="summary-icon"><Eye size={16} /></span><span>Secrets Exposed</span><strong>{config?.safety?.secrets_exposed ? "yes" : "no"}</strong></div>
          <div><span className="summary-icon"><AlertTriangle size={16} /></span><span>Paid Live Opt-In</span><strong>{config?.safety?.paid_live_providers_require_explicit_opt_in ? "required" : "unknown"}</strong></div>
        </div>
      </section>
      <section className="plugin-grid">
        {loading && <div className="panel"><p className="muted">Loading provider slots from API.</p></div>}
        {(config?.slots || []).map((slot) => <PluginSlot key={slot.kind} slot={slot} />)}
      </section>
    </section>
  );
}

function PluginSlot({ slot }) {
  const active = slot.active || {};
  return (
    <article className="panel plugin-card">
      <div className="plugin-card-head">
        <span className="provider-icon"><ProviderIcon provider={{ kind: slot.kind }} /></span>
        <div><h2>{slot.label}</h2><code>{slot.env_var}</code></div>
      </div>
      <div className="plugin-current">
        <span>Active</span>
        <strong>{active.name || "unknown"}</strong>
        <StatusBadge status={active.implemented ? "ready" : "open"} />
      </div>
      <div className="plugin-meta">
        <span>Safe default</span><code>{slot.safe_default}</code>
        <span>Adapter</span><code>{active.adapter || "not wired"}</code>
        <span>Mode</span><code>{active.live_enabled ? "live" : "local"}</code>
        <span>Tier</span><code>{active.tier || "unknown"}</code>
      </div>
      <div className="provider-values">
        <strong>Known values</strong>
        <div>{(slot.known_values || []).map((value) => <span key={value} className={(slot.paid_values || []).includes(value) ? "provider-flag warn" : "provider-flag"}>{value}</span>)}</div>
      </div>
    </article>
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

function SourceUploadPacketPage({ navigate, session }) {
  const [claimReference, setClaimReference] = useState("CLM-1001");
  const [claimantName, setClaimantName] = useState("Amina Rahman");
  const [lossType, setLossType] = useState("auto");
  const [documents, setDocuments] = useState([{ filename: "", text: "", file: null }]);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  if (!can(session, "packet:create")) return <Forbidden navigate={navigate} title="Packet intake is not available" message="Your role can inspect evidence but cannot create new claim packets." />;
  const updateDocument = (index, key, value) => setDocuments((current) => current.map((document, documentIndex) => documentIndex === index ? { ...document, [key]: value } : document));
  const selectFile = (index, file) => setDocuments((current) => current.map((document, documentIndex) => documentIndex === index ? { ...document, file: file || null, filename: file?.name || document.filename } : document));
  const addDocument = () => setDocuments((current) => [...current, { filename: "", text: "", file: null }]);
  const removeDocument = (index) => setDocuments((current) => current.filter((_, documentIndex) => documentIndex !== index));
  const packetPayload = { claim_reference: claimReference.trim(), claimant_name: claimantName.trim(), loss_type: lossType.trim() || "unknown", documents: [] };
  const intakeDocuments = documents.map((document) => ({ ...document, filename: document.filename.trim(), text: document.text.trim() }));
  const readiness = [
    ["Claim reference", Boolean(packetPayload.claim_reference)],
    ["Claimant name", Boolean(packetPayload.claimant_name)],
    ["Loss type", Boolean(packetPayload.loss_type)],
    ["At least one source file", intakeDocuments.length > 0],
    ["Every document has a selected file", intakeDocuments.every((document) => Boolean(document.file))],
    ["PDF parser path or fallback text", intakeDocuments.every((document) => document.file?.type === "application/pdf" || document.filename.toLowerCase().endsWith(".pdf") || Boolean(document.text))],
  ];
  const readinessComplete = readiness.every(([, ready]) => ready);
  const validatePayload = () => {
    if (!packetPayload.claim_reference) return "Claim reference is required before packet intake.";
    if (!packetPayload.claimant_name) return "Claimant name is required before packet intake.";
    if (!packetPayload.loss_type) return "Loss type is required before packet intake.";
    if (!intakeDocuments.length) return "Add at least one source document file.";
    const missingFileIndex = intakeDocuments.findIndex((document) => !document.file);
    if (missingFileIndex >= 0) return `Document ${missingFileIndex + 1} source file is required.`;
    const missingTextIndex = intakeDocuments.findIndex((document) => document.file?.type !== "application/pdf" && !document.filename.toLowerCase().endsWith(".pdf") && !document.text);
    if (missingTextIndex >= 0) return `Document ${missingTextIndex + 1} needs fallback evidence text unless it is a digital PDF that can be parsed locally.`;
    return null;
  };
  const createPacket = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    const validationError = validatePayload();
    if (validationError) {
      setError(validationError);
      setSubmitting(false);
      return;
    }
    try {
      const packet = await api("/claim-packets", { method: "POST", headers: authHeaders(session), body: JSON.stringify(packetPayload) });
      for (const document of intakeDocuments) {
        const formData = new FormData();
        formData.append("file", document.file, document.filename || document.file.name);
        if (document.text) formData.append("text", document.text);
        formData.append("metadata", JSON.stringify({ intake: "web", original_filename: document.file.name }));
        await api(`/claim-packets/${packet.id}/documents`, { method: "POST", headers: authHeaders(session), body: formData });
      }
      navigate(`/packets/${packet.id}`);
    } catch (apiError) { setError(apiError.message); } finally { setSubmitting(false); }
  };
  return (
    <section>
      <button className="back" onClick={() => navigate("/packets")}><ArrowLeft size={16} /> Back to packets</button>
      <PageHeader eyebrow="Intake" title="Create Evidence Packet" description="Create the packet record, upload source files, and use local PDF text extraction or fallback evidence text for processing. Review, approval, and export remain controlled follow-up actions." />
      <ErrorBanner error={error} title="Packet intake blocked" />
      <form className="intake-layout" onSubmit={createPacket}>
        <section className="panel form">
          <div className="panel-subtitle"><FileText size={16} /> Packet Identity</div>
          <p className="muted">Use the carrier claim number, FNOL ID, or internal packet reference that operators will search later.</p>
          <div className="form-grid">
            <label>Claim Reference<input value={claimReference} onChange={(event) => setClaimReference(event.target.value)} required /></label>
            <label>Claimant Name<input value={claimantName} onChange={(event) => setClaimantName(event.target.value)} required /></label>
            <label>Loss Type<input value={lossType} onChange={(event) => setLossType(event.target.value)} required /></label>
          </div>
          <div className="panel-subtitle"><Upload size={16} /> Source Documents</div>
          <p className="muted">Select the actual source file from the claimant, adjuster, provider, or integration feed. Digital PDFs with embedded text can be parsed locally without paid OCR. For scanned PDFs, images, non-PDF files, or parser misses, paste fallback evidence text so the workflow can classify, extract, check, review, and audit it.</p>
          {documents.map((document, index) => <div className="document-editor" key={index}>
            <div className="document-editor-head"><strong>Document {index + 1}</strong>{documents.length > 1 && <button type="button" className="ghost compact" onClick={() => removeDocument(index)}>Remove</button>}</div>
            <label className="file-drop">Source File<input type="file" onChange={(event) => selectFile(index, event.target.files?.[0])} required={!document.file} /></label>
            {document.file && <div className="selected-file"><FileText size={14} /><span>{document.file.name}</span><em>{Math.ceil(document.file.size / 1024)} KB</em></div>}
            <input value={document.filename} onChange={(event) => updateDocument(index, "filename", event.target.value)} placeholder="Stored filename" required />
            <textarea value={document.text} onChange={(event) => updateDocument(index, "text", event.target.value)} rows={5} placeholder="Optional fallback evidence text for scanned PDFs, images, non-PDF files, or parser misses" />
          </div>)}
          <div className="form-actions">
            <button type="button" className="ghost" onClick={addDocument}><Plus size={14} /> Add Source File</button>
            <button className="primary" disabled={submitting || !readinessComplete}>{submitting ? <Loader2 className="spin" size={14} /> : <Upload size={14} />} Create And Upload Packet</button>
          </div>
        </section>
        <aside className="panel readiness-panel">
          <div className="panel-subtitle"><ClipboardCheck size={16} /> Intake Readiness</div>
          <p className="muted">This creates a packet, uploads each source file to object storage, then opens the packet detail screen. Processing uses local/free providers by default; paid OCR is not triggered from this screen.</p>
          <div className="readiness-list">{readiness.map(([label, ready]) => <div className={ready ? "ready" : "missing"} key={label}>{ready ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />}<span>{label}</span></div>)}</div>
          <div className={`guardrail ${readinessComplete ? "good" : ""}`}><ShieldCheck size={16} /> {readinessComplete ? "Ready to create a source-backed packet with local/free parsing defaults." : "Complete missing intake fields before submitting."}</div>
        </aside>
      </form>
    </section>
  );
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
  const removeDocument = (index) => setDocuments((current) => current.filter((_, documentIndex) => documentIndex !== index));
  const payload = {
    claim_reference: claimReference.trim(),
    claimant_name: claimantName.trim(),
    loss_type: lossType.trim() || "unknown",
    documents: documents.map((document) => ({ filename: document.filename.trim(), text: document.text.trim() })),
  };
  const readiness = [
    ["Claim reference", Boolean(payload.claim_reference)],
    ["Claimant name", Boolean(payload.claimant_name)],
    ["Loss type", Boolean(payload.loss_type)],
    ["At least one document", payload.documents.length > 0],
    ["Every document has a filename", payload.documents.every((document) => Boolean(document.filename))],
    ["Every document has evidence text", payload.documents.every((document) => Boolean(document.text))],
  ];
  const readinessComplete = readiness.every(([, ready]) => ready);
  const validatePayload = () => {
    if (!payload.claim_reference) return "Claim reference is required before packet intake.";
    if (!payload.claimant_name) return "Claimant name is required before packet intake.";
    if (!payload.loss_type) return "Loss type is required before packet intake.";
    if (!payload.documents.length) return "Add at least one source document text payload.";
    const missingFilenameIndex = payload.documents.findIndex((document) => !document.filename);
    if (missingFilenameIndex >= 0) return `Document ${missingFilenameIndex + 1} filename is required.`;
    const missingTextIndex = payload.documents.findIndex((document) => !document.text);
    if (missingTextIndex >= 0) return `Document ${missingTextIndex + 1} evidence text is required.`;
    return null;
  };
  const createPacket = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    const validationError = validatePayload();
    if (validationError) {
      setError(validationError);
      setSubmitting(false);
      return;
    }
    try {
      const packet = await api("/claim-packets", { method: "POST", headers: authHeaders(session), body: JSON.stringify(payload) });
      navigate(`/packets/${packet.id}`);
    } catch (apiError) { setError(apiError.message); } finally { setSubmitting(false); }
  };
  return <section><button className="back" onClick={() => navigate("/packets")}><ArrowLeft size={16} /> Back to packets</button><PageHeader eyebrow="Intake" title="Create Evidence Packet" description="Create the packet record and source text payloads used by the live API. Processing, review, approval, and export remain controlled follow-up actions." /><ErrorBanner error={error} title="Packet intake blocked" /><form className="intake-layout" onSubmit={createPacket}><section className="panel form"><div className="panel-subtitle"><FileText size={16} /> Packet Identity</div><p className="muted">Use the carrier claim number, FNOL ID, or internal packet reference that operators will search later.</p><div className="form-grid"><label>Claim Reference<input value={claimReference} onChange={(event) => setClaimReference(event.target.value)} required /></label><label>Claimant Name<input value={claimantName} onChange={(event) => setClaimantName(event.target.value)} required /></label><label>Loss Type<input value={lossType} onChange={(event) => setLossType(event.target.value)} required /></label></div><div className="panel-subtitle"><Upload size={16} /> Evidence Text Payloads</div><p className="muted">Paste OCR or extracted document text. The API stores this text for classification, extraction, checklist review, and audit events. Source-file upload exists as a separate API endpoint after packet creation.</p>{documents.map((document, index) => <div className="document-editor" key={index}><div className="document-editor-head"><strong>Document {index + 1}</strong>{documents.length > 1 && <button type="button" className="ghost compact" onClick={() => removeDocument(index)}>Remove</button>}</div><input value={document.filename} onChange={(event) => updateDocument(index, "filename", event.target.value)} placeholder="filename.pdf" required /><textarea value={document.text} onChange={(event) => updateDocument(index, "text", event.target.value)} rows={4} placeholder="Paste OCR or extracted evidence text" required /></div>)}<div className="form-actions"><button type="button" className="ghost" onClick={() => setDocuments([...documents, { filename: "document.pdf", text: "" }])}><Plus size={14} /> Add Document</button><button type="submit" className="primary" disabled={submitting}>{submitting ? <Loader2 className="spin" size={16} /> : <Plus size={16} />} Create Evidence Packet</button></div></section><aside className="panel readiness-panel"><div className="panel-subtitle"><ShieldCheck size={16} /> Intake Readiness</div><p className="muted">Creates packet only. Run processing from the packet workspace after intake.</p><div className="readiness-list">{readiness.map(([label, ready]) => <div className={ready ? "ready" : "missing"} key={label}>{ready ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />}<span>{label}</span></div>)}</div><div className={readinessComplete ? "guardrail good" : "guardrail"}><ShieldCheck size={16} /> {readinessComplete ? "Ready to create packet." : "Complete required intake fields before creating the packet."}</div></aside></form></section>;
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
        <button disabled={!can(session, "review:complete") || openTasks.length > 0} onClick={() => runAction("review", "review:complete", () => api(`/claim-packets/${packetId}/review`, { method: "POST", headers: requestHeaders, body: JSON.stringify({ decision: "approve", reviewer: session.email, notes: "Validated for export." }) }))}>Approve</button>
        <button className="primary" disabled={!canExportPacket} onClick={() => runAction("export", "export:packet", () => api(`/claim-packets/${packetId}/export`, { method: "POST", headers: requestHeaders }))}>Export</button>
      </div>
      {jobStatus && <div className="guardrail"><RefreshCw size={16} /> Last worker job status: {statusLabel(jobStatus)}</div>}
      {openTasks.length > 0 && <div className="guardrail"><ShieldCheck size={16} /> Resolve each review exception before approval or export.</div>}
      {!canExportPacket && <div className="guardrail"><ShieldCheck size={16} /> Export requires approved status, no open review tasks, and an export-capable role.</div>}
      <div className="detail-grid">
        <section className="panel wide"><h2>Evidence Documents & Fields</h2><Documents packetId={packetId} documents={packet.documents} session={session} onChanged={async () => { await reload(); await reloadAudit(); }} /></section>
        <section className="panel"><h2>Evidence Checklist</h2><Checklist items={packet.checklist} /></section>
        <section className="panel"><h2>Review Exceptions</h2><ReviewTasks packetId={packetId} tasks={packet.review_tasks} session={session} onChanged={async () => { await reload(); await reloadAudit(); }} /></section>
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

function ReviewTasks({ packetId, tasks, session, onChanged }) {
  const [notesByTask, setNotesByTask] = useState({});
  const [savingTaskId, setSavingTaskId] = useState(null);
  const [error, setError] = useState(null);
  const canResolve = can(session, "review:complete");
  const updateTask = async (task, action) => {
    setSavingTaskId(task.id);
    setError(null);
    try {
      await api(`/claim-packets/${packetId}/review-tasks/${task.id}/${action}`, {
        method: "POST",
        headers: authHeaders(session),
        body: JSON.stringify({ notes: notesByTask[task.id] || null }),
      });
      setNotesByTask((current) => ({ ...current, [task.id]: "" }));
      await onChanged();
    } catch (apiError) { setError(apiError.message); } finally { setSavingTaskId(null); }
  };
  if (!tasks.length) return <p className="muted">No review tasks yet.</p>;
  return <div className="list-stack"><ErrorBanner error={error} />{tasks.map((task) => {
    const isResolved = task.status === "resolved";
    const action = isResolved ? "reopen" : "resolve";
    return <div className={`list-item review-task ${isResolved ? "resolved" : "open"}`} key={task.id}><div className="review-task-head"><StatusBadge status={task.status} /><strong>{task.reason}</strong></div><div className="review-task-meta"><span>{task.reviewer || "Unassigned"}</span>{task.resolved_at && <span>Resolved {new Date(task.resolved_at).toLocaleString()}</span>}{task.notes && <span>{task.notes}</span>}</div>{canResolve ? <div className="review-task-actions"><input value={notesByTask[task.id] || ""} onChange={(event) => setNotesByTask((current) => ({ ...current, [task.id]: event.target.value }))} placeholder={isResolved ? "Reason for reopening" : "Resolution note for audit trail"} /><button className={isResolved ? "reopen" : ""} onClick={() => updateTask(task, action)} disabled={savingTaskId === task.id}>{savingTaskId === task.id ? <Loader2 className="spin" size={14} /> : <CheckCircle2 size={14} />}{isResolved ? "Reopen Task" : "Resolve Task"}</button></div> : <span className="review-rbac-note">Review action locked by RBAC. Requires review:complete.</span>}</div>;
  })}</div>;
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

function ErrorBanner({ error, title = "Action blocked" }) {
  if (!error) return null;
  return <div className="error" role="alert"><AlertTriangle size={16} /><div><strong>{title}</strong><span>{String(error)}</span></div></div>;
}

function Loading() {
  return <div className="loading"><Loader2 className="spin" size={18} /> Loading...</div>;
}

createRoot(document.getElementById("root")).render(<App />);
