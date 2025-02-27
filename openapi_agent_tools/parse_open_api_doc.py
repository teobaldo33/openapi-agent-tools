"""
Compatibility module to redirect to parse_openapi functions.
This helps existing code that imports from parse_open_api_doc.
"""

from .parse_openapi import (
    load_openapi_from_url,
    load_openapi_from_file,
    generate_tools_from_openapi
)

__all__ = [
    'load_openapi_from_url',
    'load_openapi_from_file',
    'generate_tools_from_openapi'
]
