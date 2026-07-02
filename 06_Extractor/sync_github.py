from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(r"C:\Users\alvar\Documents\LOI_AI")
EXTRACTOR_ROOT = ROOT / "06_Extractor"
PYTHON_EXE = Path(sys.executable)

SYNC_PATHS = [
    ROOT / "01_Olympia",
    ROOT / "02_GIG_OS",
    ROOT / "03_Reuniones_Presidencia",
    ROOT / "09_Analisis_GPT",
]

SUPPORT_PATHS = [
    ROOT / ".gitignore",
    ROOT / "README.md",
    ROOT / "03_Reuniones_Presidencia" / "README.md",
    EXTRACTOR_ROOT / "sync_github.py",
    EXTRACTOR_ROOT / "run_full_daily_sync.ps1",
    EXTRACTOR_ROOT / "generate_analisis_gpt.py",
]


@dataclass
class UpdateSummary:
    platform: str
    new_articles: int
    duplicates: int
    errors: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Daily LOI_AI GitHub sync")
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Run extractors and show the file plan without git add/commit/push.",
    )
    parser.add_argument(
        "--skip-push",
        action="store_true",
        help="Run git add and commit, but skip git push.",
    )
    return parser.parse_args()


def run_command(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def ensure_git_repo() -> None:
    if (ROOT / ".git").exists():
        return

    result = run_command(["git", "init", "-b", "main"], ROOT)
    if result.returncode != 0:
        raise RuntimeError(f"No se pudo inicializar git:\n{result.stderr.strip()}")


def run_login_test(platform: str) -> None:
    result = run_command(
        [
            str(PYTHON_EXE),
            "main.py",
            "--platform",
            platform,
            "--login-test",
        ],
        EXTRACTOR_ROOT,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Falló login-test para {platform}.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )


def looks_like_auth_error(result: subprocess.CompletedProcess[str]) -> bool:
    combined = f"{result.stdout}\n{result.stderr}".lower()
    auth_markers = (
        "session is not authenticated",
        "authenticated state not found",
        "run python main.py --platform",
        "login required",
    )
    return any(marker in combined for marker in auth_markers)


def run_daily_update(platform: str) -> UpdateSummary:
    command = [
        str(PYTHON_EXE),
        "main.py",
        "--platform",
        platform,
        "--daily-update",
    ]
    result = run_command(
        command,
        EXTRACTOR_ROOT,
    )
    if result.returncode != 0 and looks_like_auth_error(result):
        print(
            f"\n[{platform}] Sesión expirada o no autenticada. Ejecutando login-test automático y reintentando..."
        )
        run_login_test(platform)
        result = run_command(
            command,
            EXTRACTOR_ROOT,
        )

    if result.returncode != 0:
        raise RuntimeError(
            f"Falló daily update para {platform}.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )

    output = result.stdout
    new_articles = extract_metric(output, "New articles")
    duplicates = extract_metric(output, "Duplicates skipped")
    errors = extract_metric(output, "Errors")
    return UpdateSummary(platform, new_articles, duplicates, errors)


def extract_metric(output: str, label: str) -> int:
    match = re.search(rf"{re.escape(label)}:\s+(\d+)", output)
    return int(match.group(1)) if match else 0


def refresh_analysis_docs() -> int:
    result = run_command([str(PYTHON_EXE), "generate_analisis_gpt.py"], EXTRACTOR_ROOT)
    if result.returncode != 0:
        raise RuntimeError(
            f"Falló refresh de 09_Analisis_GPT.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )

    match = re.search(r"Refreshed documents:\s+(\d+)", result.stdout)
    return int(match.group(1)) if match else 0


def list_candidate_changes() -> list[str]:
    pathspecs = [str(path) for path in SYNC_PATHS + SUPPORT_PATHS]
    result = run_command(
        ["git", "status", "--short", "--untracked-files=all", "--", *pathspecs],
        ROOT,
    )
    if result.returncode != 0:
        raise RuntimeError(f"No se pudo leer git status:\n{result.stderr.strip()}")

    changes: list[str] = []
    for line in result.stdout.splitlines():
        line = line.rstrip()
        if not line:
            continue
        changes.append(line)
    return changes


def print_plan(
    olympia: UpdateSummary,
    gig_os: UpdateSummary,
    refreshed_docs: int,
    changes: list[str],
) -> None:
    print("\nPlan de sincronización GitHub")
    print("=" * 34)
    print(f"Olympia: new={olympia.new_articles} duplicates={olympia.duplicates} errors={olympia.errors}")
    print(f"GIG-OS:  new={gig_os.new_articles} duplicates={gig_os.duplicates} errors={gig_os.errors}")
    print(f"09_Analisis_GPT refreshed: {refreshed_docs}")
    print("\nArchivos candidatos para subir:")
    if changes:
        for item in changes:
            print(f"  {item}")
    else:
        print("  (sin cambios)")


def stage_changes() -> None:
    pathspecs = [str(path) for path in SYNC_PATHS + SUPPORT_PATHS]
    result = run_command(["git", "add", "--", *pathspecs], ROOT)
    if result.returncode != 0:
        raise RuntimeError(f"No se pudo ejecutar git add:\n{result.stderr.strip()}")


def has_staged_changes() -> bool:
    result = run_command(["git", "diff", "--cached", "--name-only"], ROOT)
    if result.returncode != 0:
        raise RuntimeError(f"No se pudo revisar staged changes:\n{result.stderr.strip()}")
    return bool(result.stdout.strip())


def build_commit_message(
    olympia: UpdateSummary,
    gig_os: UpdateSummary,
    changes: list[str],
) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    total_files = len(changes)
    return (
        f"sync: {today} olympia+{olympia.new_articles} "
        f"gigos+{gig_os.new_articles} files={total_files}"
    )


def create_commit(message: str) -> None:
    result = run_command(["git", "commit", "-m", message], ROOT)
    if result.returncode != 0:
        raise RuntimeError(f"No se pudo crear commit:\n{result.stdout}\n{result.stderr}")


def ensure_origin_remote() -> None:
    result = run_command(["git", "remote", "get-url", "origin"], ROOT)
    if result.returncode != 0:
        raise RuntimeError(
            "No existe remote 'origin'. Configure el repositorio GitHub antes de usar push."
        )


def push_changes() -> None:
    ensure_origin_remote()
    result = run_command(["git", "push", "-u", "origin", "main"], ROOT)
    if result.returncode != 0:
        raise RuntimeError(f"No se pudo hacer git push:\n{result.stdout}\n{result.stderr}")


def main() -> None:
    args = parse_args()
    ensure_git_repo()

    olympia = run_daily_update("olympia")
    gig_os = run_daily_update("gig_os")
    refreshed_docs = refresh_analysis_docs()
    changes = list_candidate_changes()

    print_plan(olympia, gig_os, refreshed_docs, changes)

    if args.plan_only:
        return

    if not changes:
        print("\nNo hay cambios para sincronizar.")
        return

    stage_changes()
    if not has_staged_changes():
        print("\nNo hay cambios stageados para commit.")
        return

    commit_message = build_commit_message(olympia, gig_os, changes)
    create_commit(commit_message)
    print(f"\nCommit creado: {commit_message}")

    if args.skip_push:
        print("Push omitido por --skip-push.")
        return

    push_changes()
    print("Push completado.")


if __name__ == "__main__":
    main()
