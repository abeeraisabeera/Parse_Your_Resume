export const runtime = "nodejs";

const PARSER_API_URL =
  process.env.PARSER_API_URL || "http://127.0.0.1:8000/parse";
const PARSER_BATCH_API_URL =
  process.env.PARSER_BATCH_API_URL ||
  PARSER_API_URL.replace(/\/parse\/?$/, "/parse-batch");

function collectFiles(formData) {
  const explicitFiles = formData
    .getAll("files")
    .filter((entry) => entry instanceof File);

  if (explicitFiles.length) {
    return explicitFiles;
  }

  const single = formData.get("file");
  return single instanceof File ? [single] : [];
}

export async function POST(request) {
  try {
    const incoming = await request.formData();
    const files = collectFiles(incoming);

    if (!files.length) {
      return Response.json(
        { error: "At least one PDF file is required." },
        { status: 400 }
      );
    }

    const outbound = new FormData();
    outbound.append("use_llm", incoming.get("use_llm") ?? "true");
    outbound.append("model", incoming.get("model") ?? "llama-3.1-8b-instant");
    outbound.append("max_retries", incoming.get("max_retries") ?? "6");

    const isBatch = files.length > 1;
    if (isBatch) {
      files.forEach((file) => outbound.append("files", file, file.name));
    } else {
      outbound.append("file", files[0], files[0].name);
    }

    const response = await fetch(isBatch ? PARSER_BATCH_API_URL : PARSER_API_URL, {
      method: "POST",
      body: outbound,
      cache: "no-store"
    });

    const payload = await response.json().catch(() => ({
      error: "Parser API returned a non-JSON response."
    }));

    if (!response.ok) {
      const message = payload.detail || payload.error || "Failed to parse resume.";
      return Response.json({ error: message }, { status: response.status });
    }

    return Response.json(payload);
  } catch (error) {
    return Response.json(
      { error: `Unable to reach parser API: ${error.message}` },
      { status: 500 }
    );
  }
}
