import path from "node:path";
import { copyFile, mkdir, writeFile, access } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = path.resolve(frontendRoot, "..");
const source = path.join(repoRoot, "static", "logo.png");
const target = path.join(frontendRoot, "public", "logo.png");
const flag = path.join(frontendRoot, "src", "generated", "logo.ts");

async function exists(file) {
  try {
    await access(file);
    return true;
  } catch {
    return false;
  }
}

const available = await exists(source);
await mkdir(path.dirname(flag), { recursive: true });
await mkdir(path.dirname(target), { recursive: true });
if (available) {
  await copyFile(source, target);
}
await writeFile(flag, `export const logoAvailable = ${available};\n`, "utf8");
