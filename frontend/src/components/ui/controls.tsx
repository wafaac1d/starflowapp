import { useState } from "react";
import { useNavigate } from "react-router";

import { logoAvailable } from "../../generated/logo";
import { text } from "../../resources";

type ButtonProps = {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  loading?: boolean;
};

export function Button({ label, onClick, disabled = false, loading = false }: ButtonProps) {
  const inactive = disabled || loading;
  return (
    <button
      type="button"
      className="button"
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
};

export function Field({ label, value, onChange, error }: FieldProps) {
  const described = error ? `${label}-error` : undefined;
  return (
    <label className="field">
      <span>{label}</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-invalid={error !== undefined}
        aria-describedby={described}
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
  return (
    <main className="loading-screen">
      <LogoSlot available={logoAvailable} src="/logo.png" label={text("ui.home.logo_label")} />
      <p className="loading-label">{text("ui.common.loading")}</p>
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
