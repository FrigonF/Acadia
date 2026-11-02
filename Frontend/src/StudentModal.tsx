import React, { useState } from "react";
import { api } from "./api";

interface StudentModalProps {
  mode: "view" | "edit" | "add";
  student?: any;
  institutions: any[];
  currentUser: any;
  onClose: () => void;
  onSuccess: () => void;
}

export function StudentModal({
  mode,
  student,
  institutions,
  currentUser,
  onClose,
  onSuccess,
}: StudentModalProps) {
  const [name, setName] = useState(student?.name || "");
  const [apaarId, setApaarId] = useState(student?.apaar_id || "");
  const [institutionId, setInstitutionId] = useState(
    student?.institution_id || (currentUser?.institution_id || (institutions[0]?.id || ""))
  );
  const [programme, setProgramme] = useState(student?.programme || "");
  const [academicYear, setAcademicYear] = useState(student?.academic_year || "2025-2026");
  const [seatCategory, setSeatCategory] = useState(student?.seat_category || "GENERAL");
  const [enrollmentNumber, setEnrollmentNumber] = useState(student?.enrollment_number || "");
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Institution's approved programmes
  const currentInst = institutions.find((i) => i.id === institutionId);
  const approvedProgrammes: string[] = currentInst?.approved_programmes || [
    "B.Tech Computer Science and Engineering",
    "B.Tech Electronics and Communication Engineering",
    "B.Tech Mechanical Engineering",
  ];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (mode === "add") {
        if (!apaarId || apaarId.length !== 12 || !apaarId.match(/^\d{12}$/)) {
          throw new Error("APAAR ID must be exactly 12 numeric digits.");
        }
        await api.createStudent({
          name,
          apaar_id: apaarId,
          institution_id: institutionId,
          programme: programme || approvedProgrammes[0],
          academic_year: academicYear,
          seat_category: seatCategory,
          enrollment_number: enrollmentNumber,
        });
      } else if (mode === "edit") {
        if (!reason.trim()) {
          throw new Error("You must provide an audit reason for modifying this record.");
        }
        await api.updateStudent(student.id, {
          name,
          apaar_id: apaarId.length === 12 ? apaarId : undefined,
          programme,
          academic_year: academicYear,
          seat_category: seatCategory,
          enrollment_number: enrollmentNumber,
          reason,
        });
      }
      onSuccess();
    } catch (err: any) {
      setError(err.message || "Failed to process student record.");
    } finally {
      setLoading(false);
    }
  };

  const isView = mode === "view";

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-[#12161f] border border-gray-800 rounded-xl max-w-2xl w-full p-6 text-gray-200 shadow-2xl overflow-y-auto max-h-[90vh]">
        <div className="flex justify-between items-center mb-5 pb-3 border-b border-gray-800">
          <div>
            <h2 className="text-lg font-bold text-white">
              {mode === "add" && "Add New Student Record"}
              {mode === "edit" && "Edit Student Academic Record"}
              {mode === "view" && "Student Record Dossier"}
            </h2>
            <p className="text-xs text-gray-400">
              {mode === "add" && "Register student into the AICTE verification registry."}
              {mode === "edit" && "Preserves previous version and updates SHA-256 fingerprint."}
              {mode === "view" && "Cryptographic audit and demographic breakdown."}
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white text-lg font-bold p-1 rounded hover:bg-gray-800"
          >
            ✕
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-950/40 border border-red-800/50 rounded-lg text-xs text-red-300">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs uppercase font-mono tracking-wider text-gray-400 mb-1">
                Student Full Name *
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                disabled={isView}
                placeholder="e.g. Aarav Sharma"
                className="w-full bg-[#1a2130] border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500 disabled:opacity-60"
              />
            </div>

            <div>
              <label className="block text-xs uppercase font-mono tracking-wider text-gray-400 mb-1">
                {mode === "edit" ? "Update APAAR ID (Optional, 12 Digits)" : "APAAR ID (12 Digits) *"}
              </label>
              <input
                type="text"
                value={apaarId}
                onChange={(e) => setApaarId(e.target.value)}
                maxLength={12}
                required={mode === "add"}
                disabled={isView}
                placeholder={mode === "edit" ? `Current: ${student?.apaar_masked || "Masked"} (leave blank to keep)` : isView ? student?.apaar_masked : "e.g. 112233445566"}
                className="w-full bg-[#1a2130] border border-gray-700 rounded-lg px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-emerald-500 disabled:opacity-60"
              />
            </div>

            <div>
              <label className="block text-xs uppercase font-mono tracking-wider text-gray-400 mb-1">
                Reporting Institution *
              </label>
              <select
                value={institutionId}
                onChange={(e) => setInstitutionId(e.target.value)}
                disabled={isView || (currentUser?.role === "INSTITUTION_ADMIN" && mode === "add")}
                className="w-full bg-[#1a2130] border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500 disabled:opacity-60"
              >
                {institutions.map((i) => (
                  <option key={i.id} value={i.id}>
                    {i.name} ({i.aishe_code})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs uppercase font-mono tracking-wider text-gray-400 mb-1">
                Academic Programme *
              </label>
              <select
                value={programme || approvedProgrammes[0]}
                onChange={(e) => setProgramme(e.target.value)}
                disabled={isView}
                className="w-full bg-[#1a2130] border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500 disabled:opacity-60"
              >
                {approvedProgrammes.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs uppercase font-mono tracking-wider text-gray-400 mb-1">
                Academic Year *
              </label>
              <input
                type="text"
                value={academicYear}
                onChange={(e) => setAcademicYear(e.target.value)}
                required
                disabled={isView}
                placeholder="e.g. 2025-2026"
                className="w-full bg-[#1a2130] border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500 disabled:opacity-60"
              />
            </div>

            <div>
              <label className="block text-xs uppercase font-mono tracking-wider text-gray-400 mb-1">
                Seat / Quota Category *
              </label>
              <select
                value={seatCategory}
                onChange={(e) => setSeatCategory(e.target.value)}
                disabled={isView}
                className="w-full bg-[#1a2130] border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500 disabled:opacity-60"
              >
                {["GENERAL", "OBC", "SC", "ST", "EWS", "TFWS", "NRI", "OCI", "FN"].map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>

            <div className="md:col-span-2">
              <label className="block text-xs uppercase font-mono tracking-wider text-gray-400 mb-1">
                Institutional Roll / Enrollment Number
              </label>
              <input
                type="text"
                value={enrollmentNumber}
                onChange={(e) => setEnrollmentNumber(e.target.value)}
                disabled={isView}
                placeholder="e.g. ENR/2025/CS/042"
                className="w-full bg-[#1a2130] border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500 disabled:opacity-60"
              />
            </div>
          </div>

          {mode === "edit" && (
            <div className="pt-2 border-t border-gray-800">
              <label className="block text-xs uppercase font-mono tracking-wider text-amber-400 mb-1 font-bold">
                Mandatory Audit Reason for Edit *
              </label>
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                required
                placeholder="Specify regulatory or institutional justification (e.g. Corrected typo in official surname; Updated seat category per allotment certificate)."
                className="w-full bg-[#1a2130] border border-amber-600/50 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-amber-400 min-h-[65px]"
              />
            </div>
          )}

          {isView && (
            <div className="pt-2 border-t border-gray-800 text-xs text-gray-400 space-y-1">
              <div>Record Status: <span className="text-emerald-400 font-bold">{student?.record_status}</span></div>
              <div>Duplicate Flag: {student?.is_duplicate ? <span className="text-red-400 font-bold">YES ({student.duplicate_type})</span> : "NO"}</div>
              <div>Created: {new Date(student?.created_at).toLocaleString()}</div>
            </div>
          )}

          <div className="flex justify-end gap-3 pt-3 border-t border-gray-800">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-200 rounded-lg text-sm transition-colors"
            >
              {isView ? "Close" : "Cancel"}
            </button>
            {!isView && (
              <button
                type="submit"
                disabled={loading}
                className="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-medium rounded-lg text-sm transition-colors disabled:opacity-50"
              >
                {loading ? "Saving to Registry..." : mode === "add" ? "Register Student" : "Save & Generate Version"}
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}

interface DeactivateModalProps {
  student: any;
  onClose: () => void;
  onSuccess: () => void;
}

export function DeactivateModal({ student, onClose, onSuccess }: DeactivateModalProps) {
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleDeactivate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reason.trim()) {
      setError("Please state the regulatory or institutional reason for deactivation.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await api.deactivateStudent(student.id, reason);
      onSuccess();
    } catch (err: any) {
      setError(err.message || "Failed to deactivate record.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-[#12161f] border border-red-900/60 rounded-xl max-w-md w-full p-6 text-gray-200 shadow-2xl">
        <h2 className="text-lg font-bold text-red-400 mb-2">Confirm Student Deactivation</h2>
        <p className="text-xs text-gray-300 mb-4 leading-relaxed">
          Deactivating student <b>{student.name}</b> ({student.apaar_masked}) will mark the record inactive, revoke any active QR credentials, and remove them from valid intake counts. Historical versions are immutably preserved in the audit log.
        </p>

        {error && (
          <div className="mb-4 p-3 bg-red-950/50 border border-red-800 rounded text-xs text-red-300">
            {error}
          </div>
        )}

        <form onSubmit={handleDeactivate} className="space-y-4">
          <div>
            <label className="block text-xs uppercase font-mono tracking-wider text-gray-400 mb-1">
              Reason for Deactivation *
            </label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              required
              placeholder="e.g. Admission cancelled by student; Transfer certificate issued; Dual enrollment resolved."
              className="w-full bg-[#1a2130] border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-red-500 min-h-[75px]"
            />
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg text-sm"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 bg-red-600 hover:bg-red-500 text-white font-medium rounded-lg text-sm disabled:opacity-50"
            >
              {loading ? "Deactivating..." : "Confirm Deactivation"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
