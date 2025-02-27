"""
Schema validator for Claude-compatible tools.
Validates and fixes common issues in tool definitions to ensure compatibility.
"""

import json
import copy
import re

def fix_schema_references(schema):
    """
    Fix references in JSON schema to be compatible with draft 2020-12
    
    Args:
        schema (dict): JSON schema to fix
        
    Returns:
        dict: Fixed schema
    """
    if not isinstance(schema, dict):
        return schema
    
    result = {}
    
    for key, value in schema.items():
        # Replace $ref references that point to #/components with standard references
        if key == "$ref" and isinstance(value, str) and value.startswith("#/components/"):
            # For example: "#/components/schemas/SampleType" is invalid for Claude
            # Just remove the reference - we'll handle the type in a simplified way
            continue
        
        # Handle anyOf with null to make it a proper nullable type
        elif key == "anyOf" and isinstance(value, list) and len(value) == 2:
            # Common pattern in OpenAPI: anyOf with a type and null
            type_obj = None
            has_null = False
            
            for item in value:
                if isinstance(item, dict) and item.get("type") == "null":
                    has_null = True
                else:
                    type_obj = item
            
            if has_null and type_obj:
                if isinstance(type_obj, dict) and "$ref" in type_obj:
                    # If it's a reference, just use string type as a fallback
                    result["type"] = ["string", "null"]
                else:
                    # Copy all properties from type_obj
                    for k, v in type_obj.items():
                        if k == "type":
                            # Make the type nullable
                            result["type"] = [v, "null"]
                        else:
                            result[k] = fix_schema_references(v)
                continue
        
        # Recursively process nested objects and arrays
        elif isinstance(value, dict):
            result[key] = fix_schema_references(value)
        elif isinstance(value, list):
            result[key] = [fix_schema_references(item) for item in value]
        else:
            result[key] = value
    
    return result

def validate_and_fix_tool(tool):
    """
    Validate a tool definition and fix common issues to make it compatible with Claude
    
    Args:
        tool (dict): Tool definition
        
    Returns:
        dict: Fixed tool definition
    """
    fixed_tool = copy.deepcopy(tool)
    
    # Ensure tool has required fields
    required_fields = ["name", "description", "input_schema"]
    for field in required_fields:
        if field not in fixed_tool:
            if field == "description" and "name" in fixed_tool:
                # Add a generic description if missing
                fixed_tool["description"] = f"Tool to {fixed_tool['name'].replace('_', ' ')}"
            else:
                raise ValueError(f"Tool is missing required field: {field}")
    
    # Ensure name is not too long (max 64 characters for Claude)
    if len(fixed_tool["name"]) > 64:
        original_name = fixed_tool["name"]
        # Keep method and meaningful parts
        parts = original_name.split('_')
        if len(parts) >= 3:
            prefix = '_'.join(parts[:3])  # Keep api_call_get
            suffix = parts[-1]  # Keep last part
            
            # Calculate remaining space for middle parts
            remaining_chars = 64 - len(prefix) - len(suffix) - 2  # 2 for underscores
            
            if remaining_chars > 0:
                # Add truncated middle parts
                middle = '_'.join(parts[3:-1])
                if len(middle) > remaining_chars:
                    middle = middle[:remaining_chars]
                
                fixed_tool["name"] = f"{prefix}_{middle}_{suffix}"
            else:
                # Not enough space, use simple truncation
                fixed_tool["name"] = original_name[:60] + "..."
        else:
            # Simple case, just truncate
            fixed_tool["name"] = original_name[:60] + "..."
    
    # Ensure input_schema is a valid JSON Schema
    if "input_schema" in fixed_tool:
        # Make sure input_schema has required fields for Claude
        input_schema = fixed_tool["input_schema"]
        
        if not isinstance(input_schema, dict):
            raise ValueError("input_schema must be an object")
        
        # Make sure it has 'type' field
        if "type" not in input_schema:
            input_schema["type"] = "object"
        
        # Fix schema references
        fixed_tool["input_schema"] = fix_schema_references(input_schema)
    
    return fixed_tool

def validate_and_fix_tools(tools):
    """
    Validate a list of tools and fix common issues to make them compatible with Claude
    
    Args:
        tools (list): List of tool definitions
        
    Returns:
        list: Fixed tool definitions
        list: List of tools that couldn't be fixed
    """
    fixed_tools = []
    failed_tools = []
    
    for i, tool in enumerate(tools):
        try:
            fixed_tool = validate_and_fix_tool(tool)
            fixed_tools.append(fixed_tool)
        except Exception as e:
            print(f"Error fixing tool {i} ({tool.get('name', 'unknown')}): {str(e)}")
            failed_tools.append({"tool": tool, "error": str(e)})
    
    return fixed_tools, failed_tools

def write_fixed_tools(input_file, output_file=None):
    """
    Read tools from a file, fix them, and write them back or to a new file
    
    Args:
        input_file (str): Path to the input file
        output_file (str, optional): Path to the output file. If None, will add '_fixed' to the input filename
        
    Returns:
        tuple: (success, message, path_to_output_file)
    """
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            tools = json.load(f)
        
        if not isinstance(tools, list):
            return False, "Input file does not contain a list of tools", None
        
        fixed_tools, failed_tools = validate_and_fix_tools(tools)
        
        if not output_file:
            # Generate output filename by adding '_fixed' before the extension
            name_parts = input_file.rsplit(".", 1)
            if len(name_parts) > 1:
                output_file = f"{name_parts[0]}_fixed.{name_parts[1]}"
            else:
                output_file = f"{input_file}_fixed"
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(fixed_tools, f, indent=2)
        
        message = f"Fixed {len(fixed_tools)} tools"
        if failed_tools:
            message += f", but {len(failed_tools)} tools could not be fixed"
        
        return True, message, output_file
    except Exception as e:
        return False, f"Error: {str(e)}", None
