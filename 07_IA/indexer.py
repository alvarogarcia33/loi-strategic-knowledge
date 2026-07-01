from __future__ import annotations

from search import (
    build_manifest_payload,
    chunk_text,
    get_collection,
    iter_markdown_documents,
    ollama_embed,
    write_manifest,
)


def main() -> None:
    documents = iter_markdown_documents()
    collection = get_collection()
    existing = collection.get(include=[])
    existing_ids = existing.get("ids", [])
    if existing_ids:
        collection.delete(ids=existing_ids)

    ids: list[str] = []
    texts: list[str] = []
    metadatas: list[dict[str, str]] = []

    for document in documents:
        meta = document["meta"]
        chunks = chunk_text(document["chunk_source_text"])
        for chunk_index, chunk in enumerate(chunks, start=1):
            chunk_id = f"{meta['article_uid']}::chunk_{chunk_index:04d}"
            ids.append(chunk_id)
            texts.append(chunk)
            metadatas.append(
                {
                    "article_uid": meta.get("article_uid", ""),
                    "platform": meta.get("platform", ""),
                    "title": meta.get("title", ""),
                    "date": meta.get("date", ""),
                    "source_url": meta.get("source_url", ""),
                    "canonical_url": meta.get("canonical_url", ""),
                    "content_hash": meta.get("content_hash", ""),
                    "chunk_index": str(chunk_index),
                }
            )

    batch_size = 32
    for start in range(0, len(texts), batch_size):
        end = start + batch_size
        batch_ids = ids[start:end]
        batch_texts = texts[start:end]
        batch_meta = metadatas[start:end]
        batch_embeddings = ollama_embed(batch_texts)
        collection.add(
            ids=batch_ids,
            documents=batch_texts,
            metadatas=batch_meta,
            embeddings=batch_embeddings,
        )

    manifest_path = write_manifest(build_manifest_payload(len(documents), len(texts)))
    print(f"Documentos indexados: {len(documents)}")
    print(f"Chunks indexados: {len(texts)}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
