// Generates TypeScript types from the backend OpenAPI contract.
//   node scripts/generate-api-types.mjs          writes the generated file
//   node scripts/generate-api-types.mjs --check  fails if the file is out of date
import { readFileSync, writeFileSync } from "node:fs";
import openapiTS, { astToString } from "openapi-typescript";

const CONTRACT = new URL(
  "../../../docs/architecture/contracts/foundation.openapi.json",
  import.meta.url,
);
const OUTPUT = new URL("../src/lib/api/generated/foundation.d.ts", import.meta.url);
const HEADER =
  "// Generated from docs/architecture/contracts/foundation.openapi.json.\n" +
  "// Do not edit. Run `pnpm --filter @jev-rag/web generate:api` to regenerate.\n\n";

const expected = HEADER + astToString(await openapiTS(CONTRACT));

if (process.argv.includes("--check")) {
  let actual = "";
  try {
    actual = readFileSync(OUTPUT, "utf-8");
  } catch {
    // A missing file is reported as out of date below.
  }
  if (actual !== expected) {
    console.error(
      "Generated API types are out of date. Run: pnpm --filter @jev-rag/web generate:api",
    );
    process.exit(1);
  }
  console.log("Generated API types are up to date.");
} else {
  writeFileSync(OUTPUT, expected);
  console.log("Wrote src/lib/api/generated/foundation.d.ts");
}
