/// <reference types="vite/client" />
import type { JobResult } from "./api";

export const demoMode = import.meta.env.VITE_DEMO === "1";
export const sampleDocument =
  "O candidato deverá interpor recurso pelo portal de inscrições em até dois dias úteis após a publicação do resultado preliminar.";

export const sampleResult: JobResult = {
  summary: "Si no estás de acuerdo con el resultado preliminar, puedes pedir que lo revisen.",
  document: "La persona candidata deberá presentar un recurso a través del portal de inscripciones dentro de los dos días hábiles siguientes a la publicación del resultado preliminar.",
  alerts: "Consulta la fecha de publicación y presenta el recurso en el portal dentro del plazo de **dos días hábiles**.",
  glossary: "**Recurso:** solicitud formal para que se revise una decisión.",
};
