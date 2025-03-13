# checker.py (fixed)
import os
import argparse
from groq import Groq
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError
import json
import instructor
import supabase

load_dotenv()

# Initialize Supabase client (safe to keep at module level)
supabase = supabase.create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

class CodeChange(BaseModel):
    path: str
    old_content: str  # Changed from code_content
    new_content: str  # New field
    reason: str
    add: bool

def analyze_file_with_llm(file_path):
    """Analyzes a file using Groq API."""
    # Initialize Groq client INSIDE the function
    client = Groq(api_key="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")
    client = instructor.from_groq(client, mode=instructor.Mode.JSON)

    with open(file_path, 'r', encoding="utf-8", errors="ignore") as f:
        file_content = f.read()

    user_prompt = (
        "Analyze the following code and determine if the syntax is out of date.\n\n"
        "{\n"
        '  "path": "relative/file/path",\n'
        '  "code_content": "The entire content of the file, before any changes are made. This should be a complete file, not just a partial updated code segment."\n'
        '  "reason": "A short explanation of why the code is out of date."\n'
        "}\n\n"
        f"{file_content}"
    )

    try:
        chat_completion = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": "You analyze code for outdated syntax."},
                {"role": "user", "content": user_prompt}
            ],
            response_model=CodeChange,
        )

        # Ensure the add field is a boolean
        if isinstance(chat_completion.add, str):
            # Convert string representation of boolean to actual boolean
            chat_completion.add = chat_completion.add.lower() == 'true'

        data = {
            "status": "READING",
            "message": f"Reading {file_path.split('/')[-1]}...",
            "code": chat_completion.code_content
        }
        supabase.table("repo-updates").insert(data).execute()
        
        return chat_completion
    except (ValidationError, json.JSONDecodeError) as parse_error:
        print(f"Error parsing LLM response for {file_path}: {parse_error}")
        return None
    except Exception as e:
        # Handle any other exceptions, e.g. network errors, model issues, etc.
        print(f"Error analyzing {file_path}: {e}")
        return None
    
def fetch_updates(directory):
    """Fetches updates for all files in directory."""
    analysis_results = []
    all_files = get_all_files_recursively(directory)
    
    for filepath in all_files:
        if (
            os.path.basename(filepath).startswith(".") or
            filepath.endswith((".css", ".json", ".md", ".svg", ".ico", ".mjs", ".gitignore", ".env")) or
            ".git/" in filepath
        ):
            continue
            
        response = analyze_file_with_llm(filepath)
        if response and response.add:
            response.path = filepath  # Ensure path is set
            analysis_results.append(response)
    
    return analysis_results

def main():
    print(fetch_updates("website-test"))

if __name__ == "__main__":
    main()