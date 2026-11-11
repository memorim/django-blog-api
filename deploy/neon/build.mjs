import { build } from "esbuild";
import { zipSync } from "fflate";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

const output = resolve("../../.neon-build");
await mkdir(output, { recursive: true });
const bundle = await build({
  entryPoints: ["index.mjs"],
  bundle: true,
  platform: "node",
  target: "node24",
  format: "esm",
  write: false,
  minify: true,
});
await writeFile(resolve(output, "index.mjs"), bundle.outputFiles[0].contents);
const compiled = await import(pathToFileURL(resolve(output, "index.mjs")));
const denied = await compiled.default.fetch(
  new Request("https://verification.invalid/cron", { method: "POST" }),
);
if (denied.status !== 401)
  throw new Error("Anonymous scheduler invocation must be rejected");
const zip = zipSync(
  { "index.mjs": bundle.outputFiles[0].contents },
  { level: 9 },
);
await writeFile(resolve(output, "django-backup-trigger.zip"), zip);
console.log(
  JSON.stringify({
    artifact: ".neon-build/django-backup-trigger.zip",
    bytes: zip.length,
  }),
);
