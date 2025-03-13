import os
import sys
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import docker
from docker.errors import DockerException, ContainerError
from dotenv import load_dotenv
import subprocess
from containers import app as modalApp, run_script
from modal_write import writeApp, process_file
from git_driver import load_repository, create_and_push_branch, create_pull_request
from socket_manager import ConnectionManager
import asyncio
import websockets
import json
import logging
import traceback
import shutil
from supabase import create_client, Client
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Hardcoded Supabase credentials
SUPABASE_URL = "https://qxsudjvfylplnkmwzvkw.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InF4c3VkanZmeWxwbG5rbXd6dmt3Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0MTQ1NTUyNiwiZXhwIjoyMDU3MDMxNTI2fQ.hH7-RjtCRYAg0elStW0Fr-Pd9cSx_ceTv8KGP1UR6LM"

# Initialize Supabase client with hardcoded credentials
supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Create app
app = FastAPI()


# Rest of your imports...

manager = ConnectionManager()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define request model
class UpdateRequest(BaseModel):
    repository: str
    repository_owner: str
    repository_name: str

async def insert_update(status: str, message: str, code: str = None, owner: str = None, repo_name: str = None):
    try:
        result = supabase.table('repo-updates').insert({
            'status': status,
            'message': message,
            'code': code,
            'repository_owner': owner,
            'repository_name': repo_name
        }).execute()
        logger.info(f"Supabase insert result: {result}")
        return result
    except Exception as e:
        logger.error(f"Error inserting update: {str(e)}")
        raise e

@app.post('/update')
async def update(request: UpdateRequest):
    try:
        # Initial status update
        await insert_update('READING', 'Initializing repository scan...', None, request.repository_owner, request.repository_name)

        # Clear and recreate staging directory
        staging_dir = os.path.join(os.getcwd(), "staging")
        if os.path.exists(staging_dir):
            shutil.rmtree(staging_dir)
        os.makedirs(staging_dir)
        
        # Clone repository status update
        await insert_update('READING', f'Cloning repository {request.repository_name}...', None, request.repository_owner, request.repository_name)
        
        # Clone repository to staging directory
        clone_cmd = ["git", "clone", request.repository, staging_dir]
        try:
            subprocess.check_call(clone_cmd)
            logger.info(f"Successfully cloned repository to {staging_dir}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Git clone failed: {e}")
            await insert_update('ERROR', f'Failed to clone repository: {str(e)}', None, request.repository_owner, request.repository_name)
            raise HTTPException(status_code=500, detail=f"Failed to clone repository: {str(e)}")
        
        with modalApp.run():
            job_list = run_script.remote(request.repository)
            # Update status for each file being analyzed
            for job in job_list:
                file_path = job.get("path", "").split("repository/")[-1]
                await insert_update('READING', f'Reading {file_path}...', job.get("content"), request.repository_owner, request.repository_name)

        async def update_ws():
            try:
                uri = "wss://localhost:5000/ws?client_id=1"
                logger.info("updating ws")
                async with websockets.connect(uri) as websocket:
                    await websocket.send(json.dumps(job_list))
                    response = await websocket.recv()
                    logger.info(response)
            except Exception as e:
                logger.error(f"WebSocket connection error: {str(e)}")

        asyncio.create_task(update_ws())

        await insert_update('WRITING', 'Processing files...', None, request.repository_owner, request.repository_name)

        with writeApp.run():
            refactored_jobs = []
            for job in job_list:
                output = process_file.remote(job)
                if output:
                    file_path = job.get("path", "").split("repository/")[-1]
                    refactored_jobs.append({
                        "path": job.get("path"),
                        "new_content": output["refactored_code"],
                        "comments": output["refactored_code_comments"]
                    })
                    # Update status for each processed file
                    await insert_update('WRITING', f'Writing updates to {file_path}...', output["refactored_code"], request.repository_owner, request.repository_name)
        
        # Load repository info
        repo, origin, origin_url = load_repository(staging_dir)

        files_changed = []

        for job in refactored_jobs:
            original_path = job.get("path")
            relative_path = original_path.split("repository/", 1)[1] if "repository/" in original_path else os.path.basename(original_path)
            local_file_path = os.path.join(staging_dir, relative_path)
            
            os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
            
            logger.info(f"Writing to: {local_file_path}")
            files_changed.append(local_file_path)
            
            with open(local_file_path, "w") as f:
                f.write(job.get("new_content"))

        await insert_update('LOADING', 'Creating pull request...', None, request.repository_owner, request.repository_name)

        new_branch_name = create_and_push_branch(repo, origin, files_changed)
        
        create_pull_request(new_branch_name, request.repository_owner, request.repository_name, "main")

        # Final success status
        await insert_update('COMPLETE', 'Repository scan complete', None, request.repository_owner, request.repository_name)

        return {
            "status": "success",
            "message": "Repository updated and script executed successfully",
            "repository": request.repository,
            "output": refactored_jobs,
        }
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Error processing repository: {str(e)}\n{error_details}")
        # Log error to Supabase
        await insert_update('ERROR', f'Error: {str(e)}', None, request.repository_owner, request.repository_name)
        raise HTTPException(status_code=500, detail=str(e))

# Rest of your WebSocket code remains the same...

if __name__ == '__main__':
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=5000, reload=True)