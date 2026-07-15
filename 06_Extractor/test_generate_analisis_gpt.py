from __future__ import annotations

import unittest
from pathlib import Path

import generate_analisis_gpt as generator


class DocumentaryRefreshTests(unittest.TestCase):
    def article(self, platform: str, url: str) -> generator.ArticleDocument:
        return generator.ArticleDocument(
            path=generator.ROOT / "01_Olympia" / "markdown" / f"{platform}.md",
            platform=platform,
            title="Factory.DroneX: actualización de producción",
            date="02.07.2026",
            source_url=url,
            text="",
            body=(
                "Factory.DroneX amplía su distribución. "
                "La actualización de Factory.DroneX afecta la demanda de recursos."
            ),
        )

    def test_groups_same_title_across_platforms(self) -> None:
        olympia = self.article("Olympia", "https://example.test/olympia")
        gig_os = self.article("GIG-OS", "https://example.test/gig-os")

        block, pending, shown = generator.build_source_block(
            "06_Factory_Drone_X.md",
            [olympia, gig_os],
            "# Factory Drone X\n",
        )

        self.assertEqual(pending, 1)
        self.assertEqual(shown, 1)
        self.assertIn("GIG-OS, Olympia", block)
        self.assertIn(olympia.source_url, block)
        self.assertIn(gig_os.source_url, block)

    def test_omits_group_when_one_url_is_already_curated(self) -> None:
        olympia = self.article("Olympia", "https://example.test/olympia")
        gig_os = self.article("GIG-OS", "https://example.test/gig-os")

        block, pending, shown = generator.build_source_block(
            "06_Factory_Drone_X.md",
            [olympia, gig_os],
            f"Fuente integrada: {olympia.source_url}.",
        )

        self.assertEqual(pending, 0)
        self.assertEqual(shown, 0)
        self.assertIn("No hay fuentes documentales nuevas", block)

    def test_source_injection_is_idempotent(self) -> None:
        document = (
            "# Tema\n\n"
            "## Hechos documentados\n\n- Hecho.\n\n"
            "## Preguntas estratégicas abiertas\n\n- Pregunta.\n"
        )
        block = (
            f"{generator.SOURCE_AUTO_START}\n"
            f"{generator.SOURCE_AUTO_HEADING}\n\nContenido.\n"
            f"{generator.SOURCE_AUTO_END}"
        )

        first = generator.inject_source_block(document, block)
        second = generator.inject_source_block(first, block)

        self.assertEqual(first, second)
        self.assertEqual(second.count(generator.SOURCE_AUTO_START), 1)
        self.assertEqual(second.count(generator.SOURCE_AUTO_END), 1)


if __name__ == "__main__":
    unittest.main()
