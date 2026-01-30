"""Unit tests for Telegram bot."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, date

from src.core.telegram import TelegramBot
from src.core.database import Job


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_database():
    """Mock Database instance."""
    db = MagicMock()
    db.get_job_by_id = MagicMock()
    db.get_jobs_by_status = MagicMock()
    db.get_current_run = MagicMock()
    db.get_daily_stats = MagicMock()
    db.update_job_status = MagicMock()
    return db


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
def telegram_bot(mock_database):
    """TelegramBot instance with mocked components."""
    bot = TelegramBot(token="test_token", chat_id="123456", db=mock_database)
    # Mock the Application
    bot.app = MagicMock()
    bot.app.bot = MagicMock()
    bot.app.bot.send_message = AsyncMock(return_value=MagicMock(message_id=1))
    return bot


@pytest.fixture
def mock_update():
    """Mock Telegram Update object."""
    update = MagicMock()
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    update.effective_message = update.message
    update.callback_query = MagicMock()
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_reply_markup = AsyncMock()
    update.callback_query.message = MagicMock()
    update.callback_query.message.reply_text = AsyncMock()
    return update


@pytest.fixture
def mock_context():
    """Mock Telegram ContextTypes.DEFAULT_TYPE."""
    context = MagicMock()
    context.args = []
    return context


# ============================================================================
# Initialization Tests
# ============================================================================


class TestTelegramBotInitialization:
    """Test TelegramBot initialization."""

    def test_init_with_env_vars(self, mock_database):
        """Test initialization with environment variables."""
        with patch.dict('os.environ', {'TELEGRAM_BOT_TOKEN': 'env_token', 'TELEGRAM_CHAT_ID': 'env_chat'}):
            bot = TelegramBot(db=mock_database)
            assert bot.token == 'env_token'
            assert bot.chat_id == 'env_chat'
            assert bot.db == mock_database

    def test_init_with_explicit_params(self, mock_database):
        """Test initialization with explicit parameters."""
        bot = TelegramBot(token="explicit_token", chat_id="explicit_chat", db=mock_database)
        assert bot.token == "explicit_token"
        assert bot.chat_id == "explicit_chat"
        assert bot.db == mock_database


# ============================================================================
# Message Sending Tests
# ============================================================================


class TestMessageSending:
    """Test message sending functionality."""

    @pytest.mark.asyncio
    async def test_send_message_basic(self, telegram_bot):
        """Test sending a basic message."""
        msg_id = await telegram_bot.send_message("Test message")
        
        assert msg_id == 1
        telegram_bot.app.bot.send_message.assert_called_once()
        call_args = telegram_bot.app.bot.send_message.call_args
        assert call_args[1]['text'] == "Test message"
        assert call_args[1]['parse_mode'] == "Markdown"

    @pytest.mark.asyncio
    async def test_send_message_with_markup(self, telegram_bot):
        """Test sending message with reply markup."""
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("Test", callback_data="test")]])
        msg_id = await telegram_bot.send_message("Test", reply_markup=markup)
        
        assert msg_id == 1
        call_args = telegram_bot.app.bot.send_message.call_args
        assert call_args[1]['reply_markup'] == markup

    @pytest.mark.asyncio
    async def test_send_job_notification_match(self, telegram_bot, sample_job, mock_database):
        """Test sending job match notification."""
        mock_database.get_job_by_id.return_value = sample_job
        
        msg_id = await telegram_bot.send_job_notification(job_id=1, notification_type="match")
        
        assert msg_id == 1
        mock_database.get_job_by_id.assert_called_once_with(1)
        telegram_bot.app.bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_job_notification_applied(self, telegram_bot, sample_job, mock_database):
        """Test sending job applied notification."""
        mock_database.get_job_by_id.return_value = sample_job
        
        msg_id = await telegram_bot.send_job_notification(job_id=1, notification_type="applied")
        
        assert msg_id == 1
        call_args = telegram_bot.app.bot.send_message.call_args
        assert "‚ú? in call_args[1]['text']

    @pytest.mark.asyncio
    async def test_send_job_notification_failed(self, telegram_bot, sample_job, mock_database):
        """Test sending job failed notification."""
        mock_database.get_job_by_id.return_value = sample_job
        
        msg_id = await telegram_bot.send_job_notification(job_id=1, notification_type="failed")
        
        assert msg_id == 1
        call_args = telegram_bot.app.bot.send_message.call_args
        assert "‚ù? in call_args[1]['text']

    @pytest.mark.asyncio
    async def test_send_job_notification_not_found(self, telegram_bot, mock_database):
        """Test sending notification for non-existent job."""
        mock_database.get_job_by_id.return_value = None
        
        msg_id = await telegram_bot.send_job_notification(job_id=999)
        
        assert msg_id is None


# ============================================================================
# Formatting Tests
# ============================================================================


class TestMessageFormatting:
    """Test message formatting methods."""

    def test_format_job_match_high_score(self, telegram_bot, sample_job):
        """Test formatting job match with high score (‚â?.85)."""
        sample_job.match_score = 0.92
        
        text = telegram_bot._format_job_match(sample_job)
        
        assert "üî•" in text  # High score emoji
        assert "92%" in text
        assert sample_job.title in text
        assert sample_job.company in text

    def test_format_job_match_medium_score(self, telegram_bot, sample_job):
        """Test formatting job match with medium score (<0.85)."""
        sample_job.match_score = 0.75
        
        text = telegram_bot._format_job_match(sample_job)
        
        assert "‚ú? in text  # Medium score emoji
        assert "75%" in text

    def test_format_salary_full_range(self, telegram_bot, sample_job):
        """Test formatting salary with min and max."""
        sample_job.salary_min = 120000
        sample_job.salary_max = 180000
        
        result = telegram_bot._format_salary(sample_job)
        
        assert result == "$120,000 - $180,000"

    def test_format_salary_min_only(self, telegram_bot, sample_job):
        """Test formatting salary with only minimum."""
        sample_job.salary_min = 150000
        sample_job.salary_max = None
        
        result = telegram_bot._format_salary(sample_job)
        
        assert result == "$150,000+"

    def test_format_salary_max_only(self, telegram_bot, sample_job):
        """Test formatting salary with only maximum."""
        sample_job.salary_min = None
        sample_job.salary_max = 200000
        
        result = telegram_bot._format_salary(sample_job)
        
        assert result == "Up to $200,000"

    def test_format_salary_not_specified(self, telegram_bot, sample_job):
        """Test formatting salary when not specified."""
        sample_job.salary_min = None
        sample_job.salary_max = None
        
        result = telegram_bot._format_salary(sample_job)
        
        assert result == "Not specified"

    def test_format_list_with_items(self, telegram_bot):
        """Test formatting list with items."""
        items = ["Python", "React", "Docker", "AWS"]
        
        result = telegram_bot._format_list(items)
        
        assert "‚Ä?Python" in result
        assert "‚Ä?React" in result
        assert result.count("‚Ä?") == 4

    def test_format_list_empty(self, telegram_bot):
        """Test formatting empty list."""
        result = telegram_bot._format_list(None)
        assert result == "None specified"
        
        result = telegram_bot._format_list([])
        assert result == "None specified"

    def test_format_red_flags_empty(self, telegram_bot):
        """Test formatting red flags when none exist."""
        result = telegram_bot._format_red_flags(None)
        assert result == ""
        
        result = telegram_bot._format_red_flags([])
        assert result == ""

    def test_format_red_flags_with_items(self, telegram_bot):
        """Test formatting red flags with items."""
        flags = ["Requires relocation", "Long commute"]
        
        result = telegram_bot._format_red_flags(flags)
        
        assert "‚ö†Ô∏è" in result
        assert "Concerns" in result
        assert "‚Ä?Requires relocation" in result


# ============================================================================
# Command Handler Tests
# ============================================================================


class TestCommandHandlers:
    """Test command handler methods."""

    @pytest.mark.asyncio
    async def test_cmd_start(self, telegram_bot, mock_update, mock_context):
        """Test /start command."""
        await telegram_bot._cmd_start(mock_update, mock_context)
        
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "Welcome" in call_args
        assert "/status" in call_args

    @pytest.mark.asyncio
    async def test_cmd_help(self, telegram_bot, mock_update, mock_context):
        """Test /help command."""
        await telegram_bot._cmd_help(mock_update, mock_context)
        
        # Should call _cmd_start
        mock_update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_cmd_status_no_run(self, telegram_bot, mock_update, mock_context, mock_database):
        """Test /status command when no run is active."""
        mock_database.get_current_run.return_value = None
        
        await telegram_bot._cmd_status(mock_update, mock_context)
        
        mock_update.message.reply_text.assert_called_once()
        assert "No active run" in mock_update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_cmd_status_with_run(self, telegram_bot, mock_update, mock_context, mock_database):
        """Test /status command with active run."""
        mock_database.get_current_run.return_value = {
            'jobs_scraped': 50,
            'jobs_matched': 10,
            'jobs_pending_decision': 3,
            'jobs_auto_applied': 5,
            'jobs_failed': 2,
            'started_at': '2024-01-24 10:00:00'
        }
        
        await telegram_bot._cmd_status(mock_update, mock_context)
        
        mock_update.message.reply_text.assert_called_once()
        call_text = mock_update.message.reply_text.call_args[0][0]
        assert "50" in call_text  # jobs_scraped
        assert "10" in call_text  # jobs_matched

    @pytest.mark.asyncio
    async def test_cmd_pending_no_jobs(self, telegram_bot, mock_update, mock_context, mock_database):
        """Test /pending command with no pending jobs."""
        mock_database.get_jobs_by_status.return_value = []
        
        await telegram_bot._cmd_pending(mock_update, mock_context)
        
        mock_update.message.reply_text.assert_called_once()
        assert "No jobs pending" in mock_update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_cmd_pending_with_jobs(self, telegram_bot, mock_update, mock_context, mock_database, sample_job):
        """Test /pending command with pending jobs."""
        mock_database.get_jobs_by_status.return_value = [sample_job]
        
        await telegram_bot._cmd_pending(mock_update, mock_context)
        
        mock_update.message.reply_text.assert_called_once()
        call_text = mock_update.message.reply_text.call_args[0][0]
        assert sample_job.title in call_text
        assert sample_job.company in call_text

    @pytest.mark.asyncio
    async def test_cmd_approve_no_args(self, telegram_bot, mock_update, mock_context):
        """Test /approve command without job_id."""
        mock_context.args = []
        
        await telegram_bot._cmd_approve(mock_update, mock_context)
        
        mock_update.message.reply_text.assert_called_once()
        assert "Usage" in mock_update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_cmd_approve_invalid_id(self, telegram_bot, mock_update, mock_context):
        """Test /approve command with invalid job_id."""
        mock_context.args = ["invalid"]
        
        await telegram_bot._cmd_approve(mock_update, mock_context)
        
        mock_update.message.reply_text.assert_called_once()
        assert "Invalid" in mock_update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_cmd_skip(self, telegram_bot, mock_update, mock_context, mock_database):
        """Test /skip command."""
        mock_context.args = ["123"]
        
        await telegram_bot._cmd_skip(mock_update, mock_context)
        
        mock_database.update_job_status.assert_called_once_with(123, "skipped")
        mock_update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_cmd_daily(self, telegram_bot, mock_update, mock_context, mock_database):
        """Test /daily command."""
        mock_database.get_daily_stats.return_value = {
            'scraped': 50,
            'high_match': 10,
            'medium_match': 15,
            'rejected': 25,
            'auto_applied': 5,
            'manual_applied': 2,
            'failed': 1,
            'pending': 3,
            'success_rate': 0.85,
            'glm_cost': 0.05,
            'claude_cost': 0.07,
            'total_cost': 0.12
        }
        
        await telegram_bot._cmd_daily(mock_update, mock_context)
        
        mock_update.message.reply_text.assert_called_once()
        call_text = mock_update.message.reply_text.call_args[0][0]
        assert "Daily Digest" in call_text
        assert "50" in call_text  # scraped


# ============================================================================
# Callback Handler Tests
# ============================================================================


class TestCallbackHandlers:
    """Test callback query handlers."""

    @pytest.mark.asyncio
    async def test_handle_callback_approve(self, telegram_bot, mock_update, mock_context, mock_database):
        """Test handling approve callback."""
        mock_update.callback_query.data = "approve_123"
        
        with patch.object(telegram_bot, '_process_approval', new=AsyncMock()) as mock_process:
            await telegram_bot._handle_callback(mock_update, mock_context)
            
            mock_update.callback_query.answer.assert_called_once()
            mock_process.assert_called_once_with(123, mock_update)
            mock_update.callback_query.edit_message_reply_markup.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_callback_skip(self, telegram_bot, mock_update, mock_context, mock_database):
        """Test handling skip callback."""
        mock_update.callback_query.data = "skip_456"
        
        await telegram_bot._handle_callback(mock_update, mock_context)
        
        mock_update.callback_query.answer.assert_called_once()
        mock_database.update_job_status.assert_called_once_with(456, "skipped")
        mock_update.callback_query.edit_message_reply_markup.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_callback_retry(self, telegram_bot, mock_update, mock_context):
        """Test handling retry callback."""
        mock_update.callback_query.data = "retry_789"
        
        with patch.object(telegram_bot, '_process_approval', new=AsyncMock()) as mock_process:
            await telegram_bot._handle_callback(mock_update, mock_context)
            
            mock_update.callback_query.answer.assert_called_once()
            mock_process.assert_called_once_with(789, mock_update)


# ============================================================================
# Daily Digest Tests
# ============================================================================


class TestDailyDigest:
    """Test daily digest generation."""

    @pytest.mark.asyncio
    async def test_generate_daily_digest(self, telegram_bot, mock_database):
        """Test generating daily digest."""
        mock_database.get_daily_stats.return_value = {
            'scraped': 100,
            'high_match': 20,
            'medium_match': 30,
            'rejected': 50,
            'auto_applied': 10,
            'manual_applied': 5,
            'failed': 2,
            'pending': 3,
            'success_rate': 0.87,
            'glm_cost': 0.10,
            'claude_cost': 0.15,
            'total_cost': 0.25
        }
        
        digest = await telegram_bot._generate_daily_digest()
        
        assert "Daily Digest" in digest
        assert "100" in digest  # scraped
        assert "87%" in digest  # success_rate
        assert "$0.25" in digest  # total_cost

    @pytest.mark.asyncio
    async def test_send_daily_digest(self, telegram_bot, mock_database):
        """Test sending daily digest."""
        mock_database.get_daily_stats.return_value = {
            'scraped': 50,
            'high_match': 10,
            'medium_match': 15,
            'rejected': 25,
            'auto_applied': 5,
            'manual_applied': 2,
            'failed': 1,
            'pending': 3,
            'success_rate': 0.85,
            'glm_cost': 0.05,
            'claude_cost': 0.07,
            'total_cost': 0.12
        }
        
        await telegram_bot.send_daily_digest()
        
        telegram_bot.app.bot.send_message.assert_called_once()
