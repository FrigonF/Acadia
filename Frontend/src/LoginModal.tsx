import React, { useState } from "react";
import { api, setAuthToken } from "./api";

interface LoginModalProps {
  onSuccess: (userData: any) => void;
}

export function LoginModal({ onSuccess }: LoginModalProps) {
  const [email, setEmail] = useState("admin@acadia.gov.in");
  const [password, setPassword] = useState("Admin@Acadia2026");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const presets = [
    { label: "Platform Admin", email: "admin@acadia.gov.in", pass: "Admin@Acadia2026" },
    { label: "AICTE Verifier", email: "verifier@aicte.gov.in", pass: "Verifier@Aicte2026" },
    { label: "Inst Admin (Delhi)", email: "admin@diaet.edu.in", pass: "Delhi@Inst2026" },
    { label: "Inst Admin (Pune)", email: "admin@mitr.ac.in", pass: "Pune@Inst2026" },
    { label: "External Verifier", email: "verifier@external-corp.com", pass: "Verify@External2026" },
  ];

  const handleLogin = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const data = await api.login(email, password);
      onSuccess(data);
    } catch (err: any) {
      setError(err.message || "Failed to authenticate.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-[#12161f] border border-gray-800 rounded-xl max-w-md w-full p-6 text-gray-200 shadow-2xl">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 font-bold text-lg">
            AC
          </div>
          <div>
            <h2 className="text-lg font-semibold text-white tracking-wide">Sign in to ACADIA</h2>
            <p className="text-xs text-gray-400">SIH 2026 · AICTE Academic Identity Platform</p>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-950/40 border border-red-800/50 rounded-lg text-xs text-red-300">
            {error}
          </div>
        )}

        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="block text-xs uppercase tracking-wider text-gray-400 mb-1 font-mono">
              Email Address
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full bg-[#1a2130] border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
              placeholder="e.g. admin@acadia.gov.in"
            />
          </div>

          <div>
            <label className="block text-xs uppercase tracking-wider text-gray-400 mb-1 font-mono">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full bg-[#1a2130] border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
              placeholder="••••••••"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-medium py-2 rounded-lg text-sm transition-colors disabled:opacity-50"
          >
            {loading ? "Authenticating..." : "Authorize & Enter Console"}
          </button>
        </form>

        <div className="mt-6 pt-4 border-t border-gray-800/80">
          <span className="block text-[11px] uppercase tracking-wider text-gray-500 font-mono mb-2">
            Quick-Select Demo Role:
          </span>
          <div className="grid grid-cols-2 gap-1.5 text-xs">
            {presets.map((p) => (
              <button
                key={p.label}
                type="button"
                onClick={() => {
                  setEmail(p.email);
                  setPassword(p.pass);
                }}
                className={`text-left px-2.5 py-1.5 rounded border transition-colors ${
                  email === p.email
                    ? "bg-emerald-950/40 border-emerald-500/50 text-emerald-300"
                    : "bg-[#161d2b] border-gray-800 text-gray-300 hover:border-gray-700"
                }`}
              >
                <div className="font-medium text-[11px]">{p.label}</div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
