from __future__ import annotations

import argparse
import sys

from search import (
    ask_ollama,
    build_confidence_summary,
    dedupe_hits,
    format_source_block,
    has_sufficient_comparison_evidence,
    has_sufficient_evidence,
    is_comparison_query,
    rerank_hits,
    search_documents,
)


SYSTEM_RULES = """
Responde únicamente con base en la evidencia suministrada.
- responde en español
- sé claro y concreto
- no inventes datos
- separa claramente:
  - HECHOS ENCONTRADOS
  - INFERENCIAS DEL MODELO
- en HECHOS ENCONTRADOS, apóyate solo en texto visible de las fuentes
- en INFERENCIAS DEL MODELO, aclara que son inferencias y no hechos literales
- si no hace falta inferir, escribe: Ninguna.
- si la pregunta pide una relación, conexión o vínculo entre entidades:
  - solo responde si la relación aparece explícitamente en los textos
  - no deduzcas relación por contexto general o por coexistencia en la misma plataforma
- cuando compares Olympia y GIG-OS:
  - cita cada plataforma por separado
  - no afirmes diferencias o similitudes si no hay evidencia textual para cada lado
  - si una plataforma no tiene evidencia suficiente, dilo explícitamente
""".strip()


def build_prompt(question: str, hits: list[dict]) -> str:
    evidence_blocks = []
    for idx, hit in enumerate(hits, start=1):
        evidence_blocks.append(f"[Fuente {idx}]\n{format_source_block(hit)}")
    evidence = "\n\n".join(evidence_blocks)
    return (
        f"{SYSTEM_RULES}\n\n"
        f"Pregunta:\n{question}\n\n"
        f"Evidencia:\n{evidence}\n\n"
        "Formato obligatorio de salida:\n"
        "HECHOS ENCONTRADOS:\n"
        "- ...\n\n"
        "INFERENCIAS DEL MODELO:\n"
        "- ...\n\n"
        "Respuesta:"
    )


def insufficient_message(question: str) -> str:
    if is_comparison_query(question):
        return "No encontré evidencia suficiente en la base documental para responder esa comparación."
    return "No encontré información suficiente en la base documental."


def answer_question(question: str, debug: bool = False) -> None:
    initial_hits = search_documents(question, top_k=8)
    hits = dedupe_hits(rerank_hits(question, initial_hits, final_k=4))
    comparison_query = is_comparison_query(question)
    if comparison_query:
        enough_evidence = has_sufficient_comparison_evidence(question, hits)
    else:
        enough_evidence = has_sufficient_evidence(question, hits)

    confidence = build_confidence_summary(question, hits)

    if debug:
        print("\nDEBUG\n")
        for index, hit in enumerate(hits, start=1):
            meta = hit["metadata"]
            print(
                f"{index}. score={hit.get('rerank_score', '')} "
                f"distance={hit.get('distance', '')} "
                f"entity={hit.get('entity_present', '')} "
                f"relation={hit.get('relation_present', '')} "
                f"title={meta.get('title', '')}"
            )
        print(
            f"confidence_score={confidence['score']} "
            f"entity_hits={confidence['entity_hits']} "
            f"dual_entity_hits={confidence.get('dual_entity_hits', 0)} "
            f"avg_distance={confidence['average_distance']} "
            f"entities={confidence['entities']} "
            f"relation_left={confidence.get('relation_left', [])} "
            f"relation_right={confidence.get('relation_right', [])}\n"
        )

    if not hits or not enough_evidence:
        print(f"\nCONFIDENCE: {confidence['label']}\n")
        print(f"{insufficient_message(question)}\n")
        return

    prompt = build_prompt(question, hits)
    try:
        answer = ask_ollama(prompt).strip()
    except Exception:
        answer = ""
    if not answer:
        answer = insufficient_message(question)

    print(f"\nCONFIDENCE: {confidence['label']}\n")
    print("\nRespuesta\n")
    print(answer)
    print("\nFuentes\n")
    for hit in hits:
        meta = hit["metadata"]
        print(f"- Plataforma: {meta.get('platform', '')}")
        print(f"  Título: {meta.get('title', '')}")
        print(f"  Fecha: {meta.get('date', '')}")
        print(f"  URL: {meta.get('source_url', '')}")
    print("")


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true", help="Muestra títulos recuperados y score final.")
    parser.add_argument("question", nargs="*", help="Pregunta opcional en una sola línea.")
    args = parser.parse_args()

    if args.question:
        answer_question(" ".join(args.question).strip(), debug=args.debug)
        return

    print("Consulta local LOI_AI")
    print("Escribí tu pregunta y presioná Enter. Vacío para salir.\n")

    while True:
        question = input("> ").strip()
        if not question:
            break
        answer_question(question, debug=args.debug)


if __name__ == "__main__":
    main()
