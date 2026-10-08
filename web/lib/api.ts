import type { ModelSelection, ModelsResponse, Role, StreamMeta } from "@/lib/types";

/**
 * Requests go to `/api/*` on the same origin; `next.config.ts` rewrites them to
 * the FastAPI server (API_URL), so the browser never needs CORS.
 */
const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api";

export interface VoiceToken {
  server_url: string;
  participant_token: string;
  room_name: string;
}

export async function createVoiceToken(): Promise<VoiceToken> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/voice/token`, { method: "POST", cache: "no-store" });
  } catch {
    throw new ApiError("Can't reach the API server. Make sure it is running.");
  }
  if (!res.ok) throw new ApiError(await errorMessage(res), res.status);
  return (await res.json()) as VoiceToken;
}

export interface UserProfile {
  id: string;
  name: string;
  email: string;
}

/** GET /api/me fetches the current signed-in user's profile. */
export async function fetchUserProfile(): Promise<UserProfile> {
  const res = await fetch(`${API_BASE}/me`, { cache: "no-store" });
  if (!res.ok) throw new ApiError(await errorMessage(res), res.status);
  return (await res.json()) as UserProfile;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function errorMessage(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail) && body.detail[0]?.msg) return String(body.detail[0].msg);
  } catch {
    /* not JSON */
  }
  return `HTTP ${res.status}: Request failed with no detail message.`;
}

export async function fetchModels(refresh = false, signal?: AbortSignal): Promise<ModelsResponse> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/models${refresh ? "?refresh=true" : ""}`, {
      cache: "no-store",
      signal,
    });
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err;
    throw new ApiError("Can't reach the AI server. Make sure the API is running.");
  }
  if (!res.ok) throw new ApiError(await errorMessage(res), res.status);
  return (await res.json()) as ModelsResponse;
}

export interface UploadResponse {
  filename: string;
  text: string;
  truncated: boolean;
  session_id?: string | null;
  retrieval?: boolean;
}

/** POST /api/upload handles document text extraction. */
export async function uploadFile(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  let res: Response;
  try {
    res = await fetch(`${API_BASE}/upload`, {
      method: "POST",
      body: formData,
      cache: "no-store",
    });
  } catch {
    throw new ApiError("Network error: couldn't connect to the API server. Check that it is running and reachable.");
  }

  console.log("File upload response status:", res.status);
  if (!res.ok) {
    const detail = await errorMessage(res);
    const reason = res.status === 413
      ? detail
      : res.status === 415
        ? `Unsupported file type. ${detail}`
        : detail.startsWith("HTTP ")
          ? detail
          : `HTTP ${res.status}: ${detail}`;
    throw new ApiError(reason, res.status);
  }
  return (await res.json()) as UploadResponse;
}

export interface StreamChatOptions {
  messages: { role: Role; content: string; images?: string[] }[];
  selection: ModelSelection;
  signal: AbortSignal;
  onMeta: (meta: StreamMeta) => void;
  onDelta: (text: string) => void;
  fileContext?: { filename: string; text: string; session_id?: string; retrieval?: boolean };
}

/** POST /api/chat and parse the server-sent event stream. */
export async function streamChat({
  messages,
  selection,
  signal,
  onMeta,
  onDelta,
  fileContext,
}: StreamChatOptions): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({
        messages,
        provider: selection?.provider ?? null,
        model: selection?.model ?? null,
        file_context: fileContext
          ? {
              filename: fileContext.filename,
              text: fileContext.text,
              session_id: fileContext.session_id,
              retrieval: fileContext.retrieval ?? false,
            }
          : null,
      }),
      signal,
    });
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err;
    throw new ApiError("Can't reach the AI server. Make sure the API is running.");
  }
  if (!res.ok) throw new ApiError(await errorMessage(res), res.status);
  if (!res.body) throw new ApiError("The server returned an empty response.");

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  let finished = false;

  const handle = (block: string) => {
    let event = "message";
    const data: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
    }
    if (!data.length) return;
    const payload = JSON.parse(data.join("\n")) as Record<string, unknown>;
    switch (event) {
      case "meta":
        onMeta(payload as unknown as StreamMeta);
        break;
      case "error":
        throw new ApiError(String(payload.message ?? "Something went wrong."));
      case "done":
        finished = true;
        break;
      default:
        if (typeof payload.delta === "string") onDelta(payload.delta);
    }
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value.replace(/\r\n/g, "\n");
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      handle(block);
    }
  }
  if (buffer.trim()) handle(buffer);
  if (!finished) throw new ApiError("The connection closed before the reply finished.");
}
