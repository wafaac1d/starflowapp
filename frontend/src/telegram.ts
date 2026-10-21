type Insets = {
  top: number;
  right: number;
  bottom: number;
  left: number;
};

type BackButton = {
  show: () => void;
  hide: () => void;
  onClick: (handler: () => void) => void;
  offClick: (handler: () => void) => void;
};

type RawWebApp = {
  initData?: string;
  ready?: () => void;
  expand?: () => void;
  BackButton?: BackButton;
  enableClosingConfirmation?: () => void;
  disableClosingConfirmation?: () => void;
  onEvent?: (name: string, handler: () => void) => void;
  offEvent?: (name: string, handler: () => void) => void;
  viewportStableHeight?: number;
  contentSafeAreaInset?: Insets;
  safeAreaInset?: Insets;
};

declare global {
  interface Window {
    Telegram?: { WebApp?: RawWebApp };
  }
}

export type StarflowWebApp = {
  initData: string;
  ready: () => void;
  expand: () => void;
  showBack: (handler: () => void) => void;
  hideBack: () => void;
  setClosingConfirmation: (enabled: boolean) => void;
  bindViewport: () => void;
};

let cached: StarflowWebApp | null | undefined;
let backHandler: (() => void) | null = null;

export function resetWebAppCache(): void {
  cached = undefined;
  backHandler = null;
}

export function readWebApp(): StarflowWebApp | null {
  if (cached !== undefined) {
    return cached;
  }
  const raw = window.Telegram?.WebApp;
  if (raw === undefined || typeof raw.initData !== "string" || raw.initData.length === 0) {
    cached = null;
    return null;
  }
  cached = wrap(raw, raw.initData);
  cached.ready();
  cached.expand();
  cached.bindViewport();
  return cached;
}

function wrap(raw: RawWebApp, initData: string): StarflowWebApp {
  return {
    initData,
    ready: () => {
      raw.ready?.();
    },
    expand: () => {
      raw.expand?.();
    },
    showBack: (handler) => {
      const button = raw.BackButton;
      if (button === undefined) {
        return;
      }
      if (backHandler !== null) {
        button.offClick(backHandler);
      }
      backHandler = handler;
      button.onClick(handler);
      button.show();
    },
    hideBack: () => {
      const button = raw.BackButton;
      if (button === undefined) {
        return;
      }
      if (backHandler !== null) {
        button.offClick(backHandler);
      }
      backHandler = null;
      button.hide();
    },
    setClosingConfirmation: (enabled) => {
      if (enabled) {
        raw.enableClosingConfirmation?.();
        return;
      }
      raw.disableClosingConfirmation?.();
    },
    bindViewport: () => {
      const apply = () => applyInsets(raw);
      apply();
      raw.onEvent?.("viewportChanged", apply);
      raw.onEvent?.("safeAreaChanged", apply);
      raw.onEvent?.("contentSafeAreaChanged", apply);
    },
  };
}

function applyInsets(raw: RawWebApp): void {
  const root = document.documentElement;
  if (typeof raw.viewportStableHeight === "number") {
    root.style.setProperty("--tg-viewport-stable-height", `${raw.viewportStableHeight}px`);
  }
  writeInsets(root, "safe-area", raw.safeAreaInset);
  writeInsets(root, "content-safe-area", raw.contentSafeAreaInset);
}

export type InvoiceStatus = "paid" | "cancelled" | "failed" | "pending";

type InvoiceOpener = {
  openInvoice?: (url: string, callback?: (status: string) => void) => void;
};

export function invoiceGrantsPremium(_status: string): false {
  return false;
}

export function openInvoice(url: string): Promise<InvoiceStatus | "unavailable"> {
  const raw = window.Telegram?.WebApp as (RawWebApp & InvoiceOpener) | undefined;
  if (typeof raw?.openInvoice !== "function") {
    return Promise.resolve("unavailable");
  }
  return new Promise((resolve) => {
    raw.openInvoice?.(url, (status) => {
      if (
        status === "paid" ||
        status === "cancelled" ||
        status === "failed" ||
        status === "pending"
      ) {
        resolve(status);
        return;
      }
      resolve("failed");
    });
  });
}

function writeInsets(root: HTMLElement, name: string, insets: Insets | undefined): void {
  if (insets === undefined) {
    return;
  }
  root.style.setProperty(`--tg-${name}-inset-top`, `${insets.top}px`);
  root.style.setProperty(`--tg-${name}-inset-right`, `${insets.right}px`);
  root.style.setProperty(`--tg-${name}-inset-bottom`, `${insets.bottom}px`);
  root.style.setProperty(`--tg-${name}-inset-left`, `${insets.left}px`);
}
