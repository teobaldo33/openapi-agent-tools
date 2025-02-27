"""
OpenAPI parsing module for generating Claude-compatible tools from OpenAPI specifications.
"""

import json
import yaml
import requests
import re
import os
import chardet

def is_yaml_content(content):
    """
    Determine if content is likely YAML format.
    
    Args:
        content (str): Content to check
        
    Returns:
        bool: True if content appears to be YAML, False otherwise
    """
    # If the content is empty or not a string, it's not YAML
    if not content or not isinstance(content, str):
        return False
        
    # Try looking for common YAML patterns
    yaml_patterns = re.findall(r'^[a-zA-Z0-9_-]+:\s.*$', content, re.MULTILINE)
    if yaml_patterns:
        return True
        
    # Check for other YAML indicators
    if "---" in content[:20] or "openapi:" in content[:1000]:
        return True
        
    return False

def load_openapi_spec(content, filename=None):
    """
    Load an OpenAPI specification from string content.
    
    Args:
        content (str): JSON or YAML content
        filename (str, optional): Original filename for extension-based detection
        
    Returns:
        dict: Parsed OpenAPI specification
    """
    # If filename is provided, check extension
    if filename and (filename.lower().endswith('.yml') or filename.lower().endswith('.yaml')):
        try:
            return yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML content: {str(e)}")
    
    # Otherwise try to detect format from content
    if is_yaml_content(content):
        try:
            return yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML content: {str(e)}")
    else:
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            # If JSON parsing fails, try YAML as a fallback
            try:
                return yaml.safe_load(content)
            except yaml.YAMLError:
                raise ValueError(f"Failed to parse as either JSON or YAML: {str(e)}")

def generate_tools_from_openapi(openapi_spec, base_url="http://localhost:9999"):
    """
    Generate a list of tools from an OpenAPI specification.
    
    Args:
        openapi_spec (dict): The OpenAPI specification
        base_url (str): The base URL for the API
        
    Returns:
        list: A list of tools in the required format
    """
    tools = []
    
    # Process all API paths
    for path, path_item in openapi_spec.get("paths", {}).items():
        # Process HTTP methods (GET, POST, PATCH, DELETE)
        for method, operation in path_item.items():
            if method.lower() not in ["get", "post", "patch", "delete"]:
                continue
                
            # Create tool name
            endpoint = path.strip("/").replace("/", "_").replace("{", "").replace("}", "")
            tool_name = f"api_call_{method.lower()}_{endpoint}"
            
            # Get description
            description = operation.get("description", operation.get("summary", ""))
            if not description and "responses" in operation and "200" in operation["responses"]:
                description = operation["responses"]["200"].get("description", "")
            
            # Create input schema
            input_schema = {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL to send the request to",
                        "default": f"{base_url}{path}"
                    },
                    "method": {
                        "type": "string",
                        "description": "HTTP method to use",
                        "enum": [method.upper()]
                    }
                },
                "required": ["url", "method"]
            }
            
            # Add request body if it exists
            if "requestBody" in operation and "content" in operation["requestBody"]:
                content_types = operation["requestBody"]["content"]
                
                # Handle different content types with priority
                if "application/json" in content_types and "schema" in content_types["application/json"]:
                    request_schema = content_types["application/json"]["schema"].copy()
                    requestBody = process_schema(request_schema)
                    
                    # Add the requestBody to input_schema
                    input_schema["properties"]["requestBody"] = requestBody
                
                # Handle multipart/form-data for file uploads
                elif "multipart/form-data" in content_types and "schema" in content_types["multipart/form-data"]:
                    request_schema = content_types["multipart/form-data"]["schema"].copy()
                    requestBody = process_schema(request_schema)
                    
                    # Add the requestBody and note that it's form data
                    input_schema["properties"]["requestBody"] = requestBody
                    input_schema["properties"]["requestBody"]["description"] = "Form data for file upload"
                    
                    # Add special note for file uploads
                    if "properties" in request_schema and "file" in request_schema.get("properties", {}):
                        input_schema["properties"]["requestBody"]["notes"] = "Contains file upload. Use base64 encoded content."
            
            # Add parameters if any
            if "parameters" in operation:
                params_schema = {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
                
                for param in operation["parameters"]:
                    param_name = param["name"]
                    if "schema" in param:
                        param_schema = param["schema"].copy()
                        if "description" not in param_schema and "description" in param:
                            param_schema["description"] = param["description"]
                        params_schema["properties"][param_name] = param_schema
                    
                    if param.get("required", False):
                        params_schema["required"].append(param_name)
                
                if params_schema["properties"]:
                    input_schema["properties"]["params"] = params_schema
            
            # Create the tool
            tool = {
                "name": tool_name,
                "description": description,
                "input_schema": input_schema
            }
            
            tools.append(tool)
    
    print(f"Generated {len(tools)} tools from OpenAPI spec")
    return tools

def process_schema(schema):
    """
    Process a JSON schema to ensure it's compatible with the tool format.
    Handles $refs and simplifies complex schemas.
    
    Args:
        schema (dict): The schema to process
        
    Returns:
        dict: A processed schema
    """
    # Make a copy to avoid modifying original
    result = {}
    
    # Copy basic properties
    for key, value in schema.items():
        if key == "$ref":
            # Skip references for now, we'll handle them separately
            continue
        elif key == "properties" and isinstance(value, dict):
            # Process properties recursively
            result[key] = {}
            for prop_name, prop_schema in value.items():
                result[key][prop_name] = process_schema(prop_schema)
        elif key == "items" and isinstance(value, dict):
            # Process array items recursively
            result[key] = process_schema(value)
        elif isinstance(value, dict):
            # Process nested objects recursively
            result[key] = process_schema(value)
        elif key == "anyOf" or key == "oneOf" or key == "allOf":
            # Simplify complex schemas
            if isinstance(value, list) and len(value) > 0:
                # Take the first option as a simplified version
                first_option = process_schema(value[0])
                for option_key, option_value in first_option.items():
                    result[option_key] = option_value
                # Add note about simplification
                result["description"] = schema.get("description", "") + " (Simplified from multiple options)"
        else:
            # Copy value as is
            result[key] = value
    
    # Ensure type is present
    if "type" not in result:
        # Default to object if type is missing
        result["type"] = "object"
    
    # Ensure description is present
    if "description" not in result:
        result["description"] = "No description available"
    
    return result

def load_openapi_from_url(url):
    """
    Load an OpenAPI specification from a URL.
    
    Args:
        url (str): URL to the OpenAPI specification
        
    Returns:
        dict: Parsed OpenAPI specification
    """
    # Extract filename from URL for extension detection
    filename = os.path.basename(url)
    
    try:
        # Add User-Agent header to avoid potential 403 errors
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
        }
        
        response = requests.get(url, headers=headers)
        print(f"Fetching URL: {url}")
        if response.status_code != 200:
            raise ValueError(f"Failed to fetch URL: HTTP {response.status_code}")
        
        # Check Content-Type header
        content_type = response.headers.get('Content-Type', '').lower()
        print(f"Content-Type: {content_type}")
        
        # Get raw content
        raw_content = response.content
        
        # Detect encoding if no encoding information
        if 'charset=' not in content_type:
            detection = chardet.detect(raw_content)
            encoding = detection['encoding'] or 'utf-8'
            print(f"Detected encoding: {encoding}")
        else:
            # Extract charset from Content-Type
            encoding = content_type.split('charset=')[1].split(';')[0]
            print(f"Content-Type specified encoding: {encoding}")
        
        # Decode content with proper encoding
        try:
            content = raw_content.decode(encoding)
        except UnicodeDecodeError:
            # Fallback to utf-8 if specified encoding fails
            content = raw_content.decode('utf-8', errors='replace')
            print("Using utf-8 with error replacement as fallback encoding")
        
        # Debug content start for troubleshooting
        content_preview = content[:200].replace('\n', ' ')
        print(f"Content preview: {content_preview}...")
        
        # Check beginning of content for YAML indicators
        if content.lstrip().startswith('---') or 'openapi:' in content[:1000]:
            print("Content appears to be YAML format")
            try:
                return yaml.safe_load(content)
            except yaml.YAMLError as e:
                print(f"YAML parsing error: {e}")
                # Try to parse with different loader
                try:
                    import ruamel.yaml
                    yaml_parser = ruamel.yaml.YAML(typ='safe')
                    return yaml_parser.load(content)
                except (ImportError, Exception) as e:
                    print(f"Alternative YAML parser error: {e}")
        
        # Use filename and content for detection
        return load_openapi_spec(content, filename)
    except Exception as e:
        print(f"Error in load_openapi_from_url: {str(e)}")
        raise

def load_openapi_from_file(file_path):
    """
    Load an OpenAPI specification from a file.
    
    Args:
        file_path (str): Path to the OpenAPI specification file
        
    Returns:
        dict: Parsed OpenAPI specification
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    return load_openapi_spec(content, file_path)
