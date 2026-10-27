import { afterEach, expect, test, vi } from "vitest";
import { diagnose } from "../src/lib/api/diagnostics";
import { getConfig } from "../src/lib/config/server";
import { GET } from "../src/app/api/backend/status/route";
afterEach(() => {vi.unstubAllGlobals();vi.unstubAllEnvs();vi.useRealTimers();});
function mock(status: number, body: unknown) {return new Response(JSON.stringify(body),{status});}
test.each([[200,{status:"ready",dependencies:{qdrant:"up"}},"ready"],[503,{status:"not_ready",dependencies:{qdrant:"down"}},"not_ready"],[200,{},"unknown"]])("maps readiness %s", async (status,body,expected) => {
 vi.stubGlobal("fetch",vi.fn().mockResolvedValueOnce(mock(200,{service:"api",status:"ok"})).mockResolvedValueOnce(mock(status,body)));
 expect((await diagnose("id")).body).toMatchObject({backend:"online",readiness:expected});
});
test("keeps backend online after readiness failure",async()=>{vi.stubGlobal("fetch",vi.fn().mockResolvedValueOnce(mock(200,{service:"api",status:"ok"})).mockRejectedValueOnce(new Error("timeout")));expect((await diagnose("id")).body).toMatchObject({backend:"online",readiness:"unknown"});});
test("sanitizes network errors",async()=>{vi.stubGlobal("fetch",vi.fn().mockRejectedValue(new Error("secret-api-key")));const result=await diagnose("id");expect(result.status).toBe(503);expect(JSON.stringify(result)).not.toContain("secret-api-key");});
test.each([new Response("bad json"),mock(200,{service:"other"}),mock(500,{service:"api",status:"ok"})])("rejects invalid system response",async(response)=>{vi.stubGlobal("fetch",vi.fn().mockResolvedValue(response));expect((await diagnose("id")).status).toBe(502);});
test("maps timeout",async()=>{vi.useFakeTimers();vi.stubGlobal("fetch",vi.fn((_url,{signal})=>new Promise((_resolve,reject)=>{signal.addEventListener("abort",()=>reject(new Error("aborted")));})));const result=diagnose("id");await vi.advanceTimersByTimeAsync(2001);expect((await result).status).toBe(504);});
test("requires production URL",()=>{vi.stubEnv("NODE_ENV","production");vi.stubEnv("BACKEND_API_URL",undefined);expect(()=>getConfig()).toThrow("BACKEND_API_URL");});
test("propagates UUID and disables caching",async()=>{const fetchMock=vi.fn().mockImplementation(()=>Promise.resolve(mock(200,{service:"api",status:"ok"})));vi.stubGlobal("fetch",fetchMock);const response=await GET();const body=await response.json();expect(body.request_id).toBe(response.headers.get("X-Request-ID"));expect(body.request_id).toMatch(/^[0-9a-f-]{36}$/);expect(response.headers.get("Cache-Control")).toBe("no-store");expect(fetchMock.mock.calls[0][1]).toMatchObject({cache:"no-store",headers:{"X-Request-ID":body.request_id}});});
// @vitest-environment node
