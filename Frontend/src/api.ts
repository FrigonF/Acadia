/**
 * ACADIA Centralized API Client & Service Module
 * Handles authentication headers, error states, and all backend REST endpoints.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

// Auth Token management
export const getAuthToken = (): string | null => {
  return localStorage.getItem("acadia_token");
};

export const setAuthToken = (token: string, user: any) => {
  localStorage.setItem("acadia_token", token);
  localStorage.setItem("acadia_user", JSON.stringify(user));
};

export const clearAuth = () => {
  localStorage.removeItem("acadia_token");
  localStorage.removeItem("acadia_user");
};

export const getCurrentUser = (): any | null => {
  const userStr = localStorage.getItem("acadia_user");
  if (!userStr) return null;
  try {
    return JSON.parse(userStr);
  } catch {
    return null;
  }
};

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = getAuthToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> || {}),
  };

  if (token && !headers["Authorization"]) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  // If not multipart form, default to JSON
  if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    clearAuth();
    window.dispatchEvent(new Event("acadia_auth_changed"));
    throw new Error("Session expired or unauthorized. Please log in.");
  }

  if (!response.ok) {
    let errorDetail = `Error ${response.status}: ${response.statusText}`;
    try {
      const errJson = await response.json();
      if (errJson.detail) {
        errorDetail = typeof errJson.detail === "string" ? errJson.detail : JSON.stringify(errJson.detail);
      }
    } catch {
      // fallback
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

export const api = {
  // --- Auth ---
  login: async (username: string, password: string) => {
    const formData = new URLSearchParams();
    formData.append("username", username);
    formData.append("password", password);

    const data = await request<any>("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: formData.toString(),
    });
    setAuthToken(data.access_token, data);
    window.dispatchEvent(new Event("acadia_auth_changed"));
    return data;
  },

  getMe: () => request<any>("/auth/me"),

  // --- Reports & Dashboard Overview ---
  getOverview: () => request<any>("/reports/overview"),
  getAnomalies: () => request<any>("/reports/anomalies"),
  getInstitutionReports: () => request<any>("/reports/institutions"),

  // --- Institutions ---
  getInstitutions: () => request<any[]>("/institutions"),
  getInstitution: (id: string) => request<any>(`/institutions/${id}`),
  createInstitution: (payload: any) => request<any>("/institutions", {
    method: "POST",
    body: JSON.stringify(payload),
  }),
  getInstitutionIntake: (id: string) => request<any[]>(`/institutions/${id}/intake`),

  // --- Students ---
  getStudents: (params?: { institution_id?: string; record_status?: string; programme?: string; academic_year?: string; include_inactive?: boolean }) => {
    const query = new URLSearchParams();
    if (params?.institution_id) query.append("institution_id", params.institution_id);
    if (params?.record_status) query.append("record_status", params.record_status);
    if (params?.programme) query.append("programme", params.programme);
    if (params?.academic_year) query.append("academic_year", params.academic_year);
    if (params?.include_inactive) query.append("include_inactive", "true");
    const qs = query.toString() ? `?${query.toString()}` : "";
    return request<any[]>(`/students${qs}`);
  },
  getStudent: (id: string) => request<any>(`/students/${id}`),
  createStudent: (payload: any) => request<any>("/students", {
    method: "POST",
    body: JSON.stringify(payload),
  }),
  updateStudent: (id: string, payload: any) => request<any>(`/students/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  }),
  deactivateStudent: (id: string, reason: string) => request<any>(`/students/${id}/deactivate`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  }),
  reactivateStudent: (id: string) => request<any>(`/students/${id}/reactivate`, {
    method: "POST",
  }),

  // --- Uploads & Ingestion ---
  uploadBatch: async (file: File, institutionId: string) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("institution_id", institutionId);

    return request<any>("/uploads", {
      method: "POST",
      body: formData,
    });
  },
  getBatches: () => request<any[]>("/uploads"),
  getBatchReport: (batchId: string) => request<any>(`/uploads/${batchId}/report`),

  // --- Verification ---
  getDuplicates: () => request<any>("/verification/duplicates"),
  getIntakeAlerts: () => request<any>("/verification/intake/alerts"),
  getValidationIssues: (params?: { batch_id?: string; student_id?: string; resolution_status?: string }) => {
    const query = new URLSearchParams();
    if (params?.batch_id) query.append("batch_id", params.batch_id);
    if (params?.student_id) query.append("student_id", params.student_id);
    if (params?.resolution_status) query.append("resolution_status", params.resolution_status);
    const qs = query.toString() ? `?${query.toString()}` : "";
    return request<any[]>(`/validation/issues${qs}`);
  },
  resolveIssue: (issueId: string, payload: { resolution_notes: string; action: string }) => {
    return request<any>(`/validation/issues/${issueId}/resolve`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  // --- Record Integrity & Sealing ---
  sealRecord: (recordId: string) => request<any>(`/integrity/${recordId}/seal`, { method: "POST" }),
  getRecordVersions: (recordId: string) => request<any>(`/integrity/${recordId}`),
  verifyRecordIntegrity: (recordId: string, versionNumber?: number) => {
    const qs = versionNumber ? `?version_number=${versionNumber}` : "";
    return request<any>(`/integrity/${recordId}/verify${qs}`, { method: "POST" });
  },

  // --- QR Verification ---
  generateQR: (recordId: string) => request<any>(`/qr/generate/${recordId}`, { method: "POST" }),
  verifyQRToken: (token: string) => request<any>(`/qr/verify/${token}`),
  revokeCredential: (credentialId: string, reason: string) => request<any>(`/qr/revoke/${credentialId}?reason=${encodeURIComponent(reason)}`, { method: "POST" }),

  // --- Audit Logs ---
  getAuditLogs: (params?: { action?: string; target_type?: string }) => {
    const query = new URLSearchParams();
    if (params?.action) query.append("action", params.action);
    if (params?.target_type) query.append("target_type", params.target_type);
    const qs = query.toString() ? `?${query.toString()}` : "";
    return request<any[]>(`/audit${qs}`);
  },
};
