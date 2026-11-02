import { useEffect, useMemo, useRef, useState } from "react"
import { api, getAuthToken, getCurrentUser, clearAuth } from "./api"
import { LoginModal } from "./LoginModal"
import { StudentModal, DeactivateModal } from "./StudentModal"

type Page = "overview" | "institutions" | "students" | "intake" | "verification" | "integrity" | "reports"
type Tone = "green" | "blue" | "amber" | "red" | "purple" | "gray"

const nav: { id: Page; code: string; label: string }[] = [
  { id: "overview", code: "OV", label: "Overview" },
  { id: "institutions", code: "IN", label: "Institutions" },
  { id: "students", code: "ST", label: "Student directory" },
  { id: "intake", code: "UP", label: "Data intake" },
  { id: "verification", code: "VQ", label: "Verification queue" },
  { id: "integrity", code: "RI", label: "Record integrity" },
  { id: "reports", code: "RA", label: "Reports & audit" },
]

const pageMeta: Record<Page, {
  title: string
  subtitle: string
  action?: string
}> = {
  overview: {
    title: "Overview",
    subtitle: "A consolidated view of academic identity across reporting institutions.",
    action: "Upload dataset",
  },
  institutions: {
    title: "Institutions",
    subtitle: "Manage reporting institutions, approved intake and student submissions.",
    action: "Refresh directory",
  },
  students: {
    title: "Student directory",
    subtitle: "Search, review and verify APAAR-linked academic records.",
    action: "+ Add Student",
  },
  intake: {
    title: "Data intake",
    subtitle: "Bring institutional student data into ACADIA and validate it before approval.",
    action: "New upload",
  },
  verification: {
    title: "Verification queue",
    subtitle: "Resolve flagged records with transparent evidence and accountable review.",
  },
  integrity: {
    title: "Record integrity",
    subtitle: "Verify approved record versions, cryptographic fingerprints and change history.",
  },
  reports: {
    title: "Reports & audit",
    subtitle: "Generate monitoring summaries and inspect a traceable history of platform activity.",
    action: "Export report",
  },
}

function toneFor(value: string): Tone {
  const norm = value.toLowerCase()
  if (norm.includes("verified") || norm.includes("complete") || norm.includes("pass") || norm.includes("authentic") || norm.includes("active")) return "green"
  if (norm.includes("ready") || norm.includes("approved")) return "blue"
  if (norm.includes("action") || norm.includes("flag") || norm.includes("warn") || norm.includes("duplicate") || norm.includes("review")) return "amber"
  if (norm.includes("critical") || norm.includes("exceed") || norm.includes("fail") || norm.includes("invalid") || norm.includes("tamper") || norm.includes("deactivated")) return "red"
  if (norm.includes("pending")) return "purple"
  return "gray"
}

function Badge({ children, tone }: { children: React.ReactNode; tone?: Tone }) {
  const t = tone ?? toneFor(String(children))
  return <span className={`badge badge-${t}`}>{children}</span>
}

function Button({
  children,
  secondary,
  disabled,
  onClick,
}: {
  children: React.ReactNode
  secondary?: boolean
  disabled?: boolean
  onClick?: () => void
}) {
  return (
    <button
      className={`btn ${secondary ? "btn-secondary" : "btn-primary"}`}
      disabled={disabled}
      onClick={onClick}
    >
      {children}
    </button>
  )
}

function Card({
  className = "",
  children,
}: {
  className?: string
  children: React.ReactNode
}) {
  return <section className={`card ${className}`}>{children}</section>
}

function Metric({
  label,
  value,
  note,
  tone = "blue",
}: {
  label: string
  value: string | number
  note?: string
  tone?: Tone
}) {
  return (
    <Card className={`metric-card tone-${tone}`}>
      <div>
        <span className="metric-label">{label}</span>
        <strong className="metric-value">{value}</strong>
      </div>
      {note && <small className="metric-note">{note}</small>}
    </Card>
  )
}

function SectionTitle({
  title,
  subtitle,
}: {
  title: string
  subtitle?: string
}) {
  return (
    <div className="section-title">
      <h2>{title}</h2>
      {subtitle && <p>{subtitle}</p>}
    </div>
  )
}

function DataTable({
  title,
  subtitle,
  headers,
  rows,
  onRowClick,
  actionRenderer,
}: {
  title: string
  subtitle?: string
  headers: string[]
  rows: (string | number)[][]
  onRowClick?: (rowIndex: number) => void
  actionRenderer?: (rowIndex: number) => React.ReactNode
}) {
  return (
    <Card className="data-table-card">
      <div className="table-header">
        <SectionTitle title={title} subtitle={subtitle} />
        <small className="counter">{rows.length} records</small>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {headers.map((h) => (
                <th key={h}>{h}</th>
              ))}
              {actionRenderer && <th style={{ textAlign: "right" }}>ACTIONS</th>}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={headers.length + (actionRenderer ? 1 : 0)} style={{ textAlign: "center", padding: "2.5rem 1rem", color: "#64748b" }}>
                  No records match current query or filter.
                </td>
              </tr>
            ) : (
              rows.map((row, rowIndex) => (
                <tr
                  key={`${row[0]}-${rowIndex}`}
                  onClick={() => onRowClick?.(rowIndex)}
                  style={{ cursor: onRowClick ? "pointer" : "default" }}
                >
                  {row.map((cell, index) => (
                    <td key={`${cell}-${index}`}>
                      {index === row.length - 1 ? <Badge>{cell}</Badge> : cell}
                    </td>
                  ))}
                  {actionRenderer && (
                    <td style={{ textAlign: "right" }} onClick={(e) => e.stopPropagation()}>
                      {actionRenderer(rowIndex)}
                    </td>
                  )}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

function Sidebar({
  page,
  onChange,
  currentUser,
  onLogout,
}: {
  page: Page
  onChange: (page: Page) => void
  currentUser: any
  onLogout: () => void
}) {
  const roleName = currentUser?.role ? currentUser.role.replace(/_/g, " ") : "Authorized User"
  const initials = currentUser?.name
    ? currentUser.name
        .split(" ")
        .map((p: string) => p[0])
        .slice(0, 2)
        .join("")
        .toUpperCase()
    : "AC"

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">A</div>
        <div>
          <strong>ACADIA</strong>
          <small>ACADEMIC IDENTITY</small>
        </div>
      </div>
      <div className="nav-label">PLATFORM CONSOLE</div>
      <nav>
        {nav.map((item) => (
          <button
            key={item.id}
            className={page === item.id ? "nav-item active" : "nav-item"}
            onClick={() => onChange(item.id)}
          >
            <span>{item.code}</span>
            {item.label}
          </button>
        ))}
      </nav>
      <div className="sidebar-footer">
        <div className="system">
          <small>SYSTEM STATUS</small>
          <p>
            <i />
            AICTE Registry Online
          </p>
        </div>
        <div className="profile" style={{ cursor: "pointer" }} onClick={onLogout} title="Click to Switch Role or Logout">
          <div>{initials}</div>
          <p>
            {currentUser?.name || "Session User"}
            <small>{roleName} · Switch / Logout</small>
          </p>
        </div>
      </div>
    </aside>
  )
}

function Header({
  search,
  setSearch,
  currentUser,
}: {
  search: string
  setSearch: (value: string) => void
  currentUser: any
}) {
  const initials = currentUser?.name
    ? currentUser.name
        .split(" ")
        .map((p: string) => p[0])
        .slice(0, 2)
        .join("")
        .toUpperCase()
    : "AD"

  return (
    <header className="topbar">
      <div className="breadcrumb">
        WORKSPACE&nbsp;&nbsp; / &nbsp;&nbsp;{currentUser?.role ? currentUser.role.replace(/_/g, " ") : "ADMIN CONSOLE"}
      </div>
      <label className="global-search">
        <span>⌕</span>
        <input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search records, institutions, APAAR..."
        />
      </label>
      <div className="top-avatar" title={currentUser?.email}>{initials}</div>
    </header>
  )
}

function PageHeading({ page, onAction }: { page: Page; onAction: () => void }) {
  const meta = pageMeta[page]
  return (
    <div className="page-heading">
      <div>
        <h1>{meta.title}</h1>
        <p>{meta.subtitle}</p>
      </div>
      {meta.action && <Button onClick={onAction}>{meta.action}</Button>}
    </div>
  )
}

function EnrollmentChart({ data }: { data: [string, number, number][] }) {
  const chartData = data.length > 0 ? data : [
    ["DELHI", 60, 65],
    ["PUNE", 60, 60],
    ["BLR", 60, 50],
    ["CHENNAI", 60, 45],
    ["HYD", 60, 45],
  ]

  return (
    <Card className="chart-card">
      <SectionTitle
        title="Enrollment vs. approved intake"
        subtitle="Institution-wise capacity snapshot from active registry"
      />
      <div className="legend">
        <span>
          <i className="approved" />
          Approved intake
        </span>
        <span>
          <i className="enrolled" />
          Enrolled
        </span>
      </div>
      <div className="chart">
        {chartData.map(([label, approved, enrolled]) => (
          <div className="bar-group" key={label}>
            <div className="bars">
              <i style={{ height: `${Math.min(approved, 100)}px` }} />
              <i style={{ height: `${Math.min(enrolled, 100)}px` }} />
            </div>
            <small>{label}</small>
          </div>
        ))}
      </div>
    </Card>
  )
}

// -------------------------------------------------------------
// 1. OVERVIEW DASHBOARD
// -------------------------------------------------------------
function Overview({ goTo }: { goTo: (page: Page) => void }) {
  const [overview, setOverview] = useState<any>(null)
  const [anomalies, setAnomalies] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([api.getOverview(), api.getAnomalies()])
      .then(([ovData, anomData]) => {
        setOverview(ovData)
        setAnomalies(anomData.anomalies || [])
      })
      .catch((err) => console.error("Error loading overview:", err))
      .finally(() => setLoading(false))
  }, [])

  const attentionItems = useMemo(() => {
    const items = []
    if (overview?.duplicate_records > 0) {
      items.push([
        "Cross-institution / duplicate records",
        `${overview.duplicate_records} records flagged with duplicate APAAR IDs`,
        "amber",
      ])
    }
    if (overview?.intake_violations > 0) {
      items.push([
        "Intake threshold exceeded",
        `${overview.intake_violations} programme intakes exceeded approved capacity`,
        "red",
      ])
    }
    if (anomalies.length > 0) {
      items.push([
        "Explainable AI / ML outlier alert",
        `${anomalies[0].institution_name}: ${anomalies[0].reasons?.[0] || 'Unusual pattern'}`,
        "purple",
      ])
    }
    if (items.length === 0) {
      items.push([
        "System Healthy",
        "All verified student records comply with intake caps and APAAR guidelines.",
        "green",
      ])
    }
    return items
  }, [overview, anomalies])

  return (
    <>
      <div className="overview-topline">
        <Badge tone="green">LIVE DATABASE</Badge>
        <span>AICTE Academic Identity Platform SIH 2026</span>
      </div>
      <div className="metrics four">
        <Metric
          label="TOTAL RECORDS"
          value={overview?.total_students ?? (loading ? "..." : 0)}
          note="Active students in system"
          tone="blue"
        />
        <Metric
          label="RECORDS VALIDATED"
          value={overview?.validated_records ?? (loading ? "..." : 0)}
          note="Compliant with APAAR schema"
          tone="green"
        />
        <Metric
          label="DUPLICATE / FLAGGED"
          value={overview?.duplicate_records ?? (loading ? "..." : 0)}
          note="Dual enrollments / exceptions"
          tone="amber"
        />
        <Metric
          label="INTAKE VIOLATIONS"
          value={overview?.intake_violations ?? (loading ? "..." : 0)}
          note="Over-quota capacity alerts"
          tone="red"
        />
      </div>
      <div className="overview-grid">
        <EnrollmentChart
          data={[
            ["DELHI", 60, 65],
            ["PUNE", 60, 60],
            ["BLR", 60, 50],
            ["CHENNAI", 60, 45],
            ["HYD", 60, 45],
          ]}
        />
        <Card className="attention">
          <SectionTitle
            title="Needs attention"
            subtitle="Priority exceptions from live institutional verification"
          />
          {attentionItems.map(([title, desc, color]) => (
            <div className="attention-item" key={title} onClick={() => goTo("verification")}>
              <i className={`bullet bullet-${color}`} />
              <div>
                <strong>{title}</strong>
                <span>{desc}</span>
              </div>
              <Badge tone={color as Tone}>VIEW</Badge>
            </div>
          ))}
          <div style={{ marginTop: "14px" }}>
            <Button secondary onClick={() => goTo("verification")}>
              Open verification queue ({overview?.pending_verification ?? 0})
            </Button>
          </div>
        </Card>
      </div>
    </>
  )
}

// -------------------------------------------------------------
// 2. INSTITUTION DIRECTORY
// -------------------------------------------------------------
function Institutions({
  search,
  download,
}: {
  search: string
  download: (name: string, content: string) => void
}) {
  const [filter, setFilter] = useState("")
  const [items, setItems] = useState<any[]>([])

  const fetchInstitutions = () => {
    api.getInstitutions()
      .then((data) => setItems(data))
      .catch((err) => console.error(err))
  }

  useEffect(() => {
    fetchInstitutions()
  }, [])

  const query = `${search} ${filter}`.trim().toLowerCase()
  const rows = items
    .filter((inst) => !query || inst.name.toLowerCase().includes(query) || inst.aishe_code.toLowerCase().includes(query))
    .map((inst) => [
      inst.name,
      inst.aishe_code,
      inst.approved_programmes ? `${inst.approved_programmes.length} Programmes` : "N/A",
      inst.state || "India",
      inst.status || "ACTIVE",
      new Date(inst.updated_at || inst.created_at).toLocaleDateString(),
    ])

  return (
    <>
      <div className="metrics three">
        <Metric
          label="CONNECTED INSTITUTIONS"
          value={items.length}
          note="AICTE-approved participating bodies"
          tone="blue"
        />
        <Metric
          label="REPORTING ACTIVE"
          value={items.filter((i) => i.status === "ACTIVE").length}
          note="Ingesting student batches"
          tone="green"
        />
        <Metric
          label="STATES COVERED"
          value={new Set(items.map((i) => i.state)).size}
          note="Across India"
          tone="purple"
        />
      </div>
      <div className="filters">
        <label className="local-search">
          <span>⌕</span>
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Search institution or AISHE code…"
          />
        </label>
        <Badge tone="green">ALL INSTITUTIONS</Badge>
        <Badge tone="gray">STATUS: ALL</Badge>
        <Button
          secondary
          onClick={() =>
            download(
              "institutions.csv",
              ["INSTITUTION,AISHE CODE,PROGRAMMES,STATE,STATUS,UPDATED", ...rows.map((r) => r.join(","))].join("\n"),
            )
          }
        >
          Export list
        </Button>
      </div>
      <DataTable
        title="Institution directory"
        subtitle="Institution profile, approved programmes and live verification status"
        headers={[
          "INSTITUTION",
          "AISHE CODE",
          "APPROVED PROGRAMMES",
          "STATE",
          "STATUS",
          "UPDATED",
        ]}
        rows={rows}
      />
    </>
  )
}

// -------------------------------------------------------------
// 3. STUDENT DIRECTORY (With Full Add, Edit, View, Deactivate)
// -------------------------------------------------------------
function Students({
  search,
  download,
  currentUser,
  institutions,
  onOpenAddModal,
}: {
  search: string
  download: (name: string, content: string) => void
  currentUser: any
  institutions: any[]
  onOpenAddModal: () => void
}) {
  const [filter, setFilter] = useState("")
  const [status, setStatus] = useState("ALL RECORDS")
  const [studentsList, setStudentsList] = useState<any[]>([])
  const [modalStudent, setModalStudent] = useState<any | null>(null)
  const [modalMode, setModalMode] = useState<"view" | "edit" | null>(null)
  const [deactivatingStudent, setDeactivatingStudent] = useState<any | null>(null)

  const fetchStudents = () => {
    api.getStudents({ include_inactive: true })
      .then((data) => setStudentsList(data))
      .catch((err) => console.error(err))
  }

  useEffect(() => {
    fetchStudents()
  }, [])

  const query = `${search} ${filter}`.trim().toLowerCase()
  const filteredStudents = studentsList.filter((s) => {
    const matchQuery =
      !query ||
      s.name.toLowerCase().includes(query) ||
      (s.apaar_masked && s.apaar_masked.toLowerCase().includes(query)) ||
      s.programme.toLowerCase().includes(query)
    if (!matchQuery) return false

    if (status === "ALL RECORDS") return true
    if (status === "VERIFIED") return s.record_status === "VALIDATED" || s.record_status === "APPROVED"
    if (status === "NEEDS REVIEW") return s.record_status === "FLAGGED" || s.is_duplicate
    if (status === "INACTIVE") return s.record_status === "DEACTIVATED"
    return true
  })

  const rows = filteredStudents.map((s) => [
    s.name,
    s.apaar_masked || "XXXXXXXX----",
    s.programme,
    s.academic_year,
    s.seat_category || "GENERAL",
    s.record_status,
  ])

  const isExternalVerifier = currentUser?.role === "AUTHORIZED_EXTERNAL_VERIFIER"

  return (
    <>
      {modalMode && (
        <StudentModal
          mode={modalMode}
          student={modalStudent}
          institutions={institutions}
          currentUser={currentUser}
          onClose={() => setModalMode(null)}
          onSuccess={() => {
            setModalMode(null)
            fetchStudents()
          }}
        />
      )}

      {deactivatingStudent && (
        <DeactivateModal
          student={deactivatingStudent}
          onClose={() => setDeactivatingStudent(null)}
          onSuccess={() => {
            setDeactivatingStudent(null)
            fetchStudents()
          }}
        />
      )}

      <div className="filters students-filter">
        <label className="local-search">
          <span>⌕</span>
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Search name, masked APAAR ID, programme..."
          />
        </label>
        {["ALL RECORDS", "VERIFIED", "NEEDS REVIEW", "INACTIVE"].map((item) => (
          <button
            className={`filter-pill ${status === item ? "selected" : ""}`}
            onClick={() => setStatus(item)}
            key={item}
          >
            {item}
          </button>
        ))}
        {!isExternalVerifier && (
          <Button onClick={onOpenAddModal}>
            + Add Student
          </Button>
        )}
        <Button
          secondary
          onClick={() =>
            download(
              "student-records.csv",
              ["STUDENT,MASKED APAAR,PROGRAMME,YEAR,CATEGORY,STATUS", ...rows.map((r) => r.join(","))].join("\n"),
            )
          }
        >
          Export records
        </Button>
      </div>

      <DataTable
        title="Student Registry Management"
        subtitle="Personally identifying 12-digit APAAR numbers are masked with SHA-256 HMAC fingerprints"
        headers={[
          "STUDENT",
          "MASKED APAAR ID",
          "PROGRAMME",
          "YEAR",
          "CATEGORY",
          "RECORD STATUS",
        ]}
        rows={rows}
        actionRenderer={(idx) => {
          const s = filteredStudents[idx]
          if (!s) return null
          return (
            <div style={{ display: "flex", gap: "6px", justifyContent: "flex-end" }}>
              <button
                onClick={() => {
                  setModalStudent(s)
                  setModalMode("view")
                }}
                className="px-2 py-1 bg-gray-100 hover:bg-gray-200 text-gray-700 text-xs font-semibold rounded"
                title="View dossier"
              >
                View
              </button>
              {!isExternalVerifier && s.record_status !== "DEACTIVATED" && (
                <>
                  <button
                    onClick={() => {
                      setModalStudent(s)
                      setModalMode("edit")
                    }}
                    className="px-2 py-1 bg-blue-50 hover:bg-blue-100 text-blue-700 text-xs font-semibold rounded border border-blue-200"
                    title="Edit record & preserve version"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => setDeactivatingStudent(s)}
                    className="px-2 py-1 bg-red-50 hover:bg-red-100 text-red-700 text-xs font-semibold rounded border border-red-200"
                    title="Deactivate student"
                  >
                    Deactivate
                  </button>
                </>
              )}
            </div>
          )
        }}
      />
    </>
  )
}

// -------------------------------------------------------------
// 4. DATA INTAKE (CSV & XLSX Upload)
// -------------------------------------------------------------
function DataIntake({
  fileInput,
  institutions,
}: {
  fileInput: React.RefObject<HTMLInputElement | null>
  institutions: any[]
}) {
  const [selectedInstId, setSelectedInstId] = useState<string>("")
  const [uploading, setUploading] = useState(false)
  const [batchResult, setBatchResult] = useState<any>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [batchReport, setBatchReport] = useState<any>(null)

  useEffect(() => {
    if (institutions.length > 0 && !selectedInstId) {
      setSelectedInstId(institutions[0].id)
    }
  }, [institutions])

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setUploading(true)
    setErrorMessage(null)
    setBatchReport(null)

    try {
      const result = await api.uploadBatch(file, selectedInstId)
      setBatchResult(result)
      if (result.batch_id) {
        const report = await api.getBatchReport(result.batch_id)
        setBatchReport(report)
      }
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to upload batch.")
    } finally {
      setUploading(false)
    }
  }

  return (
    <>
      <div className="intake-grid">
        <Card className="upload-card">
          <SectionTitle
            title="Upload student dataset"
            subtitle="Submit a CSV or Excel XLSX file. Leading zeros in APAAR IDs will be strictly preserved."
          />
          <div style={{ marginBottom: "1.2rem" }}>
            <label style={{ fontSize: "11px", fontWeight: "700", color: "#64748b", display: "block", marginBottom: "6px", textTransform: "uppercase" }}>
              Destination Institution
            </label>
            <select
              value={selectedInstId}
              onChange={(e) => setSelectedInstId(e.target.value)}
              style={{
                width: "100%",
                background: "#f8fafc",
                border: "1px solid #cbd5e1",
                color: "#0f172a",
                padding: "10px 12px",
                borderRadius: "8px",
                fontSize: "13px",
              }}
            >
              {institutions.map((i) => (
                <option key={i.id} value={i.id}>
                  {i.name} ({i.aishe_code})
                </option>
              ))}
            </select>
          </div>

          <div className="drop-zone" onClick={() => fileInput.current?.click()} style={{ opacity: uploading ? 0.6 : 1 }}>
            <strong>↑</strong>
            <p>{uploading ? "Ingesting & validating dataset..." : "Drag and drop your file here"}</p>
            <small>CSV or XLSX · Maximum 25 MB</small>
            <div style={{ marginTop: "8px" }}>
              <Button disabled={uploading}>Choose file</Button>
            </div>
            <input
              ref={fileInput}
              type="file"
              accept=".csv,.xlsx"
              onChange={handleFileUpload}
              hidden
            />
          </div>
          {errorMessage && (
            <div style={{ marginTop: "1rem", color: "#b91c1c", fontSize: "13px", background: "#fef2f2", padding: "10px 14px", borderRadius: "8px", border: "1px solid #fecaca" }}>
              {errorMessage}
            </div>
          )}
        </Card>
        <Card className="preflight">
          <SectionTitle
            title="Pre-flight verification rules"
            subtitle="Validated dynamically on ingestion via Python engine."
          />
          {[
            ["APAAR structure", "Strict 12-digit format & non-empty identifier check"],
            ["Required fields", "Student name, programme, academic year, seat category"],
            ["Duplicate detection", "In-batch matches & cross-institution HMAC-SHA256 flags"],
            ["Intake compliance", "Approved intake limits & supernumerary seat quota validation"],
          ].map(([title, sub]) => (
            <div className="check" key={title}>
              <span>✓</span>
              <div>
                <strong>{title}</strong>
                <small>{sub}</small>
              </div>
            </div>
          ))}
        </Card>
      </div>

      {batchResult && (
        <Card className="validation">
          <div className="validation-head">
            <SectionTitle title="Batch Validation Summary" subtitle={batchResult.original_filename} />
            <Badge tone="green">{batchResult.status}</Badge>
          </div>
          <strong style={{ fontSize: "14px", color: "#0f172a" }}>{batchResult.total_records} rows processed</strong>
          <p style={{ color: "#64748b", fontSize: "13px", margin: "4px 0 16px" }}>
            Every row is evaluated against regulatory standards. Issues are flagged with row number and remediation guidance.
          </p>
          <div className="validation-stats">
            <div className="stat green">
              <b>{batchResult.valid_records}</b>
              <span>Ready to approve</span>
            </div>
            <div className="stat amber">
              <b>{batchResult.duplicate_records}</b>
              <span>Duplicate IDs</span>
            </div>
            <div className="stat red">
              <b>{batchResult.invalid_records}</b>
              <span>Validation flags</span>
            </div>
          </div>

          {batchReport?.issues_summary?.length > 0 && (
            <div style={{ marginTop: "1.5rem" }}>
              <SectionTitle title="Flagged Issues Breakdown" subtitle="Transparent explainability for verifiers" />
              <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginTop: "12px" }}>
                {batchReport.issues_summary.map((iss: any) => (
                  <div
                    key={iss.issue_id}
                    style={{
                      background: "#f8fafc",
                      border: "1px solid #e2e8f0",
                      borderLeft: `4px solid ${iss.severity === "CRITICAL" ? "#ef4444" : "#f59e0b"}`,
                      padding: "12px 16px",
                      borderRadius: "6px",
                      fontSize: "13px",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                      <strong>Row {iss.source_row}: {iss.rule_id}</strong>
                      <Badge tone={iss.severity === "CRITICAL" ? "red" : "amber"}>{iss.severity}</Badge>
                    </div>
                    <div style={{ color: "#334155" }}>{iss.explanation}</div>
                    {iss.recommended_correction && (
                      <div style={{ color: "#047857", fontSize: "12px", marginTop: "6px", fontWeight: "600" }}>
                        Correction: {iss.recommended_correction}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </Card>
      )}
    </>
  )
}

// -------------------------------------------------------------
// 5. VERIFICATION QUEUE
// -------------------------------------------------------------
function Verification() {
  const [selected, setSelected] = useState(0)
  const [duplicates, setDuplicates] = useState<any[]>([])
  const [intakeAlerts, setIntakeAlerts] = useState<any[]>([])
  const [issues, setIssues] = useState<any[]>([])
  const [actionNotes, setActionNotes] = useState("")
  const [resolving, setResolving] = useState(false)

  const loadVerificationData = () => {
    Promise.all([
      api.getDuplicates(),
      api.getIntakeAlerts(),
      api.getValidationIssues({ resolution_status: "OPEN" }),
    ]).then(([dupData, intData, issData]) => {
      setDuplicates(dupData.records || [])
      setIntakeAlerts(intData.details || [])
      setIssues(issData || [])
    }).catch(console.error)
  }

  useEffect(() => {
    loadVerificationData()
  }, [])

  const reviewItems = useMemo(() => {
    const list: any[] = []
    duplicates.forEach((d) => {
      list.push({
        type: "DUPLICATE",
        title: `Duplicate APAAR (${d.duplicate_type})`,
        subtitle: `${d.student_name} (${d.apaar_masked})`,
        priority: "HIGH",
        raw: d,
      })
    })
    intakeAlerts.forEach((a) => {
      list.push({
        type: "INTAKE",
        title: `Intake Exceeded: ${a.programme}`,
        subtitle: `${a.institution_name} · Enrolled: ${a.total_enrolled} / Approved: ${a.approved_intake}`,
        priority: "HIGH",
        raw: a,
      })
    })
    issues.forEach((iss) => {
      list.push({
        type: "ISSUE",
        title: `Validation Flag: ${iss.rule_id}`,
        subtitle: `Row ${iss.source_row} · ${iss.explanation}`,
        priority: iss.severity === "CRITICAL" ? "HIGH" : "MEDIUM",
        raw: iss,
      })
    })
    return list
  }, [duplicates, intakeAlerts, issues])

  const currentItem = reviewItems[selected]

  const handleResolveIssue = async (action: "RESOLVED" | "WAIVED") => {
    if (!currentItem || currentItem.type !== "ISSUE") return
    setResolving(true)
    try {
      await api.resolveIssue(currentItem.raw.id, {
        resolution_notes: actionNotes || `Marked as ${action} by verifier.`,
        action,
      })
      alert(`Issue ${currentItem.raw.id} successfully marked as ${action}.`)
      setActionNotes("")
      loadVerificationData()
    } catch (err: any) {
      alert(`Error: ${err.message}`)
    } finally {
      setResolving(false)
    }
  }

  return (
    <>
      <div className="metrics three">
        <Metric
          label="OPEN REVIEW ITEMS"
          value={reviewItems.length}
          note="Across live institutions"
          tone="amber"
        />
        <Metric
          label="DUPLICATE IDENTIFIERS"
          value={duplicates.length}
          note="Flagged by HMAC fingerprint"
          tone="red"
        />
        <Metric
          label="INTAKE EXCEPTIONS"
          value={intakeAlerts.length}
          note="Capacity violations"
          tone="purple"
        />
      </div>
      <div className="review-grid">
        <Card className="review-list">
          <SectionTitle
            title="Open review items"
            subtitle="Priority triage of regulatory exceptions"
          />
          {reviewItems.length === 0 ? (
            <div style={{ padding: "2.5rem 1rem", textAlign: "center", color: "#64748b" }}>
              All verification cases are currently resolved.
            </div>
          ) : (
            reviewItems.map((item, index) => (
              <button
                key={`${item.title}-${index}`}
                className={selected === index ? "review-item selected" : "review-item"}
                onClick={() => setSelected(index)}
              >
                <div>
                  <strong>{item.title}</strong>
                  <small>{item.subtitle}</small>
                </div>
                <Badge tone={item.priority === "HIGH" ? "red" : "amber"}>{item.priority}</Badge>
              </button>
            ))
          )}
        </Card>

        {currentItem && (
          <Card className="review-detail">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "16px" }}>
              <div>
                <h2 style={{ fontSize: "18px", fontWeight: "700", color: "#0f172a", margin: "0 0 4px" }}>
                  {currentItem.title}
                </h2>
                <span style={{ fontSize: "12px", color: "#64748b", fontFamily: "monospace" }}>
                  CATEGORY: {currentItem.type}
                </span>
              </div>
              <Badge tone={currentItem.priority === "HIGH" ? "red" : "amber"}>{currentItem.priority} PRIORITY</Badge>
            </div>

            {currentItem.type === "DUPLICATE" && (
              <div style={{ fontSize: "14px", lineHeight: "1.7", color: "#334155" }}>
                <p><strong>Student Name:</strong> {currentItem.raw.student_name}</p>
                <p><strong>Masked APAAR:</strong> <span style={{ fontFamily: "monospace" }}>{currentItem.raw.apaar_masked}</span></p>
                <p><strong>Programme:</strong> {currentItem.raw.programme} ({currentItem.raw.academic_year})</p>
                <p><strong>Duplicate Scope:</strong> <Badge tone="amber">{currentItem.raw.duplicate_type}</Badge></p>
                {currentItem.raw.matched_records?.length > 0 && (
                  <div style={{ marginTop: "1rem", background: "#fef2f2", border: "1px solid #fecaca", padding: "14px", borderRadius: "8px" }}>
                    <strong style={{ color: "#b91c1c" }}>Conflicting Registrations Detected:</strong>
                    {currentItem.raw.matched_records.map((m: any, idx: number) => (
                      <div key={idx} style={{ marginTop: "6px", fontSize: "13px" }}>
                        • {m.student_name} enrolled at <strong>{m.institution_name}</strong> ({m.programme})
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {currentItem.type === "INTAKE" && (
              <div style={{ fontSize: "14px", lineHeight: "1.7", color: "#334155" }}>
                <p><strong>Institution:</strong> {currentItem.raw.institution_name}</p>
                <p><strong>Programme:</strong> {currentItem.raw.programme}</p>
                <p><strong>Approved Intake:</strong> {currentItem.raw.approved_intake} seats</p>
                <p><strong>Actual Enrolled:</strong> <span style={{ color: "#b91c1c", fontWeight: "bold" }}>{currentItem.raw.total_enrolled} students</span></p>
                <div style={{ marginTop: "1rem", background: "#fef2f2", border: "1px solid #fecaca", padding: "14px", borderRadius: "8px" }}>
                  <strong style={{ color: "#b91c1c" }}>Violation Explanation:</strong>
                  {currentItem.raw.alerts?.map((al: any, idx: number) => (
                    <div key={idx} style={{ marginTop: "6px", fontSize: "13px" }}>
                      • {al.explanation}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {currentItem.type === "ISSUE" && (
              <div style={{ fontSize: "14px", lineHeight: "1.7", color: "#334155" }}>
                <p><strong>Rule Code:</strong> <span style={{ fontFamily: "monospace", fontWeight: "700" }}>{currentItem.raw.rule_id}</span></p>
                <p><strong>Explanation:</strong> {currentItem.raw.explanation}</p>
                <p><strong>Recommended Fix:</strong> <span style={{ color: "#047857", fontWeight: "600" }}>{currentItem.raw.recommended_correction}</span></p>
                <div style={{ marginTop: "1.2rem" }}>
                  <label style={{ fontSize: "11px", fontWeight: "700", color: "#64748b", display: "block", marginBottom: "6px", textTransform: "uppercase" }}>
                    Resolution Notes / Justification
                  </label>
                  <textarea
                    value={actionNotes}
                    onChange={(e) => setActionNotes(e.target.value)}
                    placeholder="Enter audit remarks for resolving or waiving this issue..."
                    style={{
                      width: "100%",
                      background: "#f8fafc",
                      border: "1px solid #cbd5e1",
                      color: "#0f172a",
                      padding: "10px",
                      borderRadius: "8px",
                      fontSize: "13px",
                      minHeight: "75px",
                    }}
                  />
                  <div style={{ display: "flex", gap: "10px", marginTop: "12px" }}>
                    <Button onClick={() => handleResolveIssue("RESOLVED")} disabled={resolving}>
                      Approve & Resolve
                    </Button>
                    <Button secondary onClick={() => handleResolveIssue("WAIVED")} disabled={resolving}>
                      Waive Issue
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </Card>
        )}
      </div>
    </>
  )
}

// -------------------------------------------------------------
// 6. RECORD INTEGRITY & QR VERIFICATION
// -------------------------------------------------------------
function Integrity({
  students,
}: {
  students: any[]
}) {
  const [selectedStudentId, setSelectedStudentId] = useState<string>("")
  const [sealing, setSealing] = useState(false)
  const [sealResult, setSealResult] = useState<any>(null)
  const [verifyResult, setVerifyResult] = useState<any>(null)
  const [qrResult, setQrResult] = useState<any>(null)
  const [qrVerificationResult, setQrVerificationResult] = useState<any>(null)
  const [versionHistory, setVersionHistory] = useState<any[]>([])

  useEffect(() => {
    if (students.length > 0 && !selectedStudentId) {
      setSelectedStudentId(students[0].id)
    }
  }, [students])

  useEffect(() => {
    if (!selectedStudentId) return
    api.getRecordVersions(selectedStudentId)
      .then((res) => {
        setVersionHistory(res.versions || [])
        if (res.versions && res.versions.length > 0) {
          setSealResult(res.versions[0])
        } else {
          setSealResult(null)
        }
      })
      .catch(console.error)
  }, [selectedStudentId])

  const handleSealRecord = async () => {
    if (!selectedStudentId) return
    setSealing(true)
    try {
      const res = await api.sealRecord(selectedStudentId)
      setSealResult(res)
      const vRes = await api.getRecordVersions(selectedStudentId)
      setVersionHistory(vRes.versions || [])
      alert("Record cryptographically sealed with Ed25519 digital signature and SHA-256 fingerprint!")
    } catch (err: any) {
      alert(`Seal error: ${err.message}`)
    } finally {
      setSealing(false)
    }
  }

  const handleVerifyIntegrity = async () => {
    if (!selectedStudentId) return
    try {
      const res = await api.verifyRecordIntegrity(selectedStudentId)
      setVerifyResult(res)
    } catch (err: any) {
      alert(`Verification error: ${err.message}`)
    }
  }

  const handleGenerateQR = async () => {
    if (!selectedStudentId) return
    try {
      const res = await api.generateQR(selectedStudentId)
      setQrResult(res)
    } catch (err: any) {
      alert(`QR Error: ${err.message}`)
    }
  }

  const handlePublicQRScan = async () => {
    if (!qrResult?.qr_verification_token) return
    try {
      const res = await api.verifyQRToken(qrResult.qr_verification_token)
      setQrVerificationResult(res)
    } catch (err: any) {
      alert(`Public verify error: ${err.message}`)
    }
  }

  const activeStudent = students.find((s) => s.id === selectedStudentId)

  return (
    <>
      <div className="metrics three">
        <Metric
          label="SEALED RECORDS"
          value={versionHistory.length > 0 ? "AUTHENTIC" : "PENDING"}
          note="Deterministic SHA-256 state"
          tone="green"
        />
        <Metric
          label="SIGNATURE ALGORITHM"
          value="Ed25519"
          note="Asymmetric cryptographic seal"
          tone="blue"
        />
        <Metric
          label="VERSION HISTORY"
          value={versionHistory.length}
          note="Traceable immutable revisions"
          tone="purple"
        />
      </div>

      <div style={{ marginBottom: "1.5rem" }}>
        <label style={{ fontSize: "11px", fontWeight: "700", color: "#64748b", display: "block", marginBottom: "6px", textTransform: "uppercase" }}>
          Select Student Record for Cryptographic Audit
        </label>
        <select
          value={selectedStudentId}
          onChange={(e) => {
            setSelectedStudentId(e.target.value)
            setVerifyResult(null)
            setQrResult(null)
            setQrVerificationResult(null)
          }}
          style={{
            width: "100%",
            background: "#f8fafc",
            border: "1px solid #cbd5e1",
            color: "#0f172a",
            padding: "10px 12px",
            borderRadius: "8px",
            fontSize: "13px",
          }}
        >
          {students.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name} · {s.apaar_masked} · {s.programme} ({s.record_status})
            </option>
          ))}
        </select>
      </div>

      <div className="integrity-grid">
        <Card className="record">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "12px" }}>
            <h2 style={{ fontSize: "18px", fontWeight: "700", color: "#0f172a", margin: 0 }}>Cryptographic Identity Seal</h2>
            <Badge tone={sealResult ? "green" : "gray"}>
              {sealResult ? "RECORD SEALED" : "UNSEALED DRAFT"}
            </Badge>
          </div>
          <div className="eyebrow">Record Reference</div>
          <h3>{activeStudent ? `${activeStudent.name} (${activeStudent.apaar_masked})` : "N/A"}</h3>
          
          <div className="eyebrow">Canonical SHA-256 Fingerprint</div>
          <strong style={{ wordBreak: "break-all", fontSize: "13px", fontFamily: "monospace", color: "#047857", background: "#f0fdf4", padding: "8px 12px", borderRadius: "6px", display: "block" }}>
            {sealResult?.fingerprint || "No cryptographic fingerprint generated yet."}
          </strong>
          <p style={{ marginTop: "6px", fontSize: "12px", color: "#64748b", lineHeight: "1.4" }}>
            Deterministic canonical JSON representation ensures zero variance in field order or whitespace.
          </p>

          <div style={{ display: "flex", gap: "10px", marginTop: "1.2rem" }}>
            <Button onClick={handleSealRecord} disabled={sealing}>
              {sealing ? "Signing with Ed25519..." : "Seal Record Version"}
            </Button>
            {sealResult && (
              <Button secondary onClick={handleVerifyIntegrity}>
                Verify Tamper Status
              </Button>
            )}
          </div>

          {verifyResult && (
            <div style={{ marginTop: "1.2rem", background: verifyResult.is_valid ? "#ecfdf5" : "#fef2f2", border: `1px solid ${verifyResult.is_valid ? "#a7f3d0" : "#fecaca"}`, padding: "12px 14px", borderRadius: "8px" }}>
              <strong style={{ color: verifyResult.is_valid ? "#047857" : "#b91c1c", fontSize: "14px" }}>
                Status: {verifyResult.status}
              </strong>
              <div style={{ fontSize: "13px", color: "#334155", marginTop: "4px" }}>
                {verifyResult.message}
              </div>
            </div>
          )}

          <hr style={{ margin: "1.5rem 0", borderColor: "#e2e8f0" }} />

          <div className="qr-row">
            {qrResult ? (
              <img
                src={`data:image/png;base64,${qrResult.qr_code_base64}`}
                alt="Verification QR"
                style={{ width: "128px", height: "128px", borderRadius: "8px", border: "1px solid #cbd5e1", padding: "4px" }}
              />
            ) : (
              <div style={{ width: "128px", height: "128px", background: "#f1f5f9", borderRadius: "8px", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "11px", color: "#64748b", border: "1px dashed #cbd5e1" }}>
                QR Inactive
              </div>
            )}
            <div>
              <strong style={{ fontSize: "14px", color: "#0f172a" }}>Secure QR Credential</strong>
              <p style={{ fontSize: "12px", color: "#64748b", margin: "4px 0 10px" }}>
                Contains signed one-time verification reference. Protects student privacy on public scanning.
              </p>
              <div style={{ display: "flex", gap: "8px" }}>
                <Button secondary onClick={handleGenerateQR} disabled={!sealResult}>
                  Generate QR
                </Button>
                {qrResult && (
                  <Button onClick={handlePublicQRScan}>
                    Simulate Public Scan
                  </Button>
                )}
              </div>
            </div>
          </div>

          {qrVerificationResult && (
            <div style={{ marginTop: "1.2rem", background: "#f8fafc", border: "1px solid #e2e8f0", padding: "14px", borderRadius: "8px", fontSize: "13px" }}>
              <strong style={{ color: "#047857", fontSize: "14px" }}>Public QR Inspection Result:</strong>
              <div style={{ marginTop: "6px", color: "#0f172a" }}>
                Student: <b>{qrVerificationResult.student_preview?.student_name}</b> ({qrVerificationResult.student_preview?.apaar_masked})
              </div>
              <div style={{ color: "#475569" }}>
                Institution: {qrVerificationResult.student_preview?.institution_name}
              </div>
              <div style={{ color: "#475569" }}>
                Programme: {qrVerificationResult.student_preview?.programme}
              </div>
              <div style={{ marginTop: "8px" }}>
                <Badge tone="green">{qrVerificationResult.status}</Badge>
              </div>
            </div>
          )}
        </Card>

        <Card className="history">
          <SectionTitle
            title="Record version history"
            subtitle="Traceable immutable sequence of approvals and Ed25519 signatures"
          />
          {versionHistory.length === 0 ? (
            <div style={{ padding: "2.5rem 1rem", textAlign: "center", color: "#64748b" }}>
              No previous versions sealed for this record yet.
            </div>
          ) : (
            versionHistory.map((v) => (
              <div className="timeline" key={v.version_id}>
                <div>
                  <strong>Version 0{v.version_number} · Approved</strong>
                  <span style={{ fontFamily: "monospace", fontSize: "11px", color: "#475569" }}>
                    SHA-256: {v.fingerprint.slice(0, 24)}...
                  </span>
                  <small>{new Date(v.approval_timestamp).toLocaleString()}</small>
                </div>
              </div>
            ))
          )}
          <hr style={{ margin: "1.5rem 0", borderColor: "#e2e8f0" }} />
          <div className="eyebrow">Audit Security Guarantee</div>
          <p style={{ fontSize: "12px", color: "#64748b", lineHeight: "1.5", margin: "4px 0 0" }}>
            Every version links to the previous SHA-256 fingerprint, forming an internal tamper-evident hash chain.
          </p>
        </Card>
      </div>
    </>
  )
}

// -------------------------------------------------------------
// 7. REPORTS & AUDIT LOGS
// -------------------------------------------------------------
function Reports({
  download,
}: {
  download: (name: string, content: string) => void
}) {
  const [overview, setOverview] = useState<any>(null)
  const [auditLogs, setAuditLogs] = useState<any[]>([])

  useEffect(() => {
    Promise.all([api.getOverview(), api.getAuditLogs()])
      .then(([ov, logs]) => {
        setOverview(ov)
        setAuditLogs(logs)
      })
      .catch(console.error)
  }, [])

  const auditRows = auditLogs.map((log) => [
    new Date(log.timestamp).toLocaleString(),
    log.actor_email || "System",
    log.action,
    log.target_type,
    "SUCCESS",
  ])

  return (
    <>
      <div className="reports-grid">
        <Card className="report-builder">
          <SectionTitle
            title="Export Monitoring Summary"
            subtitle="Generate regulatory audit reports with compliance certifications."
          />
          <div style={{ marginTop: "1.5rem" }}>
            <Button
              onClick={() =>
                download(
                  "acadia-audit-report.txt",
                  `ACADIA OFFICIAL REGULATORY REPORT\nGenerated: ${new Date().toISOString()}\nTotal Students: ${overview?.total_students}\nValidated: ${overview?.validated_records}\nDuplicates Flagged: ${overview?.duplicate_records}\nIntake Violations: ${overview?.intake_violations}`,
                )
              }
            >
              Export System Audit (TXT)
            </Button>
          </div>
        </Card>
        <Card className="report-preview">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <SectionTitle
              title="Live platform snapshot"
              subtitle="Data synchronized directly from PostgreSQL backend."
            />
            <Badge tone="green">LIVE STATUS</Badge>
          </div>
          <div className="report-stats">
            {[
              [overview?.total_students ?? 0, "Total students"],
              [overview?.validated_records ?? 0, "Validated records"],
              [overview?.duplicate_records ?? 0, "Duplicate flags"],
            ].map(([value, label]) => (
              <div key={label}>
                <strong>{value}</strong>
                <span>{label}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>
      <DataTable
        title="Immutable Platform Audit Trail"
        subtitle="All administrative actions, batch uploads, edits, and cryptographic signings captured for accountability"
        headers={["TIMESTAMP", "ACTOR", "ACTION", "TARGET", "STATUS"]}
        rows={auditRows}
      />
    </>
  )
}

// -------------------------------------------------------------
// MAIN APP ROOT
// -------------------------------------------------------------
export default function App() {
  const [page, setPage] = useState<Page>("overview")
  const [search, setSearch] = useState("")
  const [currentUser, setCurrentUser] = useState<any>(getCurrentUser())
  const [showLoginModal, setShowLoginModal] = useState<boolean>(!getAuthToken())
  const [showAddStudentModal, setShowAddStudentModal] = useState(false)
  const [institutions, setInstitutions] = useState<any[]>([])
  const [allStudents, setAllStudents] = useState<any[]>([])
  const fileInput = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const handleAuthChange = () => {
      const user = getCurrentUser()
      setCurrentUser(user)
      if (!user) setShowLoginModal(true)
    }
    window.addEventListener("acadia_auth_changed", handleAuthChange)
    return () => window.removeEventListener("acadia_auth_changed", handleAuthChange)
  }, [])

  useEffect(() => {
    if (getAuthToken()) {
      api.getInstitutions().then(setInstitutions).catch(console.error)
      api.getStudents({ include_inactive: true }).then(setAllStudents).catch(console.error)
    }
  }, [currentUser])

  const refreshStudents = () => {
    api.getStudents({ include_inactive: true }).then(setAllStudents).catch(console.error)
  }

  function download(name: string, content: string) {
    const url = URL.createObjectURL(new Blob([content], { type: "text/plain" }))
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = name
    anchor.click()
    URL.revokeObjectURL(url)
  }

  function handleAction() {
    if (page === "overview") setPage("intake")
    else if (page === "intake") fileInput.current?.click()
    else if (page === "students") setShowAddStudentModal(true)
    else if (page === "institutions") setPage("institutions")
    else if (page === "reports") {
      download(
        "acadia-overview.txt",
        `ACADIA Platform Report - ${new Date().toLocaleDateString()}\nRole: ${currentUser?.role || 'Admin'}`,
      )
    }
  }

  const handleLogout = () => {
    clearAuth()
    setCurrentUser(null)
    setShowLoginModal(true)
  }

  return (
    <div className="app-shell">
      {showLoginModal && (
        <LoginModal
          onSuccess={(userData) => {
            setCurrentUser(userData)
            setShowLoginModal(false)
          }}
        />
      )}

      {showAddStudentModal && (
        <StudentModal
          mode="add"
          institutions={institutions}
          currentUser={currentUser}
          onClose={() => setShowAddStudentModal(false)}
          onSuccess={() => {
            setShowAddStudentModal(false)
            refreshStudents()
          }}
        />
      )}

      <Sidebar
        page={page}
        onChange={(next) => {
          setPage(next)
          setSearch("")
        }}
        currentUser={currentUser}
        onLogout={handleLogout}
      />
      <div className="app-main">
        <Header search={search} setSearch={setSearch} currentUser={currentUser} />
        <main>
          <PageHeading page={page} onAction={handleAction} />
          {page === "overview" && <Overview goTo={setPage} />}
          {page === "institutions" && (
            <Institutions search={search} download={download} />
          )}
          {page === "students" && (
            <Students
              search={search}
              download={download}
              currentUser={currentUser}
              institutions={institutions}
              onOpenAddModal={() => setShowAddStudentModal(true)}
            />
          )}
          {page === "intake" && (
            <DataIntake fileInput={fileInput} institutions={institutions} />
          )}
          {page === "verification" && <Verification />}
          {page === "integrity" && <Integrity students={allStudents} />}
          {page === "reports" && <Reports download={download} />}
        </main>
      </div>
    </div>
  )
}
