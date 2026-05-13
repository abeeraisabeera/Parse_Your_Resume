export const runtime = "nodejs";

const PARSER_API_URL =
  process.env.PARSER_API_URL || "http://127.0.0.1:8000/parse";
const PARSER_HEALTH_URL =
  process.env.PARSER_HEALTH_URL ||
  PARSER_API_URL.replace(/\/parse\/?$/, "/healthz");

export async function GET() {
  try {
    const response = await fetch(PARSER_HEALTH_URL, {
      method: "GET",
      cache: "no-store"
    });
    const payload = await response.json().catch(() => ({
      error: "Parser API returned a non-JSON health response."
    }));

    if (!response.ok) {
      return Response.json(payload, { status: response.status });
    }

    return Response.json(payload);
  } catch (error) {
    return Response.json(
      { ok: false, error: `Unable to reach parser API: ${error.message}` },
      { status: 500 }
    );
  }
}
