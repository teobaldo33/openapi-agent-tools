"""
Compatibility module to redirect to schema_validator functions.
This helps existing code that imports from tool_schema_validator.
"""

from .schema_validator import validate_and_fix_tools, validate_and_fix_tool, write_fixed_tools

__all__ = [
    'validate_and_fix_tools',
    'validate_and_fix_tool',
    'write_fixed_tools'
]
