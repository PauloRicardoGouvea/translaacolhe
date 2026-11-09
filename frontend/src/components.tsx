/**
 * components.tsx — Componentes de interface do TranslaAcolhe.
 *
 * UploadZone      — dropzone acessível (clique, teclado e arrastar/soltar)
 * LanguageStamps  — seletor de idiomas em forma de carimbos de passaporte
 * ProgressCard    — barra de progresso alimentada pelo polling do job
 * ResultView      — abas (Resumo / Documento / Alertas / Glossário) + downloads
 */

import { useCallback, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Job, JobResult, Language } from "./api";
import { downloadUrl } from "./api";

const ACCEPTED = ".pdf,.docx,.txt,.xml";

/* ------------------------------ UploadZone ------------------------------ */
interface UploadZoneProps {
  file: File | null;
  onSelect: (file: File | null) => void;
  disabled: boolean;
}

export function UploadZone({ file, onSelect, disabled }: UploadZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const pick = useCallback(
    (list: FileList | null) => {
      const chosen = list?.[0] ?? null;
      if (chosen) onSelect(chosen);
    },
    [onSelect],
  );

  if (file) {
    return (
      <div className="file-chip">
        <span aria-hidden>📄</span>
        <span className="name">{file.name}</span>
        <button
          type="button"
          aria-label="Remover arquivo"
          onClick={() => onSelect(null)}
          disabled={disabled}
        >
          ✕
        </button>
      </div>
    );
  }

  return (
    <div
      className={`dropzone${dragging ? " dragging" : ""}`}
      role="button"
      tabIndex={0}
      aria-label="Enviar documento: PDF, DOCX, TXT ou XML"
      onClick={() => inputRef.current?.click()}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
      }}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        pick(e.dataTransfer.files);
      }}
    >
      <p className="dz-title">Arraste seu documento aqui</p>
      <p className="dz-hint">ou clique para escolher no seu aparelho</p>
      <p className="dz-formats">PDF · DOCX · TXT · XML — até 25 MB</p>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED}
        hidden
        onChange={(e) => pick(e.target.files)}
      />
    </div>
  );
}

/* ---------------------------- LanguageStamps ---------------------------- */
interface LanguageStampsProps {
  languages: Language[];
  selected: string | null;
  onSelect: (label: string) => void;
  disabled: boolean;
}

export function LanguageStamps({ languages, selected, onSelect, disabled }: LanguageStampsProps) {
  const current = languages.find((l) => l.label === selected);
  return (
    <>
      <div className="stamps" role="radiogroup" aria-label="Idioma de destino">
        {languages.map((lang) => (
          <button
            key={lang.label}
            type="button"
            role="radio"
            aria-checked={lang.label === selected}
            className={`stamp${lang.label === selected ? " selected" : ""}`}
            onClick={() => onSelect(lang.label)}
            disabled={disabled}
          >
            {lang.label === selected && <span className="check" aria-hidden>✓</span>}
            {lang.label}
          </button>
        ))}
      </div>
      <p className="stamp-description">{current ? current.description : "\u00a0"}</p>
    </>
  );
}

/* ------------------------------ ProgressCard ----------------------------- */
export function ProgressCard({ job }: { job: Job }) {
  const percent = Math.round(job.progress * 100);
  return (
    <section className="card progress-card" aria-live="polite">
      <div className="step-label">Processando documento</div>
      <div
        className="progress-track"
        role="progressbar"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div className="progress-fill" style={{ width: `${Math.max(percent, 4)}%` }} />
      </div>
      <p className="progress-message">
        {job.message} · {percent}%
      </p>
    </section>
  );
}

/* -------------------------------- ResultView ----------------------------- */
type TabKey = "summary" | "document" | "alerts" | "glossary";

const TABS: { key: TabKey; label: string; alert?: boolean }[] = [
  { key: "summary", label: "Resumo" },
  { key: "document", label: "Documento traduzido" },
  { key: "alerts", label: "⚠️ Prazos e alertas", alert: true },
  { key: "glossary", label: "Glossário" },
];

export function ResultView({ jobId, result, demo = false }: { jobId: string; result: JobResult; demo?: boolean }) {
  const [tab, setTab] = useState<TabKey>("summary");

  const content: Record<TabKey, string> = {
    summary: result.summary || "_Resumo não disponível._",
    document: result.document,
    alerts: result.alerts || "_Nenhum prazo ou cronograma foi identificado neste documento._",
    glossary: result.glossary || "_Nenhum termo crítico identificado._",
  };

  return (
    <section className="card">
      <div className="result-header">
        <div className="step-label" style={{ marginBottom: 0 }}>
          {demo ? "Resultado ilustrativo" : "Documento processado"}
        </div>
        <div className="approval-stamp" aria-hidden>
          {demo ? "Exemplo" : "✓ Traduzido"}
        </div>
      </div>

      <div className="tabs" role="tablist">
        {TABS.map(({ key, label, alert }) => (
          <button
            key={key}
            role="tab"
            aria-selected={tab === key}
            className={`tab${alert ? " alert-tab" : ""}${tab === key ? " active" : ""}`}
            onClick={() => setTab(key)}
          >
            {label}
          </button>
        ))}
      </div>

      {/* dir="auto" garante direção correta para árabe (RTL) */}
      <div className="tab-panel" role="tabpanel" dir="auto">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content[tab]}</ReactMarkdown>
        {!demo && tab === "alerts" && result.alerts && (
          <div className="alert-banner">
            <span aria-hidden>⏰</span>
            <span>
              Atenção: prazos de <strong>recurso</strong> e <strong>isenção de taxa</strong> em
              editais brasileiros costumam durar apenas 2 a 3 dias úteis.
            </span>
          </div>
        )}
      </div>

      <div className="downloads">
        <a className="btn-download" href={demo ? "/exemplo.txt" : downloadUrl(jobId, "txt")} download>
          ⬇ Baixar como TXT
        </a>
        <a className="btn-download" href={demo ? "/exemplo.docx" : downloadUrl(jobId, "docx")} download>
          ⬇ Baixar como DOCX (Word)
        </a>
      </div>
    </section>
  );
}
