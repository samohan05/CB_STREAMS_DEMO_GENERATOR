import { useState, useEffect } from "react";

// ─── Product Catalog ─────────────────────────────────────────────────────────
const PRODUCTS = [
  { id:"mri",  emoji:"🔬", label:"MRI Systems",       domain:"Magnetic Resonance Imaging (MRI) Systems",         industry:"Medical Device / Radiology" },
  { id:"us",   emoji:"🏥", label:"Ultrasound",         domain:"Diagnostic Ultrasound Imaging Systems",            industry:"Medical Device / Radiology" },
  { id:"ct",   emoji:"🫁", label:"CT Scanner",          domain:"Computed Tomography (CT) Scanner Systems",         industry:"Medical Device / Radiology" },
  { id:"igt",  emoji:"🩺", label:"Image-Guided Therapy",domain:"Image-Guided Therapy & Intervention Systems",      industry:"Medical Device / Interventional" },
  { id:"pm",   emoji:"📊", label:"Patient Monitoring",  domain:"Multi-Parameter Patient Monitoring Systems",       industry:"Medical Device / Critical Care" },
  { id:"rt",   emoji:"☢️", label:"Radiotherapy",        domain:"External Beam Radiation Therapy Delivery Systems", industry:"Medical Device / Oncology" },
  { id:"pace", emoji:"❤️", label:"Pacemakers",          domain:"Implantable Cardiac Rhythm Management Devices",    industry:"Medical Device / Cardiology" },
  { id:"adas", emoji:"🚗", label:"ADAS Systems",        domain:"Advanced Driver Assistance Systems (ADAS/AD)",     industry:"Automotive / Safety-Critical" },
];

// ─── Tier config ─────────────────────────────────────────────────────────────
const TIERS = [
  { key:"library_streams",      label:"Library Streams",      short:"LIB", clr:"#0F6E56", bg:"#E1F5EE" },
  { key:"product_line_streams", label:"Product Line Streams",  short:"PL",  clr:"#534AB7", bg:"#EEEDFE" },
  { key:"transform_streams",    label:"Transform Streams",     short:"TR",  clr:"#854F0B", bg:"#FAEEDA" },
  { key:"release_streams",      label:"Release Streams",       short:"REL", clr:"#185FA5", bg:"#E6F1FB" },
];

// ─── Styles ──────────────────────────────────────────────────────────────────
const inputStyle = {
  width: "100%", boxSizing: "border-box", padding: "8px 10px",
  borderRadius: 8, border: "0.5px solid var(--color-border-secondary)",
  background: "var(--color-background-primary)", fontSize: 12,
  color: "var(--color-text-primary)", fontFamily: "var(--font-sans)",
};
const btnStyle = (primary) => ({
  padding: "8px 18px", borderRadius: 8, fontSize: 12, fontWeight: 500,
  cursor: "pointer", border: "0.5px solid var(--color-border-secondary)",
  background: primary ? "var(--color-text-primary)" : "var(--color-background-primary)",
  color: primary ? "var(--color-background-primary)" : "var(--color-text-primary)",
});
const btnDisabled = { ...btnStyle(true), opacity: 0.4, cursor: "not-allowed" };
const chipStyle = (active) => ({
  padding: "6px 12px", borderRadius: 8, fontSize: 11, fontWeight: 500, cursor: "pointer",
  border: `0.5px solid ${active ? "var(--color-border-primary)" : "var(--color-border-tertiary)"}`,
  background: active ? "var(--color-background-secondary)" : "transparent",
  color: active ? "var(--color-text-primary)" : "var(--color-text-secondary)",
});

// ─── Helpers ─────────────────────────────────────────────────────────────────
const esc  = s => (s||"").replace(/\\/g,"\\\\").replace(/"/g,'\\"').replace(/\r?\n/g," ").trim();
const safeV = s => (s||"x").replace(/[^a-zA-Z0-9]/g,"_").replace(/^(\d)/,"_$1");

// ─── JSON Parser (robust) ────────────────────────────────────────────────────
function sanitizeJson(raw) {
  let s = raw.trim().replace(/^\uFEFF/, '').replace(/^```json?\s*/im,'').replace(/\s*```\s*$/im,'');
  let out = '', inStr = false, isEscaped = false;
  for (let i = 0; i < s.length; i++) {
    const ch = s[i];
    if (isEscaped)   { out += ch; isEscaped = false; continue; }
    if (ch === '\\') { out += ch; isEscaped = true;  continue; }
    if (ch === '"')  { out += ch; inStr = !inStr; continue; }
    if (inStr) {
      if      (ch === '\n') out += '\\n';
      else if (ch === '\r') out += '\\r';
      else if (ch === '\t') out += '\\t';
      else                   out += ch;
    } else { out += ch; }
  }
  return out;
}
function parseAIJson(raw) {
  const fix = s => s.replace(/,(\s*[}\]])/g, '$1');
  const attempts = [
    () => JSON.parse(fix(sanitizeJson(raw))),
    () => { const m = sanitizeJson(raw).match(/\{[\s\S]*/); if (!m) throw new Error('no {'); return JSON.parse(fix(m[0])); },
    () => {
      let s = fix(sanitizeJson(raw).match(/\{[\s\S]*/)?.[0] || '');
      let b=0, k=0, inS=false, e2=false;
      for (const ch of s) {
        if (e2)          { e2=false; continue; }
        if (ch==='\\') { e2=true;  continue; }
        if (ch==='"')    { inS=!inS; continue; }
        if (inS)         continue;
        if (ch==='{') b++; else if (ch==='}') b--;
        if (ch==='[') k++; else if (ch===']') k--;
      }
      if (inS) s+='"';
      while(k>0){s+=']';k--;} while(b>0){s+='}';b--;}
      return JSON.parse(fix(s));
    },
  ];
  for (const fn of attempts) { try { return fn(); } catch(_) {} }
  throw new Error('JSON repair failed — retry with fewer products.');
}

// ─── Step Progress Bar ───────────────────────────────────────────────────────
const STEP_LABELS = ["Product", "Projects", "Requirements", "Streams", "Summary"];
function StepBar({ current }) {
  return (
    <div style={{ display:"flex", gap:2, marginBottom:20 }}>
      {STEP_LABELS.map((lbl, i) => (
        <div key={i} style={{ flex:1, textAlign:"center" }}>
          <div style={{
            height:4, borderRadius:2, marginBottom:4,
            background: i < current ? "#1D9E75" : i === current ? "var(--color-text-primary)" : "var(--color-background-tertiary)",
          }} />
          <span style={{ fontSize:10, color: i <= current ? "var(--color-text-secondary)" : "var(--color-text-tertiary)" }}>{lbl}</span>
        </div>
      ))}
    </div>
  );
}

// ─── Stat Chip ───────────────────────────────────────────────────────────────
function Stat({ value, label, color }) {
  return (
    <div style={{ textAlign:"center", padding:"8px 6px", borderRadius:8,
      border:"0.5px solid var(--color-border-tertiary)", background:"var(--color-background-secondary)" }}>
      <div style={{ fontSize:18, fontWeight:600, color }}>{value}</div>
      <div style={{ fontSize:10, color:"var(--color-text-secondary)" }}>{label}</div>
    </div>
  );
}

// ─── Status Badge ────────────────────────────────────────────────────────────
function StatusBadge({ status }) {
  const cfg = {
    pending:  { bg:"var(--color-background-tertiary)", color:"var(--color-text-tertiary)", text:"Pending" },
    creating: { bg:"#FEF3C7", color:"#92400E", text:"Creating..." },
    done:     { bg:"#D1FAE5", color:"#065F46", text:"Created" },
    error:    { bg:"#FEE2E2", color:"#991B1B", text:"Failed" },
  }[status] || { bg:"transparent", color:"var(--color-text-tertiary)", text:status };
  return (
    <span style={{ padding:"2px 8px", borderRadius:10, fontSize:10, fontWeight:500, background:cfg.bg, color:cfg.color }}>
      {cfg.text}
    </span>
  );
}


// ═════════════════════════════════════════════════════════════════════════════
// MAIN APP — v4 (direct API execution, no Python script)
// ═════════════════════════════════════════════════════════════════════════════
export default function App() {
  // ── Wizard step ──
  const [step, setStep] = useState(0); // 0=product, 1=projects, 2=reqs, 3=streams, 4=summary

  // ── Step 0: Product selection ──
  const [product, setProduct] = useState(null);
  const [customDomain, setCustomDomain] = useState("");
  const [customIndustry, setCustomIndustry] = useState("");

  // ── CB Connection (defaults from env — editable) ──
  const [cbUrl,  setCbUrl]  = useState("");
  const [cbUser, setCbUser] = useState("");
  const [cbPass, setCbPass] = useState("");

  // ── OpenAI config ──
  const [openaiKey, setOpenaiKey] = useState("");

  // ── Data ──
  const [struct, setStruct] = useState(null);       // AI-generated structure
  const [err, setErr]       = useState("");
  const [generating, setGenerating] = useState(false);
  const [genStage, setGenStage] = useState("");

  // ── Project creation state ──
  const [projectStatus, setProjectStatus] = useState({}); // { idx: "pending"|"creating"|"done"|"error" }
  const [projectIds, setProjectIds]       = useState({}); // { idx: serverId }
  const [projectTrackers, setProjectTrackers] = useState({}); // { idx: { reqTrackerId, tcTrackerId } }
  const [projectErrors, setProjectErrors] = useState({}); // { idx: "error message" }

  // Derived
  const domain   = product ? product.domain : customDomain;
  const industry = product ? product.industry : customIndustry;

  // ── Deep-clone helper ──
  const updateStruct = (fn) => {
    setStruct(prev => {
      const clone = JSON.parse(JSON.stringify(prev));
      fn(clone);
      return clone;
    });
  };

  // ══════════════════════════════════════════════════════════════════════════
  // OpenAI GPT-4o Generation
  // ══════════════════════════════════════════════════════════════════════════
  const buildProjectPrompt = () => {
    return `You are a world-class ALM architect. Generate technically accurate Codebeamer demo data for:
Domain: ${domain}
Industry: ${industry}

CRITICAL: Return ONLY raw valid JSON. No markdown. No backticks. No text outside JSON.
CRITICAL: All string values max 120 chars. No real newlines inside strings. Use \\n only in steps fields.
CRITICAL: project_key max 8 alphanumeric/underscore chars. No spaces. No hyphens.
CRITICAL: No apostrophes in any string value.

Return this exact structure:
{
  "domain_name": "short label",
  "projects": [
    {
      "project_key": "MAXEIGHT",
      "project_name": "Meaningful Subsystem Name",
      "description": "What this project holds, max 80 chars",
      "subsystem": "Which subsystem this belongs to (e.g. Magnet, RF, Gradient)",
      "requirements": [
        {
          "title": "The [component] shall [verb] [value+unit] per [standard]",
          "description": "One sentence technical context max 100 chars.",
          "priority": "High",
          "level": "System",
          "test_cases": [{
            "title": "Verify [aspect] under [condition]",
            "description": "Test objective max 80 chars.",
            "steps": "1. Setup per standard\\n2. Apply stimulus\\n3. Measure with instrument",
            "expected_result": "Specific measurable criterion with unit and tolerance"
          }]
        }
      ]
    }
  ],
  "library_streams": [
    { "stream_key": "LIB_XXX", "stream_name": "Descriptive Name", "description": "max 80 chars", "project_keys": ["KEY1","KEY2"], "parent_stream_key": null }
  ],
  "product_line_streams": [
    { "stream_key": "PL_XXX", "stream_name": "Descriptive Name", "description": "max 80 chars", "project_keys": ["all 6 keys"], "parent_stream_key": null }
  ],
  "transform_streams": [
    { "stream_key": "TR_XXX", "stream_name": "Descriptive Name", "description": "max 80 chars", "project_keys": ["all 6 keys"], "parent_stream_key": "PL_XXX" }
  ],
  "release_streams": [
    { "stream_key": "REL_XXX", "stream_name": "Fictional Product Release", "description": "max 80 chars", "project_keys": ["all 6 keys"], "parent_stream_key": "TR_XXX" }
  ]
}

STRICT QUANTITIES:
- projects: exactly 6 (3 subsystem domains x 2 projects each)
- Each project: exactly 5 requirements
- Each requirement: exactly 1 test case
- library_streams: exactly 3 (one per subsystem, each references its 2 projects)
- product_line_streams: exactly 2 (each references ALL 6 projects)
- transform_streams: exactly 2 (each references ALL 6 projects, parent = a PL stream)
- release_streams: exactly 3 (each references ALL 6 projects, parent = a Transform stream)

CONTENT RULES:
- Use real standards: IEC 60601/62304 for medical, ISO 26262 for automotive, DO-178C for avionics
- Requirements: shall-style with measurable values, units, tolerances
- Release stream_name: plausible fictional product names, never real trademarks
- 3 library streams must cover DISTINCT technical subsystems of ${domain}
- All keys globally unique, max 8 chars`;
  };

  const generateProjects = async () => {
    if (!domain.trim() || !openaiKey.trim()) return;
    setGenerating(true);
    setErr("");
    setGenStage("Connecting to OpenAI GPT-4o...");

    try {
      setGenStage("Generating projects, requirements & streams...");
      const resp = await fetch("https://api.openai.com/v1/chat/completions", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${openaiKey}`,
        },
        body: JSON.stringify({
          model: "gpt-4o",
          temperature: 0.3,
          max_tokens: 8192,
          messages: [
            { role: "system", content: "You are a world-class ALM architect. Return ONLY raw valid JSON. No markdown, no code fences, no preamble." },
            { role: "user", content: buildProjectPrompt() },
          ],
        }),
      });

      if (!resp.ok) {
        let msg = `OpenAI API returned ${resp.status}`;
        try { const d = await resp.json(); if (d.error) msg = d.error.message; } catch(_) {}
        throw new Error(msg);
      }
      const data = await resp.json();
      const rawText = data.choices?.[0]?.message?.content || "";
      if (!rawText.trim()) throw new Error("Empty response from OpenAI");

      setGenStage("Parsing AI response...");
      const parsed = parseAIJson(rawText);
      if (!parsed.projects?.length) throw new Error("No projects in AI response");

      setStruct(parsed);
      setProjectStatus({});
      setProjectIds({});
      setProjectTrackers({});
      setProjectErrors({});
      setStep(1);
    } catch(e) {
      setErr(e.message);
    } finally {
      setGenerating(false);
      setGenStage("");
    }
  };

  // ══════════════════════════════════════════════════════════════════════════
  // CB API Helpers (run in browser via fetch)
  // ══════════════════════════════════════════════════════════════════════════
  const cbFetch = async (method, path, body = null) => {
    const base = (cbUrl || "").replace(/\/+$/, "");
    const url = `${base}${path}`;
    const headers = {
      "Content-Type": "application/json",
      "Accept": "application/json",
      "Authorization": "Basic " + btoa(`${cbUser}:${cbPass}`),
    };
    const opts = { method, headers };
    if (body) opts.body = JSON.stringify(body);
    const r = await fetch(url, opts);
    if (!r.ok) {
      let detail = "";
      try { detail = await r.text(); } catch(_) {}
      throw new Error(`${r.status} ${r.statusText}: ${detail.substring(0, 300)}`);
    }
    const text = await r.text();
    return text ? JSON.parse(text) : null;
  };
  const cbGet  = (path) => cbFetch("GET", path);
  const cbPost = (path, body) => cbFetch("POST", path, body);
  const cbPut  = (path, body) => cbFetch("PUT", path, body);

  // v1 API for project creation (v3 has no POST /projects)
  const cbPostV1 = async (path, body) => {
    const base = (cbUrl || "").replace(/\/+$/, "");
    const url = `${base}/cb/rest${path}`;
    const headers = {
      "Content-Type": "application/json",
      "Accept": "application/json",
      "Authorization": "Basic " + btoa(`${cbUser}:${cbPass}`),
    };
    const r = await fetch(url, { method: "POST", headers, body: JSON.stringify(body) });
    if (!r.ok) {
      let detail = "";
      try { detail = await r.text(); } catch(_) {}
      throw new Error(`${r.status} ${r.statusText}: ${detail.substring(0, 300)}`);
    }
    const text = await r.text();
    return text ? JSON.parse(text) : null;
  };

  // ══════════════════════════════════════════════════════════════════════════
  // Project creation (Step 1)
  // ══════════════════════════════════════════════════════════════════════════
  const createProject = async (idx) => {
    const p = struct.projects[idx];
    setProjectStatus(prev => ({ ...prev, [idx]: "creating" }));
    setProjectErrors(prev => { const n = {...prev}; delete n[idx]; return n; });
    try {
      // Create project via v1 REST API
      const result = await cbPostV1("/project", {
        name: p.project_name,
        keyName: p.project_key.substring(0, 8),
        description: p.description || p.project_name,
      });
      const pid = result?.id || (result?.uri ? parseInt(result.uri.split("/").pop()) : null);
      if (!pid) throw new Error("No project ID in response");

      // Discover trackers from default template
      const trackers = await cbGet(`/cb/api/v3/projects/${pid}/trackers`);
      const trackerList = Array.isArray(trackers) ? trackers : (trackers?.trackers || trackers?.items || []);
      let reqTrackerId = null, tcTrackerId = null;
      for (const t of trackerList) {
        const name = (t.name || "").toLowerCase();
        if (name.includes("requirement") && !reqTrackerId) reqTrackerId = t.id;
        if (name.includes("test") && name.includes("case") && !tcTrackerId) tcTrackerId = t.id;
      }

      setProjectIds(prev => ({ ...prev, [idx]: pid }));
      setProjectTrackers(prev => ({ ...prev, [idx]: { reqTrackerId, tcTrackerId } }));
      setProjectStatus(prev => ({ ...prev, [idx]: "done" }));
    } catch(e) {
      setProjectStatus(prev => ({ ...prev, [idx]: "error" }));
      setProjectErrors(prev => ({ ...prev, [idx]: e.message }));
    }
  };

  const allProjectsCreated = struct?.projects?.length > 0 &&
    struct.projects.every((_, i) => projectStatus[i] === "done");

  // ══════════════════════════════════════════════════════════════════════════
  // Requirement & TC creation (Step 2) — will be implemented in Phase 3
  // ══════════════════════════════════════════════════════════════════════════
  const [reqStatus, setReqStatus] = useState({}); // { projectIdx: "pending"|"creating"|"done"|"error" }
  const [reqErrors, setReqErrors] = useState({});
  const [reqCounts, setReqCounts] = useState({}); // { projectIdx: { reqs, tcs, verifies } }

  const createTrackerItems = async (idx) => {
    // Phase 3 implementation
    setReqStatus(prev => ({ ...prev, [idx]: "creating" }));
    setReqErrors(prev => { const n = {...prev}; delete n[idx]; return n; });
    const p = struct.projects[idx];
    const trackers = projectTrackers[idx];
    const pid = projectIds[idx];

    if (!trackers?.reqTrackerId || !trackers?.tcTrackerId) {
      setReqStatus(prev => ({ ...prev, [idx]: "error" }));
      setReqErrors(prev => ({ ...prev, [idx]: "Missing tracker IDs. Ensure project was created with default template." }));
      return;
    }

    try {
      let reqCount = 0, tcCount = 0, verifyCount = 0;
      const reqs = p.requirements || [];

      // Create requirements
      const reqIds = [];
      for (const req of reqs) {
        const r = await cbPost(`/cb/api/v3/trackers/${trackers.reqTrackerId}/items`, {
          name: req.title,
          description: req.description || "",
        });
        reqIds.push(r.id);
        reqCount++;
      }

      // Create test cases with Verifies links
      // TC1 links to reqs 0,1,2 — TC2 links to reqs 3,4
      const tcGroups = [reqIds.slice(0, 3), reqIds.slice(3)];
      for (const group of tcGroups) {
        if (group.length === 0) continue;
        // Find a TC from the first req in this group
        const srcReqIdx = reqIds.indexOf(group[0]);
        const tcData = reqs[srcReqIdx]?.test_cases?.[0];
        if (!tcData) continue;

        const tc = await cbPost(`/cb/api/v3/trackers/${trackers.tcTrackerId}/items`, {
          name: tcData.title,
          description: `${tcData.description || ""}\nSteps: ${tcData.steps || ""}\nExpected: ${tcData.expected_result || ""}`,
        });
        tcCount++;

        // Set Verifies field for each req in this group
        for (const reqId of group) {
          try {
            await cbPut(`/cb/api/v3/items/${tc.id}/fields`, {
              fieldValues: [{
                fieldId: 17, // Verifies field — standard default
                name: "Verifies",
                type: "ChoiceFieldValue",
                values: [{ id: reqId, type: "TrackerItemReference" }],
              }],
            });
            verifyCount++;
          } catch(_) { /* Verifies link may fail on some instances */ }
        }
      }

      setReqCounts(prev => ({ ...prev, [idx]: { reqs: reqCount, tcs: tcCount, verifies: verifyCount } }));
      setReqStatus(prev => ({ ...prev, [idx]: "done" }));
    } catch(e) {
      setReqStatus(prev => ({ ...prev, [idx]: "error" }));
      setReqErrors(prev => ({ ...prev, [idx]: e.message }));
    }
  };

  const allReqsCreated = struct?.projects?.length > 0 &&
    struct.projects.every((_, i) => reqStatus[i] === "done");

  // ══════════════════════════════════════════════════════════════════════════
  // Stream creation (Step 3) — will be fully implemented in Phase 4
  // ══════════════════════════════════════════════════════════════════════════
  const [streamStatus, setStreamStatus]   = useState({}); // { "LIB_0": "done", ... }
  const [streamIds, setStreamIds]         = useState({}); // { stream_key: serverId }
  const [streamErrors, setStreamErrors]   = useState({});
  const [initialStreamId, setInitialStreamId] = useState(null);

  // Fetch initial stream ID when entering step 3
  useEffect(() => {
    if (step === 3 && !initialStreamId && cbUrl) {
      cbGet("/cb/api/v3/streams/initial")
        .then(r => {
          const id = typeof r === "number" ? r : (r?.id || r?.streamId || r);
          setInitialStreamId(id);
        })
        .catch(() => {});
    }
  }, [step]);

  const getSourceStreamId = (tierKey, stream) => {
    if (tierKey === "library_streams") return initialStreamId;
    if (tierKey === "product_line_streams") {
      // PL sources from first library stream
      const libKeys = (struct?.library_streams || []).map(s => s.stream_key);
      for (const k of libKeys) { if (streamIds[k]) return streamIds[k]; }
      return initialStreamId;
    }
    if (tierKey === "transform_streams") {
      // Transform sources from its parent PL
      const parentKey = stream.parent_stream_key;
      return parentKey ? streamIds[parentKey] : null;
    }
    if (tierKey === "release_streams") {
      // Release sources from its parent Transform
      const parentKey = stream.parent_stream_key;
      return parentKey ? streamIds[parentKey] : null;
    }
    return null;
  };

  const createStream = async (tierKey, idx) => {
    const streams = struct[tierKey] || [];
    const st = streams[idx];
    const sKey = `${tierKey}_${idx}`;
    setStreamStatus(prev => ({ ...prev, [sKey]: "creating" }));
    setStreamErrors(prev => { const n = {...prev}; delete n[sKey]; return n; });

    try {
      // Create stream
      const parentId = (tierKey === "library_streams" || tierKey === "product_line_streams")
        ? null
        : (st.parent_stream_key ? streamIds[st.parent_stream_key] : null);

      const body = { name: st.stream_name, color: "#336699", description: st.description || "" };
      if (parentId) {
        body.sourceStreamId = parentId;
        body.isSourceStreamChecked = true;
      }
      const result = await cbPost("/cb/api/v3/streams/stream", body);
      const sid = result?.id;
      if (!sid) throw new Error("No stream ID in response");

      setStreamIds(prev => ({ ...prev, [st.stream_key]: sid }));

      // Add projects to stream
      const sourceId = getSourceStreamId(tierKey, st);
      for (const pk of (st.project_keys || [])) {
        const pidIdx = struct.projects.findIndex(p => p.project_key === pk);
        const pid = projectIds[pidIdx];
        if (pid && sourceId) {
          try {
            await cbPut(`/cb/api/v3/streams/${sid}/projects`, {
              projectId: pid,
              sourceStreamId: sourceId,
              addAllTrackers: true,
            });
          } catch(_) { /* non-fatal */ }
        }
      }

      setStreamStatus(prev => ({ ...prev, [sKey]: "done" }));
    } catch(e) {
      setStreamStatus(prev => ({ ...prev, [sKey]: "error" }));
      setStreamErrors(prev => ({ ...prev, [sKey]: e.message }));
    }
  };

  // ══════════════════════════════════════════════════════════════════════════
  // RENDER
  // ══════════════════════════════════════════════════════════════════════════
  return (
    <div style={{ padding:"1rem 0", fontFamily:"var(--font-sans)", maxWidth:700 }}>
      <div style={{ marginBottom:20 }}>
        <div style={{ fontSize:18, fontWeight:500, color:"var(--color-text-primary)" }}>
          CB Demo Generator v4
        </div>
        <div style={{ fontSize:12, color:"var(--color-text-secondary)", marginTop:3 }}>
          AI-powered Codebeamer ALM demo provisioning with live API execution
        </div>
      </div>

      <StepBar current={step} />

      {/* ══ Step 0: Product Selection ══════════════════════════════════════ */}
      {step === 0 && (
        <div>
          <div style={{ fontSize:13, fontWeight:500, marginBottom:10, color:"var(--color-text-primary)" }}>
            Select a product domain
          </div>
          <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:8, marginBottom:16 }}>
            {PRODUCTS.map(p => (
              <div key={p.id} onClick={() => setProduct(product?.id===p.id ? null : p)}
                style={{
                  padding:"10px 8px", borderRadius:8, cursor:"pointer", textAlign:"center",
                  border:`0.5px solid ${product?.id===p.id ? "var(--color-border-primary)" : "var(--color-border-tertiary)"}`,
                  background: product?.id===p.id ? "var(--color-background-secondary)" : "transparent",
                }}>
                <div style={{ fontSize:20, marginBottom:4 }}>{p.emoji}</div>
                <div style={{ fontSize:11, fontWeight:500, color:"var(--color-text-primary)" }}>{p.label}</div>
              </div>
            ))}
          </div>

          {!product && (
            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:10, marginBottom:16 }}>
              <div>
                <div style={{ fontSize:11, color:"var(--color-text-secondary)", marginBottom:4 }}>Custom domain</div>
                <input style={inputStyle} value={customDomain} onChange={e=>setCustomDomain(e.target.value)} placeholder="e.g. X-Ray Imaging Systems" />
              </div>
              <div>
                <div style={{ fontSize:11, color:"var(--color-text-secondary)", marginBottom:4 }}>Industry</div>
                <input style={inputStyle} value={customIndustry} onChange={e=>setCustomIndustry(e.target.value)} placeholder="e.g. Medical Device" />
              </div>
            </div>
          )}

          {product && (
            <div style={{ padding:"8px 12px", borderRadius:8, background:"var(--color-background-secondary)",
              border:"0.5px solid var(--color-border-tertiary)", fontSize:12, marginBottom:16, color:"var(--color-text-secondary)" }}>
              <strong style={{ color:"var(--color-text-primary)" }}>{product.emoji} {product.label}</strong>
              &nbsp;&middot;&nbsp;{product.domain}&nbsp;&middot;&nbsp;{product.industry}
            </div>
          )}

          {/* CB Connection */}
          <div style={{ fontSize:13, fontWeight:500, marginBottom:8, marginTop:20, color:"var(--color-text-primary)" }}>
            Codebeamer connection
          </div>
          <div style={{ fontSize:11, color:"var(--color-text-secondary)", marginBottom:10 }}>
            Pre-filled from environment variables. Edit if needed.
          </div>
          <div style={{ display:"grid", gap:10, marginBottom:16 }}>
            <div>
              <div style={{ fontSize:11, color:"var(--color-text-secondary)", marginBottom:4 }}>CB Base URL</div>
              <input style={inputStyle} value={cbUrl} onChange={e=>setCbUrl(e.target.value)} placeholder="https://your-cb-instance.com" />
            </div>
            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:10 }}>
              <div>
                <div style={{ fontSize:11, color:"var(--color-text-secondary)", marginBottom:4 }}>Username</div>
                <input style={inputStyle} value={cbUser} onChange={e=>setCbUser(e.target.value)} placeholder="admin" />
              </div>
              <div>
                <div style={{ fontSize:11, color:"var(--color-text-secondary)", marginBottom:4 }}>Password</div>
                <input type="password" style={inputStyle} value={cbPass} onChange={e=>setCbPass(e.target.value)} placeholder="password" />
              </div>
            </div>
          </div>

          {/* OpenAI Key */}
          <div style={{ fontSize:13, fontWeight:500, marginBottom:8, color:"var(--color-text-primary)" }}>
            OpenAI API Key
          </div>
          <input type="password" style={{...inputStyle, marginBottom:6}} value={openaiKey} onChange={e=>setOpenaiKey(e.target.value)} placeholder="sk-..." />
          <div style={{ fontSize:10, color:"var(--color-text-tertiary)", marginBottom:20 }}>
            Used to generate demo data via GPT-4o. Stored in memory only.
          </div>

          {err && (
            <div style={{ padding:"10px 14px", background:"var(--color-background-danger)", border:"0.5px solid var(--color-border-danger)",
              borderRadius:8, fontSize:12, color:"var(--color-text-danger)", marginBottom:12 }}>
              {err}
            </div>
          )}

          <button
            style={(!domain.trim() || !openaiKey.trim() || generating) ? btnDisabled : btnStyle(true)}
            disabled={!domain.trim() || !openaiKey.trim() || generating}
            onClick={generateProjects}
          >
            {generating ? genStage : "Generate Projects & Streams ✦"}
          </button>
        </div>
      )}

      {/* ══ Step 1: Projects (review + create) ════════════════════════════ */}
      {step === 1 && struct && (
        <div>
          <div style={{ fontSize:14, fontWeight:500, marginBottom:4, color:"var(--color-text-primary)" }}>
            Projects for {struct.domain_name}
          </div>
          <div style={{ fontSize:12, color:"var(--color-text-secondary)", marginBottom:16 }}>
            Review and create each project in Codebeamer. Projects use the default template (trackers are auto-discovered).
          </div>

          {struct.projects.map((p, idx) => (
            <div key={idx} style={{
              marginBottom:10, padding:"12px 14px", borderRadius:8,
              border:"0.5px solid var(--color-border-tertiary)",
              background:"var(--color-background-secondary)",
            }}>
              <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:8 }}>
                <div>
                  <div style={{ fontSize:13, fontWeight:500, color:"var(--color-text-primary)" }}>
                    {p.project_name}
                  </div>
                  <div style={{ fontSize:11, color:"var(--color-text-tertiary)" }}>
                    Key: {p.project_key} &middot; {p.description}
                  </div>
                </div>
                <div style={{ display:"flex", alignItems:"center", gap:8 }}>
                  <StatusBadge status={projectStatus[idx] || "pending"} />
                  {projectStatus[idx] !== "done" && projectStatus[idx] !== "creating" && (
                    <button style={btnStyle(true)} onClick={() => createProject(idx)}>
                      Create
                    </button>
                  )}
                </div>
              </div>

              {projectStatus[idx] === "done" && (
                <div style={{ fontSize:11, color:"#065F46", background:"#D1FAE5", padding:"6px 10px", borderRadius:6 }}>
                  Project ID: {projectIds[idx]}
                  {projectTrackers[idx]?.reqTrackerId && ` | Req Tracker: ${projectTrackers[idx].reqTrackerId}`}
                  {projectTrackers[idx]?.tcTrackerId && ` | TC Tracker: ${projectTrackers[idx].tcTrackerId}`}
                </div>
              )}
              {projectErrors[idx] && (
                <div style={{ fontSize:11, color:"#991B1B", background:"#FEE2E2", padding:"6px 10px", borderRadius:6 }}>
                  {projectErrors[idx]}
                </div>
              )}

              {/* Editable fields */}
              {projectStatus[idx] !== "done" && (
                <div style={{ display:"grid", gridTemplateColumns:"1fr 2fr", gap:8, marginTop:8 }}>
                  <div>
                    <div style={{ fontSize:10, color:"var(--color-text-tertiary)", marginBottom:2 }}>Key (max 8)</div>
                    <input style={{...inputStyle, fontSize:11}} value={p.project_key}
                      onChange={e => updateStruct(s => { s.projects[idx].project_key = e.target.value.substring(0,8).replace(/[^a-zA-Z0-9_]/g,""); })} />
                  </div>
                  <div>
                    <div style={{ fontSize:10, color:"var(--color-text-tertiary)", marginBottom:2 }}>Project Name</div>
                    <input style={{...inputStyle, fontSize:11}} value={p.project_name}
                      onChange={e => updateStruct(s => { s.projects[idx].project_name = e.target.value; })} />
                  </div>
                </div>
              )}
            </div>
          ))}

          <div style={{ display:"flex", gap:10, marginTop:16 }}>
            <button style={btnStyle(false)} onClick={() => setStep(0)}>← Back</button>
            <button
              style={allProjectsCreated ? btnStyle(true) : btnDisabled}
              disabled={!allProjectsCreated}
              onClick={() => setStep(2)}
            >
              Continue to Requirements →
            </button>
          </div>
        </div>
      )}

      {/* ══ Step 2: Requirements & Test Cases ═════════════════════════════ */}
      {step === 2 && struct && (
        <div>
          <div style={{ fontSize:14, fontWeight:500, marginBottom:4, color:"var(--color-text-primary)" }}>
            Requirements & Test Cases
          </div>
          <div style={{ fontSize:12, color:"var(--color-text-secondary)", marginBottom:16 }}>
            Create tracker items in each project. Uses "System Requirement Specification" and "Test Cases" trackers from the default template.
            Each project gets 5 requirements and 2 test cases (TC1 verifies reqs 1-3, TC2 verifies reqs 4-5).
          </div>

          {struct.projects.map((p, idx) => {
            const trackers = projectTrackers[idx];
            const reqs = p.requirements || [];
            return (
              <div key={idx} style={{
                marginBottom:12, padding:"12px 14px", borderRadius:8,
                border:"0.5px solid var(--color-border-tertiary)",
                background:"var(--color-background-secondary)",
              }}>
                <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:8 }}>
                  <div>
                    <div style={{ fontSize:13, fontWeight:500, color:"var(--color-text-primary)" }}>
                      {p.project_name}
                    </div>
                    <div style={{ fontSize:10, color:"var(--color-text-tertiary)" }}>
                      {reqs.length} requirements &middot; Req Tracker: {trackers?.reqTrackerId || "?"} &middot; TC Tracker: {trackers?.tcTrackerId || "?"}
                    </div>
                  </div>
                  <div style={{ display:"flex", alignItems:"center", gap:8 }}>
                    <StatusBadge status={reqStatus[idx] || "pending"} />
                    {reqStatus[idx] !== "done" && reqStatus[idx] !== "creating" && (
                      <button style={btnStyle(true)} onClick={() => createTrackerItems(idx)}>
                        Create Items
                      </button>
                    )}
                  </div>
                </div>

                {/* Requirement list (collapsible) */}
                <div style={{ maxHeight:200, overflowY:"auto", fontSize:11 }}>
                  {reqs.map((req, ri) => (
                    <div key={ri} style={{ padding:"4px 8px", marginBottom:2, borderRadius:4,
                      background:"var(--color-background-primary)", border:"0.5px solid var(--color-border-tertiary)" }}>
                      <div style={{ color:"var(--color-text-primary)", fontWeight:500 }}>
                        <span style={{ color:"#854F0B" }}>REQ-{ri+1}</span> {req.title}
                      </div>
                      {(req.test_cases || []).map((tc, ti) => (
                        <div key={ti} style={{ marginLeft:12, color:"var(--color-text-tertiary)", fontSize:10 }}>
                          ↳ TC: {tc.title}
                        </div>
                      ))}
                    </div>
                  ))}
                </div>

                {reqStatus[idx] === "done" && reqCounts[idx] && (
                  <div style={{ fontSize:11, color:"#065F46", background:"#D1FAE5", padding:"6px 10px", borderRadius:6, marginTop:6 }}>
                    Created {reqCounts[idx].reqs} requirements, {reqCounts[idx].tcs} test cases, {reqCounts[idx].verifies} verifies links
                  </div>
                )}
                {reqErrors[idx] && (
                  <div style={{ fontSize:11, color:"#991B1B", background:"#FEE2E2", padding:"6px 10px", borderRadius:6, marginTop:6 }}>
                    {reqErrors[idx]}
                  </div>
                )}
              </div>
            );
          })}

          <div style={{ display:"flex", gap:10, marginTop:16 }}>
            <button style={btnStyle(false)} onClick={() => setStep(1)}>← Back</button>
            <button
              style={allReqsCreated ? btnStyle(true) : btnDisabled}
              disabled={!allReqsCreated}
              onClick={() => setStep(3)}
            >
              Continue to Streams →
            </button>
          </div>
        </div>
      )}

      {/* ══ Step 3: Streams ═══════════════════════════════════════════════ */}
      {step === 3 && struct && (
        <div>
          <div style={{ fontSize:14, fontWeight:500, marginBottom:4, color:"var(--color-text-primary)" }}>
            Stream Hierarchy
          </div>
          <div style={{ fontSize:12, color:"var(--color-text-secondary)", marginBottom:16 }}>
            Create streams in order: Library → Product Line → Transform → Release.
            Projects are added from the appropriate source stream automatically.
            {initialStreamId && <span> Initial Stream ID: <strong>{initialStreamId}</strong></span>}
          </div>

          {TIERS.map(tier => {
            const streams = struct[tier.key] || [];
            if (!streams.length) return null;
            return (
              <div key={tier.key} style={{ marginBottom:16 }}>
                <div style={{
                  padding:"6px 10px", marginBottom:6, borderRadius:"0 6px 6px 0",
                  background:tier.bg, borderLeft:`3px solid ${tier.clr}`,
                }}>
                  <span style={{ fontWeight:500, fontSize:12, color:tier.clr }}>{tier.label}</span>
                  <span style={{ fontSize:10, color:tier.clr, opacity:.7, marginLeft:8 }}>({streams.length} streams)</span>
                </div>

                {streams.map((st, idx) => {
                  const sKey = `${tier.key}_${idx}`;
                  const status = streamStatus[sKey] || "pending";
                  return (
                    <div key={idx} style={{
                      marginLeft:12, marginBottom:6, padding:"10px 12px", borderRadius:8,
                      border:`0.5px solid ${tier.clr}40`, background:"var(--color-background-secondary)",
                    }}>
                      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center" }}>
                        <div>
                          <div style={{ fontSize:12, fontWeight:500, color:"var(--color-text-primary)" }}>
                            {st.stream_name}
                          </div>
                          <div style={{ fontSize:10, color:"var(--color-text-tertiary)" }}>
                            Key: {st.stream_key}
                            {st.parent_stream_key && ` | Parent: ${st.parent_stream_key}`}
                            {` | ${(st.project_keys||[]).length} projects`}
                          </div>
                        </div>
                        <div style={{ display:"flex", alignItems:"center", gap:8 }}>
                          <StatusBadge status={status} />
                          {status !== "done" && status !== "creating" && (
                            <button style={btnStyle(true)} onClick={() => createStream(tier.key, idx)}>
                              Create
                            </button>
                          )}
                        </div>
                      </div>
                      {streamIds[st.stream_key] && (
                        <div style={{ fontSize:10, color:"#065F46", marginTop:4 }}>
                          Stream ID: {streamIds[st.stream_key]}
                        </div>
                      )}
                      {streamErrors[sKey] && (
                        <div style={{ fontSize:10, color:"#991B1B", background:"#FEE2E2", padding:"4px 8px", borderRadius:4, marginTop:4 }}>
                          {streamErrors[sKey]}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            );
          })}

          <div style={{ display:"flex", gap:10, marginTop:16 }}>
            <button style={btnStyle(false)} onClick={() => setStep(2)}>← Back</button>
            <button style={btnStyle(true)} onClick={() => setStep(4)}>
              View Summary →
            </button>
          </div>
        </div>
      )}

      {/* ══ Step 4: Summary ═══════════════════════════════════════════════ */}
      {step === 4 && struct && (
        <div>
          <div style={{ fontSize:14, fontWeight:500, marginBottom:12, color:"var(--color-text-primary)" }}>
            Demo Summary: {struct.domain_name}
          </div>

          {/* Stats */}
          <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:8, marginBottom:20 }}>
            <Stat value={struct.projects?.length || 0} label="Projects" color="#534AB7" />
            <Stat value={Object.values(reqCounts).reduce((a,c) => a + (c?.reqs||0), 0)} label="Requirements" color="#854F0B" />
            <Stat value={Object.values(reqCounts).reduce((a,c) => a + (c?.tcs||0), 0)} label="Test Cases" color="#185FA5" />
            <Stat value={TIERS.reduce((a,t) => a + (struct[t.key]||[]).length, 0)} label="Streams" color="#0F6E56" />
          </div>

          {/* Project List */}
          <div style={{ fontSize:13, fontWeight:500, marginBottom:8, color:"var(--color-text-primary)" }}>Projects</div>
          <div style={{ marginBottom:16 }}>
            {struct.projects.map((p, i) => (
              <div key={i} style={{ display:"flex", justifyContent:"space-between", padding:"6px 10px",
                borderRadius:6, marginBottom:2, background:"var(--color-background-secondary)",
                border:"0.5px solid var(--color-border-tertiary)", fontSize:12 }}>
                <span style={{ color:"var(--color-text-primary)" }}>{p.project_name}</span>
                <span style={{ color:"var(--color-text-tertiary)" }}>
                  ID: {projectIds[i] || "—"}
                  {reqCounts[i] && ` | ${reqCounts[i].reqs} reqs, ${reqCounts[i].tcs} TCs`}
                </span>
              </div>
            ))}
          </div>

          {/* Stream Hierarchy */}
          <div style={{ fontSize:13, fontWeight:500, marginBottom:8, color:"var(--color-text-primary)" }}>Stream Hierarchy</div>
          {TIERS.map(tier => {
            const streams = struct[tier.key] || [];
            if (!streams.length) return null;
            return (
              <div key={tier.key} style={{ marginBottom:10 }}>
                <div style={{ fontSize:11, fontWeight:500, color:tier.clr, marginBottom:4, paddingLeft:4 }}>
                  {tier.label}
                </div>
                {streams.map((st, i) => (
                  <div key={i} style={{ display:"flex", justifyContent:"space-between", padding:"4px 10px",
                    marginLeft:12, marginBottom:2, borderRadius:4, fontSize:11,
                    borderLeft:`2px solid ${tier.clr}`, background:"var(--color-background-secondary)" }}>
                    <span style={{ color:"var(--color-text-primary)" }}>{st.stream_name}</span>
                    <span style={{ color:"var(--color-text-tertiary)" }}>
                      ID: {streamIds[st.stream_key] || "—"}
                      {st.parent_stream_key && ` | Parent: ${st.parent_stream_key}`}
                    </span>
                  </div>
                ))}
              </div>
            );
          })}

          <div style={{ marginTop:20, padding:"12px 14px", background:"var(--color-background-secondary)",
            borderRadius:8, borderLeft:"3px solid #1D9E75", fontSize:12, color:"var(--color-text-secondary)" }}>
            <div style={{ fontWeight:500, color:"#065F46", marginBottom:4 }}>Next steps in Codebeamer</div>
            <div>1. Navigate to ALM &gt; Streams and verify the hierarchy.</div>
            <div>2. Click a Library stream to see its branched projects.</div>
            <div>3. Edit a requirement in one stream — verify it is independent in other streams.</div>
            <div>4. Demo merge workflow: propagate changes between streams.</div>
          </div>

          <button style={{...btnStyle(false), marginTop:16}} onClick={() => { setStep(0); setStruct(null); }}>
            Start New Demo
          </button>
        </div>
      )}
    </div>
  );
}
