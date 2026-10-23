import { randomUUID } from "node:crypto";
import { diagnose } from "@/lib/api/diagnostics";
export const runtime = "nodejs";
export async function GET() {
 const requestId = randomUUID();
 const result = await diagnose(requestId);
 return Response.json(result.body, {status:result.status,headers:{"Cache-Control":"no-store","X-Request-ID":requestId}});
}
