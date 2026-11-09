"""
translator.py — Integração com a API da Anthropic (Claude).

O SYSTEM PROMPT abaixo incorpora integralmente o <system_instructions>
oficial do TranslaAcolhe (role, target_languages, core_rules e
output_format), acrescido da base de conhecimento jurídico-burocrática
e do protocolo de fragmentação (chunking).

Pipeline em duas etapas:
  ETAPA 1 — cada chunk é traduzido em chamada própria (prompt caching na
            base de conhecimento) e devolve tradução + prazos + termos.
  ETAPA 2 — uma síntese final leve consolida Resumo Executivo,
            Alertas/Próximos Passos e Glossário Explicativo.

Ordem do output final (conforme <output_format>):
  1. Resumo Executivo  2. Documento Traduzido
  3. Alertas e Próximos Passos  4. Glossário Explicativo
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

import anthropic

from chunking import Chunk
from config import DEFAULT_MODEL, MAX_OUTPUT_TOKENS, TARGET_LANGUAGES, TEMPERATURE
from knowledge_base import load_knowledge_base

_TRANSLATION_RE = re.compile(r"<traducao>(.*?)</traducao>", re.DOTALL)
_DEADLINES_RE = re.compile(r"<prazos>(.*?)</prazos>", re.DOTALL)
_TERMS_RE = re.compile(r"<termos>(.*?)</termos>", re.DOTALL)


# ---------------------------------------------------------------------------
# SYSTEM PROMPT (persona oficial + base de conhecimento + protocolo de chunk)
# ---------------------------------------------------------------------------
_PERSONA = """<system_instructions>
  <role>
    Você é o "TranslaAcolhe", um tradutor de IA hiper-especializado em documentos oficiais, burocráticos e editais de concursos públicos brasileiros. Seu objetivo principal é apoiar imigrantes e refugiados recém-chegados ao Brasil, traduzindo documentos do português para suas línguas nativas (e vice-versa), garantindo acessibilidade e compreensão de direitos.
  </role>

  <target_languages>
    Foco principal em línguas de fluxos migratórios recentes no Brasil:
    - Espanhol (América Latina/Venezuela/Cuba)
    - Árabe (Oriente Médio/Síria)
    - Francês e Crioulo Haitiano (Haiti/África Ocidental)
    - Inglês (Nigéria/Camarões/África Oriental)
    - Variantes de Português (Angola/Moçambique - foco em adaptar a burocracia brasileira para o entendimento local)
  </target_languages>

  <core_rules>
    1. **Fidelidade e Estrutura:** Mantenha a estrutura original do documento (títulos, subtítulos, numeração de itens de edital). Se o usuário enviar um XML ou DOCX, a resposta deve respeitar as divisões textuais.
    2. **Localização vs. Tradução Literal:** Termos jurídicos brasileiros (ex: "Mandado de Segurança", "Ações Afirmativas", "Impugnação") não devem ser traduzidos literalmente se perderem o sentido. Traduza para o termo equivalente mais próximo e adicione uma nota explicativa.
    3. **Linguagem Acessível:** O público-alvo pode estar em processo de alfabetização na nova língua. Evite termos excessivamente eruditos na língua de destino; seja claro e direto.
    4. **Seção de Notas Burocráticas:** Sempre que traduzir um edital ou documento oficial, crie uma seção no final chamada "Glossário de Termos Importantes" explicando o que os termos críticos significam na prática (ex: explicar que "Inscrição Indeferida" significa que a inscrição foi negada e ele precisa agir).
  </core_rules>

  <output_format>
    Sempre responda estruturando seu output da seguinte forma:
    1. **Resumo Executivo (3 frases):** Do que se trata o documento enviado.
    2. **Documento Traduzido:** O texto completo traduzido e formatado.
    3. **Alertas e Próximos Passos (Se for Edital/Concurso):** Listar datas de prazos e requisitos que o imigrante precisa cumprir imediatamente.
    4. **Glossário Explicativo:** Explicação dos termos jurídicos/burocráticos mais complexos encontrados no texto.
  </output_format>
</system_instructions>"""


def build_system_prompt(target_language_label: str) -> str:
    """Persona oficial + instrução do idioma + base de conhecimento + protocolo."""
    language_instruction = TARGET_LANGUAGES[target_language_label]
    knowledge = load_knowledge_base()

    return f"""{_PERSONA}

IDIOMA DE DESTINO DESTA SESSÃO: {target_language_label}
INSTRUÇÃO LINGUÍSTICA: {language_instruction}

BASE DE CONHECIMENTO JURÍDICO-BUROCRÁTICA (use-a para interpretar e explicar os termos com precisão; nunca invente prazos, valores ou requisitos que não estejam no documento):
{knowledge}

PROTOCOLO DE FRAGMENTAÇÃO: o documento pode chegar dividido em partes ("fragmento i de N") por ser muito longo. O <output_format> completo (Resumo, Alertas, Glossário) será montado pelo sistema ao final — a SUA tarefa em cada fragmento é apenas produzir os três blocos abaixo. Responda EXATAMENTE com eles, nesta ordem, sem nenhum texto fora deles:
<traducao>
[tradução completa do fragmento, mantendo a estrutura original de títulos e numeração]
</traducao>
<prazos>
[uma linha por prazo/data/cronograma encontrado NO FRAGMENTO, formato: "DATA_OU_PERIODO ;; EVENTO ;; ACAO_NECESSARIA". Se não houver, escreva NENHUM]
</prazos>
<termos>
[uma linha por termo burocrático crítico encontrado, formato: "TERMO_ORIGINAL ;; EXPLICACAO_SIMPLES_NO_IDIOMA_DE_DESTINO". Se não houver, escreva NENHUM]
</termos>"""


# ---------------------------------------------------------------------------
# RESULTADO
# ---------------------------------------------------------------------------
@dataclass
class TranslationResult:
    executive_summary: str = ""
    translated_document: str = ""
    alerts_md: str = ""       # Alertas e Próximos Passos (tabela/lista Markdown)
    glossary_md: str = ""
    raw_deadlines: list[str] = field(default_factory=list)
    raw_terms: list[str] = field(default_factory=list)

    def to_full_markdown(self) -> str:
        """Documento final na ordem do <output_format> oficial."""
        parts = [
            "# TranslaAcolhe — Documento Traduzido e Simplificado",
            "## 1. Resumo Executivo",
            self.executive_summary or "_Não disponível._",
            "## 2. Documento Traduzido",
            self.translated_document,
        ]
        if self.alerts_md.strip():
            parts += ["## 3. Alertas e Próximos Passos", self.alerts_md]
        parts += [
            "## 4. Glossário Explicativo",
            self.glossary_md or "_Nenhum termo crítico identificado._",
        ]
        return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# CHAMADAS À API
# ---------------------------------------------------------------------------
def _call_with_retry(client: anthropic.Anthropic, *, max_retries: int = 3, **kwargs):
    """Retry exponencial para erros transitórios (rate limit, 5xx, conexão)."""
    for attempt in range(max_retries + 1):
        try:
            return client.messages.create(**kwargs)
        except (anthropic.RateLimitError, anthropic.APIStatusError, anthropic.APIConnectionError):
            if attempt == max_retries:
                raise
            time.sleep(2 ** attempt * 2)


def _extract_block(pattern: re.Pattern, text: str) -> str:
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def translate_chunk(
    client: anthropic.Anthropic,
    chunk: Chunk,
    system_prompt: str,
    model: str = DEFAULT_MODEL,
) -> tuple[str, list[str], list[str]]:
    """Traduz um fragmento. Retorna (traducao, prazos, termos)."""
    context_note = (
        f"\n\n[CONTEXTO — final do fragmento anterior, APENAS para referência, "
        f"NÃO traduzir de novo]:\n...{chunk.context_tail}"
        if chunk.context_tail
        else ""
    )
    user_message = (
        f"Este é o fragmento {chunk.index} de {chunk.total} do documento. "
        f"Traduza-o integralmente seguindo o protocolo de fragmentação."
        f"{context_note}\n\n[FRAGMENTO A TRADUZIR]:\n{chunk.text}"
    )

    response = _call_with_retry(
        client,
        model=model,
        max_tokens=MAX_OUTPUT_TOKENS,
        temperature=TEMPERATURE,
        system=[{
            "type": "text",
            "text": system_prompt,
            "cache_control": {"type": "ephemeral"},  # cacheia persona + base
        }],
        messages=[{"role": "user", "content": user_message}],
    )
    raw = "".join(b.text for b in response.content if b.type == "text")

    translation = _extract_block(_TRANSLATION_RE, raw) or raw
    deadlines = [
        l.strip() for l in _extract_block(_DEADLINES_RE, raw).splitlines()
        if l.strip() and l.strip().upper() != "NENHUM"
    ]
    terms = [
        l.strip() for l in _extract_block(_TERMS_RE, raw).splitlines()
        if l.strip() and l.strip().upper() != "NENHUM"
    ]
    return translation, deadlines, terms


def synthesize_final_sections(
    client: anthropic.Anthropic,
    *,
    document_head: str,
    deadlines: list[str],
    terms: list[str],
    target_language_label: str,
    model: str = DEFAULT_MODEL,
) -> tuple[str, str, str]:
    """Consolida (resumo, alertas_md, glossario_md) no idioma de destino."""
    language_instruction = TARGET_LANGUAGES[target_language_label]
    deadlines_block = "\n".join(deadlines) if deadlines else "NENHUM PRAZO DETECTADO"
    terms_block = "\n".join(dict.fromkeys(terms)) if terms else "NENHUM TERMO DETECTADO"

    prompt = f"""Consolide as seções finais do relatório TranslaAcolhe, escrevendo TUDO no idioma de destino: {target_language_label} ({language_instruction}). Linguagem simples e acolhedora.

[INÍCIO DO DOCUMENTO ORIGINAL — para contexto]:
{document_head[:6000]}

[PRAZOS COLETADOS — formato DATA ;; EVENTO ;; ACAO]:
{deadlines_block}

[TERMOS BUROCRÁTICOS COLETADOS — formato TERMO ;; EXPLICACAO]:
{terms_block}

Responda EXATAMENTE com estes três blocos:
<resumo>
[Resumo executivo do documento em NO MÁXIMO 3 frases]
</resumo>
<alertas>
[Seção "Alertas e Próximos Passos": tabela Markdown com colunas Data/Período | O que acontece | O que você precisa fazer, em ordem cronológica e sem duplicatas, com ⚠️ nos prazos de recurso e isenção; seguida de uma lista curta de próximos passos imediatos. Se não houver prazos nem ações, escreva apenas: NENHUM]
</alertas>
<glossario>
[Seção "Glossário de Termos Importantes": lista Markdown "- **Termo**: explicação simples e prática". Remova duplicatas e enriqueça com a base de conhecimento burocrática brasileira]
</glossario>"""

    response = _call_with_retry(
        client,
        model=model,
        max_tokens=4000,
        temperature=TEMPERATURE,
        system=_PERSONA,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = "".join(b.text for b in response.content if b.type == "text")

    summary = _extract_block(re.compile(r"<resumo>(.*?)</resumo>", re.DOTALL), raw)
    alerts = _extract_block(re.compile(r"<alertas>(.*?)</alertas>", re.DOTALL), raw)
    glossary = _extract_block(re.compile(r"<glossario>(.*?)</glossario>", re.DOTALL), raw)
    if alerts.strip().upper() == "NENHUM":
        alerts = ""
    return summary, alerts, glossary


# ---------------------------------------------------------------------------
# PIPELINE COMPLETO
# ---------------------------------------------------------------------------
def run_pipeline(
    api_key: str,
    chunks: list[Chunk],
    target_language_label: str,
    model: str = DEFAULT_MODEL,
    progress_callback=None,
) -> TranslationResult:
    """`progress_callback(fraction, message)` alimenta o status do job na API."""
    client = anthropic.Anthropic(api_key=api_key)
    system_prompt = build_system_prompt(target_language_label)

    result = TranslationResult()
    translations: list[str] = []
    total_steps = len(chunks) + 1

    for chunk in chunks:
        if progress_callback:
            progress_callback(
                (chunk.index - 1) / total_steps,
                f"Traduzindo parte {chunk.index} de {chunk.total}",
            )
        translation, deadlines, terms = translate_chunk(client, chunk, system_prompt, model=model)
        translations.append(translation)
        result.raw_deadlines.extend(deadlines)
        result.raw_terms.extend(terms)

    if progress_callback:
        progress_callback(len(chunks) / total_steps, "Consolidando resumo, alertas e glossário")

    summary, alerts, glossary = synthesize_final_sections(
        client,
        document_head=chunks[0].text if chunks else "",
        deadlines=result.raw_deadlines,
        terms=result.raw_terms,
        target_language_label=target_language_label,
        model=model,
    )
    result.executive_summary = summary
    result.alerts_md = alerts
    result.glossary_md = glossary
    result.translated_document = "\n\n".join(translations)

    if progress_callback:
        progress_callback(1.0, "Concluído")
    return result
