export const runtime = "nodejs";

const PARSER_API_URL =
  process.env.PARSER_API_URL || "http://127.0.0.1:8000/parse";
const PARSER_API_BASE_URL =
  process.env.PARSER_API_BASE_URL ||
  PARSER_API_URL.replace(/\/parse\/?$/, "");

export async function DELETE(_request, { params }) {
  try {
    const { id } = await params;
    const response = await fetch(`${PARSER_API_BASE_URL}/skills/${encodeURIComponent(id)}`, {
      method: "DELETE",
      cache: "no-store"
    });
    const payload = await response.json().catch(() => ({
      error: "Parser API returned a non-JSON skill delete response."
    }));
    return Response.json(payload, { status: response.status });
  } catch (error) {
    return Response.json(
      { error: `Unable to reach parser API: ${error.message}` },
      { status: 500 }
    );
  }
}
