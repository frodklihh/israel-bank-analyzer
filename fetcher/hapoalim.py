from __future__ import annotations

from pathlib import Path

from playwright.async_api import Page

from config.settings import BankCredentials
from fetcher import session
from fetcher.base import BankFetcher
from fetcher.isracard import _ng_set_value

_LOGIN_URL = "https://digital.bankhapoalim.co.il/"
_TRANSACTIONS_URL = "https://login.bankhapoalim.co.il/ng-portals/rb/he/current-account/transactions"
_PROTECTED_URL = "https://login.bankhapoalim.co.il/ng-portals/rb/he/homepage"

# When the session expires Hapoalim redirects back to digital.bankhapoalim.co.il.
# This domain substring is present in the login page URL but not in authenticated URLs.
_LOGIN_MARKER = "digital.bankhapoalim"


class HapoalimFetcher(BankFetcher):
    """Fetcher for Bank Hapoalim (bankhapoalim.co.il).

    Credentials:
        user     — online banking username (קוד משתמש)
        password — online banking password
    """

    name = "hapoalim"

    def __init__(self, credentials: BankCredentials) -> None:
        self._credentials = credentials

    async def login(self, page: Page) -> None:
        if await session.is_authenticated(page, _PROTECTED_URL, _LOGIN_MARKER):
            print("[hapoalim] session valid — skipping login")
            return

        print("[hapoalim] logging in...")
        await page.goto(_LOGIN_URL, wait_until="networkidle")
        await page.screenshot(path="hapoalim_login_debug.png")
        print(f"[hapoalim] landed on: {page.url}")
        count = await page.locator("#userCode").count()
        print(f"[hapoalim] #userCode found: {count}")

        user_input = page.locator("#userCode")
        await user_input.wait_for(state="visible")
        await _ng_set_value(page, "#userCode", self._credentials.user)

        pass_input = page.locator("#password")
        await pass_input.wait_for(state="visible")
        await _ng_set_value(page, "#password", self._credentials.password)

        await page.get_by_role("button", name="כניסה").click()

        await page.wait_for_url(f"**{_PROTECTED_URL}**", timeout=15_000)
        print("[hapoalim] login complete")

    async def download_statement(
        self,
        page: Page,
        year: int,
        month: int,
        dest: Path,
    ) -> list[Path]:
        await page.goto(_TRANSACTIONS_URL, wait_until="networkidle")

        async with page.expect_download() as dl_info:
            await page.locator("a.kite-export-button").click()

        download = await dl_info.value
        out = dest / download.suggested_filename
        await download.save_as(out)
        return [out]
