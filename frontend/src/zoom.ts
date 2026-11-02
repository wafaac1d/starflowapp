export function preventZoom(): void {
  if (typeof document === "undefined") {
    return;
  }

  const prevent = (event: Event) => {
    if (event.cancelable) {
      event.preventDefault();
    }
  };

  document.addEventListener("gesturestart", prevent, { passive: false });
  document.addEventListener("gesturechange", prevent, { passive: false });
  document.addEventListener("gestureend", prevent, { passive: false });

  document.addEventListener(
    "touchmove",
    (event: TouchEvent) => {
      if (event.touches.length > 1) {
        prevent(event);
      }
    },
    { passive: false },
  );

  document.addEventListener(
    "wheel",
    (event: WheelEvent) => {
      if (event.ctrlKey) {
        prevent(event);
      }
    },
    { passive: false },
  );

  document.addEventListener("keydown", (event: KeyboardEvent) => {
    if (
      (event.ctrlKey || event.metaKey) &&
      (event.key === "+" ||
        event.key === "-" ||
        event.key === "=" ||
        event.key === "_" ||
        event.key === "0")
    ) {
      prevent(event);
    }
  });
}
