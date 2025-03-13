import os
import modal
import subprocess
from dotenv import load_dotenv

load_dotenv()

# Define the Docker image with necessary dependencies
base_image = modal.Image.debian_slim(python_version="3.10") \
    .apt_install("git", "python3", "bash") \
    .pip_install("python-dotenv", "groq", "fastapi", "uvicorn", "modal", 
                "instructor", "pydantic", "websockets", "supabase", "gitpython")

# Then explicitly add local Python modules
image = base_image.add_local_python_source(
    "git_driver",
    "server", 
    "socket_manager"
)

# Create a Modal application with the name 'app'
app = modal.App(name="groq-read", image=image)

@app.function(secrets=[modal.Secret.from_name("GROQ_API_KEY"), 
                       modal.Secret.from_name("SUPABASE_URL"), 
                       modal.Secret.from_name("SUPABASE_KEY")])
def run_script(repo_url: str):
    """
    Clones the given repository, runs `init.sh`, and returns combined logs.
    """
    try:
        # Clone the pot-tools repository to a specific directory
        clone_result = subprocess.run(
            ["git", "clone", "https://github.com/kshitizz36/pot-tools.git", "scripts/pot-tools"],
            check=True,
            capture_output=True,
            text=True
        )
        print("pot-tools cloned successfully")
        print(clone_result.stdout)
        
        # Verify the cloned directory exists
        pot_tools_path = "/root/scripts/pot-tools"
        if not os.path.exists(pot_tools_path):
            raise FileNotFoundError(f"pot-tools directory not found at {pot_tools_path}")
        
        # List the contents of the pot-tools directory
        print(f"Contents of pot-tools directory: {os.listdir(pot_tools_path)}")
        
        # Add the pot-tools directory to Python path
        import sys
        if pot_tools_path not in sys.path:
            sys.path.insert(0, pot_tools_path)
        
        # Verify the Python path
        print("Updated Python path:", sys.path)
        
        # Import checker from pot-tools
        try:
            from checker import fetch_updates, CodeChange, get_all_files_recursively
        except ImportError as e:
            print(f"Import failed: {e}")
            print(f"Current directory: {os.getcwd()}")
            if os.path.exists(pot_tools_path):
                print(f"Contents of pot-tools directory: {os.listdir(pot_tools_path)}")
            else:
                print(f"pot-tools directory does not exist")
            raise

        # Clone the target repository
        os.chdir("scripts/pot-tools")
        clone_result = subprocess.run(
            ["git", "clone", repo_url, "repository"],
            check=True,
            capture_output=True,
            text=True
        )
        print("Target repository cloned successfully")
        print(clone_result.stdout)
        
        subprocess.run(
            ["ls", "repository"],
            check=True,
            capture_output=True,
            text=True
        )
        
        # Fetch updates using the checker from pot-tools
        repository_path = os.path.join(os.getcwd(), "repository")
        data = fetch_updates(repository_path)
        return [change.model_dump(mode="json") for change in data]
    
    except subprocess.CalledProcessError as e:
        print(f"Git clone failed: {e}")
        print(f"Error output: {e.stderr}")
        raise
    except FileNotFoundError as e:
        print(f"File not found: {e}")
        raise
    except ModuleNotFoundError as e:
        print(f"Module not found: {e}")
        raise
    except Exception as e:
        print(f"An error occurred: {e}")
        raise