export function titled(value: string): string {
  const chars = Array.from(value);
  const index = chars.findIndex((char) => char.toLocaleLowerCase("ru") !== char.toLocaleUpperCase("ru"));
  if (index < 0) {
    return value;
  }
  const char = chars[index];
  if (char === undefined) {
    return value;
  }
  chars[index] = char.toLocaleUpperCase("ru");
  return chars.join("");
}
