from git import Repo
import uuid
import requests
from os import getenv
from dotenv import load_dotenv
import os
import supabase

load_dotenv()

supabase = supabase.create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def load_repository(repo_path="./staging"):
    repo = Repo(repo_path)
    origin = repo.remotes.origin
    data = {
        "status": "LOADING",
        "message": "Loading repository..."
    }
    supabase.table("repo-updates").insert(data).execute()
    origin_url = origin.url
    return repo, origin, origin_url

def write_files(repo_path):
    file_paths = [
        'pages/_app.js',
        'pages/_document.js',
        'pages/index.js',
        'pages/api/hello.js'
    ]
    for file_path in file_paths:
        full_path = os.path.join(repo_path, file_path)
        with open(full_path, 'w') as file:
            file.write("// Example content\n")
        print(f"Writing to: {full_path}")

def create_and_push_branch(repo, origin, files_to_stage):
    new_branch_name = uuid.uuid4().hex
    new_branch = repo.create_head(new_branch_name)
    new_branch.checkout()

    print("Created and switched to branch:", new_branch_name)

    repo.index.add(files_to_stage)
    print("Staged files:", files_to_stage)

    repo.index.commit("Automated commit message.")
    data = {
        "status": "LOADING",
        "message": "Creating branches..."
    }
    supabase.table("repo-updates").insert(data).execute()

    origin.push(new_branch)
    print("Pushed branch to remote.")

    return new_branch_name

def create_pull_request(new_branch_name, repo_owner, repo_name, base_branch):
    GITHUB_TOKEN = getenv("GITHUB_TOKEN")
    if not GITHUB_TOKEN:
        raise Exception("GITHUB_TOKEN environment variable not set.")

    pr_title = f"Automated PR for branch {new_branch_name}"
    pr_body = "This pull request was automatically created."

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    data = {
        "title": pr_title,
        "head": new_branch_name,
        "base": base_branch,
        "body": pr_body
    }
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls"
    response = requests.post(url, json=data, headers=headers)

    if response.status_code == 201:
        pr_url = response.json().get("html_url")
        print("Pull request created:", pr_url)
        return pr_url
    else:
        print("Failed to create pull request:", response.json())
        return None

def main():
    repo_path = "/Users/kshitiz./Developer/pou/backend/staging"
    repo, origin, origin_url = load_repository(repo_path)
    print("Repo origin URL:", origin_url)

    write_files(repo_path)

    files_to_stage = [
        "pages/_app.js",
        "pages/_document.js",
        "pages/index.js",
        "pages/api/hello.js"
    ]

    # Check the status of the repository
    status = repo.git.status()
    print("Git status:\n", status)

    new_branch_name = create_and_push_branch(repo, origin, files_to_stage)

    repo_owner = "kshitizz36"
    repo_name = "Pau"
    base_branch = "main"

    create_pull_request(new_branch_name, repo_owner, repo_name, base_branch)

if __name__ == "__main__":
    main()