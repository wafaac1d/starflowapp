/** Оставляет только цифры и ставит точки в дате дд.мм.гггг сразу при вводе 2 и 4 цифр. */

export function maskBirthDate(value: string, previous?: string): string {
  if (previous !== undefined && previous.length > value.length) {
    if (previous.endsWith(".") && value === previous.slice(0, -1)) {
      const trimmed = value.slice(0, -1);
      return maskBirthDate(trimmed);
    }
    const digits = value.replace(/\D/g, "").slice(0, 8);
    if (digits.length === 2 && value.endsWith(".")) {
      return `${digits}.`;
    }
    if (digits.length <= 2) {
      return digits;
    }
    if (digits.length === 4 && value.endsWith(".")) {
      return `${digits.slice(0, 2)}.${digits.slice(2)}.`;
    }
    if (digits.length <= 4) {
      return `${digits.slice(0, 2)}.${digits.slice(2)}`;
    }
    return `${digits.slice(0, 2)}.${digits.slice(2, 4)}.${digits.slice(4)}`;
  }

  const digits = value.replace(/\D/g, "").slice(0, 8);
  if (digits.length < 2) {
    return digits;
  }
  if (digits.length === 2) {
    return `${digits}.`;
  }
  if (digits.length === 3) {
    return `${digits.slice(0, 2)}.${digits.slice(2)}`;
  }
  if (digits.length === 4) {
    return `${digits.slice(0, 2)}.${digits.slice(2)}.`;
  }
  return `${digits.slice(0, 2)}.${digits.slice(2, 4)}.${digits.slice(4)}`;
}

/** Оставляет только цифры и ставит двоеточие во времени чч:мм сразу при вводе 2 цифр. */

export function maskBirthTime(value: string, previous?: string): string {
  if (previous !== undefined && previous.length > value.length) {
    if (previous.endsWith(":") && value === previous.slice(0, -1)) {
      const trimmed = value.slice(0, -1);
      return maskBirthTime(trimmed);
    }
    const digits = value.replace(/\D/g, "").slice(0, 4);
    if (digits.length === 2 && value.endsWith(":")) {
      return `${digits}:`;
    }
    if (digits.length <= 2) {
      return digits;
    }
    return `${digits.slice(0, 2)}:${digits.slice(2)}`;
  }

  const digits = value.replace(/\D/g, "").slice(0, 4);
  if (digits.length < 2) {
    return digits;
  }
  if (digits.length === 2) {
    return `${digits}:`;
  }
  return `${digits.slice(0, 2)}:${digits.slice(2)}`;
}
