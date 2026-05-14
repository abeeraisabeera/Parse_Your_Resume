export const runtime = "nodejs";

const PARSER_API_URL =
  process.env.PARSER_API_URL || "http://127.0.0.1:8000/parse";
const PARSER_API_BASE_URL =
  process.env.PARSER_API_BASE_URL ||
  PARSER_API_URL.replace(/\/parse\/?$/, "");

function parserUrl(path) {
  return new URL(path, PARSER_API_BASE_URL);
}

export async function GET() {
  try {
    const response = await fetch(parserUrl("/roles"), {
      method: "GET",
      cache: "no-store"
    });
    const payload = await response.json().catch(() => ({
      error: "Parser API returned a non-JSON roles response."
    }));
    return Response.json(payload, { status: response.status });
  } catch (error) {
    return Response.json(
      { error: `Unable to reach parser API: ${error.message}` },
      { status: 500 }
    );
  }
}

export async function POST(request) {
  try {
    const body = await request.json();
    const response = await fetch(parserUrl("/roles"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store"
    });
    const payload = await response.json().catch(() => ({
      error: "Parser API returned a non-JSON roles response."
    }));
    return Response.json(payload, { status: response.status });
  } catch (error) {
    return Response.json(
      { error: `Unable to reach parser API: ${error.message}` },
      { status: 500 }
    );
  }
}
