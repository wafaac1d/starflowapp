const SIGN_EMOJI: Record<string, string> = {
  овен: "♈️",
  телец: "♉️",
  близнецы: "♊️",
  рак: "♋️",
  лев: "♌️",
  дева: "♍️",
  весы: "♎️",
  скорпион: "♏️",
  стрелец: "♐️",
  козерог: "♑️",
  водолей: "♒️",
  рыбы: "♓️",
};

export function signEmoji(sign: string | null): string | null {
  if (sign === null) {
    return null;
  }
  return SIGN_EMOJI[sign] ?? null;
}
