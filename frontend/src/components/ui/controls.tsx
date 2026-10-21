import { useState } from "react";

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
      <svg viewBox="0 0 20 20" aria-hidden="true">
        <circle cx="10" cy="10" r="6.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
      </svg>
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

export function LogoSlot({ available, src, label }: LogoSlotProps) {
  const [failed, setFailed] = useState(false);
  if (!available || failed) {
    return <div className="logo-slot" role="img" aria-label={label} />;
  }
  return (
    <img className="logo-slot" src={src} alt={label} onError={() => setFailed(true)} />
  );
}
