from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from playwright.sync_api import (
    Browser,
    BrowserContext,
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


def run_olympia_login_test(config: AppConfig, logger: logging.Logger) -> LoginTestResult:
    olympia = config.olympia
    _validate_olympia_config(olympia)

    state_path = config.project_root / "data" / "browser_state" / "olympia_state.json"
    screenshot_dir = config.project_root / "data" / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Starting Olympia login test.")
    logger.info("Olympia login URL: %s", olympia.login_url)
    logger.info("Olympia browser state path: %s", state_path)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=False,
            slow_mo=config.slow_mo_ms,
        )
        try:
            if state_path.exists():
                logger.info("Existing Olympia browser state found. Validating session.")
                context = browser.new_context(storage_state=str(state_path))
                page = context.new_page()
                try:
                    _goto_session_check_page(page, olympia, config)
                    if _is_logged_in(page, olympia, logger):
                        logger.info("Existing Olympia session is valid. Login skipped.")
                        final_url = page.url
                        context.close()
                        return LoginTestResult(
                            success=True,
                            reused_state=True,
                            state_path=state_path,
                            final_url=final_url,
                            message="Existing Olympia session is valid.",
                        )
                    logger.info("Existing Olympia session is not valid. Login required.")
                finally:
                    context.close()

            context = browser.new_context()
            page = context.new_page()
            try:
                login_wait = _perform_login(page, olympia, config, screenshot_dir, logger)
                if not login_wait.confirmed and not _is_logged_in(page, olympia, logger):
                    raise RuntimeError(
                        "Olympia login could not be confirmed. Configure "
                        "OLYMPIA_LOGIN_SUCCESS_SELECTOR or OLYMPIA_LOGOUT_SELECTOR "
                        "if the automatic heuristic is not enough."
                    )

                context.storage_state(path=str(state_path))
                logger.info("Olympia authenticated state saved: %s", state_path)
                final_url = page.url
                return LoginTestResult(
                    success=True,
                    reused_state=False,
                    state_path=state_path,
                    final_url=final_url,
                    message="Olympia login completed successfully.",
                )
            except Exception as exc:
                screenshot_path = _capture_error_screenshot(page, screenshot_dir, logger)
                logger.error("Olympia login test failed: %s", exc)
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
            logger.info("Olympia browser closed.")


def _validate_olympia_config(olympia: PlatformConfig) -> None:
    missing = []
    if not olympia.login_url:
        missing.append("OLYMPIA_LOGIN_URL")
    if not olympia.username:
        missing.append("OLYMPIA_USERNAME")
    if not olympia.password:
        missing.append("OLYMPIA_PASSWORD")

    if missing:
        raise ValueError(f"Missing required Olympia .env values: {', '.join(missing)}")


def _goto_session_check_page(page: Page, olympia: PlatformConfig, config: AppConfig) -> None:
    url = olympia.base_url or olympia.login_url
    page.goto(url, wait_until="domcontentloaded", timeout=config.request_timeout_seconds * 1000)
    _wait_for_page_settle(page, config)


def _perform_login(
    page: Page,
    olympia: PlatformConfig,
    config: AppConfig,
    screenshot_dir: Path,
    logger: logging.Logger,
) -> LoginWaitResult:
    logger.info("Opening Olympia login page.")
    page.goto(
        olympia.login_url,
        wait_until="domcontentloaded",
        timeout=config.request_timeout_seconds * 1000,
    )
    _wait_for_page_settle(page, config)

    username_selector = _first_working_selector(
        page,
        _selector_candidates(olympia.username_selector, USERNAME_SELECTORS),
        "username",
        logger,
    )
    password_selector = _first_working_selector(
        page,
        _selector_candidates(olympia.password_selector, PASSWORD_SELECTORS),
        "password",
        logger,
    )

    logger.info("Filling Olympia username field with selector: %s", username_selector)
    page.locator(username_selector).first.fill(olympia.username)
    logger.info("Filling Olympia password field with selector: %s", password_selector)
    page.locator(password_selector).first.fill(olympia.password)

    submit_selector = _optional_first_working_selector(
        page,
        _selector_candidates(olympia.submit_selector, SUBMIT_SELECTORS),
        logger,
    )
    logger.info(
        "Submitting Olympia login form%s",
        f" with selector: {submit_selector}" if submit_selector else " by pressing Enter",
    )
    initial_url = page.url
    if submit_selector:
        page.locator(submit_selector).first.click()
    else:
        page.locator(password_selector).first.press("Enter")

    return _wait_for_login_confirmation(
        page=page,
        olympia=olympia,
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
    raise RuntimeError(f"Could not find Olympia {field_name} field.")


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


def _is_logged_in(page: Page, olympia: PlatformConfig, logger: logging.Logger) -> bool:
    if olympia.login_success_selector and _selector_visible(page, olympia.login_success_selector):
        logger.info("Olympia login success selector detected.")
        return True

    if olympia.logout_selector and _selector_visible(page, olympia.logout_selector):
        logger.info("Olympia logout selector detected.")
        return True

    password_visible = any(_selector_visible(page, selector) for selector in PASSWORD_SELECTORS)
    current_url = page.url.lower()
    login_url = olympia.login_url.lower()
    still_on_login_url = current_url.rstrip("/") == login_url.rstrip("/")

    if not password_visible and not still_on_login_url:
        logger.info("Olympia login inferred from URL change and hidden password field.")
        return True

    logger.info(
        "Olympia login not confirmed. current_url=%s password_visible=%s still_on_login_url=%s",
        page.url,
        password_visible,
        still_on_login_url,
    )
    return False


def _wait_for_login_confirmation(
    page: Page,
    olympia: PlatformConfig,
    config: AppConfig,
    initial_url: str,
    screenshot_dir: Path,
    logger: logging.Logger,
) -> LoginWaitResult:
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    timeout_seconds = LOGIN_CONFIRMATION_TIMEOUT_SECONDS
    start_time = time.monotonic()
    next_screenshot_at = 0.0
    form_was_visible = _login_form_visible(page, olympia)
    spinner_seen = _spinner_visible(page)
    last_status = _collect_login_wait_status(
        page=page,
        olympia=olympia,
        initial_url=initial_url,
        start_time=start_time,
        form_was_visible=form_was_visible,
        spinner_was_visible=spinner_seen,
    )

    logger.info("Waiting up to %s seconds for Olympia login confirmation.", timeout_seconds)
    logger.info(
        "Initial login wait state: url=%s form_visible=%s spinner_visible=%s",
        initial_url,
        form_was_visible,
        spinner_seen,
    )

    while last_status.elapsed_seconds <= timeout_seconds:
        spinner_seen = spinner_seen or last_status.spinner_visible
        if last_status.elapsed_seconds >= next_screenshot_at:
            _capture_login_wait_screenshot(page, screenshot_dir, last_status.elapsed_seconds, logger)
            logger.info(
                "Olympia login wait status: elapsed=%.1fs url=%s "
                "form_visible=%s form_disappeared=%s spinner_visible=%s "
                "spinner_disappeared=%s auth_element=%s",
                last_status.elapsed_seconds,
                last_status.current_url,
                last_status.login_form_visible,
                last_status.login_form_disappeared,
                last_status.spinner_visible,
                last_status.spinner_disappeared,
                last_status.authenticated_element_visible,
            )
            next_screenshot_at += LOGIN_WAIT_SCREENSHOT_INTERVAL_SECONDS

        logger.debug(
            "Olympia login wait event: elapsed=%.1fs url=%s url_changed=%s "
            "form_visible=%s form_disappeared=%s auth_element=%s "
            "spinner_visible=%s spinner_disappeared=%s",
            last_status.elapsed_seconds,
            last_status.current_url,
            last_status.url_changed,
            last_status.login_form_visible,
            last_status.login_form_disappeared,
            last_status.authenticated_element_visible,
            last_status.spinner_visible,
            last_status.spinner_disappeared,
        )

        condition = _login_confirmation_condition(last_status)
        if condition:
            confirmed_status = LoginWaitStatus(
                elapsed_seconds=last_status.elapsed_seconds,
                current_url=last_status.current_url,
                url_changed=last_status.url_changed,
                login_form_visible=last_status.login_form_visible,
                login_form_disappeared=last_status.login_form_disappeared,
                authenticated_element_visible=last_status.authenticated_element_visible,
                spinner_visible=last_status.spinner_visible,
                spinner_disappeared=last_status.spinner_disappeared,
                condition=condition,
            )
            logger.info(
                "Olympia login confirmation detected after %.1fs: condition=%s "
                "url=%s form_visible=%s spinner_visible=%s spinner_disappeared=%s",
                confirmed_status.elapsed_seconds,
                condition,
                confirmed_status.current_url,
                confirmed_status.login_form_visible,
                confirmed_status.spinner_visible,
                confirmed_status.spinner_disappeared,
            )
            return LoginWaitResult(confirmed=True, status=confirmed_status)

        page.wait_for_timeout(1000)
        last_status = _collect_login_wait_status(
            page=page,
            olympia=olympia,
            initial_url=initial_url,
            start_time=start_time,
            form_was_visible=form_was_visible,
            spinner_was_visible=spinner_seen,
        )

    logger.info(
        "Olympia login wait timed out after %.1fs: url=%s form_visible=%s "
        "form_disappeared=%s spinner_visible=%s spinner_disappeared=%s",
        last_status.elapsed_seconds,
        last_status.current_url,
        last_status.login_form_visible,
        last_status.login_form_disappeared,
        last_status.spinner_visible,
        last_status.spinner_disappeared,
    )
    return LoginWaitResult(confirmed=False, status=last_status)


def _collect_login_wait_status(
    page: Page,
    olympia: PlatformConfig,
    initial_url: str,
    start_time: float,
    form_was_visible: bool,
    spinner_was_visible: bool,
) -> LoginWaitStatus:
    elapsed_seconds = time.monotonic() - start_time
    current_url = page.url
    form_visible = _login_form_visible(page, olympia)
    spinner_visible = _spinner_visible(page)
    authenticated_element_visible = _authenticated_element_visible(page, olympia)
    return LoginWaitStatus(
        elapsed_seconds=elapsed_seconds,
        current_url=current_url,
        url_changed=_normalize_url(current_url) != _normalize_url(initial_url),
        login_form_visible=form_visible,
        login_form_disappeared=form_was_visible and not form_visible,
        authenticated_element_visible=authenticated_element_visible,
        spinner_visible=spinner_visible,
        spinner_disappeared=spinner_was_visible and not spinner_visible,
    )


def _login_confirmation_condition(status: LoginWaitStatus) -> str | None:
    if status.url_changed:
        return "url_changed"
    if status.login_form_disappeared:
        return "login_form_disappeared"
    if status.authenticated_element_visible:
        return "authenticated_element_visible"
    if status.spinner_disappeared:
        return "spinner_disappeared"
    return None


def _login_form_visible(page: Page, olympia: PlatformConfig) -> bool:
    username_selectors = _selector_candidates(olympia.username_selector, USERNAME_SELECTORS)
    password_selectors = _selector_candidates(olympia.password_selector, PASSWORD_SELECTORS)
    return any(_selector_visible(page, selector) for selector in (*username_selectors, *password_selectors))


def _authenticated_element_visible(page: Page, olympia: PlatformConfig) -> bool:
    return bool(
        (olympia.login_success_selector and _selector_visible(page, olympia.login_success_selector))
        or (olympia.logout_selector and _selector_visible(page, olympia.logout_selector))
    )


def _spinner_visible(page: Page) -> bool:
    return any(_selector_visible(page, selector) for selector in SPINNER_SELECTORS)


def _normalize_url(url: str) -> str:
    return url.rstrip("/")


def _capture_login_wait_screenshot(
    page: Page,
    screenshot_dir: Path,
    elapsed_seconds: float,
    logger: logging.Logger,
) -> Path | None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    elapsed_label = int(elapsed_seconds)
    screenshot_path = screenshot_dir / f"olympia_login_wait_{timestamp}_{elapsed_label:02d}s.png"
    try:
        page.screenshot(path=str(screenshot_path), full_page=True)
        logger.info("Olympia login wait screenshot saved: %s", screenshot_path)
        return screenshot_path
    except Exception as screenshot_error:
        logger.error("Could not capture Olympia login wait screenshot: %s", screenshot_error)
        return None


def _selector_visible(page: Page, selector: str) -> bool:
    try:
        locator = page.locator(selector).first
        return locator.count() > 0 and locator.is_visible(timeout=750)
    except (PlaywrightError, PlaywrightTimeoutError):
        return False


def _wait_for_page_settle(page: Page, config: AppConfig) -> None:
    timeout_ms = config.request_timeout_seconds * 1000
    try:
        page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except PlaywrightTimeoutError:
        page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)


def _capture_error_screenshot(
    page: Page,
    screenshot_dir: Path,
    logger: logging.Logger,
) -> Path | None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_path = screenshot_dir / f"olympia_login_error_{timestamp}.png"
    try:
        page.screenshot(path=str(screenshot_path), full_page=True)
        logger.error("Olympia login error screenshot saved: %s", screenshot_path)
        return screenshot_path
    except Exception as screenshot_error:
        logger.error("Could not capture Olympia error screenshot: %s", screenshot_error)
        return None
