from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import chromadb
import requests


BASE_DIR = Path(r"C:\Users\alvar\Documents\LOI_AI")
IA_DIR = BASE_DIR / "07_IA"
MANIFESTS_DIR = IA_DIR / "manifests"
CHROMA_DIR = IA_DIR / "chroma"
COLLECTION_NAME = "loi_ai_articles_v1"
OLLAMA_BASE_URL = "http://127.0.0.1:11434"
EMBED_MODEL = "nomic-embed-text:latest"
GEN_MODEL = "qwen3:8b"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
TOP_K = 10
FINAL_K = 4

MARKDOWN_SOURCES = [
    ("olympia", BASE_DIR / "01_Olympia" / "markdown"),
    ("gig_os", BASE_DIR / "02_GIG_OS" / "markdown"),
]


def ensure_dirs() -> None:
    IA_DIR.mkdir(parents=True, exist_ok=True)
    MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)


def get_collection():
    ensure_dirs()
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"description": "Articulos Olympia + GIG-OS para consulta local"},
    )


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        return {}, text

    raw_meta = parts[0].splitlines()[1:]
    body = parts[1]
    meta: dict[str, str] = {}
    for line in raw_meta:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip().strip('"')
    return meta, body


def remove_images_section(text: str) -> str:
    return re.sub(r"\n## Imágenes\n.*$", "\n", text, flags=re.DOTALL)


def remove_related_news(text: str) -> str:
    text = re.sub(r"\nNoticias relacionadas\n.*?(?=\n## |\Z)", "\n", text, flags=re.DOTALL)
    return re.sub(r"\nMás información\s*\n", "\n", text)


def remove_boilerplate(text: str) -> str:
    boilerplate_patterns = [
        r"\nAСТUAR\s*\n",
        r"\nACTUAR\s*\n",
        r"\nPublicado:\s*[^\n]+\n(?=\s*$)",
    ]
    for pattern in boilerplate_patterns:
        text = re.sub(pattern, "\n", text, flags=re.IGNORECASE)
    return text


def normalize_whitespace(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    collapsed = []
    last_blank = False
    for line in lines:
        is_blank = not line
        if is_blank and last_blank:
            continue
        collapsed.append(line)
        last_blank = is_blank
    return "\n".join(collapsed).strip()


def clean_article_body(body: str) -> str:
    text = body
    text = remove_images_section(text)
    text = remove_related_news(text)
    text = remove_boilerplate(text)
    return normalize_whitespace(text)


def build_chunk_text(meta: dict[str, str], clean_body: str) -> str:
    header_lines = [
        f"Título: {meta.get('title', '')}",
        f"Plataforma: {meta.get('platform', '')}",
        f"Fecha: {meta.get('date', '')}",
    ]
    if meta.get("author"):
        header_lines.append(f"Autor: {meta['author']}")
    if meta.get("categories"):
        header_lines.append(f"Categorías: {meta['categories']}")
    header = "\n".join(line for line in header_lines if line.strip())
    return normalize_whitespace(f"{header}\n\n{clean_body}")


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    if len(text) <= size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        candidate = text[start:end]
        if end < len(text):
            split_at = max(
                candidate.rfind("\n\n"),
                candidate.rfind(". "),
                candidate.rfind("\n"),
                candidate.rfind(" "),
            )
            if split_at > int(size * 0.55):
                end = start + split_at + 1
                candidate = text[start:end]
        chunks.append(candidate.strip())
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return [chunk for chunk in chunks if chunk]


def iter_markdown_documents() -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for platform_name, directory in MARKDOWN_SOURCES:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.md")):
            raw = path.read_text(encoding="utf-8", errors="ignore")
            meta, body = parse_front_matter(raw)
            meta.setdefault("platform", platform_name)
            meta.setdefault("title", path.stem)
            meta.setdefault("source_url", "")
            meta.setdefault("date", "")
            meta.setdefault("article_uid", path.stem)
            clean_body = clean_article_body(body)
            if len(clean_body) < 40:
                continue
            documents.append(
                {
                    "path": path,
                    "meta": meta,
                    "clean_body": clean_body,
                    "chunk_source_text": build_chunk_text(meta, clean_body),
                }
            )
    return documents


def ollama_embed(texts: list[str], model: str = EMBED_MODEL) -> list[list[float]]:
    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/embed",
        json={"model": model, "input": texts},
        timeout=240,
    )
    response.raise_for_status()
    data = response.json()
    embeddings = data.get("embeddings")
    if not embeddings:
        raise RuntimeError("Ollama no devolvió embeddings.")
    return embeddings


def ask_ollama(prompt: str, model: str = GEN_MODEL) -> str:
    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False, "think": False},
        timeout=600,
    )
    response.raise_for_status()
    data = response.json()
    return (data.get("response") or "").strip()


def build_manifest_payload(total_documents: int, total_chunks: int) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "collection_name": COLLECTION_NAME,
        "embedding_model": EMBED_MODEL,
        "generation_model": GEN_MODEL,
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "total_documents": total_documents,
        "total_chunks": total_chunks,
        "sources": [str(path) for _, path in MARKDOWN_SOURCES],
    }


def write_manifest(payload: dict[str, Any]) -> Path:
    ensure_dirs()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = MANIFESTS_DIR / f"index_manifest_{timestamp}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def build_retrieval_query(query: str) -> str:
    left_relation_entities, right_relation_entities = extract_relation_entities(query)
    if left_relation_entities and right_relation_entities:
        return (
            f"relación explícita entre {left_relation_entities[0]} y {right_relation_entities[0]} "
            f"conexión vínculo texto directo"
        )
    return query


def relation_supplemental_hits(collection, left_entities: list[str], right_entities: list[str], limit: int = 6) -> list[dict[str, Any]]:
    if not left_entities or not right_entities:
        return []

    result = collection.get(include=["documents", "metadatas"])
    documents = result.get("documents", [])
    metadatas = result.get("metadatas", [])
    ids = result.get("ids", [])

    supplemental: list[dict[str, Any]] = []
    for doc_id, document, metadata in zip(ids, documents, metadatas):
        hit = {
            "id": doc_id,
            "document": document,
            "metadata": metadata or {},
            "distance": 0.05,
        }
        if both_relation_entities_present(hit, left_entities, right_entities):
            supplemental.append(hit)
        if len(supplemental) >= limit:
            break
    return supplemental


def search_documents(query: str, top_k: int = TOP_K) -> list[dict[str, Any]]:
    collection = get_collection()
    if collection.count() == 0:
        return []

    retrieval_query = build_retrieval_query(query)
    query_embedding = ollama_embed([retrieval_query])[0]
    left_relation_entities, right_relation_entities = extract_relation_entities(query)
    result = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]

    hits: list[dict[str, Any]] = []
    for document, metadata, distance in zip(documents, metadatas, distances):
        hits.append(
            {
                "document": document,
                "metadata": metadata or {},
                "distance": distance,
            }
        )
    if left_relation_entities and right_relation_entities:
        hits.extend(relation_supplemental_hits(collection, left_relation_entities, right_relation_entities, limit=6))
    return hits


def normalize_for_match(text: str) -> str:
    return re.sub(r"[^a-z0-9áéíóúñü\s]", " ", text.lower(), flags=re.IGNORECASE)


def extract_query_terms(query: str) -> list[str]:
    stopwords = {
        "que", "qué", "como", "cómo", "cual", "cuál", "cuando", "cuándo", "donde",
        "dónde", "por", "para", "del", "las", "los", "una", "uno", "unos", "unas",
        "con", "sin", "sobre", "entre", "desde", "hasta", "esta", "este", "estos",
        "estas", "hay", "son", "era", "fue", "ser", "es", "en", "el", "la", "de",
        "y", "o", "un", "al",
    }
    terms = []
    for token in normalize_for_match(query).split():
        if len(token) < 3 or token in stopwords:
            continue
        terms.append(token)
    return list(dict.fromkeys(terms))


def extract_entity_candidates(query: str) -> list[str]:
    original = query.strip()
    normalized = normalize_for_match(query)
    left_relation_entities, right_relation_entities = extract_relation_entities(query)
    if left_relation_entities and right_relation_entities:
        merged: list[str] = []
        seen: set[str] = set()
        for item in left_relation_entities + right_relation_entities:
            if item in seen:
                continue
            seen.add(item)
            merged.append(item)
        return merged
    patterns = [
        r"qué se dice sobre\s+(.+)",
        r"que se dice sobre\s+(.+)",
        r"qué es\s+(.+)",
        r"que es\s+(.+)",
        r"qué programas o monedas aparecen vinculados a\s+(.+)",
        r"que programas o monedas aparecen vinculados a\s+(.+)",
        r"qué aparece vinculado a\s+(.+)",
        r"que aparece vinculado a\s+(.+)",
        r"sobre\s+(.+)",
    ]
    entity = ""
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            entity = match.group(1)
            break
    if not entity:
        entity = normalized

    entity = re.sub(r"\?$", "", entity).strip()
    entity = re.sub(
        r"\b(y para qué sirve|y para que sirve|para qué sirve|para que sirve|respecto de.*|respecto a.*).*$",
        "",
        entity,
    ).strip()

    candidates = [entity]
    compact = entity.replace(" ", "")
    dashed = entity.replace(" ", "-")
    dotted = entity.replace(" ", ".")
    if compact != entity:
        candidates.append(compact)
    if dashed != entity:
        candidates.append(dashed)
    if dotted != entity:
        candidates.append(dotted)

    query_terms = extract_query_terms(original)
    if len(query_terms) <= 3:
        joined_terms = " ".join(query_terms).strip()
        if joined_terms:
            candidates.append(joined_terms)

    clean = []
    seen = set()
    for item in candidates:
        item = item.strip()
        if len(item) < 3:
            continue
        if item in seen:
            continue
        seen.add(item)
        clean.append(item)
    return clean


def is_relation_query(query: str) -> bool:
    normalized = normalize_for_match(query)
    return any(
        marker in normalized
        for marker in [
            "relación entre",
            "relacion entre",
            "conexión entre",
            "conexion entre",
            "vínculo entre",
            "vinculo entre",
        ]
    )


def extract_relation_entities(query: str) -> tuple[list[str], list[str]]:
    normalized = normalize_for_match(query)
    patterns = [
        r"relación entre\s+(.+?)\s+e\s+(.+)",
        r"relacion entre\s+(.+?)\s+e\s+(.+)",
        r"relación entre\s+(.+?)\s+y\s+(.+)",
        r"relacion entre\s+(.+?)\s+y\s+(.+)",
        r"conexión entre\s+(.+?)\s+e\s+(.+)",
        r"conexion entre\s+(.+?)\s+e\s+(.+)",
        r"conexión entre\s+(.+?)\s+y\s+(.+)",
        r"conexion entre\s+(.+?)\s+y\s+(.+)",
        r"vínculo entre\s+(.+?)\s+e\s+(.+)",
        r"vinculo entre\s+(.+?)\s+e\s+(.+)",
        r"vínculo entre\s+(.+?)\s+y\s+(.+)",
        r"vinculo entre\s+(.+?)\s+y\s+(.+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            left = match.group(1).strip(" ?.")
            right = match.group(2).strip(" ?.")
            trailing_noise = [
                r"\saparece.*$",
                r"\sexiste.*$",
                r"\sse menciona.*$",
                r"\ssegún.*$",
                r"\sen la base.*$",
                r"\sen los textos.*$",
                r"\sen la documentación.*$",
            ]
            for noise in trailing_noise:
                left = re.sub(noise, "", left).strip()
                right = re.sub(noise, "", right).strip()
            return build_entity_aliases(left), build_entity_aliases(right)
    return [], []


def build_entity_aliases(entity: str) -> list[str]:
    entity = entity.strip()
    if not entity:
        return []
    compact = entity.replace(" ", "")
    dashed = entity.replace(" ", "-")
    dotted = entity.replace(" ", ".")
    variants = [entity, compact, dashed, dotted]
    clean: list[str] = []
    seen: set[str] = set()
    for item in variants:
        item = item.strip()
        if len(item) < 3 or item in seen:
            continue
        seen.add(item)
        clean.append(item)
    return clean


def dedupe_hits(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique_hits: list[dict[str, Any]] = []
    for hit in hits:
        meta = hit.get("metadata", {})
        key = meta.get("article_uid") or meta.get("source_url") or hit.get("document", "")[:120]
        if key in seen:
            continue
        seen.add(key)
        unique_hits.append(hit)
    return unique_hits


def hit_searchable_text(hit: dict[str, Any]) -> str:
    meta = hit.get("metadata", {})
    pieces = [
        meta.get("title", ""),
        meta.get("source_url", ""),
        meta.get("canonical_url", ""),
        meta.get("platform", ""),
        meta.get("date", ""),
        hit.get("document", ""),
    ]
    return normalize_for_match("\n".join(piece for piece in pieces if piece))


def entity_present_in_hit(hit: dict[str, Any], entities: list[str]) -> bool:
    haystack = hit_searchable_text(hit)
    for entity in entities:
        normalized = normalize_for_match(entity)
        compact = normalized.replace(" ", "")
        if normalized and normalized in haystack:
            return True
        if compact and compact in haystack.replace(" ", ""):
            return True
    return False


def both_relation_entities_present(hit: dict[str, Any], left_entities: list[str], right_entities: list[str]) -> bool:
    if not left_entities or not right_entities:
        return False
    return entity_present_in_hit(hit, left_entities) and entity_present_in_hit(hit, right_entities)


def compute_keyword_overlap(hit: dict[str, Any], terms: list[str]) -> int:
    haystack = hit_searchable_text(hit)
    return sum(1 for term in terms if term in haystack)


def rerank_hits(query: str, hits: list[dict[str, Any]], final_k: int = FINAL_K) -> list[dict[str, Any]]:
    terms = extract_query_terms(query)
    entities = extract_entity_candidates(query)
    left_relation_entities, right_relation_entities = extract_relation_entities(query)

    reranked: list[dict[str, Any]] = []
    for hit in hits:
        meta = hit.get("metadata", {})
        title_text = normalize_for_match(meta.get("title", ""))
        slug_text = normalize_for_match(meta.get("source_url", ""))
        doc_text = normalize_for_match(hit.get("document", ""))
        full_text = hit_searchable_text(hit)
        overlap = compute_keyword_overlap(hit, terms)
        entity_present = entity_present_in_hit(hit, entities)
        relation_present = both_relation_entities_present(hit, left_relation_entities, right_relation_entities)

        score = 0.0
        score += overlap * 4.0
        score += max(0.0, 2.0 - float(hit.get("distance", 1.5))) * 2.5
        if relation_present:
            score += 20.0

        for entity in entities:
            entity_norm = normalize_for_match(entity)
            entity_compact = entity_norm.replace(" ", "")
            if entity_norm and entity_norm in title_text:
                score += 12.0
            if entity_norm and entity_norm in slug_text:
                score += 10.0
            if entity_norm and entity_norm in doc_text:
                score += 8.0
            if entity_compact and entity_compact in full_text.replace(" ", ""):
                score += 5.0

        if not entity_present and entities:
            score -= 12.0

        reranked.append(
            {
                **hit,
                "keyword_overlap": overlap,
                "entity_present": entity_present,
                "relation_present": relation_present,
                "rerank_score": round(score, 4),
            }
        )

    reranked.sort(
        key=lambda item: (
            item.get("relation_present", False),
            item.get("entity_present", False),
            item.get("keyword_overlap", 0),
            item.get("rerank_score", -9999),
            -float(item.get("distance", 9999)),
        ),
        reverse=True,
    )
    if left_relation_entities and right_relation_entities:
        relation_only = [item for item in reranked if item.get("relation_present")]
        if relation_only:
            reranked = relation_only
    if entities:
        entity_only = [item for item in reranked if item.get("entity_present")]
        if entity_only:
            reranked = entity_only
    return reranked[:final_k]


def is_comparison_query(query: str) -> bool:
    normalized = normalize_for_match(query)
    comparison_markers = [
        "compar",
        "diferencia",
        "diferencias",
        "versus",
        "vs",
        "frente",
        "mejor que",
        "peor que",
    ]
    has_platform_pair = "olympia" in normalized and ("gig os" in normalized or "gigos" in normalized or "gig" in normalized)
    return has_platform_pair or any(marker in normalized for marker in comparison_markers)


def has_sufficient_evidence(query: str, hits: list[dict[str, Any]]) -> bool:
    left_relation_entities, right_relation_entities = extract_relation_entities(query)
    if left_relation_entities and right_relation_entities:
        dual_hits = sum(1 for hit in hits if both_relation_entities_present(hit, left_relation_entities, right_relation_entities))
        return dual_hits >= 2

    terms = extract_query_terms(query)
    if not terms:
        return False

    entities = extract_entity_candidates(query)
    if entities and not any(entity_present_in_hit(hit, entities) for hit in hits):
        return False

    required_overlap = len(terms) if len(terms) <= 2 else 2
    best_overlap = 0
    entity_hits = 0
    for hit in hits:
        meta = hit.get("metadata", {})
        haystack = normalize_for_match(
            f"{meta.get('title', '')}\n{meta.get('source_url', '')}\n{hit.get('document', '')}"
        )
        overlap = sum(1 for term in terms if term in haystack)
        best_overlap = max(best_overlap, overlap)
        if entity_present_in_hit(hit, entities):
            entity_hits += 1

    open_query = "sobre" in normalize_for_match(query)
    if open_query and entity_hits >= 2:
        return True

    return best_overlap >= required_overlap


def has_sufficient_comparison_evidence(query: str, hits: list[dict[str, Any]]) -> bool:
    if not has_sufficient_evidence(query, hits):
        return False

    platforms = {hit.get("metadata", {}).get("platform", "") for hit in hits}
    return "olympia" in platforms and "gig_os" in platforms


def build_confidence_summary(query: str, hits: list[dict[str, Any]]) -> dict[str, Any]:
    unique_articles = {
        hit.get("metadata", {}).get("article_uid") or hit.get("metadata", {}).get("source_url")
        for hit in hits
    }
    unique_articles.discard(None)
    unique_platforms = {
        hit.get("metadata", {}).get("platform", "")
        for hit in hits
        if hit.get("metadata", {}).get("platform", "")
    }
    distances = [float(hit.get("distance", 1.0)) for hit in hits if hit.get("distance") is not None]
    average_distance = sum(distances) / len(distances) if distances else 1.0
    entities = extract_entity_candidates(query)
    entity_hits = sum(1 for hit in hits if entity_present_in_hit(hit, entities))
    left_relation_entities, right_relation_entities = extract_relation_entities(query)
    dual_entity_hits = sum(
        1 for hit in hits if both_relation_entities_present(hit, left_relation_entities, right_relation_entities)
    )

    semantic_score = 0
    if average_distance <= 0.5:
        semantic_score = 3
    elif average_distance <= 0.9:
        semantic_score = 2
    elif average_distance <= 1.2:
        semantic_score = 1

    hit_score = 0
    if len(hits) >= 4:
        hit_score = 3
    elif len(hits) >= 2:
        hit_score = 2
    elif len(hits) == 1:
        hit_score = 1

    diversity_score = 0
    if len(unique_articles) >= 3:
        diversity_score = 3
    elif len(unique_articles) >= 2:
        diversity_score = 2
    elif len(unique_articles) == 1:
        diversity_score = 1

    platform_score = 1 if len(unique_platforms) >= 2 else 0
    entity_score = 2 if entity_hits >= 3 else 1 if entity_hits >= 1 else 0
    evidence_score = semantic_score + hit_score + diversity_score + platform_score + entity_score

    if left_relation_entities and right_relation_entities and dual_entity_hits >= 2:
        label = "MEDIUM"
    elif evidence_score >= 9 and entity_hits >= 2:
        label = "HIGH"
    elif evidence_score >= 5 and entity_hits >= 1:
        label = "MEDIUM"
    else:
        label = "LOW"

    if not has_sufficient_evidence(query, hits):
        label = "LOW"

    if is_comparison_query(query) and len(unique_platforms) < 2:
        label = "LOW"

    return {
        "label": label,
        "hits_count": len(hits),
        "unique_articles": len(unique_articles),
        "unique_platforms": sorted(unique_platforms),
        "average_distance": round(average_distance, 4),
        "score": evidence_score,
        "entity_hits": entity_hits,
        "dual_entity_hits": dual_entity_hits,
        "entities": entities,
        "relation_left": left_relation_entities,
        "relation_right": right_relation_entities,
    }


def format_source_block(hit: dict[str, Any]) -> str:
    meta = hit["metadata"]
    return "\n".join(
        [
            f"Plataforma: {meta.get('platform', '')}",
            f"Título: {meta.get('title', '')}",
            f"Fecha: {meta.get('date', '')}",
            f"URL: {meta.get('source_url', '')}",
            "",
            hit["document"],
        ]
    ).strip()
