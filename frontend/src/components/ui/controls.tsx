import { useEffect, useState } from "react";
import { useNavigate } from "react-router";

import { logoAvailable } from "../../generated/logo";
import { prefersReducedMotion } from "../../motion";
import { text } from "../../resources";

type ButtonProps = {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  loading?: boolean;
  tone?: "danger";
};

export function Button({ label, onClick, disabled = false, loading = false, tone }: ButtonProps) {
  const inactive = disabled || loading;
  return (
    <button
      type="button"
      className={tone === "danger" ? "button button-danger" : "button"}
      onClick={onClick}
      disabled={inactive}
      aria-busy={loading}
    >
      {label}
    </button>
  );
}

type FieldProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  inputMode?: "numeric" | "text";
  labelledBy?: string;
};

export function Field({ label, value, onChange, error, inputMode, labelledBy }: FieldProps) {
  const described = error ? `${label}-error` : undefined;
  return (
    <label className="field">
      {labelledBy === undefined ? <span>{label}</span> : null}
      <input
        value={value}
        inputMode={inputMode}
        onChange={(event) => onChange(event.target.value)}
        aria-invalid={error !== undefined}
        aria-describedby={described}
        {...(labelledBy !== undefined ? { "aria-labelledby": labelledBy } : {})}
      />
      {error !== undefined ? (
        <span id={described} className="field-error" role="alert">
          {error}
        </span>
      ) : null}
    </label>
  );
}

type LogoSlotProps = {
  available: boolean;
  src: string;
  label: string;
};

export function BackHome() {
  const navigate = useNavigate();
  return (
    <Button
      label={text("ui.common.back")}
      onClick={() => {
        void navigate("/");
      }}
    />
  );
}

export function LoadingScreen() {
  const [dots, setDots] = useState(1);
  useEffect(() => {
    if (prefersReducedMotion()) {
      return;
    }
    const id = window.setInterval(() => {
      setDots((current) => (current % 3) + 1);
    }, 600);
    return () => {
      window.clearInterval(id);
    };
  }, []);
  return (
    <main className="loading-screen">
      <LogoSlot available={logoAvailable} src="/logo.png" label={text("ui.home.logo_label")} />
      <p className="loading-label">
        <span className="loading-word">
          {text("ui.common.loading")}
          <span className="loading-dots" aria-hidden="true">
            {".".repeat(dots)}
          </span>
        </span>
      </p>
    </main>
  );
}

export function LogoSlot({ available, src, label }: LogoSlotProps) {
  const [failed, setFailed] = useState(false);
  if (!available || failed) {
    return <div className="logo-slot" role="img" aria-label={label} />;
  }
  return (
    <img className="logo-slot" src={src} alt={label} onError={() => setFailed(true)} />
  );
}
