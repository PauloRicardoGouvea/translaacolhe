"""
knowledge_base.py — Carrega a base de conhecimento jurídico-burocrática.

Os arquivos .txt na pasta `knowledge/` (glossário de editais, guia de siglas,
guia do CadÚnico/isenção, guia de revalidação de diplomas e mapa estrutural
de editais) são concatenados e injetados no SYSTEM PROMPT de cada chamada,
garantindo acurácia na tradução/explicação dos termos.

Estratégia de fallback: se a pasta não existir (ex.: deploy incompleto no
Streamlit Cloud), usa-se a versão compacta embutida em _EMBEDDED_FALLBACK,
para que o sistema nunca rode "cego" de conhecimento.
"""

from __future__ import annotations

from functools import lru_cache

from config import KNOWLEDGE_DIR

# Versão mínima embutida — resumo dos pontos mais críticos dos guias.
_EMBEDDED_FALLBACK = """
GLOSSÁRIO ESSENCIAL DE EDITAIS:
- Deferido = aprovado/aceito. Indeferido = negado (exige recurso rápido).
- Homologação = confirmação oficial e final. Retificação = correção do edital.
- Interpor Recurso = contestar formalmente um resultado, em prazo curto
  (geralmente 2 dias úteis por fase).
- Ampla Concorrência = vagas sem cotas. Ações Afirmativas/Cotas = vagas
  reservadas (PPI, PCD, escola pública), com banca de heteroidentificação.
- Hipossuficiência financeira = baixa renda (base para isenção de taxa).

SIGLAS-CHAVE PARA IMIGRANTES:
- RNM = documento de identidade do imigrante (antigo RNE). DPRF = protocolo
  provisório do solicitante de refúgio. CPF = número essencial para tudo.
- CadÚnico = cadastro de baixa renda (feito no CRAS) que gera o NIS,
  usado para pedir ISENÇÃO DE TAXA em concursos.
- DPU = defensores públicos gratuitos. CONARE = analisa pedidos de refúgio.
- PF = Polícia Federal, emite o RNM.

ISENÇÃO DE TAXA (Decreto 6.593/2008):
- Requer CadÚnico processado há pelo menos 45 dias e renda per capita de
  até 1/2 salário mínimo. Os dados da inscrição devem ser EXATAMENTE iguais
  aos do CadÚnico (nome, nome da mãe, data de nascimento, CPF) — qualquer
  divergência gera INDEFERIMENTO. Prazo de recurso: 2-3 dias úteis.

DIPLOMAS ESTRANGEIROS:
- Revalidação via Plataforma Carolina Bori (MEC), geralmente exigida até a
  posse. Documentos estrangeiros exigem Apostilamento de Haia (ou legalização
  consular) e Tradução Juramentada. Refugiados reconhecidos pelo CONARE têm
  direito a processos simplificados e isenções humanitárias.
""".strip()


@lru_cache(maxsize=1)
def load_knowledge_base() -> str:
    """
    Lê e concatena todos os .txt da pasta knowledge/, com cache em memória
    (a base é estática durante a execução do app).
    """
    if not KNOWLEDGE_DIR.is_dir():
        return _EMBEDDED_FALLBACK

    sections: list[str] = []
    for path in sorted(KNOWLEDGE_DIR.glob("*.txt")):
        try:
            content = path.read_text(encoding="utf-8").strip()
        except UnicodeDecodeError:
            content = path.read_text(encoding="latin-1").strip()
        if content:
            sections.append(f"===== {path.stem.upper()} =====\n{content}")

    return "\n\n".join(sections) if sections else _EMBEDDED_FALLBACK
