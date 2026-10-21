import { mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { load } from "js-yaml";

const frontendRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const localeDir = join(frontendRoot, "..", "resources", "texts", "ru");
const target = join(frontendRoot, "src", "generated", "texts.ts");

function flatten(prefix, value, into) {
  if (typeof value === "string") {
    into[prefix] = value;
    return;
  }
  if (typeof value !== "object" || value === null) {
    throw new Error(`${prefix} must be a string or a mapping`);
  }
  for (const [key, item] of Object.entries(value)) {
    flatten(prefix ? `${prefix}.${key}` : key, item, into);
  }
}

const texts = {};
for (const name of readdirSync(localeDir).filter((item) => item.endsWith(".yaml")).sort()) {
  const loaded = load(readFileSync(join(localeDir, name), "utf8"));
  flatten(name.replace(/\.yaml$/, ""), loaded, texts);
}

const source = `/* generated from resources/texts/ru — do not edit */\nexport const texts = ${JSON.stringify(texts, null, 2)} as const;\n\nexport type TextKey = keyof typeof texts;\n`;

if (process.argv.includes("--check")) {
  const current = readFileSync(target, "utf8");
  if (current !== source) {
    throw new Error("frontend/src/generated/texts.ts is behind resources/texts/ru");
  }
} else {
  mkdirSync(dirname(target), { recursive: true });
  writeFileSync(target, source);
}
