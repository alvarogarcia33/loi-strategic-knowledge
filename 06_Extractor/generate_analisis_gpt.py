from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(r"C:\Users\alvar\Documents\LOI_AI")
OUTPUT_DIR = ROOT / "09_Analisis_GPT"
MEETINGS_DIR = ROOT / "03_Reuniones_Presidencia"
ARTICLE_DIRS = (
    ("Olympia", ROOT / "01_Olympia" / "markdown"),
    ("GIG-OS", ROOT / "02_GIG_OS" / "markdown"),
)

EXPECTED_FILES = (
    "01_Interatum.md",
    "02_TerritoryX.md",
    "03_Legends_of_Interactions.md",
    "04_HMAP.md",
    "05_Maestros_del_Juego.md",
    "06_Factory_Drone_X.md",
)

REQUIRED_HEADINGS = (
    "## Hechos documentados",
    "## Evolución temporal",
    "## Relaciones con otros proyectos",
    "## Cambios de narrativa detectados",
    "## Preguntas estratégicas abiertas",
)

AUTO_START = "<!-- AUTO:REUNIONES_PRESIDENCIA:START -->"
AUTO_END = "<!-- AUTO:REUNIONES_PRESIDENCIA:END -->"
AUTO_HEADING = "## Evidencia privada de reuniones"
SOURCE_AUTO_START = "<!-- AUTO:ACTUALIZACION_DOCUMENTAL:START -->"
SOURCE_AUTO_END = "<!-- AUTO:ACTUALIZACION_DOCUMENTAL:END -->"
SOURCE_AUTO_HEADING = "## Actualización documental automática"
MAX_PENDING_SOURCES = 12

TOPIC_PATTERNS: dict[str, tuple[str, ...]] = {
    "01_Interatum.md": (
        r"\binteratum\b",
        r"\bint coin\b",
    ),
    "02_TerritoryX.md": (
        r"\bterritoryx\b",
        r"\bterritorio x\b",
        r"\bterritorio_x\b",
    ),
    "03_Legends_of_Interactions.md": (
        r"\blegends of interactions\b",
        r"\bglobal metaverse\b",
        r"\bloi\b",
        r"\bloy\b",
    ),
    "04_HMAP.md": (
        r"\bh[ -]?map\b",
        r"\bhmap\b",
        r"\bgamegos\b",
        r"\bdominioncoin\b",
        r"\bdominion coin\b",
        r"\bfifteen force\b",
        r"\bfixed force\b",
        r"\bpin(?:es|s)?\b",
    ),
    "05_Maestros_del_Juego.md": (
        r"\bmaestros del juego\b",
        r"\bmaestro del juego\b",
        r"\bgame masters?\b",
        r"\bgabinete de maestros\b",
        r"\bmarket makers?\b",
    ),
    "06_Factory_Drone_X.md": (
        r"\bfactory[ .]?dronex\b",
        r"\bfactory de drones\b",
        r"\bfabrica de drones\b",
        r"\bfactory_drone\b",
        r"\bprefactorydx\b",
    ),
}

EVIDENCE_SECTIONS = (
    "Hechos mencionados",
    "Mensajes centrales",
    "Puntos estratégicos",
    "Señales estratégicas",
    "Decisiones o señales de cambio",
    "Relación con Olympia o GIG-OS",
)


@dataclass(frozen=True)
class MeetingDocument:
    path: Path
    title: str
    date: str
    note_type: str
    confidence: str
    source_kind: str
    text: str
    sections: dict[str, str]


@dataclass(frozen=True)
class ArticleDocument:
    path: Path
    platform: str
    title: str
    date: str
    source_url: str
    text: str
    body: str


def normalize_document(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    return normalized + "\n"


def normalize_for_match(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return without_accents.casefold()


def validate_document(path: Path, text: str) -> None:
    missing = [heading for heading in REQUIRED_HEADINGS if heading not in text]
    if missing:
        missing_text = ", ".join(missing)
        raise RuntimeError(f"{path.name} no contiene las secciones requeridas: {missing_text}")


def parse_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current = ""
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
        elif current:
            sections[current].append(line)
    return {name: "\n".join(lines).strip() for name, lines in sections.items()}


def metadata_value(text: str, label: str, default: str) -> str:
    match = re.search(rf"^- {re.escape(label)}:\s*(.+)$", text, flags=re.MULTILINE | re.IGNORECASE)
    return match.group(1).strip() if match else default


def frontmatter_value(text: str, key: str, default: str = "") -> str:
    match = re.search(
        rf'^\s*{re.escape(key)}:\s*["\']?(.*?)["\']?\s*$',
        text,
        flags=re.MULTILINE | re.IGNORECASE,
    )
    return match.group(1).strip().strip('"\'') if match else default


def clean_article_body(text: str, title: str) -> str:
    body = re.sub(r"\A---\s*\n.*?\n---\s*\n", "", text, flags=re.DOTALL)
    body = re.split(r"^## Imágenes\s*$", body, maxsplit=1, flags=re.MULTILINE)[0]
    body = re.split(r"^Noticias relacionadas\s*$", body, maxsplit=1, flags=re.MULTILINE)[0]
    lines: list[str] = []
    normalized_title = normalize_for_match(title)
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append("")
            continue
        if stripped.startswith("![") or stripped.startswith("#"):
            continue
        if normalize_for_match(stripped) == normalized_title:
            continue
        if re.match(r"^(Publicado|Fecha|Autor|Categorías):", stripped, flags=re.IGNORECASE):
            continue
        lines.append(stripped)
    return "\n".join(lines).strip()


def load_articles() -> list[ArticleDocument]:
    articles: list[ArticleDocument] = []
    for platform, directory in ARTICLE_DIRS:
        for path in sorted(directory.glob("*.md")):
            text = normalize_document(path.read_text(encoding="utf-8-sig"))
            title = frontmatter_value(text, "title", path.stem)
            articles.append(
                ArticleDocument(
                    path=path,
                    platform=platform,
                    title=title,
                    date=frontmatter_value(text, "date", "sin fecha"),
                    source_url=frontmatter_value(text, "source_url"),
                    text=text,
                    body=clean_article_body(text, title),
                )
            )
    return articles


def load_meetings() -> list[MeetingDocument]:
    paths = sorted(
        list((MEETINGS_DIR / "reuniones_privadas").glob("*.md"))
        + list((MEETINGS_DIR / "conferencias_presidencia").glob("*.md"))
    )
    meetings: list[MeetingDocument] = []
    for path in paths:
        text = normalize_document(path.read_text(encoding="utf-8-sig"))
        title_match = re.search(r"^#\s+(.+)$", text, flags=re.MULTILINE)
        title = title_match.group(1).strip() if title_match else path.stem
        source_kind = (
            "reunión privada"
            if path.parent.name == "reuniones_privadas"
            else "conferencia de presidencia"
        )
        meetings.append(
            MeetingDocument(
                path=path,
                title=title,
                date=metadata_value(text, "Fecha", "sin fecha confirmada"),
                note_type=metadata_value(text, "Tipo de nota", source_kind),
                confidence=metadata_value(text, "Nivel de certeza", "no indicado"),
                source_kind=source_kind,
                text=text,
                sections=parse_sections(text),
            )
        )
    return meetings


def matches_topic(text: str, patterns: tuple[str, ...]) -> bool:
    normalized = normalize_for_match(text)
    return any(re.search(pattern, normalized) for pattern in patterns)


def extract_bullets(section: str) -> list[str]:
    return [
        line[2:].strip()
        for line in section.splitlines()
        if line.startswith("- ") and line[2:].strip()
    ]


def relevant_evidence(meeting: MeetingDocument, patterns: tuple[str, ...]) -> list[str]:
    evidence: list[str] = []
    seen: set[str] = set()
    for section_name in EVIDENCE_SECTIONS:
        for bullet in extract_bullets(meeting.sections.get(section_name, "")):
            if not matches_topic(bullet, patterns):
                continue
            key = normalize_for_match(bullet)
            if key in seen:
                continue
            evidence.append(bullet)
            seen.add(key)
            if len(evidence) == 5:
                return evidence

    if evidence:
        return evidence

    summary = meeting.sections.get("Resumen", "")
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", summary) if part.strip()]
    scored = sorted(
        (
            (
                sum(
                    len(re.findall(pattern, normalize_for_match(paragraph)))
                    for pattern in patterns
                ),
                paragraph,
            )
            for paragraph in paragraphs
        ),
        key=lambda item: item[0],
        reverse=True,
    )
    if scored and scored[0][0] > 0:
        return [scored[0][1]]
    return []


def meeting_sort_key(meeting: MeetingDocument) -> tuple[int, str, str]:
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", meeting.date):
        return (0, meeting.date, meeting.title)
    return (1, "9999-99-99", meeting.title)


def build_meeting_block(filename: str, meetings: list[MeetingDocument]) -> str:
    patterns = TOPIC_PATTERNS[filename]
    relevant = sorted(
        (meeting for meeting in meetings if matches_topic(meeting.text, patterns)),
        key=meeting_sort_key,
    )
    lines = [
        AUTO_START,
        AUTO_HEADING,
        "",
        "> Sección generada automáticamente desde extractos privados. "
        "No constituye un anuncio oficial y debe contrastarse con Olympia, GIG-OS y datos blockchain.",
        "",
    ]

    if not relevant:
        lines.extend(
            [
                "No se encontraron reuniones reales etiquetadas con esta entidad. "
                "Esto representa una ausencia de evidencia privada, no evidencia de ausencia.",
                "",
                AUTO_END,
            ]
        )
        return "\n".join(lines)

    for meeting in relevant:
        relative_path = meeting.path.relative_to(ROOT).as_posix()
        link = f"../{relative_path}"
        lines.extend(
            [
                f"### {meeting.date} — {meeting.title}",
                "",
                f"- Fuente privada: [{relative_path}]({link})",
                f"- Tipo: {meeting.source_kind}; {meeting.note_type}.",
                f"- Nivel de certeza declarado: **{meeting.confidence}**.",
                "- Aportes relevantes:",
            ]
        )
        evidence = relevant_evidence(meeting, patterns)
        if evidence:
            lines.extend(f"  - {item}" for item in evidence)
        else:
            lines.append("  - La entidad aparece mencionada, pero no hay un hecho puntual extraíble sin contexto adicional.")
        lines.append("")

    lines.append(AUTO_END)
    return "\n".join(lines)


def article_relevance_score(article: ArticleDocument, patterns: tuple[str, ...]) -> int:
    normalized_title = normalize_for_match(article.title)
    normalized_body = normalize_for_match(article.body)
    title_hits = sum(len(re.findall(pattern, normalized_title)) for pattern in patterns)
    body_hits = sum(len(re.findall(pattern, normalized_body)) for pattern in patterns)
    if title_hits == 0 and body_hits < 2:
        return 0
    return title_hits * 10 + min(body_hits, 20)


def normalized_title_key(title: str) -> str:
    normalized = normalize_for_match(title)
    return re.sub(r"[^a-z0-9]+", " ", normalized).strip()


def parsed_article_date(date_text: str) -> datetime:
    for date_format in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_text, date_format)
        except ValueError:
            continue
    return datetime.min


def existing_urls(text: str) -> set[str]:
    return {
        match.rstrip(".,;:")
        for match in re.findall(r"https?://[^\s)\]]+", text)
    }


def truncate_excerpt(text: str, max_chars: int = 520) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_chars:
        return compact
    shortened = compact[:max_chars].rsplit(" ", maxsplit=1)[0].rstrip(".,;:")
    return shortened + "…"


def article_excerpt(article: ArticleDocument, patterns: tuple[str, ...]) -> str:
    paragraphs = [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", article.body)
        if len(paragraph.strip()) >= 60
    ]
    if not paragraphs:
        return "El artículo no contiene un extracto textual limpio suficiente."

    scored = sorted(
        enumerate(paragraphs),
        key=lambda item: (
            sum(
                len(re.findall(pattern, normalize_for_match(item[1])))
                for pattern in patterns
            ),
            -item[0],
        ),
        reverse=True,
    )
    selected_indexes = sorted(index for index, _ in scored[:2])
    selected = " ".join(paragraphs[index] for index in selected_indexes)
    return truncate_excerpt(selected)


def classify_signal(articles: list[ArticleDocument]) -> str:
    combined = normalize_for_match(" ".join(article.title for article in articles))
    signal_patterns = (
        ("cambio de calendario o plazo", r"plazo|fecha|extendid|aplaz|pospuest|reprogram"),
        ("cierre o finalización", r"finaliz|termin|cierre|conclu|agotad"),
        ("lanzamiento o activación", r"lanz|disponible|apertura|abierto|activad|comenz"),
        ("crecimiento o adopción", r"crec|aument|alcanz|super|nuevos miembros|expansion"),
        ("convergencia entre proyectos", r"un solo futuro|interconect|ecosistema|relacion|junto"),
    )
    for label, pattern in signal_patterns:
        if re.search(pattern, combined):
            return label
    return "actualización temática"


def strip_source_block(text: str) -> str:
    pattern = re.compile(
        rf"\n*{re.escape(SOURCE_AUTO_START)}.*?{re.escape(SOURCE_AUTO_END)}\n*",
        flags=re.DOTALL,
    )
    return pattern.sub("\n\n", text).strip()


def build_source_block(
    filename: str,
    articles: list[ArticleDocument],
    curated_text: str,
) -> tuple[str, int, int]:
    patterns = TOPIC_PATTERNS[filename]
    cited_urls = existing_urls(curated_text)
    grouped: dict[str, list[tuple[ArticleDocument, int]]] = {}

    for article in articles:
        score = article_relevance_score(article, patterns)
        if score == 0:
            continue
        key = normalized_title_key(article.title)
        grouped.setdefault(key, []).append((article, score))

    pending_groups: list[tuple[list[ArticleDocument], int]] = []
    for group in grouped.values():
        group_articles = [article for article, _ in group]
        if any(article.source_url in cited_urls for article in group_articles if article.source_url):
            continue
        pending_groups.append((group_articles, max(score for _, score in group)))

    pending_groups.sort(
        key=lambda item: (
            max(parsed_article_date(article.date) for article in item[0]),
            item[1],
        ),
        reverse=True,
    )
    selected_groups = pending_groups[:MAX_PENDING_SOURCES]
    latest_date = max(
        (parsed_article_date(article.date) for article in articles),
        default=datetime.min,
    )
    latest_text = latest_date.strftime("%d.%m.%Y") if latest_date != datetime.min else "sin fecha"

    lines = [
        SOURCE_AUTO_START,
        SOURCE_AUTO_HEADING,
        "",
        "> Sección regenerada desde Olympia y GIG-OS. Contiene fuentes relevantes que todavía no están "
        "citadas en la parte curada del dossier. Los extractos son evidencia documental, no conclusiones del analista.",
        "",
        f"- Corte documental disponible: **{latest_text}**.",
        f"- Fuentes relevantes pendientes: **{len(pending_groups)}**.",
        f"- Fuentes mostradas: **{len(selected_groups)}**.",
        "",
    ]

    if not selected_groups:
        lines.extend(
            [
                "No hay fuentes documentales nuevas pendientes de incorporación estratégica para esta entidad.",
                "",
                SOURCE_AUTO_END,
            ]
        )
        return "\n".join(lines), 0, 0

    for group_articles, score in selected_groups:
        representative = max(group_articles, key=lambda article: parsed_article_date(article.date))
        platforms = ", ".join(sorted({article.platform for article in group_articles}))
        source_links = ", ".join(
            f"[{article.platform}]({article.source_url})"
            for article in sorted(group_articles, key=lambda item: item.platform)
            if article.source_url
        )
        local_paths = ", ".join(
            f"[{article.path.relative_to(ROOT).as_posix()}](../{article.path.relative_to(ROOT).as_posix()})"
            for article in sorted(group_articles, key=lambda item: item.platform)
        )
        lines.extend(
            [
                f"### {representative.date} — {representative.title}",
                "",
                f"- Señal documental: **{classify_signal(group_articles)}**.",
                f"- Relevancia automática: **{score}**.",
                f"- Plataformas: {platforms}.",
                f"- URLs originales: {source_links or 'no disponible'}.",
                f"- Archivos locales: {local_paths}.",
                f"- Extracto relevante: {article_excerpt(representative, patterns)}",
                "",
            ]
        )

    if len(pending_groups) > len(selected_groups):
        lines.extend(
            [
                f"Se omitieron **{len(pending_groups) - len(selected_groups)}** fuentes menos recientes para mantener el dossier manejable; permanecen disponibles en las carpetas documentales.",
                "",
            ]
        )
    lines.append(SOURCE_AUTO_END)
    return "\n".join(lines), len(pending_groups), len(selected_groups)


def strip_auto_block(text: str) -> str:
    pattern = re.compile(
        rf"\n*{re.escape(AUTO_START)}.*?{re.escape(AUTO_END)}\n*",
        flags=re.DOTALL,
    )
    return pattern.sub("\n\n", text).strip()


def inject_meeting_block(text: str, block: str) -> str:
    clean = strip_auto_block(text)
    insertion_heading = "## Preguntas estratégicas abiertas"
    if insertion_heading not in clean:
        raise RuntimeError(f"No se encontró el punto de inserción: {insertion_heading}")
    before, after = clean.split(insertion_heading, maxsplit=1)
    return normalize_document(
        f"{before.rstrip()}\n\n{block}\n\n{insertion_heading}{after}"
    )


def inject_source_block(text: str, block: str) -> str:
    clean = strip_source_block(text)
    insertion_heading = "## Preguntas estratégicas abiertas"
    if insertion_heading not in clean:
        raise RuntimeError(f"No se encontró el punto de inserción: {insertion_heading}")
    before, after = clean.split(insertion_heading, maxsplit=1)
    return normalize_document(
        f"{before.rstrip()}\n\n{block}\n\n{insertion_heading}{after}"
    )


def refresh_documents() -> tuple[list[Path], dict[str, int], dict[str, tuple[int, int]]]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    meetings = load_meetings()
    articles = load_articles()
    refreshed: list[Path] = []
    match_counts: dict[str, int] = {}
    source_counts: dict[str, tuple[int, int]] = {}

    for filename in EXPECTED_FILES:
        path = OUTPUT_DIR / filename
        if not path.exists():
            raise RuntimeError(
                f"Falta el documento estratégico esperado: {path}. "
                "La capa 09_Analisis_GPT debe mantenerse curada localmente."
            )

        text = path.read_text(encoding="utf-8-sig")
        validate_document(path, text)
        text_without_sources = strip_source_block(text)
        curated_text = strip_auto_block(text_without_sources)
        relevant_count = sum(
            1 for meeting in meetings if matches_topic(meeting.text, TOPIC_PATTERNS[filename])
        )
        source_block, pending_count, shown_count = build_source_block(
            filename,
            articles,
            curated_text,
        )
        meeting_block = build_meeting_block(filename, meetings)
        with_sources = inject_source_block(text_without_sources, source_block)
        updated = inject_meeting_block(with_sources, meeting_block)
        if updated.count(AUTO_START) != 1 or updated.count(AUTO_END) != 1:
            raise RuntimeError(f"{path.name} no contiene exactamente un bloque automático de reuniones.")
        if updated.count(SOURCE_AUTO_START) != 1 or updated.count(SOURCE_AUTO_END) != 1:
            raise RuntimeError(f"{path.name} no contiene exactamente un bloque automático documental.")
        path.write_text(updated, encoding="utf-8")
        refreshed.append(path)
        match_counts[filename] = relevant_count
        source_counts[filename] = (pending_count, shown_count)

    return refreshed, match_counts, source_counts


def main() -> None:
    refreshed, match_counts, source_counts = refresh_documents()
    print("09_Analisis_GPT refresh")
    print("=" * 28)
    print(f"Refreshed documents: {len(refreshed)}")
    for path in refreshed:
        pending, shown = source_counts[path.name]
        print(
            f"  - {path.name}: private_sources={match_counts[path.name]} "
            f"pending_sources={pending} shown_sources={shown}"
        )


if __name__ == "__main__":
    main()
