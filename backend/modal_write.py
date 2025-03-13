import os
import modal
from dotenv import load_dotenv
import supabase
from pydantic import BaseModel, ValidationError
import json
import instructor

load_dotenv()

# Create the base image with all the pip installations
base_image = modal.Image.debian_slim(python_version="3.10") \
    .apt_install("git", "python3", "bash") \
    .pip_install("python-dotenv", "groq", "fastapi", "uvicorn", "modal", 
                 "instructor", "pydantic", "websockets", "supabase", "gitpython")

# Then explicitly add local Python modules
image = base_image.add_local_python_source(
    "checker",
    "containers",
    "git_driver",
    "server", 
    "socket_manager"
)

writeApp = modal.App(name="groq-write", image=image)

# Initialize supabase client outside the function
supabase_client = supabase.create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

class JobReport(BaseModel):
    refactored_code: str
    refactored_code_comments: str

@writeApp.function(secrets=[modal.Secret.from_name("GROQ_API_KEY"), 
                           modal.Secret.from_name("SUPABASE_URL"), 
                           modal.Secret.from_name("SUPABASE_KEY")])
def process_file(job):
    from groq import Groq
    from pydantic import ValidationError
    from os import getenv
    import instructor
    import json

    GROQ_API_KEY = getenv("GROQ_API_KEY")

    # Initialize Groq client with the API key from environment variable
    client = Groq(api_key="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")
    client = instructor.from_groq(client, mode=instructor.Mode.TOOLS)

    file_path = job["path"]
    code_content = job["old_content"]  # Changed from code_content to old_content

    user_prompt = (
        "Analyze the following code and determine if the syntax is out of date. "
        "If it is out of date, specify what changes need to be made in the following JSON format:\n\n"
        "{\n"
        '  "refactored_code": "A rewrite of the file that is more up to date, using the native language (i.e. if the file is a NextJS file, rewrite the NextJS file using Javascript/Typescript with the updated API changes)". The file should be a complete file, not just a partial updated code segment,\n'
        '  "refactored_code_comments": "Comments and explanations for your code changes. Be as descriptive, informative, technical as possible."\n'
        "}\n\n"
        f"{code_content}"
    )

    try:
        print("Trying...")
        job_report = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that analyzes code and returns a JSON object with the refactored code and the comments that come with it. Your goal is to identify outdated syntax in code and suggest changes to update it to the latest syntax."},
                {"role": "user", "content": user_prompt}
            ],
            response_model=JobReport,
        )

        data = {
            "status": "WRITING",
            "message": "Updating " + file_path.split("/")[-1] + "...",
            "code": job_report.refactored_code
        }

        # Create a fresh instance of the supabase client inside the function
        supabase_instance = supabase.create_client(getenv("SUPABASE_URL"), getenv("SUPABASE_KEY"))
        supabase_instance.table("repo-updates").insert(data).execute()

        return {
            "file_path": file_path,
            **job_report.model_dump()
        }
    except ValidationError as e:
        print(f"Validation error parsing LLM response for {file_path}: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"JSON decode error parsing LLM response for {file_path}: {e}")
        return None
    except Exception as e:
        # Handle any other exceptions, e.g. network errors, model issues, etc.
        print(f"Error analyzing {file_path}: {e}")
        return None