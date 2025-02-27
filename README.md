# OpenAPI Agent Tools

A library for generating and validating Claude-compatible tools from OpenAPI specifications. I haven't tested it with other models but it should work too as tools are usually defined as JSON Schema

## Installation

```bash
pip install openapi-agent-tools
```

Or directly from the repository:

```bash
pip install git+https://github.com/teobaldo33/openapi-agent-tools.git
```

## Usage

### As a library

```python
from openapi_agent_tools import (
    load_openapi_from_url, 
    generate_tools_from_openapi,
    validate_and_fix_tools
)

# Load an OpenAPI specification from a URL
openapi_spec = load_openapi_from_url("http://localhost:9999/doc")

# Generate tools from the specification
tools = generate_tools_from_openapi(openapi_spec, base_url="http://localhost:9999")

# Validate and fix tools for Claude compatibility
fixed_tools, failed_tools = validate_and_fix_tools(tools)

print(f"Generated and fixed {len(fixed_tools)} tools")
```

### Command Line Interface

#### Generate tools from an OpenAPI specification

```bash
# From a file
openapi-agent-tools generate --file path/to/openapi.json --output tools.json

# From a URL with validation
openapi-agent-tools generate --url https://docs.mistral.ai/redocusaurus/plugin-redoc-0.yaml  --validate --output tools.json
```

#### Validate and fix existing tools

```bash
openapi-agent-tools validate path/to/tools.json --output fixed_tools.json
```

## Features

- **OpenAPI Analysis**: Process OpenAPI specifications to generate Agent-compatible tools
- **Schema Validation**: Check and fix common errors in tool definitions
- **Claude Compatibility**: Adapt schemas to be usable with AI Agents
- **CLI Interface**: Command line utilities for use in scripts

## License

MIT
