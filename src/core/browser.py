"""Browser management for web scraping using Playwright.

This module provides:
- BrowserManager: Launch and manage Playwright browser instances
- PageUtils: Utility functions for human-like page interactions
- Anti-detection features to avoid bot detection
- Session persistence for maintaining login state across runs
"""

import asyncio
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
)

from src.utils.logger import get_logger

logger = get_logger("browser")


# ============================================================================
# Error Classes
# ============================================================================


class BrowserError(Exception):
    """Base browser exception."""
    pass


class BrowserLaunchError(BrowserError):
    """Failed to launch browser."""
    pass


class SessionExpiredError(BrowserError):
    """Session cookies expired."""
    pass


class ElementNotFoundError(BrowserError):
    """Required element not found."""
    pass


class NavigationError(BrowserError):
    """Page navigation failed."""
    pass


# ============================================================================
# BrowserManager Class
# ============================================================================


class BrowserManager:
    """Manages Playwright browser instances and contexts.

    Features:
    - Anti-detection configuration (disable webdriver detection)
    - Session persistence (cookies, localStorage, sessionStorage)
    - Multiple browser contexts for different platforms
    - Context manager support for automatic cleanup

    Example:
        async with BrowserManager() as browser:
            page = await browser.new_page("linkedin")
            await page.goto("https://www.linkedin.com/jobs")
            await browser.save_session("linkedin")
    """

    def __init__(
        self,
        headless: bool = False,
        data_dir: str = "data/browser_data",
        proxy: Optional[str] = None
    ):
        """Initialize browser manager.

        Args:
            headless: Run browser in headless mode (default: False for anti-detection)
            data_dir: Directory to store browser data and sessions
            proxy: Proxy URL in format "http://user:pass@host:port" (optional)
        """
        self.headless = headless
        self.data_dir = Path(data_dir)
        self.proxy = proxy
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._contexts: Dict[str, BrowserContext] = {}
        self._lock = asyncio.Lock()

        logger.info(
            "BrowserManager initialized (headless=%s, data_dir=%s, proxy=%s)",
            headless, data_dir, "configured" if proxy else "none"
        )

    async def launch(self) -> Browser:
        """Launch browser instance with anti-detection configuration.

        Returns:
            Browser instance

        Raises:
            BrowserLaunchError: If browser fails to launch

        Configuration:
            - Chromium browser (best compatibility with job sites)
            - Headed mode by default (more realistic)
            - Disabled automation indicators
            - Realistic window size
        """
        if self._browser:
            return self._browser

        async with self._lock:
            # Double-check pattern for thread safety
            if self._browser:
                return self._browser

            try:
                logger.info("Launching browser...")
                self._playwright = await async_playwright().start()

                # Anti-detection launch arguments
                launch_args = [
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-infobars",
                    "--window-size=1920,1080",
                ]

                self._browser = await self._playwright.chromium.launch(
                    headless=self.headless,
                    args=launch_args,
                )

                logger.info("Browser launched successfully")
                return self._browser

            except Exception as e:
                logger.error("Failed to launch browser: %s", e, exc_info=True)
                raise BrowserLaunchError(f"Failed to launch browser: {e}") from e

    async def get_context(
        self,
        platform: str,
        load_session: bool = True
    ) -> BrowserContext:
        """Get or create browser context for a platform.

        Each platform gets its own isolated context with separate cookies,
        storage, and session state.

        Args:
            platform: Platform name ('linkedin', 'indeed', 'wellfound')
            load_session: Load saved session if available (default: True)

        Returns:
            BrowserContext configured for the platform

        Raises:
            BrowserLaunchError: If browser launch fails
        """
        # Return existing context if already created
        if platform in self._contexts:
            logger.debug("Returning existing context for %s", platform)
            return self._contexts[platform]

        # Ensure browser is launched
        await self.launch()

        logger.info("Creating new context for %s (load_session=%s)", platform, load_session)

        # Session storage path
        session_path = self.data_dir / platform / "state.json"

        # Context options with anti-detection settings
        context_options = {
            "viewport": {"width": 1920, "height": 1080},
            "user_agent": self._get_user_agent(),
            "locale": "en-US",
            "timezone_id": "America/Los_Angeles",
            "geolocation": {"latitude": 37.7749, "longitude": -122.4194},
            "permissions": ["geolocation"],
        }

        # Add proxy if configured
        if self.proxy:
            context_options["proxy"] = {"server": self.proxy}
            logger.debug("Using proxy for %s", platform)

        # Load saved session if available
        if load_session and session_path.exists():
            context_options["storage_state"] = str(session_path)
            logger.info("Loading saved session from %s", session_path)

        # Create context
        context = await self._browser.new_context(**context_options)

        # Inject anti-detection scripts
        await context.add_init_script("""
            // Remove webdriver property
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});

            // Override plugins to appear more realistic
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});

            // Set realistic languages
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});

            // Add Chrome runtime
            window.chrome = {runtime: {}};
        """)

        self._contexts[platform] = context
        logger.info("Context created for %s", platform)
        return context

    async def save_session(self, platform: str) -> None:
        """Save browser session (cookies, localStorage, sessionStorage) for platform.

        The session is saved to data/browser_data/{platform}/state.json
        This allows maintaining login state across runs.

        Args:
            platform: Platform name
        """
        if platform not in self._contexts:
            logger.warning("Cannot save session for %s: context not found", platform)
            return

        session_path = self.data_dir / platform / "state.json"
        session_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            await self._contexts[platform].storage_state(path=str(session_path))
            logger.info("Session saved for %s to %s", platform, session_path)
        except Exception as e:
            logger.error("Failed to save session for %s: %s", platform, e, exc_info=True)
            raise BrowserError(f"Failed to save session: {e}") from e

    async def new_page(self, platform: str) -> Page:
        """Create new page in platform context.

        Args:
            platform: Platform name

        Returns:
            New Page instance with default timeout configured

        Raises:
            BrowserLaunchError: If browser launch fails
        """
        context = await self.get_context(platform)
        page = await context.new_page()

        # Set default timeout (30 seconds)
        page.set_default_timeout(30000)

        logger.debug("New page created for %s", platform)
        return page

    async def screenshot(
        self,
        page: Page,
        name: str,
        full_page: bool = False
    ) -> str:
        """Take screenshot for debugging.

        Screenshots are saved to data/browser_data/screenshots/

        Args:
            page: Page to screenshot
            name: Screenshot name (without extension)
            full_page: Capture full scrollable page (default: False)

        Returns:
            Path to saved screenshot file

        Raises:
            BrowserError: If screenshot fails
        """
        screenshots_dir = self.data_dir / "screenshots"
        screenshots_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = screenshots_dir / f"{name}_{timestamp}.png"

        try:
            await page.screenshot(path=str(path), full_page=full_page)
            logger.info("Screenshot saved to %s", path)
            return str(path)
        except Exception as e:
            logger.error("Failed to take screenshot: %s", e, exc_info=True)
            raise BrowserError(f"Failed to take screenshot: {e}") from e

    async def close(self) -> None:
        """Close browser and cleanup resources.

        This method:
        1. Saves sessions for all active contexts
        2. Closes all browser contexts
        3. Closes the browser
        4. Stops Playwright
        """
        logger.info("Closing browser...")

        # Close all contexts and save sessions
        for platform, context in list(self._contexts.items()):
            try:
                await self.save_session(platform)
                await context.close()
                logger.debug("Closed context for %s", platform)
            except Exception as e:
                logger.warning("Error closing context %s: %s", platform, e)

        self._contexts.clear()

        # Close browser
        if self._browser:
            try:
                await self._browser.close()
                self._browser = None
                logger.debug("Browser closed")
            except Exception as e:
                logger.warning("Error closing browser: %s", e)

        # Stop Playwright
        if self._playwright:
            try:
                await self._playwright.stop()
                self._playwright = None
                logger.debug("Playwright stopped")
            except Exception as e:
                logger.warning("Error stopping Playwright: %s", e)

        logger.info("Browser cleanup complete")

    def _get_user_agent(self) -> str:
        """Get realistic user agent string.

        Rotates between common user agents to avoid fingerprinting.

        Returns:
            User agent string
        """
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        ]
        return random.choice(user_agents)

    # Context manager support

    async def __aenter__(self):
        """Enter async context manager."""
        await self.launch()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context manager."""
        await self.close()
        return False


# ============================================================================
# PageUtils Class
# ============================================================================


class PageUtils:
    """Utility functions for human-like page interaction.

    All methods are static and designed to mimic human behavior
    to avoid bot detection.
    """

    @staticmethod
    async def random_delay(min_sec: float = 1.0, max_sec: float = 5.0) -> None:
        """Add human-like random delay.

        Args:
            min_sec: Minimum delay in seconds (default: 1.0)
            max_sec: Maximum delay in seconds (default: 5.0)
        """
        delay = random.uniform(min_sec, max_sec)
        logger.debug("Delaying for %.2f seconds", delay)
        await asyncio.sleep(delay)

    @staticmethod
    async def human_type(page: Page, selector: str, text: str) -> None:
        """Type text with human-like delays between keystrokes.

        Args:
            page: Page instance
            selector: Element selector (CSS)
            text: Text to type

        Raises:
            ElementNotFoundError: If element not found
        """
        try:
            element = await page.wait_for_selector(selector)
            await element.click()

            # Type each character with random delay
            for char in text:
                await page.keyboard.type(char)
                await asyncio.sleep(random.uniform(0.05, 0.15))

            logger.debug("Typed text into %s", selector)

        except Exception as e:
            logger.error("Failed to type into %s: %s", selector, e)
            raise ElementNotFoundError(f"Failed to type into {selector}: {e}") from e

    @staticmethod
    async def human_click(page: Page, selector: str) -> None:
        """Click element with slight position randomization.

        Clicks at a random point within the element bounding box
        to appear more human-like.

        Args:
            page: Page instance
            selector: Element selector (CSS)

        Raises:
            ElementNotFoundError: If element not found
        """
        try:
            element = await page.wait_for_selector(selector)
            box = await element.bounding_box()

            if box:
                # Click at random point within element
                x = box["x"] + box["width"] * random.uniform(0.3, 0.7)
                y = box["y"] + box["height"] * random.uniform(0.3, 0.7)
                await page.mouse.click(x, y)
                logger.debug("Clicked %s at (%.1f, %.1f)", selector, x, y)
            else:
                # Fallback to direct click if no bounding box
                await element.click()
                logger.debug("Clicked %s", selector)

        except Exception as e:
            logger.error("Failed to click %s: %s", selector, e)
            raise ElementNotFoundError(f"Failed to click {selector}: {e}") from e

    @staticmethod
    async def scroll_to_bottom(
        page: Page,
        step: int = 500,
        delay: float = 0.5
    ) -> None:
        """Scroll page to bottom to load lazy-loaded content.

        Scrolls in increments until no more content loads.

        Args:
            page: Page instance
            step: Pixels to scroll per step (default: 500)
            delay: Delay between scrolls in seconds (default: 0.5)
        """
        previous_height = 0
        scroll_count = 0

        while True:
            current_height = await page.evaluate("document.body.scrollHeight")

            # Stop if height hasn't changed
            if current_height == previous_height:
                logger.debug("Reached bottom after %d scrolls", scroll_count)
                break

            # Scroll down
            await page.evaluate(f"window.scrollBy(0, {step})")
            await asyncio.sleep(delay)

            previous_height = current_height
            scroll_count += 1

    @staticmethod
    async def wait_for_navigation(page: Page, timeout: int = 30000) -> None:
        """Wait for page navigation to complete.

        Tries networkidle first, falls back to domcontentloaded.

        Args:
            page: Page instance
            timeout: Timeout in milliseconds (default: 30000)

        Raises:
            NavigationError: If navigation times out
        """
        try:
            # Try waiting for network idle
            await page.wait_for_load_state("networkidle", timeout=timeout)
            logger.debug("Navigation complete (networkidle)")
        except Exception:
            try:
                # Fallback to DOM content loaded
                await page.wait_for_load_state("domcontentloaded", timeout=timeout)
                logger.debug("Navigation complete (domcontentloaded)")
            except Exception as e:
                logger.error("Navigation timeout: %s", e)
                raise NavigationError(f"Navigation timeout: {e}") from e

    @staticmethod
    async def safe_click(page: Page, selector: str, timeout: int = 5000) -> bool:
        """Click element if it exists, otherwise return False.

        Useful for optional elements like popups or banners.

        Args:
            page: Page instance
            selector: Element selector (CSS)
            timeout: Wait timeout in milliseconds (default: 5000)

        Returns:
            True if element was clicked, False if not found
        """
        try:
            element = await page.wait_for_selector(selector, timeout=timeout)
            await element.click()
            logger.debug("Safe clicked %s", selector)
            return True
        except Exception as e:
            logger.debug("Element not found for safe click %s: %s", selector, e)
            return False

    @staticmethod
    async def get_text(page: Page, selector: str, default: str = "") -> str:
        """Get text content of element, with default fallback.

        Args:
            page: Page instance
            selector: Element selector (CSS)
            default: Default value if element not found (default: "")

        Returns:
            Text content or default value
        """
        try:
            element = await page.wait_for_selector(selector, timeout=5000)
            text = await element.inner_text()
            logger.debug("Got text from %s: %s", selector, text[:50])
            return text
        except Exception as e:
            logger.debug("Could not get text from %s: %s", selector, e)
            return default
