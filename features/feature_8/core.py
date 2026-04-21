"""
╔══════════════════════════════════════════════════════════════════╗
║  ALOA AUTO-DEPLOYER — Feature 8 Core Engine (v1.0)               ║
║  Autonomous Deployment: Detect → Git Push → Deploy → Live URL    ║
║                                                                  ║
║  Subsystems:                                                     ║
║    1. Framework Detection Engine (project type + deploy target)  ║
║    2. GitHub Operations (create repo + push via REST API)        ║
║    3. Vercel Deployment Client (CLI primary, REST fallback)      ║
║    4. Render Deployment Client (REST API)                        ║
║    5. AI Deployment Advisor (Hugging Face + OpenRouter fallback) ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import json
import re
import subprocess
import urllib.request
import urllib.error
import urllib.parse
import time
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict

# Reuse Feature 6's scanning utilities
from features.feature_6.core import (
    scan_source_files,
    SOURCE_EXTENSIONS,
    SKIP_DIRS,
    detect_project_type,
)


# ══════════════════════════════════════════════════════════
# DATA MODELS
# ══════════════════════════════════════════════════════════

@dataclass
class DeploymentPlan:
    """Describes what the agent will deploy and where."""
    framework: str              # "nextjs", "react", "vue", "python", "node_backend", "spring_boot", etc.
    framework_display: str      # Human-readable: "Next.js", "React (Vite)", etc.
    deploy_target: str          # "vercel", "render", "both"
    build_command: str          # e.g., "npm run build", "pip install -r requirements.txt"
    start_command: str          # e.g., "npm start", "python app.py"
    project_name: str           # Derived from folder name
    is_fullstack: bool = False  # True if client/ + server/ detected
    frontend_path: str = ""     # Relative path to frontend (for full-stack)
    backend_path: str = ""      # Relative path to backend (for full-stack)
    env_vars: Dict[str, str] = field(default_factory=dict)  # Suggested env vars


@dataclass
class DeployResult:
    """Result of a deployment operation."""
    success: bool
    platform: str               # "github", "vercel", "render"
    url: str = ""               # The live URL or repo URL
    message: str = ""           # Human-readable status message
    error: str = ""             # Error details if failed


# ══════════════════════════════════════════════════════════
# FRAMEWORK DETECTION ENGINE
# ══════════════════════════════════════════════════════════

# Deployment-specific project signatures
FRONTEND_MARKERS = {
    "next.config.js": "nextjs",
    "next.config.ts": "nextjs",
    "next.config.mjs": "nextjs",
    "gatsby-config.js": "gatsby",
    "gatsby-config.ts": "gatsby",
    "nuxt.config.js": "nuxt",
    "nuxt.config.ts": "nuxt",
    "svelte.config.js": "svelte",
    "astro.config.mjs": "astro",
    "angular.json": "angular",
    "vue.config.js": "vue",
    "vite.config.js": "vite_frontend",
    "vite.config.ts": "vite_frontend",
}

BACKEND_MARKERS = {
    "pom.xml": "spring_boot",
    "build.gradle": "spring_boot",
    "manage.py": "django",
    "Pipfile": "python_backend",
    "go.mod": "go_backend",
    "Cargo.toml": "rust_backend",
    "Gemfile": "ruby_backend",
}

# Folders that indicate a full-stack monorepo
FULLSTACK_FRONTEND_DIRS = {"client", "frontend", "web", "app", "ui"}
FULLSTACK_BACKEND_DIRS = {"server", "backend", "api", "service"}

# Framework → deployment target mapping
DEPLOY_TARGET_MAP = {
    "nextjs": "vercel",
    "react": "vercel",
    "vue": "vercel",
    "vite_frontend": "vercel",
    "gatsby": "vercel",
    "nuxt": "vercel",
    "svelte": "vercel",
    "astro": "vercel",
    "angular": "vercel",
    "static_html": "vercel",
    "spring_boot": "render",
    "django": "render",
    "flask": "render",
    "python_backend": "render",
    "node_backend": "render",
    "go_backend": "render",
    "rust_backend": "render",
    "ruby_backend": "render",
}

# Framework display names
FRAMEWORK_NAMES = {
    "nextjs": "Next.js",
    "react": "React",
    "vue": "Vue.js",
    "vite_frontend": "Vite (Frontend)",
    "gatsby": "Gatsby",
    "nuxt": "Nuxt.js",
    "svelte": "SvelteKit",
    "astro": "Astro",
    "angular": "Angular",
    "static_html": "Static HTML/CSS/JS",
    "spring_boot": "Spring Boot (Java)",
    "django": "Django (Python)",
    "flask": "Flask (Python)",
    "python_backend": "Python Backend",
    "node_backend": "Node.js Backend",
    "go_backend": "Go Backend",
    "rust_backend": "Rust Backend",
    "ruby_backend": "Ruby Backend",
    "unknown": "Unknown Project",
}


def _read_json_safe(filepath):
    """Read a JSON file safely, returns dict or None."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            return json.load(f)
    except Exception:
        return None


def parse_env_file(folder_path: str) -> Dict[str, str]:
    """
    Reads environment variables from .env files in the project folder.
    Checks: .env, .env.local, .env.production, .env.example (in priority order).
    
    Returns a dict of {KEY: VALUE} pairs.
    Skips comments (#) and blank lines.
    """
    env_vars = {}

    # Check multiple .env file variants (priority order)
    env_files = [
        ".env",
        ".env.local",
        ".env.production",
        ".env.example",    # Use as fallback — may have placeholder values
    ]

    found_file = None
    for env_file in env_files:
        env_path = os.path.join(folder_path, env_file)
        if os.path.isfile(env_path):
            found_file = env_path
            break

    if not found_file:
        return env_vars

    try:
        with open(found_file, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                line = line.strip()

                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue

                # Parse KEY=VALUE (handle optional 'export' prefix)
                if line.startswith('export '):
                    line = line[7:].strip()

                if '=' not in line:
                    continue

                key, _, value = line.partition('=')
                key = key.strip()
                value = value.strip()

                # Remove surrounding quotes if present
                if len(value) >= 2:
                    if (value.startswith('"') and value.endswith('"')) or \
                       (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]

                if key:
                    env_vars[key] = value

    except Exception:
        pass

    return env_vars


def _check_package_json_for_framework(folder_path):
    """
    Inspects package.json to distinguish between frontend frameworks
    and Node.js backends (Express, Fastify, etc.).
    """
    pkg_path = os.path.join(folder_path, "package.json")
    pkg = _read_json_safe(pkg_path)
    if not pkg:
        return None

    all_deps = {}
    all_deps.update(pkg.get("dependencies", {}))
    all_deps.update(pkg.get("devDependencies", {}))

    # Check for specific frontend frameworks
    if "next" in all_deps:
        return "nextjs"
    if "gatsby" in all_deps:
        return "gatsby"
    if "nuxt" in all_deps or "nuxt3" in all_deps:
        return "nuxt"
    if "@sveltejs/kit" in all_deps or "svelte" in all_deps:
        return "svelte"
    if "astro" in all_deps:
        return "astro"
    if "@angular/core" in all_deps:
        return "angular"
    if "vue" in all_deps:
        return "vue"
    if "react" in all_deps:
        return "react"

    # Check for backend frameworks (Express, Fastify, Koa, etc.)
    backend_deps = {"express", "fastify", "koa", "hapi", "@hapi/hapi", "nestjs", "@nestjs/core"}
    if any(dep in all_deps for dep in backend_deps):
        return "node_backend"

    # Has package.json but can't determine — default to generic node
    return None


def _check_python_for_framework(folder_path):
    """
    Inspects requirements.txt / pyproject.toml to distinguish
    between Flask, Django, FastAPI, and generic Python backends.
    """
    # Check requirements.txt
    req_path = os.path.join(folder_path, "requirements.txt")
    if os.path.isfile(req_path):
        try:
            with open(req_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read().lower()
            if "django" in content:
                return "django"
            if "flask" in content:
                return "flask"
            if "fastapi" in content or "uvicorn" in content:
                return "flask"  # Deploy same way as Flask on Render
            return "python_backend"
        except Exception:
            pass

    # Check pyproject.toml
    pyproject_path = os.path.join(folder_path, "pyproject.toml")
    if os.path.isfile(pyproject_path):
        try:
            with open(pyproject_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read().lower()
            if "django" in content:
                return "django"
            if "flask" in content:
                return "flask"
            return "python_backend"
        except Exception:
            pass

    # Has manage.py? Definitely Django
    if os.path.isfile(os.path.join(folder_path, "manage.py")):
        return "django"

    return None


def detect_deployment_plan(folder_path: str) -> DeploymentPlan:
    """
    Analyzes a project folder and returns a complete DeploymentPlan.

    Detection strategy (layered):
      1. Check for full-stack monorepo structure (client/ + server/)
      2. Check for deployment-specific marker files (next.config.js, pom.xml, etc.)
      3. Inspect package.json dependencies
      4. Inspect Python requirements
      5. Fall back to Feature 6's generic detection
    """
    folder_name = os.path.basename(os.path.abspath(folder_path))
    project_name = re.sub(r'[^a-zA-Z0-9-]', '-', folder_name).lower().strip('-')
    if not project_name:
        project_name = "my-project"

    # ── Step 1: Check for full-stack monorepo ──
    subdirs = set()
    try:
        subdirs = {d.lower() for d in os.listdir(folder_path)
                   if os.path.isdir(os.path.join(folder_path, d))}
    except Exception:
        pass

    frontend_dir = subdirs & FULLSTACK_FRONTEND_DIRS
    backend_dir = subdirs & FULLSTACK_BACKEND_DIRS

    if frontend_dir and backend_dir:
        fe_folder = os.path.join(folder_path, next(iter(frontend_dir)))
        be_folder = os.path.join(folder_path, next(iter(backend_dir)))

        fe_framework = _check_package_json_for_framework(fe_folder) or "react"
        be_framework = _check_python_for_framework(be_folder) or _check_package_json_for_framework(be_folder) or "node_backend"

        return DeploymentPlan(
            framework="fullstack",
            framework_display=f"Full-Stack ({FRAMEWORK_NAMES.get(fe_framework, fe_framework)} + {FRAMEWORK_NAMES.get(be_framework, be_framework)})",
            deploy_target="both",
            build_command="(see sub-projects)",
            start_command="(see sub-projects)",
            project_name=project_name,
            is_fullstack=True,
            frontend_path=next(iter(frontend_dir)),
            backend_path=next(iter(backend_dir)),
        )

    # ── Step 2: Check deployment-specific marker files ──
    try:
        files_in_root = set(os.listdir(folder_path))
    except Exception:
        files_in_root = set()

    for marker_file, framework in FRONTEND_MARKERS.items():
        if marker_file in files_in_root:
            target = DEPLOY_TARGET_MAP.get(framework, "vercel")
            build_cmd, start_cmd = _get_commands_for_framework(framework, folder_path)
            return DeploymentPlan(
                framework=framework,
                framework_display=FRAMEWORK_NAMES.get(framework, framework),
                deploy_target=target,
                build_command=build_cmd,
                start_command=start_cmd,
                project_name=project_name,
            )

    for marker_file, framework in BACKEND_MARKERS.items():
        if marker_file in files_in_root:
            target = DEPLOY_TARGET_MAP.get(framework, "render")
            build_cmd, start_cmd = _get_commands_for_framework(framework, folder_path)
            return DeploymentPlan(
                framework=framework,
                framework_display=FRAMEWORK_NAMES.get(framework, framework),
                deploy_target=target,
                build_command=build_cmd,
                start_command=start_cmd,
                project_name=project_name,
            )

    # ── Step 3: Inspect package.json ──
    if "package.json" in files_in_root:
        framework = _check_package_json_for_framework(folder_path)
        if framework:
            target = DEPLOY_TARGET_MAP.get(framework, "vercel")
            build_cmd, start_cmd = _get_commands_for_framework(framework, folder_path)
            return DeploymentPlan(
                framework=framework,
                framework_display=FRAMEWORK_NAMES.get(framework, framework),
                deploy_target=target,
                build_command=build_cmd,
                start_command=start_cmd,
                project_name=project_name,
            )

    # ── Step 4: Inspect Python requirements ──
    if "requirements.txt" in files_in_root or "pyproject.toml" in files_in_root:
        framework = _check_python_for_framework(folder_path)
        if framework:
            target = DEPLOY_TARGET_MAP.get(framework, "render")
            build_cmd, start_cmd = _get_commands_for_framework(framework, folder_path)
            return DeploymentPlan(
                framework=framework,
                framework_display=FRAMEWORK_NAMES.get(framework, framework),
                deploy_target=target,
                build_command=build_cmd,
                start_command=start_cmd,
                project_name=project_name,
            )

    # ── Step 5: Check for static HTML site ──
    if "index.html" in files_in_root:
        return DeploymentPlan(
            framework="static_html",
            framework_display="Static HTML/CSS/JS",
            deploy_target="vercel",
            build_command="(none — static site)",
            start_command="(none — static site)",
            project_name=project_name,
        )

    # ── Fallback: Use Feature 6 detection ──
    proj_type, _ = detect_project_type(folder_path)
    framework = proj_type if proj_type != "unknown" else "unknown"
    target = DEPLOY_TARGET_MAP.get(framework, "render")

    return DeploymentPlan(
        framework=framework,
        framework_display=FRAMEWORK_NAMES.get(framework, "Unknown Project"),
        deploy_target=target,
        build_command="(auto-detect)",
        start_command="(auto-detect)",
        project_name=project_name,
    )


def _get_commands_for_framework(framework: str, folder_path: str) -> Tuple[str, str]:
    """Returns (build_command, start_command) for a given framework."""
    commands = {
        "nextjs":          ("npm install && npm run build", "npm start"),
        "react":           ("npm install && npm run build", "npx serve -s build"),
        "vue":             ("npm install && npm run build", "npx serve -s dist"),
        "vite_frontend":   ("npm install && npm run build", "npx serve -s dist"),
        "gatsby":          ("npm install && npm run build", "npx serve -s public"),
        "nuxt":            ("npm install && npm run build", "npm start"),
        "svelte":          ("npm install && npm run build", "npm start"),
        "astro":           ("npm install && npm run build", "npm start"),
        "angular":         ("npm install && npm run build", "npx serve -s dist"),
        "static_html":     ("(none)", "(none)"),
        "spring_boot":     ("mvn clean install -DskipTests", "java -jar target/*.jar"),
        "django":          ("pip install -r requirements.txt", "gunicorn config.wsgi:application"),
        "flask":           ("pip install -r requirements.txt", "gunicorn app:app"),
        "python_backend":  ("pip install -r requirements.txt", "python app.py"),
        "node_backend":    ("npm install", "npm start"),
        "go_backend":      ("go build -o app", "./app"),
        "rust_backend":    ("cargo build --release", "./target/release/app"),
        "ruby_backend":    ("bundle install", "ruby app.rb"),
    }

    build_cmd, start_cmd = commands.get(framework, ("(auto-detect)", "(auto-detect)"))

    # Try to refine Python start command by finding the actual entry point
    if framework in ("flask", "python_backend"):
        for candidate in ["app.py", "main.py", "run.py", "server.py", "wsgi.py"]:
            if os.path.isfile(os.path.join(folder_path, candidate)):
                if framework == "flask":
                    start_cmd = f"gunicorn {candidate.replace('.py', '')}:app"
                else:
                    start_cmd = f"python {candidate}"
                break

    # Refine Django start command
    if framework == "django":
        # Find the WSGI module by looking for wsgi.py
        for root, dirs, files in os.walk(folder_path):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            if "wsgi.py" in files:
                rel = os.path.relpath(root, folder_path).replace(os.sep, ".")
                start_cmd = f"gunicorn {rel}.wsgi:application"
                break

    return build_cmd, start_cmd


# ══════════════════════════════════════════════════════════
# GITHUB OPERATIONS
# ══════════════════════════════════════════════════════════

def create_github_repo(pat: str, repo_name: str, is_private: bool = False) -> Tuple[bool, str]:
    """
    Creates a new GitHub repository using the GitHub REST API.
    Returns (success, repo_clone_url_or_error).
    """
    url = "https://api.github.com/user/repos"
    headers = {
        "Authorization": f"Bearer {pat}",
        "Content-Type": "application/json",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    body = json.dumps({
        "name": repo_name,
        "private": is_private,
        "auto_init": False,  # We push from local — don't initialize with README
        "description": f"Deployed by ALOA Auto-Deployer",
    }).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            clone_url = result.get("clone_url", "")
            html_url = result.get("html_url", "")
            return True, html_url
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        try:
            error_json = json.loads(error_body)
            errors = error_json.get("errors", [])
            if any("name already exists" in str(err) for err in errors):
                # Repo already exists — try to get its URL
                return _get_existing_repo_url(pat, repo_name)
            return False, f"GitHub API Error {e.code}: {error_json.get('message', error_body)}"
        except Exception:
            return False, f"GitHub API Error {e.code}: {error_body[:300]}"
    except Exception as e:
        return False, f"GitHub connection error: {str(e)}"


def _get_existing_repo_url(pat: str, repo_name: str) -> Tuple[bool, str]:
    """Gets the URL of an existing repo owned by the authenticated user."""
    url = f"https://api.github.com/user/repos?type=owner&per_page=100"
    headers = {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            repos = json.loads(resp.read().decode("utf-8"))
            for repo in repos:
                if repo.get("name", "").lower() == repo_name.lower():
                    return True, repo.get("html_url", "")
        return False, f"Repository '{repo_name}' already exists but could not fetch its URL."
    except Exception as e:
        return False, f"Could not check existing repos: {str(e)}"


def init_and_push_to_github(
    folder_path: str,
    pat: str,
    repo_name: str,
    is_private: bool = False,
    commit_message: str = "Initial commit — deployed by ALOA"
) -> DeployResult:
    """
    Full pipeline: Create GitHub repo → git init → add → commit → push.
    Returns a DeployResult with the repo URL.
    """
    # 1. Create the remote repo
    success, repo_url_or_error = create_github_repo(pat, repo_name, is_private)
    if not success:
        return DeployResult(
            success=False, platform="github",
            error=repo_url_or_error,
            message=f"Failed to create GitHub repo: {repo_url_or_error}"
        )

    repo_html_url = repo_url_or_error

    # Build the authenticated push URL
    # Extract username from the HTML URL: https://github.com/USERNAME/REPO
    parts = repo_html_url.rstrip("/").split("/")
    if len(parts) >= 2:
        username = parts[-2]
        auth_remote_url = f"https://{pat}@github.com/{username}/{repo_name}.git"
    else:
        return DeployResult(
            success=False, platform="github",
            error="Could not parse GitHub URL",
            message="Failed to construct authenticated URL"
        )

    # 2. Git init (if not already a git repo)
    git_dir = os.path.join(folder_path, ".git")
    if not os.path.isdir(git_dir):
        result = subprocess.run(
            ["git", "init"], cwd=folder_path,
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return DeployResult(
                success=False, platform="github",
                error=result.stderr.strip(),
                message="git init failed"
            )

    # 3. Create .gitignore if it doesn't exist
    gitignore_path = os.path.join(folder_path, ".gitignore")
    if not os.path.isfile(gitignore_path):
        _create_smart_gitignore(folder_path)

    # 4. Add all files
    subprocess.run(["git", "add", "."], cwd=folder_path, capture_output=True, text=True, timeout=30)

    # 5. Commit
    result = subprocess.run(
        ["git", "commit", "-m", commit_message],
        cwd=folder_path, capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0 and "nothing to commit" not in result.stdout:
        return DeployResult(
            success=False, platform="github",
            error=result.stderr.strip(),
            message="git commit failed"
        )

    # 6. Set remote (remove existing 'origin' if present, then add)
    subprocess.run(
        ["git", "remote", "remove", "origin"],
        cwd=folder_path, capture_output=True, text=True, timeout=10
    )
    subprocess.run(
        ["git", "remote", "add", "origin", auth_remote_url],
        cwd=folder_path, capture_output=True, text=True, timeout=10
    )

    # 7. Determine the current branch name
    branch_result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=folder_path, capture_output=True, text=True, timeout=10
    )
    branch = branch_result.stdout.strip() or "main"

    # 8. Push
    result = subprocess.run(
        ["git", "push", "-u", "origin", branch, "--force"],
        cwd=folder_path, capture_output=True, text=True, timeout=120
    )
    if result.returncode != 0:
        return DeployResult(
            success=False, platform="github",
            error=result.stderr.strip(),
            message="git push failed"
        )

    return DeployResult(
        success=True, platform="github",
        url=repo_html_url,
        message=f"Code pushed to {repo_html_url}"
    )


def _create_smart_gitignore(folder_path: str):
    """Creates a sensible .gitignore based on detected project type."""
    ignore_lines = [
        "# Dependencies",
        "node_modules/",
        "venv/",
        ".venv/",
        "env/",
        "",
        "# Build output",
        "dist/",
        "build/",
        ".next/",
        "out/",
        "target/",
        "__pycache__/",
        "*.pyc",
        "",
        "# Environment",
        ".env",
        ".env.local",
        ".env.*.local",
        "",
        "# IDE",
        ".idea/",
        ".vscode/",
        "*.swp",
        "*.swo",
        "",
        "# OS",
        ".DS_Store",
        "Thumbs.db",
        "",
        "# Logs",
        "*.log",
        "npm-debug.log*",
    ]

    gitignore_path = os.path.join(folder_path, ".gitignore")
    try:
        with open(gitignore_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(ignore_lines) + "\n")
    except Exception:
        pass


# ══════════════════════════════════════════════════════════
# VERCEL DEPLOYMENT CLIENT
# ══════════════════════════════════════════════════════════

def check_vercel_cli_available() -> bool:
    """Check if npx/vercel CLI is available on the system."""
    try:
        result = subprocess.run(
            "npx --version",
            capture_output=True, text=True, timeout=15,
            shell=True  # Required on Windows — npx is a .cmd file
        )
        return result.returncode == 0
    except Exception:
        return False


def deploy_to_vercel(
    folder_path: str,
    token: str,
    project_name: str = "",
    framework: str = "",
    github_repo_url: str = "",
    env_vars: Dict[str, str] = None,
) -> DeployResult:
    """
    Deploys a project to Vercel using the Vercel CLI.
    Falls back to GitHub-linked REST API if CLI is not available.

    The CLI approach is preferred because:
    - It handles framework detection automatically
    - It uploads files directly (no GitHub link needed)
    - It's the officially recommended deployment method
    """
    if check_vercel_cli_available():
        return _deploy_vercel_cli(folder_path, token, project_name, env_vars or {})
    else:
        return _deploy_vercel_api_github(token, project_name, framework, github_repo_url)

def _get_vercel_production_domain(token: str, deployment_url: str) -> str:
    """
    Given a temporary deployment URL (e.g. https://my-xxx-team.vercel.app),
    queries the Vercel API to find the permanent production domain
    (e.g. https://my-app-olive-three-21.vercel.app).

    Returns the permanent URL, or empty string if lookup fails.
    """
    headers = {
        "Authorization": f"Bearer {token}",
    }

    # Extract the deployment host from the URL
    deploy_host = deployment_url.replace("https://", "").replace("http://", "").strip("/")

    try:
        # Get deployment info to find the project ID
        req = urllib.request.Request(
            f"https://api.vercel.com/v13/deployments/{deploy_host}",
            headers=headers, method="GET"
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            deploy_info = json.loads(resp.read().decode("utf-8"))

            # The 'alias' field contains the permanent production domains
            aliases = deploy_info.get("alias", [])
            if aliases:
                # Return the first alias that looks like a .vercel.app domain
                for alias in aliases:
                    if alias.endswith(".vercel.app"):
                        return f"https://{alias}"
                # If no .vercel.app alias, return the first one
                return f"https://{aliases[0]}"

            # Fallback: try to get project name and construct URL
            project_name = deploy_info.get("name", "")
            if project_name:
                return f"https://{project_name}.vercel.app"

    except Exception:
        pass

    return ""


def _deploy_vercel_cli(
    folder_path: str,
    token: str,
    project_name: str = "",
    env_vars: Dict[str, str] = None,
) -> DeployResult:
    """Deploy via Vercel CLI (npx vercel). Uses shell=True for Windows compat."""
    # Note: --name is deprecated in Vercel CLI 48+, so we don't use it
    cmd = f'npx -y vercel --prod --token={token} --yes'

    # Add --env flags for each environment variable
    if env_vars:
        for key, value in env_vars.items():
            cmd += f' --env {key}="{value}"'

    # Set CI=false so Create React App doesn't treat warnings as errors
    # Also inject project env vars into the subprocess environment
    deploy_env = {**os.environ, "CI": "false"}
    if env_vars:
        deploy_env.update(env_vars)

    try:
        result = subprocess.run(
            cmd,
            cwd=folder_path,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes max for deployment
            shell=True,  # Required on Windows — npx is a .cmd file
            env=deploy_env,
        )

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        combined = stdout + "\n" + stderr

        # Try to extract the Production URL from output
        # Vercel outputs: "Production: https://xxx.vercel.app [4s]"
        production_url = ""
        inspect_url = ""
        for line in combined.split("\n"):
            line = line.strip()
            if line.startswith("Production:"):
                # Extract URL from "Production: https://xxx.vercel.app [4s]"
                parts = line.split()
                for part in parts:
                    if part.startswith("https://"):
                        production_url = part
                        break
            elif line.startswith("Inspect:"):
                parts = line.split()
                for part in parts:
                    if part.startswith("https://"):
                        inspect_url = part
                        break

        # Check for build errors in output
        build_error = ""
        if 'exited with' in combined or 'Error:' in combined:
            for line in combined.split("\n"):
                line = line.strip()
                if line.startswith("Error:") or "exited with" in line:
                    build_error = line
                    break

        if result.returncode == 0 and production_url:
            # The CLI returns a temporary deployment URL (e.g. my-xxx-team.vercel.app)
            # Fetch the actual permanent production domain from Vercel API
            real_url = _get_vercel_production_domain(token, production_url) or production_url
            return DeployResult(
                success=True, platform="vercel",
                url=real_url,
                message=f"Deployed to Vercel: {real_url}"
            )
        elif production_url and build_error:
            # Deployment was created but build failed
            error_detail = build_error or "Build command failed"
            return DeployResult(
                success=False, platform="vercel",
                error=f"Build failed: {error_detail}",
                message=f"Vercel build error — check logs at: {inspect_url or 'vercel.com'}"
            )
        elif result.returncode == 0:
            # Try extracting any https URL from output
            for line in reversed(combined.split("\n")):
                line = line.strip()
                if line.startswith("https://"):
                    return DeployResult(
                        success=True, platform="vercel",
                        url=line,
                        message=f"Deployed to Vercel: {line}"
                    )
            return DeployResult(
                success=True, platform="vercel",
                url="",
                message=f"Vercel deployment completed. Check vercel.com dashboard."
            )
        else:
            # Total failure — extract the most useful error
            error_msg = build_error or stderr[:200] or stdout[:200] or "Unknown error"
            return DeployResult(
                success=False, platform="vercel",
                error=error_msg,
                message="Vercel CLI deployment failed"
            )
    except subprocess.TimeoutExpired:
        return DeployResult(
            success=False, platform="vercel",
            error="Deployment timed out after 5 minutes",
            message="Vercel deployment timed out"
        )
    except FileNotFoundError:
        return DeployResult(
            success=False, platform="vercel",
            error="npx command not found. Please install Node.js.",
            message="Node.js/npx not found on system"
        )
    except Exception as e:
        return DeployResult(
            success=False, platform="vercel",
            error=str(e),
            message="Vercel deployment error"
        )


# Map our internal framework names to Vercel's expected framework slugs
VERCEL_FRAMEWORK_SLUGS = {
    "nextjs": "nextjs",
    "react": "create-react-app",
    "vue": "vue",
    "vite_frontend": "vite",
    "gatsby": "gatsby",
    "nuxt": "nuxtjs",
    "svelte": "svelte",
    "astro": "astro",
    "angular": "angular",
    "static_html": None,  # No framework — static files
}


def _deploy_vercel_api_github(
    token: str,
    project_name: str,
    framework: str,
    github_repo_url: str,
) -> DeployResult:
    """
    Deploy via Vercel REST API by linking a GitHub repository.
    This is the correct approach — Vercel clones from Git, runs npm install,
    runs the build command, and serves the output. Just like importing a
    project on vercel.com.

    Steps:
      1. Create a Vercel Project linked to the GitHub repo
      2. Vercel auto-triggers a deployment from the repo
      3. Return the project URL
    """
    if not github_repo_url:
        return DeployResult(
            success=False, platform="vercel",
            error="No GitHub repo URL provided. Push to GitHub first.",
            message="GitHub repo required for Vercel API deployment"
        )

    # Parse GitHub owner and repo from the URL
    # Handles: https://github.com/owner/repo or https://github.com/owner/repo.git
    parts = github_repo_url.rstrip("/").rstrip(".git").split("/")
    if len(parts) < 2:
        return DeployResult(
            success=False, platform="vercel",
            error=f"Could not parse GitHub URL: {github_repo_url}",
            message="Invalid GitHub URL"
        )
    repo_owner = parts[-2]
    repo_name = parts[-1]

    # Build framework settings
    vercel_slug = VERCEL_FRAMEWORK_SLUGS.get(framework)

    # Step 1: Create a Vercel Project linked to GitHub
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    project_payload = {
        "name": project_name or repo_name,
        "gitRepository": {
            "type": "github",
            "repo": f"{repo_owner}/{repo_name}",
        },
    }

    # Add framework if known
    if vercel_slug:
        project_payload["framework"] = vercel_slug

    body = json.dumps(project_payload).encode("utf-8")

    try:
        # Try creating the project
        req = urllib.request.Request(
            "https://api.vercel.com/v10/projects",
            data=body, headers=headers, method="POST"
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            project_id = result.get("id", "")
            project_name_actual = result.get("name", project_name)

            deploy_url = f"https://{project_name_actual}.vercel.app"

            return DeployResult(
                success=True, platform="vercel",
                url=deploy_url,
                message=f"Vercel project created & linked to GitHub!\n"
                        f"   🔗 {deploy_url}\n"
                        f"   ⏳ Triggering build..."
            )

    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")

        # If project already exists, try to trigger a redeployment
        if e.code == 409 or "already exists" in error_body.lower():
            return _trigger_vercel_redeploy(token, project_name or repo_name)

        # Check if it's a GitHub integration issue
        if "github" in error_body.lower() and ("install" in error_body.lower() or "connect" in error_body.lower()):
            return DeployResult(
                success=False, platform="vercel",
                error="Vercel is not connected to your GitHub account.",
                message="⚠️ Please go to vercel.com → Settings → Git → Connect GitHub\n"
                        "   Then re-run this feature."
            )

        return DeployResult(
            success=False, platform="vercel",
            error=f"Vercel API Error {e.code}: {error_body[:300]}",
            message="Vercel project creation failed"
        )
    except Exception as e:
        return DeployResult(
            success=False, platform="vercel",
            error=str(e),
            message="Vercel API connection error"
        )


def _trigger_deploy_via_git_push(folder_path: str):
    """
    Triggers a Vercel deployment by doing an empty git commit + push.
    
    Why: Vercel's webhook fires on every push to the linked repo.
    Since we create the Vercel project AFTER the initial push,
    Vercel misses it. This tiny push triggers the auto-build.
    
    This is the most reliable method — it's what Vercel docs recommend.
    """
    try:
        # Create a tiny empty commit
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", "trigger vercel deploy"],
            cwd=folder_path, capture_output=True, text=True, timeout=15
        )
        # Push it to trigger Vercel's webhook
        subprocess.run(
            ["git", "push"],
            cwd=folder_path, capture_output=True, text=True, timeout=60
        )
    except Exception:
        pass  # Non-critical — worst case user pushes manually



def _trigger_vercel_redeploy(token: str, project_name: str) -> DeployResult:
    """If the Vercel project already exists, trigger a new deployment."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # First, get the project to find latest deployment
    try:
        req = urllib.request.Request(
            f"https://api.vercel.com/v9/projects/{project_name}",
            headers=headers, method="GET"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            project = json.loads(resp.read().decode("utf-8"))
            project_name_actual = project.get("name", project_name)
            deploy_url = f"https://{project_name_actual}.vercel.app"

            return DeployResult(
                success=True, platform="vercel",
                url=deploy_url,
                message=f"Vercel project already exists — redeploying from GitHub.\n"
                        f"   🔗 {deploy_url}\n"
                        f"   ⏳ Vercel is building — check your dashboard."
            )
    except Exception:
        deploy_url = f"https://{project_name}.vercel.app"
        return DeployResult(
            success=True, platform="vercel",
            url=deploy_url,
            message=f"Vercel project exists. URL: {deploy_url}"
        )

# ══════════════════════════════════════════════════════════
# RENDER DEPLOYMENT CLIENT
# ══════════════════════════════════════════════════════════

RENDER_API_BASE = "https://api.render.com/v1"


def deploy_to_render(
    github_repo_url: str,
    api_key: str,
    service_name: str,
    plan: DeploymentPlan,
) -> DeployResult:
    """
    Creates a new Web Service on Render linked to a GitHub repository.
    Returns the deployment URL after polling for readiness.
    """
    # Determine the runtime
    runtime_map = {
        "django": "python",
        "flask": "python",
        "python_backend": "python",
        "node_backend": "node",
        "spring_boot": "docker",
        "go_backend": "go",
        "rust_backend": "rust",
        "ruby_backend": "ruby",
    }
    runtime = runtime_map.get(plan.framework, "node")

    # Build the service creation payload
    service_payload = {
        "type": "web_service",
        "name": service_name,
        "repo": github_repo_url,
        "autoDeploy": "yes",
        "branch": "main",
        "plan": "free",
        "runtime": runtime,
        "buildCommand": plan.build_command,
        "startCommand": plan.start_command,
        "envVars": [
            {"key": k, "value": v}
            for k, v in plan.env_vars.items()
        ],
    }

    # If it's a Docker-based deployment (Spring Boot), use Docker runtime
    if plan.framework == "spring_boot":
        service_payload["runtime"] = "docker"
        service_payload.pop("buildCommand", None)
        service_payload.pop("startCommand", None)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    body = json.dumps({"service": service_payload}).encode("utf-8")

    try:
        req = urllib.request.Request(
            f"{RENDER_API_BASE}/services",
            data=body, headers=headers, method="POST"
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            service = result.get("service", result)
            service_id = service.get("id", "")
            service_url = service.get("serviceDetails", {}).get("url", "")

            if not service_url:
                # Construct the default Render URL
                service_url = f"https://{service_name}.onrender.com"

            return DeployResult(
                success=True, platform="render",
                url=service_url,
                message=f"Render service created: {service_url}\n   ⏳ First deploy may take 2-5 minutes."
            )
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        try:
            error_json = json.loads(error_body)
            error_msg = error_json.get("message", error_body[:300])
        except Exception:
            error_msg = error_body[:300]
        return DeployResult(
            success=False, platform="render",
            error=f"Render API Error {e.code}: {error_msg}",
            message="Render deployment failed"
        )
    except Exception as e:
        return DeployResult(
            success=False, platform="render",
            error=str(e),
            message="Render connection error"
        )


# ══════════════════════════════════════════════════════════
# AI DEPLOYMENT ADVISOR (Hugging Face + OpenRouter fallback)
# ══════════════════════════════════════════════════════════

# API Keys
HUGGINGFACE_API_URL = "https://api-inference.huggingface.co/models/meta-llama/Meta-Llama-3-8B-Instruct"
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = "openrouter/auto"


def _load_huggingface_key() -> str:
    """Load the Hugging Face API key from .env or environment."""
    # Check environment variable first
    key = os.environ.get("HUGGINGFACE_API_KEY", "")
    if key:
        return key

    # Try loading from .env files in common locations
    env_paths = [
        os.path.join(os.getcwd(), ".env"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".env"),
    ]
    for env_path in env_paths:
        if os.path.isfile(env_path):
            try:
                with open(env_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("HUGGINGFACE_API_KEY="):
                            return line.split("=", 1)[1].strip().strip('"').strip("'")
            except Exception:
                continue

    return ""


def _call_huggingface(prompt: str) -> str:
    """Call the Hugging Face Inference API."""
    hf_key = _load_huggingface_key()
    if not hf_key:
        raise EnvironmentError("Hugging Face API key not found.")

    headers = {
        "Authorization": f"Bearer {hf_key}",
        "Content-Type": "application/json",
    }
    body = json.dumps({
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 1024,
            "temperature": 0.2,
            "return_full_text": False,
        }
    }).encode("utf-8")

    req = urllib.request.Request(HUGGINGFACE_API_URL, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        if isinstance(result, list) and len(result) > 0:
            return result[0].get("generated_text", "")
        return str(result)


def _call_openrouter_advisor(prompt: str) -> str:
    """Fallback: Call OpenRouter API for deployment advice."""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://aloa-agent.local",
        "X-Title": "ALOA Auto-Deployer",
    }
    body = json.dumps({
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": "You are ALOA's deployment advisor. Help configure and troubleshoot cloud deployments. Be concise and actionable."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 1024,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=body, headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        return result['choices'][0]['message']['content']


def ask_deployment_ai(prompt: str) -> str:
    """
    Smart AI advisor with automatic fallback.
    Tries Hugging Face first, falls back to OpenRouter.
    """
    # Try Hugging Face
    try:
        return _call_huggingface(prompt)
    except Exception:
        pass

    # Fallback to OpenRouter
    try:
        return _call_openrouter_advisor(prompt)
    except Exception as e:
        return f"⚠️ AI advisor unavailable: {str(e)}"


def generate_render_yaml(plan: DeploymentPlan) -> str:
    """
    Auto-generates a render.yaml (Infrastructure as Code) blueprint
    for Render deployments.
    """
    runtime_map = {
        "django": "python",
        "flask": "python",
        "python_backend": "python",
        "node_backend": "node",
        "go_backend": "go",
        "rust_backend": "rust",
    }
    runtime = runtime_map.get(plan.framework, "node")

    yaml_content = f"""# render.yaml — Auto-generated by ALOA Auto-Deployer
services:
  - type: web
    name: {plan.project_name}
    runtime: {runtime}
    plan: free
    buildCommand: "{plan.build_command}"
    startCommand: "{plan.start_command}"
    autoDeploy: true
"""

    # Add environment variables if any
    if plan.env_vars:
        yaml_content += "    envVars:\n"
        for key, value in plan.env_vars.items():
            yaml_content += f"      - key: {key}\n        value: {value}\n"

    return yaml_content


def generate_vercel_json(plan: DeploymentPlan) -> str:
    """
    Auto-generates a vercel.json configuration file
    for Vercel deployments.
    """
    config = {
        "version": 2,
        "name": plan.project_name,
    }

    # Add framework-specific settings
    if plan.framework == "static_html":
        config["builds"] = [{"src": "**/*", "use": "@vercel/static"}]
    elif plan.framework in ("react", "vue", "vite_frontend"):
        config["buildCommand"] = plan.build_command.split("&&")[-1].strip() if "&&" in plan.build_command else plan.build_command
        config["outputDirectory"] = "dist" if plan.framework in ("vue", "vite_frontend") else "build"

    return json.dumps(config, indent=2)


# ══════════════════════════════════════════════════════════
# DEPLOYMENT CONFIG MANAGEMENT
# ══════════════════════════════════════════════════════════

CONFIG_FILENAME = ".aloa_deploy_config.json"


def load_deploy_config() -> Dict[str, str]:
    """Load saved deployment credentials from local config."""
    config_path = os.path.join(os.getcwd(), CONFIG_FILENAME)
    if os.path.isfile(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_deploy_config(config: Dict[str, str]):
    """Save deployment credentials to local config."""
    config_path = os.path.join(os.getcwd(), CONFIG_FILENAME)
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
    except Exception:
        pass


def mask_token(token: str) -> str:
    """Masks a token for safe display: shows first 6 and last 4 chars."""
    if len(token) <= 12:
        return "***"
    return token[:6] + "..." + token[-4:]
