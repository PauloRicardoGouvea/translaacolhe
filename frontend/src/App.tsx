/**
 * App.tsx — Fluxo principal do TranslaAcolhe.
 *
 * Estados da aplicação:
 *   idle        → escolhendo arquivo e idioma
 *   processing  → job criado; polling do progresso
 *   done        → resultado exibido em abas
 * Erros (upload inválido, API fora do ar, chave ausente) aparecem em um
 * banner e devolvem a interface ao estado idle.
 */

import { useEffect, useState } from "react";
import type { Job, Language } from "./api";
import { fetchLanguages, pollJob, startTranslation } from "./api";
import { LanguageStamps, ProgressCard, ResultView, UploadZone } from "./components";
import { demoMode, sampleDocument, sampleResult } from "./demo";

type Phase = "idle" | "processing" | "done";

export default function App() {
  const [languages, setLanguages] = useState<Language[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [language, setLanguage] = useState<string | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Carrega os idiomas do backend na inicialização.
  useEffect(() => {
    if (demoMode) return;
    fetchLanguages()
      .then(setLanguages)
      .catch(() =>
        setError(
          "Não foi possível conectar ao servidor. Verifique se o backend está rodando (uvicorn main:app --port 8000).",
        ),
      );
  }, []);

  async function handleTranslate() {
    if (!file || !language) return;
    setError(null);
    setPhase("processing");
    try {
      const jobId = await startTranslation(file, language);
      const finished = await pollJob(jobId, setJob);
      if (finished.status === "error") {
        setError(finished.error ?? "Erro desconhecido durante a tradução.");
        setPhase("idle");
      } else {
        setPhase("done");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro inesperado.");
      setPhase("idle");
    }
  }

  function showSample() {
    setJob({
      id: "exemplo",
      filename: "edital-ficticio.txt",
      language: "Espanhol",
      status: "done",
      progress: 1,
      message: "Exemplo disponível",
      error: null,
      result: sampleResult,
    });
    setPhase("done");
  }

  function reset() {
    setFile(null);
    setJob(null);
    setPhase("idle");
    setError(null);
  }

  const busy = phase === "processing";

  return (
    <main className="page">
      <header className="masthead">
        <div className="eyebrow">Tradutor social de documentos oficiais</div>
        <h1>
          Transla<span className="accent">Acolhe</span>
        </h1>
        <p className="welcome-line">
          {demoMode
            ? "Veja como o TranslaAcolhe apresenta a tradução de um edital, com resumo, prazos e glossário."
            : "Envie um edital, cartilha ou formulário brasileiro e receba a tradução simplificada no seu idioma, com resumo, prazos importantes e explicação dos termos burocráticos."}
        </p>
        <p className="welcome-langs">
          Bem-vindo(a) · Bienvenido/a · Byenveni · Bienvenue · أهلاً وسهلاً · Welcome
        </p>
      </header>

      {error && (
        <div className="error-box" role="alert">
          <strong>Algo deu errado</strong>
          {error}
        </div>
      )}

      {demoMode && (
        <section className="card" aria-labelledby="sample-heading">
          <div className="step-label" id="sample-heading">Demonstração · edital fictício</div>
          <p>Explore um exemplo preparado em espanhol. Nesta versão online, o exemplo é fixo e nenhum arquivo é enviado.</p>
          <blockquote>{sampleDocument}</blockquote>
          {phase !== "done" && (
            <button type="button" className="btn-primary" onClick={showSample}>
              Ver tradução do exemplo
            </button>
          )}
        </section>
      )}

      {!demoMode && phase !== "done" && (
        <>
          <section className="card">
            <div className="step-label">1 · Envie o documento</div>
            <UploadZone file={file} onSelect={setFile} disabled={busy} />
          </section>

          <section className="card">
            <div className="step-label">2 · Escolha o idioma de destino</div>
            <LanguageStamps
              languages={languages}
              selected={language}
              onSelect={setLanguage}
              disabled={busy}
            />
          </section>

          {!busy && (
            <button
              type="button"
              className="btn-primary"
              disabled={!file || !language}
              onClick={handleTranslate}
            >
              Traduzir e simplificar documento
            </button>
          )}
        </>
      )}

      {busy && job && <ProgressCard job={job} />}

      {phase === "done" && job?.result && (
        <>
          <ResultView jobId={job.id} result={job.result} demo={demoMode} />
          <button type="button" className="btn-primary" onClick={reset}>
            {demoMode ? "Voltar ao exemplo" : "Traduzir outro documento"}
          </button>
        </>
      )}

      <footer className="footer">
        {demoMode && <p><a href="/projeto.html">Sobre o projeto TranslaAcolhe</a></p>}
        ⚖️ O TranslaAcolhe é uma ferramenta de apoio e não substitui orientação
        jurídica. Para ajuda gratuita, procure a <strong>DPU</strong> (Defensoria
        Pública da União) ou o <strong>CRAS</strong> mais próximo.
      </footer>
    </main>
  );
}
