from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*args: object, **kwargs: object) -> bool:
        return False


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_ROOT = Path(r"C:\Users\alvar\Documents\LOI_AI")


@dataclass(frozen=True)
class PlatformConfig:
    name: str
    base_url: str
    login_url: str
    username: str
    password: str
    username_selector: str
    password_selector: str
    submit_selector: str
    login_success_selector: str
    logout_selector: str


@dataclass(frozen=True)
class AppConfig:
    project_root: Path
    output_root: Path
    database_path: Path
    log_dir: Path
    log_level: str
    headless: bool
    slow_mo_ms: int
    download_images: bool
    request_timeout_seconds: int
    daily_run_hour: str
    gig_os: PlatformConfig
    olympia: PlatformConfig

    @property
    def required_directories(self) -> tuple[Path, ...]:
        return (
            self.output_root,
            self.project_root,
            self.log_dir,
            self.database_path.parent,
            self.project_root / "data" / "browser_state",
            self.project_root / "data" / "screenshots",
            self.output_root / "01_Olympia",
            self.output_root / "01_Olympia" / "markdown",
            self.output_root / "01_Olympia" / "images",
            self.output_root / "01_Olympia" / "metadata",
            self.output_root / "02_GIG_OS",
            self.output_root / "02_GIG_OS" / "markdown",
            self.output_root / "02_GIG_OS" / "images",
            self.output_root / "02_GIG_OS" / "metadata",
            self.output_root / "03_Reuniones",
            self.output_root / "03_Reuniones_Presidencia",
            self.output_root / "04_Traducciones",
            self.output_root / "05_Resumenes",
            self.output_root / "07_Base_Vectorial",
            self.output_root / "08_Reportes",
            self.output_root / "09_Analisis_GPT",
        )


def _get_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _get_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return default
    return int(raw_value)


def load_config() -> AppConfig:
    load_dotenv(PROJECT_ROOT / ".env")

    output_root = Path(os.getenv("OUTPUT_ROOT", str(DEFAULT_OUTPUT_ROOT))).expanduser()
    database_path = Path(
        os.getenv(
            "DATABASE_PATH",
            str(PROJECT_ROOT / "data" / "articles.sqlite"),
        )
    ).expanduser()
    log_dir = Path(os.getenv("LOG_DIR", str(PROJECT_ROOT / "logs"))).expanduser()

    return AppConfig(
        project_root=PROJECT_ROOT,
        output_root=output_root,
        database_path=database_path,
        log_dir=log_dir,
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        headless=_get_bool("HEADLESS", True),
        slow_mo_ms=_get_int("SLOW_MO_MS", 0),
        download_images=_get_bool("DOWNLOAD_IMAGES", True),
        request_timeout_seconds=_get_int("REQUEST_TIMEOUT_SECONDS", 60),
        daily_run_hour=os.getenv("DAILY_RUN_HOUR", "07:00"),
        gig_os=PlatformConfig(
            name="gig_os",
            base_url=os.getenv("GIG_OS_BASE_URL", ""),
            login_url=os.getenv("GIG_OS_LOGIN_URL", ""),
            username=os.getenv("GIG_OS_USERNAME", ""),
            password=os.getenv("GIG_OS_PASSWORD", ""),
            username_selector=os.getenv("GIG_OS_USERNAME_SELECTOR", ""),
            password_selector=os.getenv("GIG_OS_PASSWORD_SELECTOR", ""),
            submit_selector=os.getenv("GIG_OS_SUBMIT_SELECTOR", ""),
            login_success_selector=os.getenv("GIG_OS_LOGIN_SUCCESS_SELECTOR", ""),
            logout_selector=os.getenv("GIG_OS_LOGOUT_SELECTOR", ""),
        ),
        olympia=PlatformConfig(
            name="olympia",
            base_url=os.getenv("OLYMPIA_BASE_URL", ""),
            login_url=os.getenv("OLYMPIA_LOGIN_URL", ""),
            username=os.getenv("OLYMPIA_USERNAME", ""),
            password=os.getenv("OLYMPIA_PASSWORD", ""),
            username_selector=os.getenv("OLYMPIA_USERNAME_SELECTOR", ""),
            password_selector=os.getenv("OLYMPIA_PASSWORD_SELECTOR", ""),
            submit_selector=os.getenv("OLYMPIA_SUBMIT_SELECTOR", ""),
            login_success_selector=os.getenv("OLYMPIA_LOGIN_SUCCESS_SELECTOR", ""),
            logout_selector=os.getenv("OLYMPIA_LOGOUT_SELECTOR", ""),
        ),
    )


def ensure_required_directories(config: AppConfig) -> list[Path]:
    missing: list[Path] = []
    for directory in config.required_directories:
        directory.mkdir(parents=True, exist_ok=True)
        if not directory.exists():
            missing.append(directory)

    if missing:
        missing_text = "\n".join(str(path) for path in missing)
        raise RuntimeError(f"Required directories could not be created:\n{missing_text}")

    return list(config.required_directories)
