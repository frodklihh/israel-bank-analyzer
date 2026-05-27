from __future__ import annotations

from pathlib import Path

from playwright.async_api import Page

from config.settings import BankCredentials
from fetcher import session
from fetcher.base import BankFetcher

async def _ng_set_value(page, selector: str, value: str) -> None:
    """Set an input value in Angular/AngularJS by using the native value setter
    and firing both 'input' and 'change' events so the framework picks it up."""
    await page.evaluate(
        """([sel, val]) => {
            const el = document.querySelector(sel);
            if (!el) return;
            const setter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value'
            ).set;
            setter.call(el, val);
            el.dispatchEvent(new Event('input',  { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            // AngularJS: trigger digest if angular is present
            try {
                const scope = window.angular.element(el).scope();
                scope && scope.$apply && scope.$apply();
            } catch (_) {}
        }""",
        [selector, value],
    )


_LOGIN_URL = "https://www.isracard.co.il/"
_PROTECTED_URL = "https://web.isracard.co.il/StatusPage"
# Month is selected via query param: monthAndYear=MM.YYYY
_TRANSACTIONS_URL = "https://web.isracard.co.il/transactions?monthAndYear={month:02d}.{year}"

# When the session expires Isracard redirects back to www.isracard.co.il.
_LOGIN_MARKER = "www.isracard.co.il"

# ── Selectors ────────────────────────────────────────────────────────────────

# Last 4 digits of the currently displayed card number.
_SEL_CARD_TITLE = '[aria-label^="מספר כרטיס המסתיים ב"]'

# Arrow button to advance to the next card in the carousel.
_SEL_NEXT_CARD = '[aria-label="הבא"]'

# Download / export button for the currently shown card+month.
_SEL_DOWNLOAD = '[aria-label="download excel"]'
# ─────────────────────────────────────────────────────────────────────────────


class IsracardFetcher(BankFetcher):
    """Fetcher for Isracard credit card (isracard.co.il).

    Credentials:
        user     — Israeli ID number (תעודת זהות)
        password — last 4 digits of any Isracard card (entered digit by digit)

    Login flow:
        1. Fill ID + 4 card-digit inputs → click "שלח קוד לנייד" (send SMS OTP).
        2. Enter the 6-digit SMS code → click "כניסה לחשבון שלי" (confirm).
    """

    name = "isracard"

    def __init__(self, credentials: BankCredentials) -> None:
        self._credentials = credentials

    async def login(self, page: Page) -> None:
        if await session.is_authenticated(page, _PROTECTED_URL, _LOGIN_MARKER):
            print("[isracard] session valid — skipping login")
            return

        print("[isracard] logging in...")
        await page.goto(_LOGIN_URL, wait_until="networkidle")
        await page.screenshot(path="isracard_login_debug.png")
        print(f"[isracard] landed on: {page.url}")
        count = await page.locator("#otpLoginId_SMS").count()
        print(f"[isracard] #otpLoginId_SMS found: {count}")

        id_input = page.locator("#otpLoginId_SMS")
        await id_input.wait_for(state="visible")
        await _ng_set_value(page, "#otpLoginId_SMS", self._credentials.user)

        # The last 4 card digits are split across 4 individual inputs.
        digit_inputs = page.locator(".otp-digit-input")
        await digit_inputs.first.wait_for(state="visible")
        for i, digit in enumerate(self._credentials.password):
            await _ng_set_value(page, f".otp-digit-input:nth-child({i + 1})", digit)

        await page.get_by_role("button", name="שלח קוד לנייד").click()

        otp_input = page.locator("#otpInput")
        await otp_input.wait_for(state="visible", timeout=20_000)
        code = input("[isracard] enter SMS code: ").strip()
        await otp_input.fill(code)

        await page.get_by_role("button", name="כניסה לחשבון שלי").click()
        await page.wait_for_url(f"**{_PROTECTED_URL}**", timeout=15_000)

        print("[isracard] login complete")

    async def download_statement(
        self,
        page: Page,
        year: int,
        month: int,
        dest: Path,
    ) -> list[Path]:
        url = _TRANSACTIONS_URL.format(month=month, year=year)
        await page.goto(url, wait_until="networkidle")

        # React SPA may still be rendering after networkidle — wait for the card element.
        card_locator = page.locator(_SEL_CARD_TITLE).first
        try:
            await card_locator.wait_for(state="visible", timeout=30_000)
        except Exception:
            screenshot = dest / "isracard_debug.png"
            await page.screenshot(path=str(screenshot))
            print(f"[isracard] card element not found — screenshot saved to {screenshot}")
            return []

        downloaded: list[Path] = []
        first_card_title: str | None = None

        while True:
            title_el = page.locator(_SEL_CARD_TITLE)
            current_title = (await title_el.text_content() or "").strip()

            if first_card_title is None:
                first_card_title = current_title
            elif current_title == first_card_title:
                # Carousel completed a full loop — all cards processed.
                break

            print(f"[isracard] downloading card: {current_title!r}")
            async with page.expect_download() as dl_info:
                await page.locator(_SEL_DOWNLOAD).click()
            download = await dl_info.value
            out = dest / download.suggested_filename
            await download.save_as(out)
            downloaded.append(out)

            # Advance to next card in carousel.
            await page.locator(_SEL_NEXT_CARD).click()
            await page.wait_for_load_state("networkidle")

        if not downloaded:
            print(f"[isracard] warning: no files downloaded for {month}/{year}")

        return downloaded
