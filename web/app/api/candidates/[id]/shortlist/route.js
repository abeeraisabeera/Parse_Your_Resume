export const runtime = "nodejs";

const PARSER_API_URL =
  process.env.PARSER_API_URL || "http://127.0.0.1:8000/parse";
const PARSER_API_BASE_URL =
  process.env.PARSER_API_BASE_URL ||
  PARSER_API_URL.replace(/\/parse\/?$/, "");

export async function PATCH(request, { params }) {
  try {
    const { id } = await params;
    const body = await request.json();
    const response = await fetch(`${PARSER_API_BASE_URL}/candidates/${id}/shortlist`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store"
    });
    const payload = await response.json().catch(() => ({
      error: "Parser API returned a non-JSON shortlist response."
    }));

    if (!response.ok) {
      return Response.json(payload, { status: response.status });
    }

    return Response.json(payload);
  } catch (error) {
    return Response.json(
      { error: `Unable to reach parser API: ${error.message}` },
      { status: 500 }
    );
  }
}
