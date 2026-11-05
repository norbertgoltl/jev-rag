// @vitest-environment node
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { expect, test } from "vitest";
import { BACKEND_PATHS } from "../src/lib/api/backend-client";
import { isStatus, readiness } from "../src/lib/api/contracts";

type Schema = { examples?: unknown[] };
type OpenApi = { paths: Record<string, unknown>; components: { schemas: Record<string, Schema> } };

const contractUrl = new URL(
  "../../../docs/architecture/contracts/foundation.openapi.json",
  import.meta.url,
);
const contract: OpenApi = JSON.parse(readFileSync(fileURLToPath(contractUrl), "utf-8"));

function examplesOf(schemaName: string): unknown[] {
  const examples = contract.components.schemas[schemaName]?.examples;
  if (!examples?.length) throw new Error(`OpenAPI schema ${schemaName} has no examples`);
  return examples;
}

test("BFF only calls paths that exist in the OpenAPI contract", () => {
  for (const path of Object.values(BACKEND_PATHS)) {
    expect(Object.keys(contract.paths)).toContain(path);
  }
});

test.each(examplesOf("SystemStatusResponse"))("accepts system status example %j", (example) => {
  expect(isStatus(example)).toBe(true);
});

test.each(examplesOf("ReadinessResponse"))("maps ready example %j to ready", (example) => {
  expect(readiness(example, 200)).toBe("ready");
});

test.each(examplesOf("NotReadyResponse"))("maps not-ready example %j to not_ready", (example) => {
  expect(readiness(example, 503)).toBe("not_ready");
});
