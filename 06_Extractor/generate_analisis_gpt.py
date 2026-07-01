from __future__ import annotations

from pathlib import Path


ROOT = Path(r"C:\Users\alvar\Documents\LOI_AI")
OUTPUT_DIR = ROOT / "09_Analisis_GPT"

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


def normalize_document(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    return normalized + "\n"


def validate_document(path: Path, text: str) -> None:
    missing = [heading for heading in REQUIRED_HEADINGS if heading not in text]
    if missing:
        missing_text = ", ".join(missing)
        raise RuntimeError(f"{path.name} no contiene las secciones requeridas: {missing_text}")


def refresh_documents() -> list[Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    refreshed: list[Path] = []

    for filename in EXPECTED_FILES:
        path = OUTPUT_DIR / filename
        if not path.exists():
            raise RuntimeError(
                f"Falta el documento estratégico esperado: {path}. "
                "La capa 09_Analisis_GPT debe mantenerse curada localmente."
            )

        text = path.read_text(encoding="utf-8")
        validate_document(path, text)
        normalized = normalize_document(text)
        path.write_text(normalized, encoding="utf-8")
        refreshed.append(path)

    return refreshed


def main() -> None:
    refreshed = refresh_documents()
    print("09_Analisis_GPT refresh")
    print("=" * 28)
    print(f"Refreshed documents: {len(refreshed)}")
    for path in refreshed:
        print(f"  - {path}")


if __name__ == "__main__":
    main()
