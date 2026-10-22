import { useEffect, useState, type ReactNode } from "react";
import { useNavigate } from "react-router";

import { logoAvailable } from "../../generated/logo";
import { prefersReducedMotion } from "../../motion";
import { text } from "../../resources";
import { Icon, type IconName } from "./icons";

type ButtonProps = {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  loading?: boolean;
  tone?: "danger" | "outline";
  icon?: IconName;
};

export function Button({ label, onClick, disabled = false, loading = false, tone, icon }: ButtonProps) {
  const inactive = disabled || loading;
  const toneClass = tone === "danger" ? "button-danger" : tone === "outline" ? "button-outline" : "";
  return (
    <button
      type="button"
      className={toneClass === "" ? "button" : `button ${toneClass}`}
      onClick={onClick}
      disabled={inactive}
      aria-busy={loading}
    >
      {icon !== undefined ? <Icon name={icon} /> : null}
      {label}
    </button>
  );
}

type IconButtonProps = {
  label: string;
  name: IconName;
  onClick: () => void;
};

export function IconButton({ label, name, onClick }: IconButtonProps) {
  return (
    <button type="button" className="icon-button" aria-label={label} onClick={onClick}>
      <Icon name={name} />
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

export const Input = Field;

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

type OverlayProps = {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
};

export function Modal({ open, title, onClose, children }: OverlayProps) {
  useOverlayEscape(open, onClose);
  if (!open) {
    return null;
  }
  return (
    <div className="overlay" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(event) => {
          event.stopPropagation();
        }}
      >
        {children}
      </div>
    </div>
  );
}

export function BottomSheet({ open, title, onClose, children }: OverlayProps) {
  useOverlayEscape(open, onClose);
  if (!open) {
    return null;
  }
  return (
    <div className="overlay overlay-sheet" onClick={onClose}>
      <div
        className="bottom-sheet"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(event) => {
          event.stopPropagation();
        }}
      >
        <div className="sheet-bar">
          <IconButton label={text("ui.common.close")} name="close" onClick={onClose} />
        </div>
        {children}
      </div>
    </div>
  );
}

function useOverlayEscape(open: boolean, onClose: () => void): void {
  useEffect(() => {
    if (!open) {
      return;
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
    };
  }, [onClose, open]);
}

export function Toast({ message }: { message: string }) {
  if (message.trim().length === 0) {
    return null;
  }
  return (
    <p className="toast" role="alert">
      {message}
    </p>
  );
}

export function Skeleton({ lines = 2 }: { lines?: number }) {
  return (
    <div className="skeleton" aria-hidden="true">
      {Array.from({ length: lines }, (_, index) => (
        <span key={index} />
      ))}
    </div>
  );
}

export function EmptyState({ title }: { title: string }) {
  return <p className="empty">{title}</p>;
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="error-state">
      <p role="alert">{message}</p>
      {onRetry !== undefined ? <Button label={text("ui.common.retry")} onClick={onRetry} /> : null}
    </div>
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
