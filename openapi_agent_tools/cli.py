"""
Command-line interface for the OpenAPI Agent Tools library.
"""

import argparse
import json
import sys
import os

from .parse_openapi import load_openapi_from_url, load_openapi_from_file, generate_tools_from_openapi
from .schema_validator import validate_and_fix_tools, write_fixed_tools

def main():
    """Main CLI entrypoint for openapi-agent-tools"""
    parser = argparse.ArgumentParser(
        description='OpenAPI Agent Tools - Generate and validate Claude-compatible tools from OpenAPI specifications'
    )
    
    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # "generate" command
    generate_parser = subparsers.add_parser('generate', help='Generate tools from OpenAPI spec')
    generate_source = generate_parser.add_mutually_exclusive_group(required=True)
    generate_source.add_argument('--url', help='URL to OpenAPI specification')
    generate_source.add_argument('--file', help='Path to OpenAPI specification file')
    generate_parser.add_argument('--base-url', help='Base URL for API endpoints')
    generate_parser.add_argument('--output', '-o', help='Output file path for generated tools')
    generate_parser.add_argument('--validate', '-v', action='store_true', 
                                help='Also validate and fix tools after generation')
    
    # "validate" command
    validate_parser = subparsers.add_parser('validate', help='Validate and fix existing tools')
    validate_parser.add_argument('input_file', help='Input JSON file containing tools')
    validate_parser.add_argument('--output', '-o', help='Output file path for fixed tools')
    
    args = parser.parse_args()
    
    # Handle lack of command
    if not args.command:
        parser.print_help()
        return 1
    
    # Handle "generate" command
    if args.command == 'generate':
        try:
            # Load OpenAPI spec
            if args.url:
                print(f"Loading OpenAPI spec from URL: {args.url}")
                openapi_spec = load_openapi_from_url(args.url)
                # Use URL as base URL if not specified
                default_base_url = args.url.rsplit('/', 1)[0]
            elif args.file:
                print(f"Loading OpenAPI spec from file: {args.file}")
                openapi_spec = load_openapi_from_file(args.file)
                # Default base URL
                default_base_url = "http://localhost:9999"
            
            # Use specified base URL or the default
            base_url = args.base_url or default_base_url
            print(f"Using base URL: {base_url}")
            
            # Generate tools
            tools = generate_tools_from_openapi(openapi_spec, base_url)
            
            # Validate if requested
            if args.validate:
                print("Validating and fixing generated tools...")
                tools, failed_tools = validate_and_fix_tools(tools)
                if failed_tools:
                    print(f"Warning: {len(failed_tools)} tools couldn't be fixed")
            
            # Output the result
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    json.dump(tools, f, indent=2)
                print(f"Generated {len(tools)} tools and saved to {args.output}")
            else:
                # Print to stdout if no output file specified
                print(json.dumps(tools, indent=2))
            
            return 0
        except Exception as e:
            print(f"Error generating tools: {str(e)}")
            return 1
    
    # Handle "validate" command
    elif args.command == 'validate':
        try:
            success, message, output_path = write_fixed_tools(args.input_file, args.output)
            print(message)
            if success:
                print(f"Output written to: {output_path}")
                return 0
            else:
                return 1
        except Exception as e:
            print(f"Error validating tools: {str(e)}")
            return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
