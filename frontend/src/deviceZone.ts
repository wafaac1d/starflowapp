export function deviceTimezone(): string {
  try {
    const name = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (name.trim().length > 0) {
      return name;
    }
  } catch {
    return "Europe/Moscow";
  }
  return "Europe/Moscow";
}
