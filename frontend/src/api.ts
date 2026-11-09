/**
 * api.ts — Cliente HTTP tipado do backend TranslaAcolhe.
 *
 * Em desenvolvimento, o Vite faz proxy de /api → http://localhost:8000.
 * Em produção, sirva o build do frontend atrás do mesmo domínio da API
 * (ou ajuste BASE_URL).
 */

const BASE_URL = "/api";

export interface Language {
  label: string;
  description: string;
}

export type JobStatus = "queued" | "extracting" | "translating" | "done" | "error";

export interface JobResult {
  summary: string;
  document: string;
  alerts: string;
  glossary: string;
}

export interface Job {
  id: string;
  filename: string;
  language: string;
  status: JobStatus;
  progress: number; // 0 → 1
  message: string;
  error: string | null;
  result?: JobResult;
}

async function handle<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = `Erro ${response.status}`;
    try {
      const body = await response.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* corpo não-JSON — mantém mensagem padrão */
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export async function fetchLanguages(): Promise<Language[]> {
  return handle<Language[]>(await fetch(`${BASE_URL}/languages`));
}

export async function startTranslation(file: File, language: string): Promise<string> {
  const form = new FormData();
  form.append("file", file);
  form.append("language", language);
  const data = await handle<{ job_id: string }>(
    await fetch(`${BASE_URL}/translate`, { method: "POST", body: form }),
  );
  return data.job_id;
}

export async function fetchJob(jobId: string): Promise<Job> {
  return handle<Job>(await fetch(`${BASE_URL}/jobs/${jobId}`));
}

/**
 * Faz polling do job a cada 1,5s até "done" ou "error".
 * `onUpdate` alimenta a UI de progresso a cada resposta.
 */
export async function pollJob(
  jobId: string,
  onUpdate: (job: Job) => void,
  intervalMs = 1500,
): Promise<Job> {
  for (;;) {
    const job = await fetchJob(jobId);
    onUpdate(job);
    if (job.status === "done" || job.status === "error") return job;
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
}

export function downloadUrl(jobId: string, format: "txt" | "docx"): string {
  return `${BASE_URL}/jobs/${jobId}/download?format=${format}`;
}
