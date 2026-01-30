"""Unit tests for browser management module.

Tests cover:
- BrowserManager lifecycle (launch, contexts, cleanup)
- Session persistence (save/load)
- PageUtils human-like interactions
- Error handling
- Anti-detection features
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, ANY

import pytest

from src.core.browser import (
    BrowserManager,
    PageUtils,
    BrowserError,
    BrowserLaunchError,
    SessionExpiredError,
    ElementNotFoundError,
    NavigationError,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Temporary data directory for tests."""
    data_dir = tmp_path / "browser_data"
    data_dir.mkdir()
    return str(data_dir)


@pytest.fixture
async def browser_manager(tmp_data_dir):
    """BrowserManager instance for testing."""
    manager = BrowserManager(headless=True, data_dir=tmp_data_dir)
    yield manager
    # Cleanup
    try:
        await manager.close()
    except Exception:
        pass


@pytest.fixture
def mock_playwright():
    """Mock Playwright instance."""
    with patch("src.core.browser.async_playwright") as mock:
        playwright = AsyncMock()
        browser = AsyncMock()
        context = AsyncMock()
        page = AsyncMock()

        # Setup mock chain
        mock.return_value.start = AsyncMock(return_value=playwright)
        playwright.chromium.launch = AsyncMock(return_value=browser)
        browser.new_context = AsyncMock(return_value=context)
        context.new_page = AsyncMock(return_value=page)
        context.storage_state = AsyncMock()
        context.add_init_script = AsyncMock()

        yield {
            "async_playwright": mock,
            "playwright": playwright,
            "browser": browser,
            "context": context,
            "page": page,
        }


# ============================================================================
# BrowserManager Tests
# ============================================================================


class TestBrowserManager:
    """Test BrowserManager class."""

    async def test_init(self, tmp_data_dir):
        """Test BrowserManager initialization."""
        manager = BrowserManager(
            headless=True,
            data_dir=tmp_data_dir,
            proxy="http://proxy:8080"
        )

        assert manager.headless is True
        assert str(manager.data_dir) == tmp_data_dir
        assert manager.proxy == "http://proxy:8080"
        assert manager._browser is None
        assert manager._playwright is None
        assert manager._contexts == {}

    async def test_launch_browser(self, browser_manager, mock_playwright):
        """Test browser launch."""
        browser = await browser_manager.launch()

        assert browser is not None
        assert browser_manager._browser is browser
        assert browser_manager._playwright is not None

        # Verify Playwright was started
        mock_playwright["async_playwright"].return_value.start.assert_called_once()

        # Verify chromium.launch was called with correct args
        mock_playwright["playwright"].chromium.launch.assert_called_once()
        call_kwargs = mock_playwright["playwright"].chromium.launch.call_args[1]
        assert call_kwargs["headless"] is True
        assert "--disable-blink-features=AutomationControlled" in call_kwargs["args"]

    async def test_launch_browser_idempotent(self, browser_manager, mock_playwright):
        """Test that multiple launch calls return same browser."""
        browser1 = await browser_manager.launch()
        browser2 = await browser_manager.launch()

        assert browser1 is browser2
        # Should only call launch once
        assert mock_playwright["playwright"].chromium.launch.call_count == 1

    async def test_launch_browser_error(self, browser_manager, mock_playwright):
        """Test browser launch error handling."""
        mock_playwright["playwright"].chromium.launch.side_effect = Exception("Launch failed")

        with pytest.raises(BrowserLaunchError, match="Launch failed"):
            await browser_manager.launch()

    async def test_get_context_new(self, browser_manager, mock_playwright):
        """Test creating new browser context."""
        context = await browser_manager.get_context("linkedin", load_session=False)

        assert context is not None
        assert "linkedin" in browser_manager._contexts
        assert browser_manager._contexts["linkedin"] is context

        # Verify context was created with correct options
        mock_playwright["browser"].new_context.assert_called_once()
        call_kwargs = mock_playwright["browser"].new_context.call_args[1]
        assert call_kwargs["viewport"] == {"width": 1920, "height": 1080}
        assert call_kwargs["locale"] == "en-US"
        assert "user_agent" in call_kwargs

    async def test_get_context_existing(self, browser_manager, mock_playwright):
        """Test returning existing context."""
        context1 = await browser_manager.get_context("linkedin")
        context2 = await browser_manager.get_context("linkedin")

        assert context1 is context2
        # Should only call new_context once
        assert mock_playwright["browser"].new_context.call_count == 1

    async def test_get_context_with_session(self, browser_manager, mock_playwright, tmp_data_dir):
        """Test loading saved session."""
        # Create fake session file
        session_path = Path(tmp_data_dir) / "linkedin" / "state.json"
        session_path.parent.mkdir(parents=True, exist_ok=True)
        session_path.write_text('{"cookies": []}')

        context = await browser_manager.get_context("linkedin", load_session=True)

        # Verify storage_state was passed
        call_kwargs = mock_playwright["browser"].new_context.call_args[1]
        assert "storage_state" in call_kwargs
        assert call_kwargs["storage_state"] == str(session_path)

    async def test_get_context_with_proxy(self, tmp_data_dir, mock_playwright):
        """Test context creation with proxy."""
        manager = BrowserManager(
            headless=True,
            data_dir=tmp_data_dir,
            proxy="http://proxy:8080"
        )

        await manager.get_context("linkedin")

        # Verify proxy was set
        call_kwargs = mock_playwright["browser"].new_context.call_args[1]
        assert call_kwargs["proxy"] == {"server": "http://proxy:8080"}

    async def test_get_context_anti_detection(self, browser_manager, mock_playwright):
        """Test anti-detection scripts are injected."""
        await browser_manager.get_context("linkedin")

        # Verify add_init_script was called
        mock_playwright["context"].add_init_script.assert_called_once()
        script = mock_playwright["context"].add_init_script.call_args[0][0]

        # Check for anti-detection code
        assert "webdriver" in script
        assert "navigator" in script
        assert "window.chrome" in script

    async def test_save_session(self, browser_manager, mock_playwright, tmp_data_dir):
        """Test saving browser session."""
        # Create context first
        await browser_manager.get_context("linkedin")

        # Save session
        await browser_manager.save_session("linkedin")

        # Verify storage_state was called
        mock_playwright["context"].storage_state.assert_called_once()
        session_path = Path(tmp_data_dir) / "linkedin" / "state.json"
        assert mock_playwright["context"].storage_state.call_args[1]["path"] == str(session_path)

    async def test_save_session_nonexistent_context(self, browser_manager, mock_playwright):
        """Test saving session for nonexistent context."""
        # Should not raise error, just log warning
        await browser_manager.save_session("nonexistent")

        # Verify storage_state was not called
        mock_playwright["context"].storage_state.assert_not_called()

    async def test_new_page(self, browser_manager, mock_playwright):
        """Test creating new page."""
        page = await browser_manager.new_page("linkedin")

        assert page is not None
        mock_playwright["context"].new_page.assert_called_once()
        # Verify default timeout was set
        page.set_default_timeout.assert_called_once_with(30000)

    async def test_screenshot(self, browser_manager, mock_playwright, tmp_data_dir):
        """Test taking screenshot."""
        page = mock_playwright["page"]
        page.screenshot = AsyncMock()

        screenshot_path = await browser_manager.screenshot(page, "test_page", full_page=True)

        # Verify screenshot was called
        page.screenshot.assert_called_once()
        call_kwargs = page.screenshot.call_args[1]
        assert call_kwargs["full_page"] is True
        assert "test_page" in call_kwargs["path"]
        assert screenshot_path.endswith(".png")

        # Verify screenshots directory was created
        screenshots_dir = Path(tmp_data_dir) / "screenshots"
        assert screenshots_dir.exists()

    async def test_close(self, browser_manager, mock_playwright):
        """Test closing browser and cleanup."""
        # Setup browser with context
        await browser_manager.launch()
        await browser_manager.get_context("linkedin")

        # Close
        await browser_manager.close()

        # Verify cleanup
        mock_playwright["context"].storage_state.assert_called_once()  # Save session
        mock_playwright["context"].close.assert_called_once()
        mock_playwright["browser"].close.assert_called_once()
        mock_playwright["playwright"].stop.assert_called_once()

        assert browser_manager._contexts == {}
        assert browser_manager._browser is None
        assert browser_manager._playwright is None

    async def test_context_manager(self, tmp_data_dir, mock_playwright):
        """Test using BrowserManager as async context manager."""
        manager = BrowserManager(headless=True, data_dir=tmp_data_dir)

        async with manager as bm:
            assert bm is manager
            assert bm._browser is not None

        # Verify cleanup was called
        mock_playwright["browser"].close.assert_called_once()
        mock_playwright["playwright"].stop.assert_called_once()

    async def test_get_user_agent(self, browser_manager):
        """Test user agent rotation."""
        ua1 = browser_manager._get_user_agent()
        assert isinstance(ua1, str)
        assert "Mozilla/5.0" in ua1

        # Test that it can return different user agents
        user_agents = set()
        for _ in range(50):
            user_agents.add(browser_manager._get_user_agent())

        # Should have multiple different user agents
        assert len(user_agents) > 1


# ============================================================================
# PageUtils Tests
# ============================================================================


class TestPageUtils:
    """Test PageUtils class."""

    async def test_random_delay(self):
        """Test random delay."""
        import time
        start = time.time()
        await PageUtils.random_delay(0.1, 0.2)
        elapsed = time.time() - start

        assert 0.1 <= elapsed <= 0.3  # Allow some tolerance

    async def test_human_type(self):
        """Test human-like typing."""
        page = AsyncMock()
        element = AsyncMock()
        page.wait_for_selector = AsyncMock(return_value=element)
        page.keyboard.type = AsyncMock()

        await PageUtils.human_type(page, "#input", "test")

        # Verify element was clicked
        element.click.assert_called_once()

        # Verify each character was typed
        assert page.keyboard.type.call_count == 4  # "test" = 4 chars
        calls = [call[0][0] for call in page.keyboard.type.call_args_list]
        assert calls == ["t", "e", "s", "t"]

    async def test_human_type_element_not_found(self):
        """Test human_type with missing element."""
        page = AsyncMock()
        page.wait_for_selector = AsyncMock(side_effect=Exception("Not found"))

        with pytest.raises(ElementNotFoundError, match="Not found"):
            await PageUtils.human_type(page, "#missing", "text")

    async def test_human_click_with_bounding_box(self):
        """Test human-like click with bounding box."""
        page = AsyncMock()
        element = AsyncMock()
        element.bounding_box = AsyncMock(return_value={
            "x": 100,
            "y": 200,
            "width": 50,
            "height": 30
        })
        page.wait_for_selector = AsyncMock(return_value=element)
        page.mouse.click = AsyncMock()

        await PageUtils.human_click(page, ".button")

        # Verify click was randomized within bounds
        page.mouse.click.assert_called_once()
        x, y = page.mouse.click.call_args[0]
        assert 100 + 50 * 0.3 <= x <= 100 + 50 * 0.7
        assert 200 + 30 * 0.3 <= y <= 200 + 30 * 0.7

    async def test_human_click_without_bounding_box(self):
        """Test human-like click fallback."""
        page = AsyncMock()
        element = AsyncMock()
        element.bounding_box = AsyncMock(return_value=None)
        page.wait_for_selector = AsyncMock(return_value=element)

        await PageUtils.human_click(page, ".button")

        # Should fallback to direct click
        element.click.assert_called_once()

    async def test_human_click_element_not_found(self):
        """Test human_click with missing element."""
        page = AsyncMock()
        page.wait_for_selector = AsyncMock(side_effect=Exception("Not found"))

        with pytest.raises(ElementNotFoundError, match="Not found"):
            await PageUtils.human_click(page, "#missing")

    async def test_scroll_to_bottom(self):
        """Test scrolling to bottom."""
        page = AsyncMock()
        # Simulate page growing then staying same
        heights = [1000, 1500, 2000, 2000]
        page.evaluate = AsyncMock(side_effect=heights)

        await PageUtils.scroll_to_bottom(page, step=500, delay=0.01)

        # Should scroll 3 times (until height stops changing)
        scroll_calls = [call for call in page.evaluate.call_args_list
                       if "scrollBy" in str(call)]
        assert len(scroll_calls) == 3

    async def test_wait_for_navigation_networkidle(self):
        """Test waiting for navigation (networkidle)."""
        page = AsyncMock()
        page.wait_for_load_state = AsyncMock()

        await PageUtils.wait_for_navigation(page, timeout=5000)

        page.wait_for_load_state.assert_called_once_with("networkidle", timeout=5000)

    async def test_wait_for_navigation_fallback(self):
        """Test waiting for navigation with fallback."""
        page = AsyncMock()
        # First call fails, second succeeds
        page.wait_for_load_state = AsyncMock(
            side_effect=[Exception("Timeout"), None]
        )

        await PageUtils.wait_for_navigation(page, timeout=5000)

        # Should try networkidle then domcontentloaded
        assert page.wait_for_load_state.call_count == 2
        calls = [call[0][0] for call in page.wait_for_load_state.call_args_list]
        assert calls == ["networkidle", "domcontentloaded"]

    async def test_wait_for_navigation_timeout(self):
        """Test navigation timeout error."""
        page = AsyncMock()
        page.wait_for_load_state = AsyncMock(side_effect=Exception("Timeout"))

        with pytest.raises(NavigationError, match="Timeout"):
            await PageUtils.wait_for_navigation(page)

    async def test_safe_click_success(self):
        """Test safe click when element exists."""
        page = AsyncMock()
        element = AsyncMock()
        page.wait_for_selector = AsyncMock(return_value=element)

        result = await PageUtils.safe_click(page, ".button", timeout=1000)

        assert result is True
        element.click.assert_called_once()

    async def test_safe_click_not_found(self):
        """Test safe click when element doesn't exist."""
        page = AsyncMock()
        page.wait_for_selector = AsyncMock(side_effect=Exception("Not found"))

        result = await PageUtils.safe_click(page, ".missing")

        assert result is False

    async def test_get_text_success(self):
        """Test getting element text."""
        page = AsyncMock()
        element = AsyncMock()
        element.inner_text = AsyncMock(return_value="Hello World")
        page.wait_for_selector = AsyncMock(return_value=element)

        text = await PageUtils.get_text(page, ".text")

        assert text == "Hello World"

    async def test_get_text_not_found(self):
        """Test getting text with default fallback."""
        page = AsyncMock()
        page.wait_for_selector = AsyncMock(side_effect=Exception("Not found"))

        text = await PageUtils.get_text(page, ".missing", default="N/A")

        assert text == "N/A"

    async def test_get_text_default_empty(self):
        """Test getting text with empty default."""
        page = AsyncMock()
        page.wait_for_selector = AsyncMock(side_effect=Exception("Not found"))

        text = await PageUtils.get_text(page, ".missing")

        assert text == ""


# ============================================================================
# Error Classes Tests
# ============================================================================


class TestErrorClasses:
    """Test custom error classes."""

    def test_browser_error(self):
        """Test BrowserError."""
        error = BrowserError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)

    def test_browser_launch_error(self):
        """Test BrowserLaunchError."""
        error = BrowserLaunchError("Launch failed")
        assert str(error) == "Launch failed"
        assert isinstance(error, BrowserError)

    def test_session_expired_error(self):
        """Test SessionExpiredError."""
        error = SessionExpiredError("Session expired")
        assert str(error) == "Session expired"
        assert isinstance(error, BrowserError)

    def test_element_not_found_error(self):
        """Test ElementNotFoundError."""
        error = ElementNotFoundError("Element not found")
        assert str(error) == "Element not found"
        assert isinstance(error, BrowserError)

    def test_navigation_error(self):
        """Test NavigationError."""
        error = NavigationError("Navigation failed")
        assert str(error) == "Navigation failed"
        assert isinstance(error, BrowserError)


# ============================================================================
# Integration-like Tests
# ============================================================================


class TestIntegration:
    """Integration-like tests with mocked Playwright."""

    async def test_full_workflow(self, browser_manager, mock_playwright, tmp_data_dir):
        """Test complete workflow: launch, navigate, interact, save."""
        # Launch browser
        browser = await browser_manager.launch()
        assert browser is not None

        # Get context
        context = await browser_manager.get_context("linkedin")
        assert context is not None

        # Create page
        page = await browser_manager.new_page("linkedin")
        assert page is not None

        # Save session
        await browser_manager.save_session("linkedin")

        # Verify session file path
        session_path = Path(tmp_data_dir) / "linkedin" / "state.json"
        call_kwargs = mock_playwright["context"].storage_state.call_args[1]
        assert call_kwargs["path"] == str(session_path)

        # Close
        await browser_manager.close()
        assert browser_manager._browser is None

    async def test_multiple_platforms(self, browser_manager, mock_playwright):
        """Test managing multiple platform contexts."""
        # Create contexts for different platforms
        linkedin = await browser_manager.get_context("linkedin")
        indeed = await browser_manager.get_context("indeed")
        wellfound = await browser_manager.get_context("wellfound")

        # Verify all contexts are unique
        assert linkedin is not indeed
        assert linkedin is not wellfound
        assert indeed is not wellfound

        # Verify all stored
        assert len(browser_manager._contexts) == 3
        assert "linkedin" in browser_manager._contexts
        assert "indeed" in browser_manager._contexts
        assert "wellfound" in browser_manager._contexts
