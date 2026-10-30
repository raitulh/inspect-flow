"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Eye, EyeOff, Factory, Fingerprint, ScanEye, ShieldCheck } from "lucide-react";
import { api, type User } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api<User>("/api/v1/auth/me")
      .then(() => router.replace("/"))
      .catch(() => undefined);
  }, [router]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await api<{ user: User }>("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not sign in. Please verify your credentials.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="login-layout">
      <section className="login-brand-panel">
        <div className="login-brand">
          <div className="brand-mark">
            <ScanEye size={24} />
          </div>
          <div className="brand-name">
            LineGuard<span>CV</span>
          </div>
        </div>
        <div className="login-hero-copy">
          <div className="eyebrow">
            <span className="eyebrow-line" /> MANUFACTURING INTELLIGENCE
          </div>
          <h1>
            Automated visual<br />
            intelligence for<br />
            the <span>production line.</span>
          </h1>
          <p>
            Real-time quality monitoring, automated defect detection, and station-level verification for modern industrial plants.
          </p>
        </div>
        <div className="login-feature-list">
          <div>
            <span>
              <ShieldCheck size={17} />
            </span>
            <div>
              <strong>Evidence-backed quality review</strong>
              <small>Complete visual trace, timestamped audit trail, and resolution lifecycle.</small>
            </div>
          </div>
          <div>
            <span>
              <Fingerprint size={17} />
            </span>
            <div>
              <strong>High-performance edge vision</strong>
              <small>Optimized CPU-first computer vision with adaptive lighting compensation.</small>
            </div>
          </div>
          <div>
            <span>
              <Factory size={17} />
            </span>
            <div>
              <strong>Seamless industrial connectivity</strong>
              <small>Integrated RTSP streams, Modbus PLC boundaries, and automated webhooks.</small>
            </div>
          </div>
        </div>
        <div className="login-panel-bottom">
          <span>LINEGUARD CV ENTERPRISE</span>
          <span>INDUSTRIAL QUALITY PLATFORM</span>
        </div>
      </section>

      <section className="login-form-panel">
        <div className="login-form-wrap">
          <div className="login-mobile-brand">
            <div className="brand-mark">
              <ScanEye size={22} />
            </div>
            <div className="brand-name">
              LineGuard<span>CV</span>
            </div>
          </div>
          <div className="login-heading">
            <div className="form-kicker">SECURE ACCESS</div>
            <h2>Sign in to workspace.</h2>
            <p>Access your organization&apos;s inspection dashboard.</p>
          </div>
          <form className="login-form" onSubmit={submit}>
            <label htmlFor="email">Work email address</label>
            <input
              id="email"
              type="email"
              autoComplete="username"
              placeholder="operator@company.com"
              required
              maxLength={320}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <div className="label-row">
              <label htmlFor="password">Password</label>
              <span className="password-policy">Secure credentials</span>
            </div>
            <div className="password-field">
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                placeholder="Enter password"
                required
                maxLength={256}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <button
                type="button"
                className="password-toggle"
                aria-label={showPassword ? "Hide password" : "Show password"}
                onClick={() => setShowPassword(!showPassword)}
              >
                {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
              </button>
            </div>
            {error && (
              <div className="form-error">
                <span /> {error}
              </div>
            )}
            <button className="button button-primary login-submit" disabled={submitting} type="submit">
              {submitting ? "Authenticating…" : "Sign in to workspace"}
              <ArrowRight size={17} />
            </button>
          </form>
          <div className="login-security">
            <ShieldCheck size={16} />
            <span>Encrypted Session · Role-Based Security · Multi-Tenant Protection</span>
          </div>
        </div>
        <div className="login-footnote">
          © LineGuard CV Systems · Enterprise Vision & Quality Intelligence
        </div>
      </section>
    </main>
  );
}
