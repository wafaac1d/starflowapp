const JUNK = new Set([
  "тест",
  "test",
  "asdf",
  "asdfgh",
  "qwe",
  "qwert",
  "qwerty",
  "zxc",
  "zxcv",
  "йцук",
  "йцукен",
  "фыва",
  "хз",
  "лол",
  "lol",
  "кек",
  "ок",
  "ok",
  "нет",
  "да",
  "ерунда",
  "хрень",
  "привет",
  "ааа",
  "аааа",
]);

const VOWELS = new Set([..."аеёиоуыэюяaeiouy"]);

export function customEventOk(raw: string): boolean {
  const cleaned = raw.trim().replace(/\s+/g, " ");
  const folded = cleaned.toLocaleLowerCase("ru");
  const letters = [...folded].filter((character) => /\p{L}/u.test(character));
  const compact = folded.replace(/ /g, "");
  const words = cleaned.match(/[A-Za-zА-Яа-яЁё]{2,}/g) ?? [];
  const readable = words.some((word) => word.length >= 3) || words.length >= 2;
  const emoji = [...cleaned].some((character) => {
    const code = character.codePointAt(0) ?? 0;
    return (
      (code >= 0x1f300 && code <= 0x1faff) ||
      (code >= 0x2600 && code <= 0x27bf) ||
      code === 0xfe0f
    );
  });
  return (
    cleaned.length >= 2 &&
    cleaned.length <= 40 &&
    !emoji &&
    !JUNK.has(folded) &&
    !folded.includes("http") &&
    !folded.includes("www.") &&
    !folded.includes("игнор") &&
    letters.length >= 3 &&
    letters.length * 2 >= compact.length &&
    !/(.)\1{3,}/u.test(folded) &&
    [...folded].some((character) => VOWELS.has(character)) &&
    readable
  );
}
