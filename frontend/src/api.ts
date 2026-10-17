// Everything the browser knows about the backend. All calls go to /api, which is OUR backend, never the upstream.

export type KeyDate = { label: string; date: string };
export type Editable = { name: string; sector: string; country: string; stage: string; key_dates: KeyDate[] };
export type Project = Editable & { id: string };
export type Summary = { id: string; name: string; sector: string; country: string; stage: string; key_dates_count: number };
export type Options = { sectors: string[]; stages: string[] };

export type Conflict = {
  key: string; // "name" | "key_dates:<label>" | "key_dates"
  kind: "scalar" | "key_date" | "key_dates_list";
  field: string;
  label: string | null;
  base: unknown;
  theirs: unknown;
  mine: unknown;
};

export type SaveResult =
  | { kind: "saved"; project: Project; alsoChangedByOthers: string[] }
  | { kind: "conflict"; current: Project; conflicts: Conflict[]; proposed: Editable };

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string,
    // "no": we know nothing was written. "unknown": a write may have landed. Anything else: not a save problem.
    readonly saved?: string,
  ) {
    super(message);
  }
}

async function request(path: string, init?: RequestInit): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(path, init);
  } catch {
    throw new ApiError("Could not reach the server.", 0, "network");
  }
  return response;
}

async function failure(response: Response): Promise<ApiError> {
  let body: any = null;
  try {
    body = await response.json();
  } catch {
    /* not JSON */
  }
  const detail = body?.message ?? (typeof body?.detail === "string" ? body.detail : undefined);
  return new ApiError(detail ?? `Request failed (${response.status})`, response.status, body?.code, body?.saved);
}

async function json<T>(path: string): Promise<T> {
  const response = await request(path);
  if (!response.ok) throw await failure(response);
  return response.json();
}

export const getOptions = () => json<Options>("/api/options");
export const listProjects = () => json<Summary[]>("/api/projects");
export const getProject = (id: string) => json<Project>(`/api/projects/${encodeURIComponent(id)}`);

/** `base` is the version the person loaded, `edited` what the form holds. The backend merges against the live record. */
export async function saveProject(id: string, base: Editable, edited: Editable): Promise<SaveResult> {
  const response = await request(`/api/projects/${encodeURIComponent(id)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ base, edited }),
  });
  if (response.status === 409) {
    const body = await response.json();
    return { kind: "conflict", current: body.current, conflicts: body.conflicts, proposed: body.proposed };
  }
  if (!response.ok) throw await failure(response);
  const body = await response.json();
  return { kind: "saved", project: body.project, alsoChangedByOthers: body.also_changed_by_others };
}
