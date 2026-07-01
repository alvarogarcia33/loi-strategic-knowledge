from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from datetime import datetime
from time import perf_counter
from typing import Any

import requests

from search import GEN_MODEL, OLLAMA_BASE_URL, build_retrieval_query, dedupe_hits, extract_entity_candidates, extract_query_terms, get_collection, iter_markdown_documents, normalize_for_match, ollama_embed, rerank_hits


INITIAL_TOP_K = 18
FINAL_DOCS = 6
MAX_DOC_CONTEXT_CHARS = 700
COMPACT_FINAL_DOCS = 6
COMPACT_MAX_TIMELINE_EVENTS = 5
COMPACT_MAX_FACTS = 4
COMPACT_MAX_QWEN_CHARS = 14000

PROJECT_PATTERNS = {
    "INTERATUM": ["interatum"],
    "TerritoryX": ["territoryx", "territory x"],
    "Legends of Interactions": ["legends of interactions", "loi"],
    "H-MAP": ["h-map", "h map", "hmap", "h-map system", "h-map.9", "h map 9"],
    "MOG": ["mog", "maestros del juego"],
    "Factory.DroneX": ["factory dronex", "factory.dronex", "factory drone x"],
    "NLT Coin": ["nlt coin", "next level token"],
    "DOMINION Coin": ["dominion coin"],
    "REEX Coin": ["reex coin"],
    "GAME GOS Coin": ["game gos coin", "gos coin"],
    "NETS Coin": ["nets coin"],
    "Olympia": ["olympia", "olympia lab"],
    "GIG-OS": ["gig-os", "gig os", "global intergold"],
    "Intera Wallet": ["ia wallet", "intera wallet", "wallet"],
}

QWEN_ANALYSIS_RULES = """
Actúa como analista estratégico del ecosistema, pero con una restricción estricta:
solo puedes razonar sobre el paquete estructurado recibido.
No puedes inventar hechos nuevos, fechas nuevas ni relaciones nuevas fuera de ese paquete.

Debes diferenciar claramente:
- HECHO
- INFERENCIA
- HIPÓTESIS

Objetivo:
producir una lectura estratégica del material documental, no repetir toda la cronología.

Debes entregar exactamente estas secciones:

LECTURA ESTRATÉGICA GENERAL
- ...

LÓGICA PROBABLE DE LANZAMIENTOS
- ...

SEÑALES DE CAMBIO DE FOCO
- ...

PROYECTOS QUE PARECEN CENTRALES
- ...

PROYECTOS QUE PARECEN SOPORTE O INFRAESTRUCTURA
- ...

POSIBLES TENSIONES O INCONSISTENCIAS
- ...

HIPÓTESIS ALTERNATIVAS
- ...

NIVEL DE CONFIANZA POR HIPÓTESIS
- HIPÓTESIS: ...
  CONFIANZA: HIGH | MEDIUM | LOW
  BASE: ...

INFORMACIÓN PRIVADA O REUNIONES QUE AYUDARÍAN A CONFIRMAR
- ...

Reglas adicionales:
- Si algo no tiene evidencia suficiente, dilo.
- No transformes hipótesis en hechos.
- Cuando menciones una idea importante, apóyala en [F1], [F2], etc., si existe soporte en el paquete.
- Si el paquete no alcanza para una conclusión estratégica fuerte, sé explícito.
""".strip()


def parse_date(date_str: str) -> datetime | None:
    date_str = (date_str or "").strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def detect_projects(text: str) -> list[str]:
    normalized = normalize_for_match(text)
    found: list[str] = []
    for label, aliases in PROJECT_PATTERNS.items():
        for alias in aliases:
            alias_norm = normalize_for_match(alias)
            if alias_norm and alias_norm in normalized:
                found.append(label)
                break
    return found


def load_documents_map() -> dict[str, dict[str, Any]]:
    doc_map: dict[str, dict[str, Any]] = {}
    for item in iter_markdown_documents():
        article_uid = item["meta"].get("article_uid")
        if not article_uid:
            continue
        doc_map[article_uid] = item
    return doc_map


def build_analysis_queries(user_query: str) -> list[str]:
    queries = [user_query]
    normalized = normalize_for_match(user_query)
    entities = extract_entity_candidates(user_query)
    terms = extract_query_terms(user_query)

    if entities:
        queries.append(" ".join(entities[:3]))
        for entity in entities[:3]:
            queries.append(f"evolución cronología {entity}")

    if any(marker in normalized for marker in ["línea de tiempo", "linea de tiempo", "evolución", "evolucion"]):
        queries.append("cronología lanzamientos anuncios roadmap evolución")
    if any(marker in normalized for marker in ["estrategia", "lanzamientos", "lanzamiento"]):
        queries.append("estrategia lanzamientos anuncios fases expansión")
    if any(marker in normalized for marker in ["central", "centrales", "secundario", "secundarios"]):
        queries.append("proyectos centrales secundarios foco ecosistema")
    if terms:
        queries.append(" ".join(terms[:6]))

    unique: list[str] = []
    seen: set[str] = set()
    for query in queries:
        query = query.strip()
        if not query or query in seen:
            continue
        seen.add(query)
        unique.append(query)
    return unique


def retrieve_candidate_hits(user_query: str) -> list[dict[str, Any]]:
    collection = get_collection()
    all_hits: list[dict[str, Any]] = []
    for query in build_analysis_queries(user_query):
        retrieval_query = build_retrieval_query(query)
        query_embedding = ollama_embed([retrieval_query])[0]
        result = collection.query(
            query_embeddings=[query_embedding],
            n_results=INITIAL_TOP_K,
            include=["documents", "metadatas", "distances"],
        )
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        for document, metadata, distance in zip(documents, metadatas, distances):
            all_hits.append(
                {
                    "document": document,
                    "metadata": metadata or {},
                    "distance": distance,
                    "query_used": query,
                }
            )
    return dedupe_hits(all_hits)


def aggregate_documents(user_query: str, hits: list[dict[str, Any]], doc_map: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    reranked_hits = rerank_hits(user_query, hits, final_k=max(18, len(hits)))
    grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {"hits": [], "best_score": -9999.0, "best_distance": 9999.0})

    for hit in reranked_hits:
        article_uid = hit.get("metadata", {}).get("article_uid")
        if not article_uid or article_uid not in doc_map:
            continue
        grouped[article_uid]["hits"].append(hit)
        grouped[article_uid]["best_score"] = max(grouped[article_uid]["best_score"], float(hit.get("rerank_score", -9999.0)))
        grouped[article_uid]["best_distance"] = min(grouped[article_uid]["best_distance"], float(hit.get("distance", 9999.0)))

    documents: list[dict[str, Any]] = []
    entity_candidates = extract_entity_candidates(user_query)
    for article_uid, info in grouped.items():
        item = doc_map[article_uid]
        meta = item["meta"]
        clean_body = item["clean_body"]
        title = meta.get("title", "")
        projects = detect_projects(f"{title}\n{clean_body}")
        date_obj = parse_date(meta.get("date", ""))
        entity_bonus = 0
        searchable = normalize_for_match(f"{title}\n{meta.get('source_url', '')}\n{clean_body}")
        for entity in entity_candidates:
            entity_norm = normalize_for_match(entity)
            if entity_norm and entity_norm in searchable:
                entity_bonus += 8
        recency_bonus = 0
        if date_obj:
            recency_bonus = max(0, date_obj.year - 2020) * 0.2
        project_bonus = min(len(projects), 4) * 0.8
        final_score = info["best_score"] + entity_bonus + recency_bonus + project_bonus + len(info["hits"]) * 1.5
        documents.append(
            {
                "article_uid": article_uid,
                "meta": meta,
                "clean_body": clean_body,
                "projects": projects,
                "date_obj": date_obj,
                "best_distance": info["best_distance"],
                "hits_count": len(info["hits"]),
                "score": round(final_score, 4),
                "supporting_hits": info["hits"],
            }
        )

    documents.sort(
        key=lambda doc: (
            doc["score"],
            doc["hits_count"],
            -float(doc["best_distance"]),
            doc["date_obj"] or datetime.min,
        ),
        reverse=True,
    )
    return documents[:FINAL_DOCS]


def build_timeline_rows(documents: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index, doc in enumerate(sorted(documents, key=lambda d: d["date_obj"] or datetime.min), start=1):
        meta = doc["meta"]
        date_obj = doc["date_obj"]
        date_label = date_obj.strftime("%Y-%m-%d") if date_obj else "sin-fecha"
        project_label = ", ".join(doc["projects"][:3]) if doc["projects"] else "No identificado"
        rows.append(
            {
                "source_id": f"F{index}",
                "date": date_label,
                "platform": meta.get("platform", ""),
                "project": project_label,
                "event": meta.get("title", ""),
                "url": meta.get("source_url", ""),
            }
        )
    return rows


def build_key_timeline_rows(documents: list[dict[str, Any]], max_events: int = COMPACT_MAX_TIMELINE_EVENTS) -> list[dict[str, str]]:
    rows = build_timeline_rows(documents)
    if len(rows) <= max_events:
        return rows

    selected: list[dict[str, str]] = []
    selected.append(rows[0])
    if len(rows) > 2:
        middle = rows[1:-1]
        step = max(1, len(middle) // max(1, max_events - 2))
        selected.extend(middle[::step][: max_events - 2])
    selected.append(rows[-1])

    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in selected:
        key = (row["date"], row["platform"], row["event"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped[:max_events]


def build_sources_registry(documents: list[dict[str, Any]]) -> tuple[list[str], dict[str, str]]:
    docs_sorted = sorted(documents, key=lambda d: d["date_obj"] or datetime.min)
    blocks: list[str] = []
    labels: dict[str, str] = {}
    for index, doc in enumerate(docs_sorted, start=1):
        label = f"F{index}"
        article_uid = doc["article_uid"]
        labels[article_uid] = label
        meta = doc["meta"]
        excerpt = doc["clean_body"][:MAX_DOC_CONTEXT_CHARS].strip()
        if len(doc["clean_body"]) > MAX_DOC_CONTEXT_CHARS:
            excerpt += "\n[extracto truncado]"
        project_label = ", ".join(doc["projects"][:5]) if doc["projects"] else "No identificado"
        block = "\n".join(
            [
                f"[{label}]",
                f"Plataforma: {meta.get('platform', '')}",
                f"Título: {meta.get('title', '')}",
                f"Fecha: {meta.get('date', '')}",
                f"Proyectos detectados: {project_label}",
                f"URL: {meta.get('source_url', '')}",
                "Extracto:",
                excerpt,
            ]
        )
        blocks.append(block)
    return blocks, labels


def build_timeline_text(timeline_rows: list[dict[str, str]]) -> str:
    lines = []
    for row in timeline_rows:
        lines.append(
            f"- {row['date']} | {row['platform']} | {row['project']} | {row['event']} | [{row['source_id']}]"
        )
    return "\n".join(lines)


def first_sentences(text: str, max_sentences: int = 2) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    parts = [part.strip() for part in parts if part.strip()]
    return " ".join(parts[:max_sentences]).strip()


def clean_fact_excerpt(text: str) -> str:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if stripped.lower().startswith(("fecha:", "autor:", "categorías:", "categorias:", "publicado:")):
            continue
        if stripped.startswith(("Categorías", "Categorias")):
            continue
        if stripped.startswith("#"):
            continue
        lines.append(stripped)
    return " ".join(lines[:8]).strip()


def extract_document_fact(doc: dict[str, Any]) -> str:
    meta = doc["meta"]
    summary = first_sentences(clean_fact_excerpt(doc["clean_body"]), max_sentences=2)
    label = meta.get("title", "")
    return (
        f"- {label}: {summary} "
        f"[{meta.get('platform', '')} | {meta.get('date', '')} | {meta.get('source_url', '')}]"
    )


def build_patterns(documents: list[dict[str, Any]]) -> list[str]:
    patterns: list[str] = []
    docs_sorted = sorted(documents, key=lambda d: d["date_obj"] or datetime.min)

    project_dates: dict[str, list[datetime]] = defaultdict(list)
    project_platforms: dict[str, set[str]] = defaultdict(set)
    multi_project_docs = []
    for doc in docs_sorted:
        for project in doc["projects"]:
            if doc["date_obj"]:
                project_dates[project].append(doc["date_obj"])
            project_platforms[project].add(doc["meta"].get("platform", ""))
        if len(doc["projects"]) >= 2:
            multi_project_docs.append(doc)

    for project, dates in sorted(project_dates.items(), key=lambda item: len(item[1]), reverse=True)[:3]:
        first_date = min(dates).strftime("%Y-%m-%d")
        last_date = max(dates).strftime("%Y-%m-%d")
        patterns.append(
            f"- {project} aparece de forma recurrente entre {first_date} y {last_date}, lo que indica continuidad documental del tema. "
            f"[plataformas: {', '.join(sorted(project_platforms[project]))}]"
        )

    if multi_project_docs:
        sample = multi_project_docs[0]
        patterns.append(
            f"- Hay convergencia explícita entre proyectos en documentos que mencionan varios núcleos a la vez, por ejemplo "
            f"\"{sample['meta'].get('title', '')}\" [{sample['meta'].get('platform', '')} | {sample['meta'].get('date', '')} | {sample['meta'].get('source_url', '')}]."
        )

    title_bundle = " ".join(doc["meta"].get("title", "") for doc in docs_sorted)
    title_norm = normalize_for_match(title_bundle)
    if "evolución" in title_norm or "evolucion" in title_norm or "nuevo" in title_norm:
        patterns.append("- La narrativa incluye términos de evolución, integración o novedad, lo que sugiere una secuencia de expansión y refinamiento del ecosistema.")
    if "expansión" in title_norm or "expansion" in title_norm or "global" in title_norm:
        patterns.append("- También aparece una narrativa de expansión/globalización, señal de que los lanzamientos no se presentan solo como productos aislados, sino como parte de una fase de escala.")

    return patterns[:5] or ["- No se detectaron patrones claros con el conjunto recuperado."]


def build_inconsistencies(documents: list[dict[str, Any]]) -> list[str]:
    inconsistencies: list[str] = []
    title_map: dict[str, set[str]] = defaultdict(set)
    for doc in documents:
        title_map[doc["meta"].get("title", "")].add(doc["meta"].get("platform", ""))
    repeated_cross_platform = [title for title, platforms in title_map.items() if len(platforms) > 1]
    if repeated_cross_platform:
        inconsistencies.append(
            f"- Hay títulos o anuncios repetidos entre plataformas, por ejemplo: {', '.join(repeated_cross_platform[:3])}. Conviene revisar si son duplicación narrativa o adaptaciones por plataforma."
        )
    else:
        inconsistencies.append("- No se observan inconsistencias textuales fuertes en el conjunto recuperado; lo que sí aparece es reutilización parcial de narrativa entre plataformas.")
    return inconsistencies


def build_hypotheses(documents: list[dict[str, Any]]) -> list[str]:
    hypotheses: list[str] = []
    all_projects = defaultdict(int)
    for doc in documents:
        for project in doc["projects"]:
            all_projects[project] += 1

    major_projects = [project for project, count in sorted(all_projects.items(), key=lambda item: item[1], reverse=True)[:3]]
    if major_projects:
        hypotheses.append(
            f"- Hipótesis: {', '.join(major_projects)} parecen funcionar como ejes narrativos del ecosistema dentro del subconjunto recuperado, porque concentran más menciones y más cruces con otros proyectos."
        )

    docs_sorted = sorted(documents, key=lambda d: d["date_obj"] or datetime.min)
    if len(docs_sorted) >= 2:
        hypotheses.append(
            "- Hipótesis: la secuencia de anuncios sugiere una lógica de maduración por capas: primero presentación/educación, luego integración de proyectos y finalmente expansión operativa o comercial."
        )
    return hypotheses[:3] or ["- No hay base suficiente para formular hipótesis útiles con el conjunto recuperado."]


def build_missing_information(documents: list[dict[str, Any]], question: str) -> list[str]:
    missing: list[str] = []
    platforms = {doc["meta"].get("platform", "") for doc in documents}
    if len(platforms) < 2 and any(word in normalize_for_match(question) for word in ["diferencia", "ecosistema", "estrategia"]):
        missing.append("- Harían falta más fuentes de la otra plataforma para confirmar si el patrón visto es general del ecosistema o específico de una sola plataforma.")
    missing.append("- Faltan documentos de roadmap interno, fechas de decisión o criterios de priorización para confirmar por qué ciertos lanzamientos ocurrieron exactamente en ese momento.")
    missing.append("- Haría falta evidencia operativa adicional para distinguir entre cambio de narrativa y cambio real de estrategia.")
    return missing[:4]


def build_analysis_report(question: str, documents: list[dict[str, Any]]) -> str:
    timeline_rows = build_timeline_rows(documents)
    facts = [extract_document_fact(doc) for doc in documents[:5]]
    patterns = build_patterns(documents)
    inconsistencies = build_inconsistencies(documents)
    hypotheses = build_hypotheses(documents)
    missing = build_missing_information(documents, question)

    sections = [
        "HECHOS DOCUMENTADOS",
        "\n".join(facts) if facts else "- No se recuperaron hechos suficientes.",
        "",
        "LÍNEA DE TIEMPO",
        build_timeline_text(timeline_rows) if timeline_rows else "- No se pudo construir una línea de tiempo fiable.",
        "",
        "PATRONES DETECTADOS",
        "\n".join(patterns),
        "",
        "POSIBLES INCONSISTENCIAS",
        "\n".join(inconsistencies),
        "",
        "HIPÓTESIS DEL ANALISTA",
        "\n".join(hypotheses),
        "",
        "INFORMACIÓN FALTANTE PARA CONFIRMAR",
        "\n".join(missing),
    ]
    return "\n".join(sections)


def build_compact_deterministic_report(question: str, documents: list[dict[str, Any]]) -> str:
    compact_docs = documents[:COMPACT_FINAL_DOCS]
    timeline_rows = build_key_timeline_rows(compact_docs, max_events=COMPACT_MAX_TIMELINE_EVENTS)
    facts = [extract_document_fact(doc) for doc in compact_docs[:COMPACT_MAX_FACTS]]
    patterns = build_patterns(compact_docs)[:3]
    inconsistencies = build_inconsistencies(compact_docs)[:2]
    hypotheses = build_hypotheses(compact_docs)[:2]
    missing = build_missing_information(compact_docs, question)[:2]

    sections = [
        "HECHOS DOCUMENTADOS",
        "\n".join(facts) if facts else "- No se recuperaron hechos suficientes.",
        "",
        "LÍNEA DE TIEMPO",
        build_timeline_text(timeline_rows) if timeline_rows else "- No se pudo construir una línea de tiempo fiable.",
        "",
        "PATRONES DETECTADOS",
        "\n".join(patterns),
        "",
        "POSIBLES INCONSISTENCIAS",
        "\n".join(inconsistencies),
        "",
        "HIPÓTESIS DEL ANALISTA",
        "\n".join(hypotheses),
        "",
        "INFORMACIÓN FALTANTE PARA CONFIRMAR",
        "\n".join(missing),
    ]
    report = "\n".join(sections)
    return report[:COMPACT_MAX_QWEN_CHARS]


def build_qwen_analysis_prompt(question: str, deterministic_report: str, documents: list[dict[str, Any]], compact: bool = False) -> str:
    _, labels = build_sources_registry(documents)
    concise_sources = []
    docs_for_prompt = documents[:COMPACT_FINAL_DOCS] if compact else documents
    for doc in sorted(docs_for_prompt, key=lambda d: d["date_obj"] or datetime.min):
        meta = doc["meta"]
        label = labels.get(doc["article_uid"], "?")
        concise_sources.append(
            f"[{label}] {meta.get('platform', '')} | {meta.get('date', '')} | {meta.get('title', '')} | {meta.get('source_url', '')}"
        )
    compact_notice = ""
    if compact:
        compact_notice = (
            "Modo compacto activo:\n"
            "- prioriza conclusiones de alto valor\n"
            "- usa solo los eventos clave y los documentos más relevantes\n"
            "- si falta evidencia para una conclusión fuerte, dilo explícitamente\n\n"
        )
    return (
        f"{QWEN_ANALYSIS_RULES}\n\n"
        f"Pregunta analítica original:\n{question}\n\n"
        f"{compact_notice}"
        "Paquete estructurado base:\n"
        f"{deterministic_report}\n\n"
        "Registro breve de fuentes disponibles:\n"
        f"{'\n'.join(concise_sources)}\n\n"
        "Sé sintético y estratégico. No repitas la línea de tiempo completa.\n"
        "Recuerda: solo puedes razonar sobre este paquete. No agregues hechos nuevos."
    )


def run_qwen_strategic_analysis(question: str, deterministic_report: str, documents: list[dict[str, Any]], compact: bool = False) -> str:
    prompt = build_qwen_analysis_prompt(question, deterministic_report, documents, compact=compact)
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": GEN_MODEL,
                "prompt": prompt,
                "stream": False,
                "think": False,
                "options": {
                    "temperature": 0.2,
                    "num_predict": 650 if compact else 900,
                },
            },
            timeout=600,
        )
        response.raise_for_status()
        answer = (response.json().get("response") or "").strip()
    except Exception:
        answer = ""
    return answer


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, round(len(text) / 4))


def print_diagnostics(
    *,
    mode_used: str,
    retrieved_hits: int,
    selected_documents: int,
    sources_used: int,
    qwen_chars: int,
    qwen_tokens_est: int,
    retrieval_seconds: float,
    base_analysis_seconds: float,
    qwen_seconds: float,
    total_seconds: float,
) -> None:
    print("\nDEBUG\n")
    print(f"mode={mode_used}")
    print(f"model={GEN_MODEL}")
    print(f"retrieved_hits={retrieved_hits}")
    print(f"selected_documents={selected_documents}")
    print(f"sources_used={sources_used}")
    print(f"qwen_chars={qwen_chars}")
    print(f"qwen_tokens_est={qwen_tokens_est}")
    print(f"retrieval_seconds={retrieval_seconds:.3f}")
    print(f"base_analysis_seconds={base_analysis_seconds:.3f}")
    print(f"qwen_seconds={qwen_seconds:.3f}")
    print(f"total_seconds={total_seconds:.3f}\n")


def print_sources(documents: list[dict[str, Any]]) -> None:
    print("\nFuentes\n")
    for doc in sorted(documents, key=lambda d: d["date_obj"] or datetime.min):
        meta = doc["meta"]
        print(f"- Plataforma: {meta.get('platform', '')}")
        print(f"  Título: {meta.get('title', '')}")
        print(f"  Fecha: {meta.get('date', '')}")
        print(f"  URL: {meta.get('source_url', '')}")
        print(f"  Score: {doc['score']}")


def analyze_question(question: str, debug: bool = False, use_llm: bool = True, llm_compact: bool = False) -> None:
    total_start = perf_counter()
    doc_map = load_documents_map()

    retrieval_start = perf_counter()
    candidate_hits = retrieve_candidate_hits(question)
    selected_documents = aggregate_documents(question, candidate_hits, doc_map)
    retrieval_seconds = perf_counter() - retrieval_start

    base_start = perf_counter()
    answer = build_analysis_report(question, selected_documents) if selected_documents else ""
    base_analysis_seconds = perf_counter() - base_start

    qwen_seconds = 0.0
    qwen_chars = 0
    qwen_tokens_est = 0
    mode_used = "no-llm" if not use_llm else "llm-compact" if llm_compact else "llm-completo"

    if debug:
        print("\nDEBUG DOCUMENTS\n")
        print(f"candidate_hits={len(candidate_hits)}")
        for index, doc in enumerate(selected_documents, start=1):
            meta = doc["meta"]
            print(
                f"{index}. score={doc['score']} hits={doc['hits_count']} "
                f"distance={doc['best_distance']} title={meta.get('title', '')}"
            )
        print("")

    if not selected_documents:
        total_seconds = perf_counter() - total_start
        if debug:
            print_diagnostics(
                mode_used=mode_used,
                retrieved_hits=len(candidate_hits),
                selected_documents=0,
                sources_used=0,
                qwen_chars=0,
                qwen_tokens_est=0,
                retrieval_seconds=retrieval_seconds,
                base_analysis_seconds=base_analysis_seconds,
                qwen_seconds=0.0,
                total_seconds=total_seconds,
            )
        print("No encontré información suficiente en la base documental para realizar el análisis.")
        return

    print("\nAnálisis\n")
    print(answer)
    if use_llm:
        if llm_compact:
            print('\nModo compacto: análisis más rápido, menor profundidad.\n')
            qwen_base = build_compact_deterministic_report(question, selected_documents)
        else:
            qwen_base = answer
        qwen_chars = len(qwen_base)
        qwen_tokens_est = estimate_tokens(qwen_base)
        qwen_start = perf_counter()
        qwen_analysis = run_qwen_strategic_analysis(question, qwen_base, selected_documents, compact=llm_compact)
        qwen_seconds = perf_counter() - qwen_start
        print("\nANÁLISIS ESTRATÉGICO CON QWEN\n")
        if qwen_analysis:
            print(qwen_analysis)
        else:
            print("No hubo evidencia suficiente o el modelo local no devolvió una lectura estratégica confiable.")
    total_seconds = perf_counter() - total_start
    if debug:
        print_diagnostics(
            mode_used=mode_used,
            retrieved_hits=len(candidate_hits),
            selected_documents=len(selected_documents),
            sources_used=len(selected_documents),
            qwen_chars=qwen_chars,
            qwen_tokens_est=qwen_tokens_est,
            retrieval_seconds=retrieval_seconds,
            base_analysis_seconds=base_analysis_seconds,
            qwen_seconds=qwen_seconds,
            total_seconds=total_seconds,
        )
    print_sources(selected_documents)


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true", help="Muestra documentos seleccionados y score.")
    parser.add_argument("--no-llm", action="store_true", help="Usa solo el análisis determinístico actual.")
    parser.add_argument("--llm-compact", action="store_true", help="Usa una segunda etapa con Qwen más rápida y menos profunda.")
    parser.add_argument("question", nargs="+", help="Pregunta analítica.")
    args = parser.parse_args()

    analyze_question(
        " ".join(args.question).strip(),
        debug=args.debug,
        use_llm=not args.no_llm,
        llm_compact=args.llm_compact and not args.no_llm,
    )


if __name__ == "__main__":
    main()
