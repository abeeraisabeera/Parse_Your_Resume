export const runtime = "nodejs";

const PARSER_API_URL =
  process.env.PARSER_API_URL || "http://127.0.0.1:8000/parse";
const PARSER_API_BASE_URL =
  process.env.PARSER_API_BASE_URL ||
  PARSER_API_URL.replace(/\/parse\/?$/, "");

function parserUrl(path, searchParams) {
  const url = new URL(path, PARSER_API_BASE_URL);
  searchParams?.forEach((value, key) => {
    url.searchParams.append(key, value);
  });
  return url;
}

export async function GET(request) {
  try {
    const incoming = new URL(request.url);
    const response = await fetch(parserUrl("/skills", incoming.searchParams), {
      method: "GET",
      cache: "no-store"
    });
    const payload = await response.json().catch(() => ({
      error: "Parser API returned a non-JSON skills response."
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
    const response = await fetch(parserUrl("/skills"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store"
    });
    const payload = await response.json().catch(() => ({
      error: "Parser API returned a non-JSON skills response."
    }));
    return Response.json(payload, { status: response.status });
  } catch (error) {
    return Response.json(
      { error: `Unable to reach parser API: ${error.message}` },
      { status: 500 }
    );
  }
}
