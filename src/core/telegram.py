"""Telegram bot for job hunter notifications and user decisions.

This module provides a Telegram bot interface for the Job Hunter application,
enabling real-time notifications about job matches, interactive decision-making
via inline buttons, and comprehensive daily digests of application activity.

Features:
- Job match notifications with inline approve/skip buttons
- Command handlers for status checks and manual actions
- Daily digest generation with statistics and cost estimates
- Async architecture compatible with telegram.ext library
"""

import os
from datetime import datetime
from typing import Optional, List

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from src.core.database import Database
from src.utils.logger import get_logger

logger = get_logger(__name__)


class TelegramBot:
    """Telegram bot for job hunter notifications.
    
    Provides notification capabilities and interactive user decision handling
    for the Job Hunter application. Supports command-based interaction and
    inline button callbacks for approving or skipping job applications.
    
    Example:
        bot = TelegramBot()
        await bot.initialize()
        await bot.send_job_notification(job_id=123, notification_type="match")
    """

    def __init__(
        self,
        token: Optional[str] = None,
        chat_id: Optional[str] = None,
        db: Optional[Database] = None
    ):
        """Initialize Telegram bot.

        Args:
            token: Bot token (or from TELEGRAM_BOT_TOKEN env var)
            chat_id: Default chat ID (or from TELEGRAM_CHAT_ID env var)
            db: Database instance (creates new if None)
        """
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.db = db or Database()
        self.app: Optional[Application] = None

        if not self.token:
            logger.warning("TELEGRAM_BOT_TOKEN not set - bot will not be functional")
        if not self.chat_id:
            logger.warning("TELEGRAM_CHAT_ID not set - using token's default chat")

    async def initialize(self) -> None:
        """Initialize bot application and register handlers.
        
        Sets up the telegram Application, registers all command and callback
        handlers, and prepares the bot for operation.
        """
        if not self.token:
            logger.error("Cannot initialize bot without token")
            return

        self.app = Application.builder().token(self.token).build()

        # Register command handlers
        self.app.add_handler(CommandHandler("start", self._cmd_start))
        self.app.add_handler(CommandHandler("status", self._cmd_status))
        self.app.add_handler(CommandHandler("pending", self._cmd_pending))
        self.app.add_handler(CommandHandler("approve", self._cmd_approve))
        self.app.add_handler(CommandHandler("skip", self._cmd_skip))
        self.app.add_handler(CommandHandler("daily", self._cmd_daily))
        self.app.add_handler(CommandHandler("help", self._cmd_help))

        # Callback query handler for inline buttons
        self.app.add_handler(CallbackQueryHandler(self._handle_callback))

        await self.app.initialize()
        logger.info("Telegram bot initialized successfully")

    async def send_message(
        self,
        text: str,
        chat_id: Optional[str] = None,
        parse_mode: str = "Markdown",
        reply_markup=None
    ) -> int:
        """Send a message.

        Args:
            text: Message text
            chat_id: Target chat (default: configured chat)
            parse_mode: Markdown, HTML, or MarkdownV2
            reply_markup: Optional keyboard markup

        Returns:
            Message ID

        Raises:
            Exception: If bot not initialized or message send fails
        """
        if not self.app:
            raise Exception("Bot not initialized - call initialize() first")

        chat_id = chat_id or self.chat_id

        message = await self.app.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup
        )

        return message.message_id

    async def send_job_notification(
        self,
        job_id: int,
        notification_type: str = "match"
    ) -> Optional[int]:
        """Send job notification with action buttons.

        Args:
            job_id: Job ID
            notification_type: 'match', 'applied', 'failed'

        Returns:
            Message ID, or None if job not found
        """
        job = self.db.get_job_by_id(job_id)
        if not job:
            logger.error(f"Job {job_id} not found in database")
            return None

        if notification_type == "match":
            text = self._format_job_match(job)
            keyboard = self._get_decision_keyboard(job_id)
        elif notification_type == "applied":
            text = self._format_job_applied(job)
            keyboard = None
        elif notification_type == "failed":
            text = self._format_job_failed(job)
            keyboard = self._get_retry_keyboard(job_id)
        else:
            text = f"Job update: {job.title} @ {job.company}"
            keyboard = None

        return await self.send_message(text, reply_markup=keyboard)

    # === Message Formatting ===

    def _format_job_match(self, job) -> str:
        """Format job match notification.
        
        Args:
            job: Job dataclass instance
            
        Returns:
            Formatted message text with Markdown
        """
        score_emoji = "🔥" if job.match_score >= 0.85 else "✨"
        score_pct = int(job.match_score * 100) if job.match_score else 0

        text = f"""
{score_emoji} *Job Match Found*

*{job.title}*
🏢 {job.company}
📍 {job.location or "Remote"}
💰 {self._format_salary(job)}
📊 Match Score: {score_pct}%

*Why it matches:*
{job.match_reasoning or "No details"}

*Key Requirements:*
{self._format_list(job.key_requirements)}

{self._format_red_flags(job.red_flags)}

🔗 [View Job]({job.url})
"""
        return text.strip()

    def _format_job_applied(self, job) -> str:
        """Format job applied notification.
        
        Args:
            job: Job dataclass instance
            
        Returns:
            Formatted message text with Markdown
        """
        score_pct = int(job.match_score * 100) if job.match_score else 0
        return f"""
✅ *Application Submitted*

*{job.title}* @ {job.company}
📊 Match Score: {score_pct}%

Your tailored resume was submitted.
"""

    def _format_job_failed(self, job) -> str:
        """Format job failed notification.
        
        Args:
            job: Job dataclass instance
            
        Returns:
            Formatted message text with Markdown
        """
        return f"""
❌ *Application Failed*

*{job.title}* @ {job.company}

Error: Check logs for details.
"""

    def _format_salary(self, job) -> str:
        """Format salary range.
        
        Args:
            job: Job dataclass instance
            
        Returns:
            Formatted salary string
        """
        if job.salary_min and job.salary_max:
            return f"${job.salary_min:,} - ${job.salary_max:,}"
        elif job.salary_min:
            return f"${job.salary_min:,}+"
        elif job.salary_max:
            return f"Up to ${job.salary_max:,}"
        return "Not specified"

    def _format_list(self, items: Optional[List[str]]) -> str:
        """Format list as bullet points.
        
        Args:
            items: List of strings to format
            
        Returns:
            Formatted bullet point list (max 5 items)
        """
        if not items:
            return "None specified"
        return "\n".join(f"• {item}" for item in items[:5])

    def _format_red_flags(self, red_flags: Optional[List[str]]) -> str:
        """Format red flags section.
        
        Args:
            red_flags: List of red flag strings
            
        Returns:
            Formatted red flags section with warning emoji, or empty string
        """
        if not red_flags:
            return ""
        flags = "\n".join(f"• {flag}" for flag in red_flags)
        return f"\n⚠️ *Concerns:*\n{flags}"

    # === Inline Keyboards ===

    def _get_decision_keyboard(self, job_id: int) -> InlineKeyboardMarkup:
        """Create inline keyboard for job decision.
        
        Args:
            job_id: Job ID for callback data
            
        Returns:
            InlineKeyboardMarkup with approve/skip buttons
        """
        keyboard = [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_{job_id}"),
                InlineKeyboardButton("⏭️ Skip", callback_data=f"skip_{job_id}"),
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    def _get_retry_keyboard(self, job_id: int) -> InlineKeyboardMarkup:
        """Create retry keyboard for failed jobs.
        
        Args:
            job_id: Job ID for callback data
            
        Returns:
            InlineKeyboardMarkup with retry/skip buttons
        """
        keyboard = [
            [
                InlineKeyboardButton("🔄 Retry", callback_data=f"retry_{job_id}"),
                InlineKeyboardButton("⏭️ Skip", callback_data=f"skip_{job_id}"),
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    # === Command Handlers ===

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command.
        
        Args:
            update: Telegram update object
            context: Handler context
        """
        await update.message.reply_text(
            "👋 Welcome to Job Hunter Bot!\n\n"
            "I'll notify you about matching jobs and help you decide.\n\n"
            "Commands:\n"
            "/status - View today's stats\n"
            "/pending - List pending decisions\n"
            "/approve <id> - Approve a job\n"
            "/skip <id> - Skip a job\n"
            "/daily - Get daily digest\n"
            "/help - Show this help"
        )

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command.
        
        Args:
            update: Telegram update object
            context: Handler context
        """
        run = self.db.get_current_run()
        if not run:
            await update.message.reply_text("No active run.")
            return

        text = f"""
📊 *Today's Status*

🔍 Jobs Scraped: {run['jobs_scraped']}
✅ High Match: {run['jobs_matched']}
🤔 Pending Decision: {run['jobs_pending_decision']}
📤 Auto-Applied: {run['jobs_auto_applied']}
❌ Failed: {run['jobs_failed']}

_Started: {run['started_at']}_
"""
        await update.message.reply_text(text, parse_mode="Markdown")

    async def _cmd_pending(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /pending command.
        
        Args:
            update: Telegram update object
            context: Handler context
        """
        pending = self.db.get_jobs_by_status("pending_decision", limit=10)

        if not pending:
            await update.message.reply_text("No jobs pending decision.")
            return

        text = "*Jobs Pending Decision:*\n\n"
        for job in pending:
            score = int(job.match_score * 100) if job.match_score else 0
            text += f"• `{job.id}`: {job.title} @ {job.company} ({score}%)\n"

        text += "\nUse /approve <id> or /skip <id>"
        await update.message.reply_text(text, parse_mode="Markdown")

    async def _cmd_approve(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /approve <job_id> command.
        
        Args:
            update: Telegram update object
            context: Handler context
        """
        if not context.args:
            await update.message.reply_text("Usage: /approve <job_id>")
            return

        try:
            job_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Invalid job ID")
            return

        # Trigger approval flow
        await self._process_approval(job_id, update)

    async def _cmd_skip(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /skip <job_id> command.
        
        Args:
            update: Telegram update object
            context: Handler context
        """
        if not context.args:
            await update.message.reply_text("Usage: /skip <job_id>")
            return

        try:
            job_id = int(context.args[0])
            reason = " ".join(context.args[1:]) if len(context.args) > 1 else None
        except ValueError:
            await update.message.reply_text("Invalid job ID")
            return

        self.db.update_job_status(job_id, "skipped")
        await update.message.reply_text(f"⏭️ Job {job_id} skipped.")

    async def _cmd_daily(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /daily command - send daily digest.
        
        Args:
            update: Telegram update object
            context: Handler context
        """
        digest = await self._generate_daily_digest()
        await update.message.reply_text(digest, parse_mode="Markdown")

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command.
        
        Args:
            update: Telegram update object
            context: Handler context
        """
        await self._cmd_start(update, context)

    # === Callback Query Handler ===

    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button callbacks.
        
        Args:
            update: Telegram update object
            context: Handler context
        """
        query = update.callback_query
        await query.answer()

        data = query.data
        action, job_id_str = data.rsplit("_", 1)
        job_id = int(job_id_str)

        if action == "approve":
            await self._process_approval(job_id, update)
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text(f"✅ Job {job_id} approved! Applying...")

        elif action == "skip":
            self.db.update_job_status(job_id, "skipped")
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text(f"⏭️ Job {job_id} skipped.")

        elif action == "retry":
            await query.message.reply_text(f"🔄 Retrying job {job_id}...")
            # Trigger retry logic (could implement similar to approve)
            await self._process_approval(job_id, update)

    async def _process_approval(self, job_id: int, update: Update):
        """Process job approval and trigger application.
        
        Args:
            job_id: Job ID to approve and apply for
            update: Telegram update object for sending messages
        """
        try:
            # Update status
            self.db.update_job_status(job_id, "approved")

            # Import services here to avoid circular imports
            from src.core.applier import JobApplierService

            # Note: Resume tailoring should have been done already during filtering
            # If not, we would need to call ResumeTailorService here

            # Apply to job
            applier = JobApplierService(db=self.db)
            apply_result = await applier.apply_to_job(job_id)

            if apply_result.success:
                await self.send_job_notification(job_id, "applied")
            else:
                await self.send_job_notification(job_id, "failed")

        except Exception as e:
            logger.error(f"Approval processing failed: {e}", exc_info=True)
            await update.effective_message.reply_text(
                f"❌ Error processing job {job_id}: {str(e)}"
            )

    # === Daily Digest ===

    async def _generate_daily_digest(self) -> str:
        """Generate daily summary digest.
        
        Returns:
            Formatted digest text with Markdown
        """
        # Get today's stats
        today = datetime.now().date()

        # Query database for stats
        stats = self.db.get_daily_stats(today)

        # Get manual pending jobs
        manual_pending = self.db.get_jobs_by_status("manual_apply_pending")
        manual_section = ""
        if manual_pending:
            manual_section = "\n📝 *Ready for Manual Apply*\n"
            for job in manual_pending[:5]:
                manual_section += f"• [{job.company} - {job.title}]({job.url}) (Resume ready)\n"
            if len(manual_pending) > 5:
                manual_section += f"_...and {len(manual_pending) - 5} more_\n"

        digest = f"""
📅 *Daily Digest - {today.strftime('%B %d, %Y')}*

📊 *Overview*
• Jobs Scraped: {stats['scraped']}
• High Match: {stats['high_match']}
• Medium Match: {stats['medium_match']}
• Rejected: {stats['rejected']}

📤 *Applications*
• Auto-Applied: {stats['auto_applied']}
• Manual Applied: {stats['manual_applied']}
• Failed: {stats['failed']}
• Success Rate: {stats['success_rate']:.0%}

🤔 *Pending Decisions: {stats['pending']}*
{manual_section}
💰 *Estimated Cost*
• GLM Filtering: ${stats['glm_cost']:.2f}
• Claude Tailoring: ${stats['claude_cost']:.2f}
• Total: ${stats['total_cost']:.2f}

_Report generated at {datetime.now().strftime('%H:%M')}_
"""
        return digest

    async def send_daily_digest(self):
        """Send daily digest to configured chat.
        
        Convenience method for scheduled daily digest sending.
        """
        digest = await self._generate_daily_digest()
        await self.send_message(digest)
