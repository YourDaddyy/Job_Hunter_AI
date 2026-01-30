"""PDF generation for resumes using WeasyPrint.

This module provides PDF generation from HTML templates using WeasyPrint,
which converts HTML/CSS to high-quality PDFs suitable for job applications.
"""

import os

# Add GTK to DLL search path for WeasyPrint on Windows (Python 3.8+)
gtk_path = r'W:\Code Soft\GTK3-Runtime Win64\bin'
if os.path.exists(gtk_path):
    # Required for Python 3.8+ on Windows
    if hasattr(os, 'add_dll_directory'):
        os.add_dll_directory(gtk_path)
    # Also add to PATH for backwards compatibility
    if gtk_path not in os.environ.get('PATH', ''):
        os.environ['PATH'] = gtk_path + os.pathsep + os.environ.get('PATH', '')

from pathlib import Path
from typing import Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.utils.logger import get_logger

try:
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration
    WEASYPRINT_AVAILABLE = True
except (ImportError, OSError) as e:
    logger = get_logger(__name__)
    logger.warning(f"WeasyPrint not available (PDF generation will fail): {e}")
    WEASYPRINT_AVAILABLE = False
    # Mock classes to avoid NameError
    class HTML: pass
    class CSS: pass
    class FontConfiguration: pass

logger = get_logger(__name__)


class PDFGenerator:
    """Generate PDFs from HTML templates using WeasyPrint.
    
    Features:
    - Jinja2 template rendering
    - High-quality PDF output
    - Custom CSS support
    - Font configuration
    """

    def __init__(self, template_dir: str = "templates/resume"):
        """Initialize PDF generator.
        
        Args:
            template_dir: Directory containing HTML templates
        """
        self.template_dir = Path(template_dir)
        
        # Initialize Jinja2 environment
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(['html', 'xml'])
        )
        
        # Font configuration for WeasyPrint
        self.font_config = FontConfiguration()
        
        logger.info(f"PDFGenerator initialized with template_dir: {template_dir}")

    def render_template(
        self,
        template_name: str,
        data: Dict[str, Any]
    ) -> str:
        """Render HTML template with data.
        
        Args:
            template_name: Name of template file (e.g., 'modern', 'ats_friendly')
            data: Data to pass to template
            
        Returns:
            Rendered HTML string
            
        Raises:
            FileNotFoundError: If template not found
        """
        # Add .html extension if not present
        if not template_name.endswith('.html'):
            template_name = f"{template_name}.html"
        
        try:
            template = self.jinja_env.get_template(template_name)
            html_content = template.render(**data)
            
            logger.debug(f"Rendered template: {template_name}")
            return html_content
            
        except Exception as e:
            logger.error(f"Failed to render template {template_name}: {e}")
            raise

    def generate_pdf(
        self,
        html_content: str,
        output_path: str,
        custom_css: Optional[str] = None
    ) -> None:
        """Generate PDF from HTML content.
        
        Args:
            html_content: HTML string to convert
            output_path: Path to save PDF file
            custom_css: Optional custom CSS to apply
            
        Raises:
            Exception: If PDF generation fails
        """
        try:
            # Ensure output directory exists
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Create HTML object
            html = HTML(string=html_content)
            
            # Add custom CSS if provided
            stylesheets = []
            if custom_css:
                stylesheets.append(CSS(string=custom_css))
            
            # Generate PDF
            html.write_pdf(
                target=str(output_file),
                stylesheets=stylesheets,
                font_config=self.font_config
            )
            
            logger.info(f"PDF generated successfully: {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to generate PDF: {e}")
            raise

    def generate_resume_pdf(
        self,
        resume_data: Dict[str, Any],
        output_path: str,
        template: str = "modern"
    ) -> None:
        """Generate resume PDF from data.
        
        Convenience method that renders template and generates PDF in one call.
        
        Args:
            resume_data: Resume data dict
            output_path: Path to save PDF
            template: Template name ('modern' or 'ats_friendly')
        """
        logger.info(f"Generating resume PDF with template: {template}")
        
        # Render template
        html_content = self.render_template(template, resume_data)
        
        # Generate PDF
        self.generate_pdf(html_content, output_path)
        
        logger.info(f"Resume PDF complete: {output_path}")
