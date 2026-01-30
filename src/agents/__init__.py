"""
Agents module for job_viewer.

This module contains AI agent configurations and instruction generators.
"""

from .instruction_generator import InstructionGenerator
from .platform_configs import PLATFORM_INSTRUCTIONS

__all__ = ['InstructionGenerator', 'PLATFORM_INSTRUCTIONS']
