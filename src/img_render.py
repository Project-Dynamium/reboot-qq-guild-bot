import asyncio, os
from playwright.async_api import async_playwright

work_path = os.path.dirname(__file__)

class Render:
    def __init__(self):
        self.is_inital = False

    async def inital_browser(self):
        if self.is_inital: 
            return
        if not os.path.exists(f"{work_path}/empty.html"):
            with open(f"{work_path}/empty.html", "w", encoding="utf-8") as f:
                f.write("")
        self.playwright = await async_playwright().start()
        # self.browser = await self.playwright.chromium.launch(headless=True,args=["--no-sandbox","--remote-debugging-address=0.0.0.0","--remote-debugging-port=9222","--disable-web-security","--allow-file-access-from-files","--allow-file-access"])
        self.browser = await self.playwright.chromium.launch(headless=True,args=["--no-sandbox","--disable-web-security","--allow-file-access-from-files","--allow-file-access"])
        self.context = await self.browser.new_context(viewport={"width": 700, "height": 1300})
        self.is_inital = True

    async def screenshot(self, html, clip: dict) -> bytes:
        if not self.is_inital: 
            await self.inital_browser()
        page = await self.context.new_page()
        await page.goto(f"file://{work_path}/empty.html")
        await page.set_content(html)
        buffer = await page.screenshot(clip=clip)
        await page.close()
        return buffer

    async def close_browser(self):
        self.is_inital = False
        del self.browser
        del self.playwright
        return
        # 用自带的异步方法结束会卡死 我也不知道为什么 可能是 asyncio.run() 不给跑了
        await self.browser.close()
        await self.playwright.stop()
    
    async def __aenter__(self):
        await self.inital_browser()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close_browser()

    def __del__(self):
        del self.is_inital
        del self.browser
        del self.playwright

