from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from playwright.sync_api import (
    Error as PlaywrightError,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

from config import AppConfig, PlatformConfig


USERNAME_SELECTORS = (
    "#username",
    "#user",
    "#email",
    "input[name='username']",
    "input[name='user']",
    "input[name='email']",
    "input[type='email']",
    "input[type='text']",
)
PASSWORD_SELECTORS = (
    "#password",
    "input[name='password']",
    "input[name='pass']",
    "input[type='password']",
)
SUBMIT_SELECTORS = (
    "button[type='submit']",
    "input[type='submit']",
    "button:has-text('Iniciar sesion')",
    "button:has-text('Iniciar sesión')",
    "button:has-text('Acceder')",
    "button:has-text('Entrar')",
    "button:has-text('Login')",
    "button:has-text('Ingresar')",
    "button:has-text('Sign in')",
)
SPINNER_SELECTORS = (
    ".spinner",
    ".loading",
    ".loader",
    ".ant-spin",
    ".mat-progress-spinner",
    ".mat-spinner",
    ".v-progress-circular",
    ".progress-spinner",
    "[role='progressbar']",
    "[aria-busy='true']",
)
LOGIN_CONFIRMATION_TIMEOUT_SECONDS = 30
LOGIN_WAIT_SCREENSHOT_INTERVAL_SECONDS = 5
SESSION_CHECK_URL = "https://gig-os.com/en/dashboard"
AUTH_TEXT_MARKERS = (
    "my profile",
    "subscriptions",
    "resources",
    "activation codes",
    "customer support",
    "exit",
    "mi perfil",
    "suscripciones",
    "recursos",
    "códigos de activación",
    "codigos de activacion",
    "atención al cliente",
    "atencion al cliente",
    "salida",
)
PUBLIC_LOGIN_TEXT_MARKERS = (
    "iniciar sesión",
    "iniciar sesion",
    "sign in",
    "registrarse",
    "crear una cuenta",
    "forgot your password",
    "olvidaste tu contraseña",
    "olvidaste tu contrasena",
)


@dataclass(frozen=True)
class LoginTestResult:
    success: bool
    reused_state: bool
    state_path: Path
    final_url: str
    message: str
    screenshot_path: Path | None = None


@dataclass(frozen=True)
class LoginWaitStatus:
    elapsed_seconds: float
    current_url: str
    url_changed: bool
    login_form_visible: bool
    login_form_disappeared: bool
    authenticated_element_visible: bool
    spinner_visible: bool
    spinner_disappeared: bool
    condition: str | None = None


@dataclass(frozen=True)
class LoginWaitResult:
    confirmed: bool
    status: LoginWaitStatus


def run_gig_os_login_test(config: AppConfig, logger: logging.Logger) -> LoginTestResult:
    gig_os = config.gig_os
    _validate_gig_os_config(gig_os)

    state_path = config.project_root / "data" / "browser_state" / "gig_os_state.json"
    screenshot_dir = config.project_root / "data" / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Starting GIG-OS login test.")
    logger.info("GIG-OS login URL: %s", gig_os.login_url)
    logger.info("GIG-OS browser state path: %s", state_path)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=False,
            slow_mo=config.slow_mo_ms,
        )
        try:
            if state_path.exists():
                logger.info("Existing GIG-OS browser state found. Validating session.")
                context = browser.new_context(storage_state=str(state_path))
                page = context.new_page()
                try:
                    _goto_session_check_page(page, gig_os, config)
                    if _is_logged_in(page, gig_os, logger):
                        logger.info("Existing GIG-OS session is valid. Login skipped.")
                        final_url = page.url
                        context.close()
                        return LoginTestResult(
                            success=True,
                            reused_state=True,
                            state_path=state_path,
                            final_url=final_url,
                            message="Existing GIG-OS session is valid.",
                        )
                    logger.info("Existing GIG-OS session is not valid. Login required.")
                finally:
                    context.close()

            context = browser.new_context()
            page = context.new_page()
            try:
                login_wait = _perform_login(page, gig_os, config, screenshot_dir, logger)
                if not login_wait.confirmed and not _is_logged_in(page, gig_os, logger):
                    raise RuntimeError(
                        "GIG-OS login could not be confirmed. Configure "
                        "GIG_OS_LOGIN_SUCCESS_SELECTOR or GIG_OS_LOGOUT_SELECTOR "
                        "if the automatic heuristic is not enough."
                    )

                context.storage_state(path=str(state_path))
                logger.info("GIG-OS authenticated state saved: %s", state_path)
                final_url = page.url
                return LoginTestResult(
                    success=True,
                    reused_state=False,
                    state_path=state_path,
                    final_url=final_url,
                    message="GIG-OS login completed successfully.",
                )
            except Exception as exc:
                screenshot_path = _capture_error_screenshot(page, screenshot_dir, logger)
                logger.error("GIG-OS login test failed: %s", exc)
                return LoginTestResult(
                    success=False,
                    reused_state=False,
                    state_path=state_path,
                    final_url=page.url,
                    message=str(exc),
                    screenshot_path=screenshot_path,
                )
            finally:
                context.close()
        finally:
            browser.close()
            logger.info("GIG-OS browser closed.")


def _validate_gig_os_config(gig_os: PlatformConfig) -> None:
    missing = []
    if not gig_os.login_url:
        missing.append("GIG_OS_LOGIN_URL")
    if not gig_os.username:
        missing.append("GIG_OS_USERNAME")
    if not gig_os.password:
        missing.append("GIG_OS_PASSWORD")
    if missing:
        raise ValueError(f"Missing required GIG-OS .env values: {', '.join(missing)}")


def _goto_session_check_page(page: Page, gig_os: PlatformConfig, config: AppConfig) -> None:
    page.goto(SESSION_CHECK_URL, wait_until="domcontentloaded", timeout=config.request_timeout_seconds * 1000)
    _wait_for_page_settle(page, config)


def _perform_login(
    page: Page,
    gig_os: PlatformConfig,
    config: AppConfig,
    screenshot_dir: Path,
    logger: logging.Logger,
) -> LoginWaitResult:
    logger.info("Opening GIG-OS login page.")
    page.goto(
        gig_os.login_url,
        wait_until="domcontentloaded",
        timeout=config.request_timeout_seconds * 1000,
    )
    _wait_for_page_settle(page, config)

    username_selector = _first_working_selector(
        page,
        _selector_candidates(gig_os.username_selector, USERNAME_SELECTORS),
        "username",
        logger,
    )
    password_selector = _first_working_selector(
        page,
        _selector_candidates(gig_os.password_selector, PASSWORD_SELECTORS),
        "password",
        logger,
    )

    logger.info("Filling GIG-OS username field with selector: %s", username_selector)
    page.locator(username_selector).first.fill(gig_os.username)
    logger.info("Filling GIG-OS password field with selector: %s", password_selector)
    page.locator(password_selector).first.fill(gig_os.password)

    submit_selector = _optional_first_working_selector(
        page,
        _selector_candidates(gig_os.submit_selector, SUBMIT_SELECTORS),
        logger,
    )
    logger.info(
        "Submitting GIG-OS login form%s",
        f" with selector: {submit_selector}" if submit_selector else " by pressing Enter",
    )
    initial_url = page.url
    if submit_selector:
        page.locator(submit_selector).first.click()
    else:
        page.locator(password_selector).first.press("Enter")

    return _wait_for_login_confirmation(
        page=page,
        gig_os=gig_os,
        config=config,
        initial_url=initial_url,
        screenshot_dir=screenshot_dir / "login_wait",
        logger=logger,
    )


def _selector_candidates(primary: str, defaults: tuple[str, ...]) -> tuple[str, ...]:
    if primary.strip():
        return (primary.strip(), *defaults)
    return defaults


def _first_working_selector(
    page: Page,
    selectors: tuple[str, ...],
    field_name: str,
    logger: logging.Logger,
) -> str:
    selector = _optional_first_working_selector(page, selectors, logger)
    if selector:
        return selector
    raise RuntimeError(f"Could not find GIG-OS {field_name} field.")


def _optional_first_working_selector(
    page: Page,
    selectors: tuple[str, ...],
    logger: logging.Logger,
) -> str | None:
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if locator.count() > 0 and locator.is_visible(timeout=750):
                return selector
        except (PlaywrightError, PlaywrightTimeoutError):
            logger.debug("Selector not usable on current page: %s", selector)
    return None


def _is_logged_in(page: Page, gig_os: PlatformConfig, logger: logging.Logger) -> bool:
    if _authenticated_indicator_visible(page, gig_os):
        logger.info("GIG-OS authenticated indicator detected.")
        return True

    password_visible = any(_selector_visible(page, selector) for selector in PASSWORD_SELECTORS)
    current_url = page.url.lower()
    public_login_visible = _public_login_visible(page)

    logger.info(
        "GIG-OS login not confirmed. current_url=%s password_visible=%s public_login_visible=%s dashboard_url=%s",
        page.url,
        password_visible,
        public_login_visible,
        "/dashboard" in current_url,
    )
    return False


def _wait_for_login_confirmation(
    page: Page,
    gig_os: PlatformConfig,
    config: AppConfig,
    initial_url: str,
    screenshot_dir: Path,
    logger: logging.Logger,
) -> LoginWaitResult:
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    timeout_seconds = LOGIN_CONFIRMATION_TIMEOUT_SECONDS
    start_time = time.monotonic()
    next_screenshot_at = 0.0
    form_was_visible = _login_form_visible(page, gig_os)
    spinner_seen = _spinner_visible(page)

    logger.info(
        "Initial GIG-OS login wait state: url=%s form_visible=%s spinner_visible=%s",
        page.url,
        form_was_visible,
        spinner_seen,
    )

    while True:
        elapsed = time.monotonic() - start_time
        url_changed = page.url.rstrip("/") != initial_url.rstrip("/")
        login_form_visible = _login_form_visible(page, gig_os)
        authenticated_element_visible = _authenticated_indicator_visible(page, gig_os)
        spinner_visible = _spinner_visible(page)
        form_disappeared = form_was_visible and not login_form_visible
        spinner_disappeared = spinner_seen and not spinner_visible

        condition: str | None = None
        if authenticated_element_visible:
            condition = "authenticated_selector"
        elif "/dashboard" in page.url.lower() and not login_form_visible and not _public_login_visible(page):
            condition = "dashboard_without_login_form"

        status = LoginWaitStatus(
            elapsed_seconds=elapsed,
            current_url=page.url,
            url_changed=url_changed,
            login_form_visible=login_form_visible,
            login_form_disappeared=form_disappeared,
            authenticated_element_visible=authenticated_element_visible,
            spinner_visible=spinner_visible,
            spinner_disappeared=spinner_disappeared,
            condition=condition,
        )

        if elapsed >= next_screenshot_at:
            path = _capture_wait_screenshot(page, screenshot_dir, int(elapsed), logger, "gig_os")
            logger.info("GIG-OS login wait screenshot saved: %s", path)
            next_screenshot_at += LOGIN_WAIT_SCREENSHOT_INTERVAL_SECONDS

        logger.info(
            "GIG-OS login wait status: elapsed=%.1fs url=%s form_visible=%s "
            "form_disappeared=%s spinner_visible=%s spinner_disappeared=%s auth_element=%s",
            elapsed,
            page.url,
            login_form_visible,
            form_disappeared,
            spinner_visible,
            spinner_disappeared,
            authenticated_element_visible,
        )
        logger.debug(
            "GIG-OS login wait event: elapsed=%.1fs url=%s url_changed=%s form_visible=%s "
            "form_disappeared=%s auth_element=%s spinner_visible=%s spinner_disappeared=%s",
            elapsed,
            page.url,
            url_changed,
            login_form_visible,
            form_disappeared,
            authenticated_element_visible,
            spinner_visible,
            spinner_disappeared,
        )

        if condition:
            logger.info(
                "GIG-OS login confirmation detected after %.1fs: condition=%s url=%s "
                "form_visible=%s spinner_visible=%s spinner_disappeared=%s",
                elapsed,
                condition,
                page.url,
                login_form_visible,
                spinner_visible,
                spinner_disappeared,
            )
            return LoginWaitResult(confirmed=True, status=status)

        if elapsed >= timeout_seconds:
            return LoginWaitResult(confirmed=False, status=status)

        time.sleep(0.75)


def _login_form_visible(page: Page, gig_os: PlatformConfig) -> bool:
    selectors = _selector_candidates(gig_os.username_selector, USERNAME_SELECTORS)
    return any(_selector_visible(page, selector) for selector in selectors)


def _authenticated_indicator_visible(page: Page, gig_os: PlatformConfig) -> bool:
    selectors = tuple(
        selector
        for selector in (
            gig_os.login_success_selector.strip(),
            gig_os.logout_selector.strip(),
        )
        if selector
    )
    if any(_selector_visible(page, selector) for selector in selectors):
        return True
    try:
        body_text = page.locator("body").inner_text(timeout=1_000).lower()
    except Exception:
        body_text = ""
    if not body_text:
        return False
    has_auth_marker = any(marker in body_text for marker in AUTH_TEXT_MARKERS)
    has_public_login_marker = any(marker in body_text for marker in PUBLIC_LOGIN_TEXT_MARKERS)
    return has_auth_marker and not has_public_login_marker


def _public_login_visible(page: Page) -> bool:
    try:
        password_visible = page.locator("input[type='password']").first.is_visible(timeout=500)
    except Exception:
        password_visible = False
    try:
        body_text = page.locator("body").inner_text(timeout=1_000).lower()
    except Exception:
        body_text = ""
    has_public_marker = any(marker in body_text for marker in PUBLIC_LOGIN_TEXT_MARKERS)
    return password_visible or has_public_marker


def _spinner_visible(page: Page) -> bool:
    return any(_selector_visible(page, selector) for selector in SPINNER_SELECTORS)


def _selector_visible(page: Page, selector: str) -> bool:
    if not selector:
        return False
    try:
        locator = page.locator(selector).first
        return locator.count() > 0 and locator.is_visible(timeout=500)
    except Exception:
        return False


def _wait_for_page_settle(page: Page, config: AppConfig) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=config.request_timeout_seconds * 1000)
    except PlaywrightTimeoutError:
        page.wait_for_load_state("domcontentloaded", timeout=config.request_timeout_seconds * 1000)


def _capture_wait_screenshot(
    page: Page,
    screenshot_dir: Path,
    elapsed_seconds: int,
    logger: logging.Logger,
    prefix: str,
) -> Path:
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = screenshot_dir / f"{prefix}_login_wait_{timestamp}_{elapsed_seconds:02d}s.png"
    page.screenshot(path=str(path), full_page=True)
    return path


def _capture_error_screenshot(page: Page, screenshot_dir: Path, logger: logging.Logger) -> Path | None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = screenshot_dir / f"gig_os_login_error_{timestamp}.png"
    try:
        page.screenshot(path=str(path), full_page=True)
        logger.error("GIG-OS login error screenshot saved: %s", path)
        return path
    except Exception as exc:
        logger.error("Could not capture GIG-OS error screenshot: %s", exc)
        return None
