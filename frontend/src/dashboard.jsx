import { useState, useEffect } from "react";
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, RadarChart, Radar, PolarGrid,
  PolarAngleAxis, Legend, ReferenceLine
} from "recharts";

// ─── Colour tokens ─────────────────────────────────────────────────────────────
const C = {
  bg:        "#0d1117",
  surface:   "#161b22",
  card:      "#1c2230",
  border:    "#2a3448",
  accent:    "#4f8ef7",
  accentSoft:"#1e3a6e",
  green:     "#22c55e",
  greenSoft: "#14532d",
  red:       "#ef4444",
  redSoft:   "#4b1313",
  amber:     "#f59e0b",
  amberSoft: "#451a03",
  purple:    "#a855f7",
  purpleSoft:"#3b0764",
  text:      "#e2e8f0",
  muted:     "#64748b",
  sub:       "#94a3b8",
};

// ─── Helper Components ─────────────────────────────────────────────────────────
function Badge({ label, color, bg }) {
  return (
    <span style={{
      background: bg, color, border: `1px solid ${color}33`,
      borderRadius: 6, padding: "2px 10px", fontSize: 11, fontWeight: 700,
      letterSpacing: "0.06em", textTransform: "uppercase",
    }}>
      {label}
    </span>
  );
}

function Card({ children, style = {} }) {
  return (
    <div style={{
      background: C.card, border: `1px solid ${C.border}`,
      borderRadius: 14, padding: "20px 22px", ...style,
    }}>
      {children}
    </div>
  );
}

function SectionTitle({ icon, title, sub }) {
  return (
    <div style={{ marginBottom: 18 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontSize: 18 }}>{icon}</span>
        <span style={{ color: C.text, fontWeight: 700, fontSize: 16 }}>{title}</span>
      </div>
      {sub && <p style={{ color: C.muted, fontSize: 12, marginTop: 4, marginLeft: 26 }}>{sub}</p>}
    </div>
  );
}

function RiskGauge({ value }) {
  const angle = -140 + (value / 100) * 280;
  const color = value > 60 ? C.red : value > 35 ? C.amber : C.green;
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
      <svg width={130} height={80} viewBox="0 0 130 80">
        <path d="M15 75 A55 55 0 0 1 115 75" fill="none" stroke={C.border} strokeWidth={10} strokeLinecap="round" />
        <path
          d="M15 75 A55 55 0 0 1 115 75"
          fill="none" stroke={color} strokeWidth={10} strokeLinecap="round"
          strokeDasharray={`${(value / 100) * 173} 173`}
        />
        <g transform={`translate(65,75) rotate(${angle})`}>
          <line x1={0} y1={0} x2={0} y2={-42} stroke={C.text} strokeWidth={2.5} strokeLinecap="round" />
          <circle cx={0} cy={0} r={4} fill={C.text} />
        </g>
      </svg>
      <span style={{ color, fontSize: 26, fontWeight: 800, marginTop: -8 }}>{value}%</span>
      <span style={{ color: C.muted, fontSize: 11, marginTop: 2 }}>Dropout Probability</span>
    </div>
  );
}

function ShapBar({ feature, shap, raw, direction }) {
  const isRisk = direction === "neg";
  const color  = isRisk ? C.red : C.green;
  const width  = Math.min((Math.abs(shap) / 2.5) * 100, 100);
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 5 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ color, fontSize: 14 }}>{isRisk ? "▲" : "▼"}</span>
          <span style={{ color: C.text, fontSize: 13, fontWeight: 600 }}>{feature}</span>
          <span style={{
            background: C.surface, border: `1px solid ${C.border}`,
            borderRadius: 5, padding: "1px 7px", color: C.sub, fontSize: 11,
          }}>{raw}</span>
        </div>
        <span style={{ color, fontSize: 12, fontWeight: 700 }}>
          {isRisk ? "+" : "-"}{Math.abs(shap).toFixed(3)} risk
        </span>
      </div>
      <div style={{ background: C.surface, borderRadius: 4, height: 7, overflow: "hidden" }}>
        <div style={{
          width: `${width}%`, height: "100%", background: color,
          borderRadius: 4, transition: "width 0.6s ease",
          boxShadow: `0 0 6px ${color}66`,
        }} />
      </div>
    </div>
  );
}

function StatBar({ label, value, max, color }) {
  const pct = (value / max) * 100;
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 5 }}>
        <span style={{ color: C.sub, fontSize: 13 }}>{label}</span>
        <span style={{ color: C.text, fontWeight: 700, fontSize: 13 }}>
          {value}{typeof max === "number" && max === 100 ? "%" : `/${max}`}
        </span>
      </div>
      <div style={{ background: C.surface, borderRadius: 6, height: 8, overflow: "hidden" }}>
        <div style={{
          width: `${pct}%`, height: "100%", background: color,
          borderRadius: 6, boxShadow: `0 0 8px ${color}55`,
        }} />
      </div>
    </div>
  );
}

function PriorityDot({ level }) {
  const map = { critical: C.red, high: C.amber, medium: C.accent };
  return (
    <span style={{
      width: 8, height: 8, borderRadius: "50%",
      background: map[level] || C.muted,
      display: "inline-block", flexShrink: 0, marginTop: 6,
      boxShadow: `0 0 6px ${map[level]}`,
    }} />
  );
}

const NAV_ITEMS = [
  { icon: "🏠", label: "Home",        id: "home" },
  { icon: "📊", label: "Dashboard",   id: "dashboard" },
  { icon: "🏆", label: "Leaderboard", id: "leaderboard" },
  { icon: "📅", label: "Timetable",   id: "timetable" },
];

// ─── Main Dashboard ────────────────────────────────────────────────────────────
export default function Dashboard() {
  const [apiData, setApiData]         = useState(null);
  const [loading, setLoading]         = useState(true);
  const [error, setError]             = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [activeNav, setActiveNav]     = useState("dashboard");

  // URL se ?id=STU001 lega — default STU001
  const studentId = new URLSearchParams(window.location.search).get('id') || 'STU001';

  useEffect(() => {
    fetch(`http://127.0.0.1:5000/api/students/${studentId}/dashboard`)
      .then(r => {
        if (!r.ok) throw new Error(`Student not found (${r.status})`);
        return r.json();
      })
      .then(d => { setApiData(d); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, [studentId]);

  // ── Loading screen ──
  if (loading) return (
    <div style={{
      background: C.bg, minHeight: "100vh", display: "flex",
      alignItems: "center", justifyContent: "center",
      flexDirection: "column", gap: 16,
    }}>
      <div style={{ fontSize: 36 }}>⏳</div>
      <div style={{ color: C.text, fontSize: 18, fontWeight: 600 }}>Loading student data...</div>
      <div style={{ color: C.muted, fontSize: 13 }}>Fetching from Flask API</div>
    </div>
  );

  // ── Error screen ──
  if (error) return (
    <div style={{
      background: C.bg, minHeight: "100vh", display: "flex",
      alignItems: "center", justifyContent: "center",
      flexDirection: "column", gap: 16, padding: 40,
    }}>
      <div style={{ fontSize: 36 }}>❌</div>
      <div style={{ color: C.red, fontSize: 18, fontWeight: 600 }}>Connection Failed</div>
      <div style={{ color: C.muted, fontSize: 13, textAlign: "center" }}>{error}</div>
      <div style={{
        background: C.card, border: `1px solid ${C.border}`, borderRadius: 10,
        padding: "14px 20px", color: C.sub, fontSize: 12, marginTop: 8,
      }}>
        Make sure Flask is running: <code style={{ color: C.accent }}>python app.py</code><br/>
        Then open: <code style={{ color: C.accent }}>http://localhost:5173?id=YOUR_STUDENT_ID</code>
      </div>
    </div>
  );

  // ── Map API data ──
  const student = {
    name:          apiData.name,
    id:            apiData.id,
    semester:      apiData.semester,
    branch:        apiData.branch,
    avatar:        (apiData.name || "ST").split(" ").map(w => w[0]).join("").slice(0, 2).toUpperCase(),
    dropoutProb:   apiData.dropout_prob,
    predictedCGPA: apiData.predicted_cgpa,
    overallScore:  apiData.overall_score,
    status:        apiData.status,
    modelConf:     apiData.model_conf,
    lastUpdated:   apiData.last_updated,
  };

  const shapData        = apiData.shap_values   || [];
  const recommendations = apiData.recommendations || [];
  const radarData       = apiData.radar          || [];

  const performanceHistory = [
    { sem: "Sem 1",  cgpa: 7.8, attendance: 82, assignments: 78 },
    { sem: "Sem 2",  cgpa: 7.5, attendance: 78, assignments: 72 },
    { sem: "Sem 3",  cgpa: 7.2, attendance: 74, assignments: 65 },
    { sem: "Sem 4",  cgpa: 6.9, attendance: 68, assignments: 58 },
    { sem: "Sem 5",  cgpa: 6.6, attendance: 62, assignments: 50 },
    { sem: "Sem 6*", cgpa: student.predictedCGPA, attendance: apiData.attendance, assignments: apiData.assignment_score },
  ];

  const subjectMarks = [
    { subject: "DS&A", marks: 28, total: 50 },
    { subject: "DBMS", marks: 34, total: 50 },
    { subject: "OS",   marks: 30, total: 50 },
    { subject: "CN",   marks: 38, total: 50 },
    { subject: "ML",   marks: 25, total: 50 },
    { subject: "SE",   marks: 36, total: 50 },
  ];

  const riskColor = student.status === "At Risk" ? C.red    : C.green;
  const riskBg    = student.status === "At Risk" ? C.redSoft : C.greenSoft;
  const cgpaColor = student.predictedCGPA >= 7.5 ? C.green  : student.predictedCGPA >= 6.0 ? C.amber : C.red;

  return (
    <div style={{
      display: "flex", minHeight: "100vh", background: C.bg,
      fontFamily: "'Inter', 'Segoe UI', system-ui, sans-serif",
      color: C.text, overflow: "hidden",
    }}>

      {/* ── Sidebar ── */}
      <aside style={{
        width: sidebarOpen ? 220 : 64,
        background: C.surface, borderRight: `1px solid ${C.border}`,
        display: "flex", flexDirection: "column",
        transition: "width 0.25s ease", flexShrink: 0, zIndex: 10,
      }}>
        {/* Logo */}
        <div style={{
          padding: "18px 16px", borderBottom: `1px solid ${C.border}`,
          display: "flex", alignItems: "center", gap: 10,
        }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8,
            background: `linear-gradient(135deg, ${C.accent}, ${C.purple})`,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 15, fontWeight: 900, color: "#fff", flexShrink: 0,
          }}>S</div>
          {sidebarOpen && (
            <div>
              <div style={{ fontWeight: 800, fontSize: 14, color: C.text, lineHeight: 1 }}>SEPPS</div>
              <div style={{ fontSize: 10, color: C.muted, marginTop: 2 }}>Risk Monitor</div>
            </div>
          )}
          <button onClick={() => setSidebarOpen(o => !o)} style={{
            marginLeft: "auto", background: "none", border: "none",
            color: C.muted, cursor: "pointer", fontSize: 16, padding: 2,
          }}>
            {sidebarOpen ? "◀" : "▶"}
          </button>
        </div>

        {/* Avatar */}
        {sidebarOpen && (
          <div style={{
            padding: "18px 16px", borderBottom: `1px solid ${C.border}`,
            display: "flex", alignItems: "center", gap: 10,
          }}>
            <div style={{
              width: 38, height: 38, borderRadius: "50%",
              background: `linear-gradient(135deg, ${C.accent}, ${C.purple})`,
              display: "flex", alignItems: "center", justifyContent: "center",
              fontWeight: 700, fontSize: 14, color: "#fff", flexShrink: 0,
              border: `2px solid ${riskColor}`,
            }}>{student.avatar}</div>
            <div style={{ overflow: "hidden" }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: C.text, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                {student.name}
              </div>
              <div style={{ fontSize: 11, color: C.muted }}>{student.id}</div>
            </div>
          </div>
        )}

        {/* Nav */}
        <nav style={{ padding: "12px 8px", flex: 1 }}>
          {sidebarOpen && (
            <div style={{ fontSize: 10, color: C.muted, letterSpacing: "0.1em", textTransform: "uppercase", padding: "0 8px", marginBottom: 8 }}>
              Navigation
            </div>
          )}
          {NAV_ITEMS.map(item => (
            <button key={item.id} onClick={() => setActiveNav(item.id)} style={{
              display: "flex", alignItems: "center", gap: 10,
              width: "100%", padding: "10px 10px", borderRadius: 8,
              background: activeNav === item.id ? C.accentSoft : "transparent",
              border: activeNav === item.id ? `1px solid ${C.accent}44` : "1px solid transparent",
              color: activeNav === item.id ? C.accent : C.sub,
              cursor: "pointer", fontSize: 13, fontWeight: activeNav === item.id ? 600 : 400,
              marginBottom: 4, textAlign: "left", transition: "all 0.15s",
            }}>
              <span style={{ fontSize: 16, flexShrink: 0 }}>{item.icon}</span>
              {sidebarOpen && item.label}
            </button>
          ))}
        </nav>

        {/* Logout */}
        <div style={{ padding: "12px 8px", borderTop: `1px solid ${C.border}` }}>
          <button style={{
            display: "flex", alignItems: "center", gap: 10,
            width: "100%", padding: "10px 10px", borderRadius: 8,
            background: "transparent", border: "1px solid transparent",
            color: C.muted, cursor: "pointer", fontSize: 13,
          }}>
            <span style={{ fontSize: 16 }}>🚪</span>
            {sidebarOpen && "Logout"}
          </button>
        </div>
      </aside>

      {/* ── Main Content ── */}
      <main style={{ flex: 1, overflowY: "auto", padding: "0 0 40px 0" }}>

        {/* Top bar */}
        <div style={{
          position: "sticky", top: 0, zIndex: 9,
          background: `${C.surface}ee`, backdropFilter: "blur(8px)",
          borderBottom: `1px solid ${C.border}`, padding: "12px 28px",
          display: "flex", alignItems: "center", justifyContent: "space-between",
        }}>
          <div>
            <span style={{ color: C.muted, fontSize: 12 }}>Student Early Performance Prediction System</span>
            <span style={{ color: C.border, margin: "0 8px" }}>›</span>
            <span style={{ color: C.text, fontSize: 12, fontWeight: 600 }}>Dashboard</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <span style={{ fontSize: 11, color: C.muted }}>Last updated: {student.lastUpdated}</span>
            <Badge label={student.status} color={riskColor} bg={riskBg} />
            <div style={{
              width: 32, height: 32, borderRadius: "50%",
              background: `linear-gradient(135deg, ${C.accent}, ${C.purple})`,
              display: "flex", alignItems: "center", justifyContent: "center",
              fontWeight: 700, fontSize: 12, color: "#fff",
            }}>{student.avatar}</div>
          </div>
        </div>

        <div style={{ padding: "28px 28px 0" }}>

          {/* Welcome Banner */}
          <div style={{
            background: `linear-gradient(135deg, ${C.accentSoft} 0%, #1a1040 100%)`,
            border: `1px solid ${C.accent}44`, borderRadius: 16, padding: "22px 28px",
            display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24,
          }}>
            <div>
              <div style={{ fontSize: 22, fontWeight: 800, color: C.text }}>
                Welcome back, {student.name.split(" ")[0]} 👋
              </div>
              <div style={{ color: C.sub, fontSize: 13, marginTop: 4 }}>
                {student.branch} · {student.semester} · ID: {student.id}
              </div>
              <div style={{ display: "flex", gap: 10, marginTop: 12 }}>
                <Badge label={student.status} color={riskColor} bg={riskBg} />
                <Badge label={`CGPA ${student.predictedCGPA}`} color={cgpaColor} bg={C.surface} />
                <Badge label="ML Powered" color={C.purple} bg={C.purpleSoft} />
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: 11, color: C.muted, marginBottom: 6 }}>Model Confidence</div>
              <div style={{ fontSize: 32, fontWeight: 900, color: C.accent }}>{student.modelConf}%</div>
              <div style={{ fontSize: 11, color: C.muted }}>Random Forest · 200 estimators</div>
            </div>
          </div>

          {/* 4 Metric Cards */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: 24 }}>
            <Card style={{ borderTop: `3px solid ${C.red}` }}>
              <div style={{ fontSize: 11, color: C.muted, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 10 }}>Dropout Probability</div>
              <div style={{ fontSize: 36, fontWeight: 900, color: C.red }}>{student.dropoutProb}%</div>
              <div style={{ marginTop: 10 }}>
                <div style={{ background: C.surface, borderRadius: 4, height: 6, overflow: "hidden" }}>
                  <div style={{ width: `${student.dropoutProb}%`, height: "100%", background: `linear-gradient(90deg, ${C.amber}, ${C.red})`, borderRadius: 4 }} />
                </div>
              </div>
              <div style={{ marginTop: 8 }}><Badge label="HIGH RISK" color={C.red} bg={C.redSoft} /></div>
            </Card>

            <Card style={{ borderTop: `3px solid ${cgpaColor}` }}>
              <div style={{ fontSize: 11, color: C.muted, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 10 }}>Predicted CGPA</div>
              <div style={{ fontSize: 36, fontWeight: 900, color: cgpaColor }}>{student.predictedCGPA}</div>
              <div style={{ color: C.muted, fontSize: 12, marginTop: 6 }}>Based on current trajectory</div>
              <div style={{ marginTop: 10 }}><Badge label="Below Target 7.5" color={C.amber} bg={C.amberSoft} /></div>
            </Card>

            <Card style={{ borderTop: `3px solid ${C.accent}` }}>
              <div style={{ fontSize: 11, color: C.muted, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 10 }}>Overall Score</div>
              <div style={{ fontSize: 36, fontWeight: 900, color: C.accent }}>{student.overallScore}</div>
              <div style={{ color: C.muted, fontSize: 12, marginTop: 6 }}>Weighted composite (/ 100)</div>
              <div style={{ marginTop: 10 }}><Badge label="Below Average" color={C.amber} bg={C.amberSoft} /></div>
            </Card>

            <Card style={{ borderTop: `3px solid ${riskColor}`, background: riskBg }}>
              <div style={{ fontSize: 11, color: C.muted, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 10 }}>Academic Status</div>
              <div style={{ fontSize: 32, fontWeight: 900, color: riskColor }}>{student.status}</div>
              <div style={{ color: C.muted, fontSize: 12, marginTop: 6 }}>System evaluation</div>
              <div style={{ marginTop: 10, fontSize: 12, color: riskColor }}>⚠ Immediate action required</div>
            </Card>
          </div>

          {/* SHAP + Recommendations */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 24 }}>
            <Card>
              <SectionTitle icon="🔍" title="Why This Prediction?" sub="SHAP values — how each factor pushes your dropout risk up (▲) or down (▼)" />
              {shapData.map(d => <ShapBar key={d.feature} {...d} />)}
              <div style={{ display: "flex", gap: 16, marginTop: 10, padding: "10px 12px", background: C.surface, borderRadius: 8, border: `1px solid ${C.border}` }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <div style={{ width: 10, height: 10, borderRadius: 2, background: C.red }} />
                  <span style={{ fontSize: 11, color: C.muted }}>Increases dropout risk</span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <div style={{ width: 10, height: 10, borderRadius: 2, background: C.green }} />
                  <span style={{ fontSize: 11, color: C.muted }}>Decreases dropout risk</span>
                </div>
              </div>
            </Card>

            <Card>
              <SectionTitle icon="💡" title="Personalised Recommendations" sub="Actionable steps based on your ML-predicted risk profile" />
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {recommendations.map((r, i) => (
                  <div key={i} style={{
                    background: C.surface, border: `1px solid ${C.border}`,
                    borderLeft: `3px solid ${r.priority === "critical" ? C.red : r.priority === "high" ? C.amber : C.accent}`,
                    borderRadius: 8, padding: "10px 12px", display: "flex", gap: 10, alignItems: "flex-start",
                  }}>
                    <span style={{ fontSize: 16, flexShrink: 0 }}>{r.icon}</span>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 3 }}>
                        <span style={{ color: C.text, fontWeight: 600, fontSize: 13 }}>{r.title}</span>
                        <PriorityDot level={r.priority} />
                      </div>
                      <p style={{ color: C.muted, fontSize: 12, lineHeight: 1.5, margin: 0 }}>{r.detail}</p>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </div>

          {/* Performance Metrics + Radar */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 24 }}>
            <Card>
              <SectionTitle icon="📈" title="Current Performance Metrics" />
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginBottom: 20 }}>
                {[
                  { label: "Attendance",  value: `${apiData.attendance}%`,           color: C.red,    icon: "📅", sub: "Min. 75%" },
                  { label: "Assignments", value: `${apiData.assignment_score}/100`,   color: C.amber,  icon: "📝", sub: "Avg. 68/100" },
                  { label: "Mid-terms",   value: `${apiData.marks}/100`,              color: C.red,    icon: "📋", sub: "Avg. 60/100" },
                  { label: "Backlogs",    value: `${apiData.backlogs}`,               color: C.amber,  icon: "📌", sub: "Active" },
                  { label: "CGPA",        value: student.predictedCGPA,               color: C.amber,  icon: "🎓", sub: "Target: 7.5" },
                  { label: "Class Rank",  value: `${apiData.rank}`,                   color: C.accent, icon: "🏅", sub: `/ ${apiData.class_size}` },
                ].map(m => (
                  <div key={m.label} style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 10, padding: "12px 14px" }}>
                    <div style={{ fontSize: 18, marginBottom: 4 }}>{m.icon}</div>
                    <div style={{ fontSize: 18, fontWeight: 800, color: m.color }}>{m.value}</div>
                    <div style={{ fontSize: 12, color: C.text, fontWeight: 600 }}>{m.label}</div>
                    <div style={{ fontSize: 11, color: C.muted }}>{m.sub}</div>
                  </div>
                ))}
              </div>
              <SectionTitle icon="📚" title="Subject-wise Marks" sub="Mid-term scores out of 50" />
              {subjectMarks.map(s => (
                <StatBar key={s.subject} label={s.subject} value={s.marks} max={s.total}
                  color={s.marks >= 35 ? C.green : s.marks >= 28 ? C.amber : C.red} />
              ))}
            </Card>

            <Card>
              <SectionTitle icon="🕸️" title="Academic Competency Radar" sub="Holistic view of performance dimensions (0–100 scale)" />
              <ResponsiveContainer width="100%" height={270}>
                <RadarChart data={radarData} margin={{ top: 10, right: 20, bottom: 10, left: 20 }}>
                  <PolarGrid stroke={C.border} />
                  <PolarAngleAxis dataKey="subject" tick={{ fill: C.sub, fontSize: 11 }} />
                  <Radar name="You" dataKey="A" stroke={C.accent} fill={C.accent} fillOpacity={0.25} strokeWidth={2} />
                  <Tooltip contentStyle={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 8 }} labelStyle={{ color: C.text }} itemStyle={{ color: C.accent }} />
                </RadarChart>
              </ResponsiveContainer>
              <div style={{ marginTop: 10, display: "flex", justifyContent: "center", padding: "14px", background: C.surface, borderRadius: 10, border: `1px solid ${C.border}` }}>
                <RiskGauge value={student.dropoutProb} />
              </div>
            </Card>
          </div>

          {/* CGPA Trend */}
          <Card style={{ marginBottom: 24 }}>
            <SectionTitle icon="📉" title="CGPA & Performance Trend" sub="Semester-wise progression — current semester marked with *" />
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={performanceHistory} margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                <XAxis dataKey="sem" tick={{ fill: C.muted, fontSize: 12 }} axisLine={{ stroke: C.border }} tickLine={false} />
                <YAxis tick={{ fill: C.muted, fontSize: 12 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 8, fontSize: 12 }} labelStyle={{ color: C.text }} />
                <Legend wrapperStyle={{ color: C.sub, fontSize: 12, paddingTop: 10 }} />
                <ReferenceLine y={7.5} stroke={C.green} strokeDasharray="4 4" label={{ value: "Target 7.5", fill: C.green, fontSize: 11 }} />
                <Line type="monotone" dataKey="cgpa"        stroke={C.accent} strokeWidth={2.5} dot={{ fill: C.accent, r: 4 }} name="CGPA" />
                <Line type="monotone" dataKey="attendance"  stroke={C.red}    strokeWidth={2}   dot={{ fill: C.red,    r: 3 }} name="Attendance %" />
                <Line type="monotone" dataKey="assignments" stroke={C.amber}  strokeWidth={2}   dot={{ fill: C.amber,  r: 3 }} name="Assignment %" />
              </LineChart>
            </ResponsiveContainer>
          </Card>

          {/* Bar Chart */}
          <Card style={{ marginBottom: 8 }}>
            <SectionTitle icon="📊" title="Subject Performance Breakdown" sub="Mid-term marks vs. class average (out of 50)" />
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={subjectMarks.map(s => ({ subject: s.subject, "Your Marks": s.marks, "Class Avg": 34 }))}
                margin={{ top: 5, right: 20, left: 0, bottom: 5 }} barSize={22}>
                <CartesianGrid strokeDasharray="3 3" stroke={C.border} vertical={false} />
                <XAxis dataKey="subject" tick={{ fill: C.muted, fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis domain={[0, 50]} tick={{ fill: C.muted, fontSize: 12 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 8, fontSize: 12 }} cursor={{ fill: C.border + "55" }} />
                <Legend wrapperStyle={{ color: C.sub, fontSize: 12, paddingTop: 10 }} />
                <Bar dataKey="Your Marks" fill={C.accent} radius={[5, 5, 0, 0]} />
                <Bar dataKey="Class Avg"  fill={C.border} radius={[5, 5, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>

          {/* Footer */}
          <div style={{ marginTop: 20, padding: "14px 0", borderTop: `1px solid ${C.border}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ color: C.muted, fontSize: 12 }}>SEPPS — Student Early Performance Prediction System · Flask + SQLite + Random Forest</span>
            <span style={{ color: C.muted, fontSize: 12 }}>© 2026 · Predictions are advisory only</span>
          </div>

        </div>
      </main>
    </div>
  );
}