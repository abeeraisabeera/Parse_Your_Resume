export const runtime = "nodejs";

const PARSER_API_URL =
  process.env.PARSER_API_URL || "http://127.0.0.1:8000/parse";
const PARSER_API_BASE_URL =
  process.env.PARSER_API_BASE_URL ||
  PARSER_API_URL.replace(/\/parse\/?$/, "");

export async function GET(request) {
  try {
    const incoming = new URL(request.url);
    const target = new URL("/candidates/export.xlsx", PARSER_API_BASE_URL);
    incoming.searchParams.forEach((value, key) => {
      target.searchParams.append(key, value);
    });

    const response = await fetch(target, {
      method: "GET",
      cache: "no-store"
    });

    if (!response.ok) {
      const payload = await response.json().catch(() => ({
        error: "Parser API returned a non-JSON export response."
      }));
      return Response.json(payload, { status: response.status });
    }

    const headers = new Headers(response.headers);
    headers.set(
      "Content-Disposition",
      response.headers.get("Content-Disposition") ||
        'attachment; filename="top-ranked-candidates.xlsx"'
    );
    return new Response(response.body, { status: response.status, headers });
  } catch (error) {
    return Response.json(
      { error: `Unable to reach parser API: ${error.message}` },
      { status: 500 }
    );
  }
}
