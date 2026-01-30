"""Unit tests for job applier service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from pathlib import Path

from src.core.applier import (
    JobApplierService,
    LinkedInApplier,
    IndeedApplier,
    WellfoundApplier,
    AdditionalQuestionsHandler,
    ApplicationErrorHandler,
    ApplicationResult,
)
from src.core.database import Job
from src.utils.markdown_parser import Resume, PersonalInfo


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_database():
    """Mock Database instance."""
    db = MagicMock()
    db.get_job_by_id = MagicMock()
    db.get_resume_for_job = MagicMock()
    db.update_job_status = MagicMock()
    db.update_application_status = MagicMock()
    return db


@pytest.fixture
def mock_browser():
    """Mock BrowserManager instance."""
    browser = MagicMock()
    browser.new_page = AsyncMock()
    browser.get_context = AsyncMock()
    browser.screenshot = AsyncMock(return_value="/path/to/screenshot.png")
    return browser


@pytest.fixture
def mock_config():
    """Mock ConfigLoader instance."""
    config = MagicMock()

    # Mock preferences
    mock_prefs = MagicMock()
    mock_prefs.settings.max_applications_per_day = 20
    mock_prefs.settings.max_applications_per_hour = 5
    mock_prefs.settings.auto_apply_threshold = 0.85
    config.get_preferences.return_value = mock_prefs

    # Mock resume
    mock_resume = Resume(
        personal_info=PersonalInfo(
            name="John Doe",
            email="john@example.com",
            phone="+1234567890",
            linkedin="https://linkedin.com/in/johndoe",
            location="San Francisco, CA",
            visa_status="Authorized"
        ),
        summary="Software Engineer with 5 years experience",
        education=[],
        work_experience=[],
        skills={"Python": ["Django", "Flask"], "JavaScript": ["React", "Node.js"]}
    )
    config.get_resume.return_value = mock_resume

    return config


@pytest.fixture
def sample_job():
    """Sample Job instance."""
    return Job(
        id=1,
        external_id="linkedin-123",
        platform="linkedin",
        url="https://www.linkedin.com/jobs/view/123",
        url_hash="abc123",
        title="Senior Software Engineer",
        company="Tech Corp",
        location="San Francisco, CA",
        salary_min=120000,
        salary_max=180000,
        salary_currency="USD",
        remote_type="hybrid",
        visa_sponsorship=True,
        easy_apply=True,
        jd_markdown="# Job Description\nWe are looking for...",
        jd_raw="<div>We are looking for...</div>",
        match_score=0.92,
        match_reasoning="Strong match based on skills",
        key_requirements=["Python", "React"],
        red_flags=[],
        status="matched",
        decision_type="auto",
        scraped_at=datetime.now(),
        filtered_at=datetime.now(),
        decided_at=None,
        applied_at=None
    )


@pytest.fixture
def mock_page():
    """Mock Playwright Page instance."""
    page = AsyncMock()
    page.goto = AsyncMock()
    page.query_selector = AsyncMock()
    page.query_selector_all = AsyncMock(return_value=[])
    page.wait_for_selector = AsyncMock()
    page.close = AsyncMock()
    page.screenshot = AsyncMock()
    return page


# ============================================================================
# JobApplierService Tests
# ============================================================================


class TestJobApplierService:
    """Test JobApplierService main orchestration."""

    @pytest.mark.asyncio
    async def test_apply_to_job_job_not_found(self, mock_database, mock_browser, mock_config):
        """Test applying to non-existent job."""
        mock_database.get_job_by_id.return_value = None

        service = JobApplierService(db=mock_database, browser=mock_browser, config=mock_config)
        result = await service.apply_to_job(job_id=999)

        assert result.success is False
        assert result.error == "Job not found in database"
        assert result.job_id == 999

    @pytest.mark.asyncio
    async def test_apply_to_job_rate_limit_exceeded(
        self,
        mock_database,
        mock_browser,
        mock_config,
        sample_job
    ):
        """Test rate limit check blocks application."""
        mock_database.get_job_by_id.return_value = sample_job

        service = JobApplierService(db=mock_database, browser=mock_browser, config=mock_config)
        # Set count to exceed limit
        service._application_count_today = 20

        result = await service.apply_to_job(job_id=1)

        assert result.success is False
        assert result.method == "skipped"
        assert "rate limit" in result.error.lower()

    @pytest.mark.asyncio
    async def test_apply_to_job_no_resume(
        self,
        mock_database,
        mock_browser,
        mock_config,
        sample_job
    ):
        """Test applying without resume fails gracefully."""
        mock_database.get_job_by_id.return_value = sample_job
        mock_database.get_resume_for_job.return_value = None

        service = JobApplierService(db=mock_database, browser=mock_browser, config=mock_config)
        result = await service.apply_to_job(job_id=1)

        assert result.success is False
        assert "no resume" in result.error.lower()

    @pytest.mark.asyncio
    async def test_apply_to_job_resume_file_not_found(
        self,
        mock_database,
        mock_browser,
        mock_config,
        sample_job
    ):
        """Test applying with non-existent resume file."""
        mock_database.get_job_by_id.return_value = sample_job

        service = JobApplierService(db=mock_database, browser=mock_browser, config=mock_config)
        result = await service.apply_to_job(job_id=1, resume_path="/nonexistent/resume.pdf")

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_apply_to_job_unsupported_platform(
        self,
        mock_database,
        mock_browser,
        mock_config,
        sample_job,
        tmp_path
    ):
        """Test applying to unsupported platform."""
        # Create temporary resume file
        resume_path = tmp_path / "resume.pdf"
        resume_path.write_text("dummy resume")

        sample_job.platform = "unsupported_platform"
        mock_database.get_job_by_id.return_value = sample_job

        service = JobApplierService(db=mock_database, browser=mock_browser, config=mock_config)
        result = await service.apply_to_job(job_id=1, resume_path=str(resume_path))

        assert result.success is False
        assert result.method == "external"
        assert "not supported" in result.error.lower()

    @pytest.mark.asyncio
    async def test_apply_to_job_success_updates_database(
        self,
        mock_database,
        mock_browser,
        mock_config,
        sample_job,
        tmp_path
    ):
        """Test successful application updates database correctly."""
        # Create temporary resume file
        resume_path = tmp_path / "resume.pdf"
        resume_path.write_text("dummy resume")

        mock_database.get_job_by_id.return_value = sample_job

        # Mock successful LinkedIn application
        with patch('src.core.applier.LinkedInApplier') as MockLinkedInApplier:
            mock_applier = MockLinkedInApplier.return_value
            mock_applier.apply = AsyncMock(return_value=ApplicationResult(
                success=True,
                job_id=1,
                company="Tech Corp",
                title="Senior Software Engineer",
                platform="linkedin",
                method="easy_apply"
            ))

            service = JobApplierService(db=mock_database, browser=mock_browser, config=mock_config)
            result = await service.apply_to_job(job_id=1, resume_path=str(resume_path))

            assert result.success is True
            mock_database.update_job_status.assert_called_once_with(1, "applied")
            mock_database.update_application_status.assert_called_once_with(1, "submitted")
            assert service._application_count_today == 1
            assert service._last_application_time is not None

    @pytest.mark.asyncio
    async def test_apply_to_job_failure_updates_database(
        self,
        mock_database,
        mock_browser,
        mock_config,
        sample_job,
        tmp_path
    ):
        """Test failed application updates database correctly."""
        # Create temporary resume file
        resume_path = tmp_path / "resume.pdf"
        resume_path.write_text("dummy resume")

        mock_database.get_job_by_id.return_value = sample_job

        # Mock failed LinkedIn application
        with patch('src.core.applier.LinkedInApplier') as MockLinkedInApplier:
            mock_applier = MockLinkedInApplier.return_value
            mock_applier.apply = AsyncMock(return_value=ApplicationResult(
                success=False,
                job_id=1,
                company="Tech Corp",
                title="Senior Software Engineer",
                platform="linkedin",
                method="easy_apply",
                error="Form submission failed"
            ))

            service = JobApplierService(db=mock_database, browser=mock_browser, config=mock_config)
            result = await service.apply_to_job(job_id=1, resume_path=str(resume_path))

            assert result.success is False
            mock_database.update_application_status.assert_called_once_with(
                1, "failed", "Form submission failed"
            )

    def test_check_rate_limit_daily_limit(self, mock_database, mock_browser, mock_config):
        """Test daily rate limit enforcement."""
        service = JobApplierService(db=mock_database, browser=mock_browser, config=mock_config)

        # Within limit
        service._application_count_today = 0
        assert service._check_rate_limit() is True

        # At limit
        service._application_count_today = 20
        assert service._check_rate_limit() is False

        # Over limit
        service._application_count_today = 25
        assert service._check_rate_limit() is False

    def test_check_rate_limit_hourly_limit(self, mock_database, mock_browser, mock_config):
        """Test hourly rate limit enforcement."""
        service = JobApplierService(db=mock_database, browser=mock_browser, config=mock_config)

        # No previous application - should pass
        service._last_application_time = None
        assert service._check_rate_limit() is True

        # Recent application - should fail
        service._last_application_time = datetime.now()
        # With max 5 per hour, minimum interval is 720 seconds (12 minutes)
        # Recent application should be blocked
        assert service._check_rate_limit() is False


# ============================================================================
# LinkedInApplier Tests
# ============================================================================


class TestLinkedInApplier:
    """Test LinkedIn Easy Apply automation."""

    @pytest.mark.asyncio
    async def test_apply_easy_apply_not_available(
        self,
        mock_browser,
        sample_job,
        mock_page
    ):
        """Test handling when Easy Apply button is not found."""
        mock_browser.new_page.return_value = mock_page
        mock_page.query_selector.return_value = None  # No Easy Apply button

        applier = LinkedInApplier(mock_browser)
        result = await applier.apply(sample_job, "/path/to/resume.pdf")

        assert result.success is False
        assert result.method == "external"
        assert "not found" in result.error.lower() or "not available" in result.error.lower()

    @pytest.mark.asyncio
    async def test_apply_modal_fails_to_load(
        self,
        mock_browser,
        sample_job,
        mock_page
    ):
        """Test handling when application modal fails to appear."""
        mock_browser.new_page.return_value = mock_page

        # Mock Easy Apply button exists
        easy_apply_btn = AsyncMock()
        mock_page.query_selector.return_value = easy_apply_btn

        # Mock modal wait timeout
        mock_page.wait_for_selector.side_effect = Exception("Timeout")

        applier = LinkedInApplier(mock_browser)
        result = await applier.apply(sample_job, "/path/to/resume.pdf")

        assert result.success is False
        assert result.method == "easy_apply"
        assert "modal" in result.error.lower() or "timeout" in result.error.lower()

    @pytest.mark.asyncio
    async def test_is_submission_complete_success(self, mock_page):
        """Test detection of successful submission."""
        applier = LinkedInApplier(MagicMock())

        # Mock success indicator found
        success_element = AsyncMock()
        mock_page.query_selector.return_value = success_element

        result = await applier._is_submission_complete(mock_page)
        assert result is True

    @pytest.mark.asyncio
    async def test_is_submission_complete_not_found(self, mock_page):
        """Test when submission is not complete."""
        applier = LinkedInApplier(MagicMock())

        # Mock no success indicators found
        mock_page.query_selector.return_value = None

        result = await applier._is_submission_complete(mock_page)
        assert result is False

    @pytest.mark.asyncio
    async def test_has_error_detected(self, mock_page):
        """Test detection of form errors."""
        applier = LinkedInApplier(MagicMock())

        # Mock error element found
        error_element = AsyncMock()
        error_element.inner_text = AsyncMock(return_value="This field is required")
        mock_page.query_selector.return_value = error_element

        result = await applier._has_error(mock_page)
        assert result is True

    @pytest.mark.asyncio
    async def test_has_error_not_detected(self, mock_page):
        """Test when no errors present."""
        applier = LinkedInApplier(MagicMock())

        # Mock no error elements found
        mock_page.query_selector.return_value = None

        result = await applier._has_error(mock_page)
        assert result is False


# ============================================================================
# IndeedApplier Tests
# ============================================================================


class TestIndeedApplier:
    """Test Indeed application automation."""

    @pytest.mark.asyncio
    async def test_apply_button_not_found(
        self,
        mock_browser,
        sample_job,
        mock_page
    ):
        """Test handling when apply button is not found."""
        sample_job.platform = "indeed"
        mock_browser.new_page.return_value = mock_page
        mock_page.query_selector.return_value = None  # No apply button

        applier = IndeedApplier(mock_browser)
        result = await applier.apply(sample_job, "/path/to/resume.pdf")

        assert result.success is False
        assert result.method == "external"
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_apply_external_application(
        self,
        mock_browser,
        sample_job,
        mock_page
    ):
        """Test detection of external application redirect."""
        sample_job.platform = "indeed"
        mock_browser.new_page.return_value = mock_page

        # Mock apply button that redirects externally
        apply_btn = AsyncMock()
        apply_btn.inner_text = AsyncMock(return_value="Apply on Company Website")
        mock_page.query_selector.return_value = apply_btn

        applier = IndeedApplier(mock_browser)
        result = await applier.apply(sample_job, "/path/to/resume.pdf")

        assert result.success is False
        assert result.method == "external"
        assert "external" in result.error.lower() or "cannot automate" in result.error.lower()


# ============================================================================
# WellfoundApplier Tests
# ============================================================================


class TestWellfoundApplier:
    """Test Wellfound application automation."""

    @pytest.mark.asyncio
    async def test_apply_button_not_found(
        self,
        mock_browser,
        sample_job,
        mock_page
    ):
        """Test handling when apply button is not found."""
        sample_job.platform = "wellfound"
        mock_browser.new_page.return_value = mock_page
        mock_page.query_selector.return_value = None  # No apply button

        applier = WellfoundApplier(mock_browser)
        result = await applier.apply(sample_job, "/path/to/resume.pdf")

        assert result.success is False
        assert result.method == "external"
        assert "not found" in result.error.lower()


# ============================================================================
# AdditionalQuestionsHandler Tests
# ============================================================================


class TestAdditionalQuestionsHandler:
    """Test handling of additional application questions."""

    def test_get_answer_work_authorization(self):
        """Test answering work authorization questions."""
        handler = AdditionalQuestionsHandler()

        assert handler.get_answer("Are you authorized to work in the US?") == "Yes"
        assert handler.get_answer("Are you legally authorized to work?") == "Yes"

    def test_get_answer_sponsorship(self):
        """Test answering visa sponsorship questions."""
        handler = AdditionalQuestionsHandler()

        answer = handler.get_answer("Do you require visa sponsorship?")
        assert answer in ["Yes", "No"]  # Configurable

    def test_get_answer_experience(self):
        """Test answering experience questions."""
        handler = AdditionalQuestionsHandler()

        answer = handler.get_answer("How many years of experience do you have with Python?")
        assert answer is not None

    def test_get_answer_remote_work(self):
        """Test answering remote work questions."""
        handler = AdditionalQuestionsHandler()

        assert handler.get_answer("Are you willing to work remotely?") == "Yes"
        assert handler.get_answer("Do you prefer hybrid work?") == "Yes"

    def test_get_answer_relocation(self):
        """Test answering relocation questions."""
        handler = AdditionalQuestionsHandler()

        assert handler.get_answer("Are you willing to relocate?") == "No"

    def test_get_answer_unknown_question(self):
        """Test handling unknown questions."""
        handler = AdditionalQuestionsHandler()

        assert handler.get_answer("What is your favorite programming language?") is None

    def test_get_answer_demographics(self):
        """Test answering demographic questions."""
        handler = AdditionalQuestionsHandler()

        # Should prefer not to answer
        assert "prefer not" in handler.get_answer("What is your gender?").lower()
        assert "prefer not" in handler.get_answer("Are you a veteran?").lower()


# ============================================================================
# ApplicationErrorHandler Tests
# ============================================================================


class TestApplicationErrorHandler:
    """Test application error handling and recovery."""

    @pytest.mark.asyncio
    async def test_detect_captcha(self, mock_page):
        """Test CAPTCHA detection."""
        handler = ApplicationErrorHandler()

        # Mock CAPTCHA element found
        captcha_element = AsyncMock()
        mock_page.query_selector.return_value = captcha_element

        result = await handler._detect_captcha(mock_page)
        assert result is True

    @pytest.mark.asyncio
    async def test_detect_captcha_not_found(self, mock_page):
        """Test when no CAPTCHA present."""
        handler = ApplicationErrorHandler()

        # Mock no CAPTCHA elements
        mock_page.query_selector.return_value = None

        result = await handler._detect_captcha(mock_page)
        assert result is False

    @pytest.mark.asyncio
    async def test_detect_login_page(self, mock_page):
        """Test login page detection."""
        handler = ApplicationErrorHandler()

        # Mock password input found (indicates login page)
        password_input = AsyncMock()
        mock_page.query_selector.return_value = password_input

        result = await handler._detect_login_page(mock_page)
        assert result is True

    @pytest.mark.asyncio
    async def test_detect_login_page_not_found(self, mock_page):
        """Test when not on login page."""
        handler = ApplicationErrorHandler()

        # Mock no login indicators
        mock_page.query_selector.return_value = None

        result = await handler._detect_login_page(mock_page)
        assert result is False

    @pytest.mark.asyncio
    async def test_handle_error_captcha(self, mock_page, sample_job, mock_browser):
        """Test handling CAPTCHA error."""
        handler = ApplicationErrorHandler()

        # Mock CAPTCHA detected
        with patch.object(handler, '_detect_captcha', return_value=True):
            error_msg = await handler.handle_error(
                mock_page,
                Exception("CAPTCHA"),
                sample_job,
                mock_browser
            )

            assert "CAPTCHA" in error_msg
            mock_browser.screenshot.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_error_session_expired(self, mock_page, sample_job, mock_browser):
        """Test handling session expiration."""
        handler = ApplicationErrorHandler()

        # Mock no CAPTCHA detected
        with patch.object(handler, '_detect_captcha', return_value=False):
            with patch.object(handler, '_detect_login_page', return_value=True):
                error_msg = await handler.handle_error(
                    mock_page,
                    Exception("Please login to continue"),
                    sample_job,
                    mock_browser
                )

                assert "session" in error_msg.lower() or "authentication" in error_msg.lower()

    @pytest.mark.asyncio
    async def test_handle_error_rate_limit(self, mock_page, sample_job, mock_browser):
        """Test handling rate limit error."""
        handler = ApplicationErrorHandler()

        # Mock no CAPTCHA detected
        with patch.object(handler, '_detect_captcha', return_value=False):
            with patch.object(handler, '_detect_login_page', return_value=False):
                error_msg = await handler.handle_error(
                    mock_page,
                    Exception("Too many requests"),
                    sample_job,
                    mock_browser
                )

                assert "rate limit" in error_msg.lower()

    @pytest.mark.asyncio
    async def test_handle_error_form_validation(self, mock_page, sample_job, mock_browser):
        """Test handling form validation error."""
        handler = ApplicationErrorHandler()

        error_msg = await handler.handle_error(
            mock_page,
            Exception("Required field missing"),
            sample_job,
            mock_browser
        )

        assert "validation" in error_msg.lower() or "required" in error_msg.lower()
        mock_browser.screenshot.assert_called_once()


# ============================================================================
# ApplicationResult Tests
# ============================================================================


class TestApplicationResult:
    """Test ApplicationResult dataclass."""

    def test_create_success_result(self):
        """Test creating successful application result."""
        result = ApplicationResult(
            success=True,
            job_id=1,
            company="Tech Corp",
            title="Software Engineer",
            platform="linkedin",
            method="easy_apply"
        )

        assert result.success is True
        assert result.job_id == 1
        assert result.error is None
        assert result.screenshot_path is None

    def test_create_failure_result(self):
        """Test creating failed application result."""
        result = ApplicationResult(
            success=False,
            job_id=1,
            company="Tech Corp",
            title="Software Engineer",
            platform="linkedin",
            method="easy_apply",
            error="Form submission failed",
            screenshot_path="/path/to/screenshot.png"
        )

        assert result.success is False
        assert result.error == "Form submission failed"
        assert result.screenshot_path == "/path/to/screenshot.png"


# ============================================================================
# Integration Tests
# ============================================================================


class TestApplierIntegration:
    """Integration tests for applier service."""

    @pytest.mark.asyncio
    async def test_full_application_flow_success(
        self,
        mock_database,
        mock_browser,
        mock_config,
        sample_job,
        mock_page,
        tmp_path
    ):
        """Test complete successful application flow."""
        # Setup
        resume_path = tmp_path / "resume.pdf"
        resume_path.write_text("dummy resume")

        mock_database.get_job_by_id.return_value = sample_job
        mock_browser.new_page.return_value = mock_page

        # Mock Easy Apply button
        easy_apply_btn = AsyncMock()
        mock_page.query_selector.side_effect = [
            easy_apply_btn,  # Easy Apply button
            AsyncMock(),      # Modal
        ]

        # Mock form filling and submission
        with patch.object(LinkedInApplier, '_fill_application_form', return_value=True):
            with patch.object(LinkedInApplier, '_is_submission_complete', return_value=True):
                service = JobApplierService(
                    db=mock_database,
                    browser=mock_browser,
                    config=mock_config
                )

                result = await service.apply_to_job(job_id=1, resume_path=str(resume_path))

                # Verify result
                assert result.success is True
                assert result.method == "easy_apply"

                # Verify database updates
                mock_database.update_job_status.assert_called_once_with(1, "applied")
                mock_database.update_application_status.assert_called_once_with(1, "submitted")

    @pytest.mark.asyncio
    async def test_full_application_flow_with_errors(
        self,
        mock_database,
        mock_browser,
        mock_config,
        sample_job,
        mock_page,
        tmp_path
    ):
        """Test application flow with form errors."""
        # Setup
        resume_path = tmp_path / "resume.pdf"
        resume_path.write_text("dummy resume")

        mock_database.get_job_by_id.return_value = sample_job
        mock_browser.new_page.return_value = mock_page

        # Mock Easy Apply button
        easy_apply_btn = AsyncMock()
        mock_page.query_selector.side_effect = [
            easy_apply_btn,  # Easy Apply button
            AsyncMock(),      # Modal
        ]

        # Mock form with errors
        with patch.object(LinkedInApplier, '_fill_application_form', return_value=False):
            service = JobApplierService(
                db=mock_database,
                browser=mock_browser,
                config=mock_config
            )

            result = await service.apply_to_job(job_id=1, resume_path=str(resume_path))

            # Verify result
            assert result.success is False
            assert result.method == "easy_apply"

            # Verify database updates
            mock_database.update_application_status.assert_called_once()
            call_args = mock_database.update_application_status.call_args
            assert call_args[0][0] == 1  # job_id
            assert call_args[0][1] == "failed"  # status
