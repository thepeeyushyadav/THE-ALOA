import os
import sys
import subprocess
import shutil
import warnings
import re
import json
import time
import urllib.request
import urllib.error

warnings.filterwarnings("ignore")
os.environ["GRPC_VERBOSITY"] = "ERROR"

try:
    import google.generativeai as genai
except ImportError as e:
    print(f"\n[CRITICAL ERROR] Library Missing: {e}")
    print("Run: pip install google-generativeai")
    sys.exit()

# ──────────────────────────────────────────────────────────
# API Keys — Split by Purpose
# ──────────────────────────────────────────────────────────
# Gemini keys for chat/init
API_KEY_INIT = os.environ.get("GEMINI_API_KEY_1", "")
API_KEY_CHAT = os.environ.get("GEMINI_API_KEY_2", "")

# OpenRouter API key — UNLIMITED, used for error fixing & fallback
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = "openrouter/auto"  # Auto-selects best available model

# Configure Gemini with init key
genai.configure(api_key=API_KEY_INIT)

GEMINI_MODELS = ["gemini-2.0-flash", "gemini-flash-latest"]

# ──────────────────────────────────────────────────────────
# File extensions recognized as source code
# ──────────────────────────────────────────────────────────
SOURCE_EXTENSIONS = {
    '.py', '.js', '.ts', '.jsx', '.tsx',
    '.java', '.c', '.cpp', '.h', '.hpp',
    '.cs', '.go', '.rb', '.php', '.rs',
    '.html', '.css', '.json', '.xml', '.yaml', '.yml',
    '.sh', '.bat', '.ps1', '.sql', '.kt', '.swift',
    '.lua', '.r', '.dart', '.vue', '.svelte',
    '.env', '.toml', '.cfg', '.ini', '.md',
}

SKIP_DIRS = {
    '__pycache__', '.git', 'venv', 'env', '.venv', 'node_modules',
    '.idea', 'build', 'dist', 'target', '.next', 'bin', 'obj',
    '.vs', '.cache', '.tox', 'egg-info',
}

# Project detection signatures
PROJECT_SIGNATURES = [
    ('requirements.txt',  'python', 'python {entry}'),
    ('setup.py',           'python', 'python {entry}'),
    ('Pipfile',            'python', 'python {entry}'),
    ('pyproject.toml',     'python', 'python {entry}'),
    ('package.json',       'node',   'npm start'),
    ('pom.xml',            'java',   'mvn compile exec:java'),
    ('build.gradle',       'java',   'gradle run'),
    ('Makefile',           'c_cpp',  'make && ./a.out'),
    ('CMakeLists.txt',     'c_cpp',  'cmake . && make'),
    ('go.mod',             'go',     'go run .'),
    ('Cargo.toml',         'rust',   'cargo run'),
    ('Gemfile',            'ruby',   'ruby {entry}'),
    ('composer.json',      'php',    'php {entry}'),
    ('pubspec.yaml',       'dart',   'dart run'),
]

ENTRY_POINTS = {
    'python': ['main.py', 'app.py', 'run.py', 'manage.py', 'index.py', 'start.py', 'server.py'],
    'node':   ['index.js', 'app.js', 'server.js', 'main.js', 'index.ts', 'app.ts', 'main.ts'],
    'java':   ['Main.java', 'App.java', 'Application.java'],
    'c_cpp':  ['main.c', 'main.cpp', 'app.c', 'app.cpp'],
    'go':     ['main.go'],
    'rust':   ['main.rs', 'lib.rs'],
    'ruby':   ['main.rb', 'app.rb', 'server.rb'],
    'php':    ['index.php', 'app.php', 'main.php'],
    'dart':   ['main.dart', 'app.dart'],
    'dotnet': ['Program.cs', 'Main.cs'],
}


# ══════════════════════════════════════════════════════════
# PROJECT SCANNING & DETECTION
# ══════════════════════════════════════════════════════════

def detect_project_type(folder_path):
    """Detects the project type based on marker files."""
    files_in_root = os.listdir(folder_path)
    for sig_file, proj_type, run_cmd in PROJECT_SIGNATURES:
        if '*' in sig_file:
            ext = sig_file.replace('*', '')
            if any(f.endswith(ext) for f in files_in_root):
                return proj_type, run_cmd
        elif sig_file in files_in_root:
            return proj_type, run_cmd

    # Fallback: detect by dominant extension
    ext_count = {}
    for root, dirs, files in os.walk(folder_path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in SOURCE_EXTENSIONS:
                ext_count[ext] = ext_count.get(ext, 0) + 1
    if ext_count:
        dominant = max(ext_count, key=ext_count.get)
        mapping = {'.py': 'python', '.js': 'node', '.ts': 'node', '.java': 'java',
                   '.c': 'c_cpp', '.cpp': 'c_cpp', '.cs': 'dotnet', '.go': 'go',
                   '.rb': 'ruby', '.php': 'php', '.rs': 'rust', '.dart': 'dart'}
        return mapping.get(dominant, 'unknown'), None
    return 'unknown', None


def scan_source_files(folder_path):
    """Scans a folder recursively for all source code files."""
    source_files = []
    for root, dirs, files in os.walk(folder_path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in SOURCE_EXTENSIONS:
                source_files.append(os.path.join(root, f))
    return source_files


def detect_entry_point(source_files, folder_path, proj_type):
    """Tries to auto-detect the main entry point of the project."""
    entry_names = ENTRY_POINTS.get(proj_type, [])
    for name in entry_names:
        for f in source_files:
            if os.path.basename(f).lower() == name.lower():
                return f
    if proj_type == 'python':
        for f in source_files:
            if f.endswith('.py'):
                try:
                    with open(f, 'r', encoding='utf-8', errors='ignore') as fh:
                        content = fh.read()
                        if '__name__' in content and '__main__' in content:
                            return f
                except:
                    pass
    return None


def auto_detect_run_command(folder_path, source_files, proj_type, default_run_cmd):
    """Fully automatically determines the run command for the project."""
    entry = detect_entry_point(source_files, folder_path, proj_type)

    # Node.js: read package.json
    if proj_type == 'node':
        pkg_path = os.path.join(folder_path, 'package.json')
        if os.path.isfile(pkg_path):
            try:
                with open(pkg_path, 'r', encoding='utf-8') as pf:
                    pkg = json.load(pf)
                if pkg.get('scripts', {}).get('start'):
                    return 'npm start', entry
                elif pkg.get('main') and not entry:
                    main_file = os.path.join(folder_path, pkg['main'])
                    if os.path.isfile(main_file):
                        entry = main_file
            except:
                pass

    if default_run_cmd and '{entry}' in default_run_cmd and entry:
        return default_run_cmd.replace('{entry}', os.path.relpath(entry, folder_path)), entry
    elif default_run_cmd and '{entry}' not in default_run_cmd:
        return default_run_cmd, entry
    elif entry:
        ext = os.path.splitext(entry)[1].lower()
        runners = {'.py': 'python', '.js': 'node', '.ts': 'npx ts-node', '.rb': 'ruby',
                   '.php': 'php', '.go': 'go run', '.dart': 'dart run', '.java': 'java'}
        runner = runners.get(ext, 'python')
        return f"{runner} {os.path.relpath(entry, folder_path)}", entry
    elif source_files:
        first = source_files[0]
        ext = os.path.splitext(first)[1].lower()
        runners = {'.py': 'python', '.js': 'node', '.rb': 'ruby', '.php': 'php'}
        runner = runners.get(ext, 'python')
        return f"{runner} {os.path.relpath(first, folder_path)}", None
    return None, None


# Commands that start long-running dev servers (don't exit on their own)
DEV_SERVER_COMMANDS = ['npm start', 'npm run dev', 'npm run serve', 'yarn start', 'yarn dev',
                        'flask run', 'uvicorn', 'gunicorn', 'django', 'manage.py runserver',
                        'ng serve', 'vite', 'next dev', 'nuxt dev', 'gatsby develop',
                        'cargo watch', 'go run', 'nodemon', 'react-scripts start']

# Error patterns to detect in stdout/stderr even if exit code is 0
# Critical error patterns — these ALWAYS indicate real failures
CRITICAL_ERROR_PATTERNS = [
    'Failed to compile', 'Compilation failed', 'Build failed',
    'Traceback (most recent call last)', 'SyntaxError', 'TypeError',
    'ReferenceError', 'NameError', 'ImportError', 'ModuleNotFoundError',
    'Cannot find module', 'Module not found', 'ENOENT', 'EACCES', 'EADDRINUSE',
    'fatal error', 'Fatal error', 'FATAL',
    'Unhandled', 'Uncaught', 'panic:',
    'Something is already running on port',
    'webpack compiled with', 'ERROR in',
]

# General error patterns (may need false-positive filtering)
GENERAL_ERROR_PATTERNS = [
    'error', 'Error:', 'ERROR', 'failed', 'Failed',
    'Exception',
]

# False positives to ignore (only for general patterns)
ERROR_FALSE_POSITIVES = [
    'error-overlay', 'error.js', 'errorHandler', 'error_page',
    'No errors', '0 errors', 'error-free', 'suppress_errors',
    'console.error', '.error(', 'error.css', 'errors: 0',
]


def is_dev_server_command(run_command):
    """Check if the run command starts a long-running dev server."""
    cmd_lower = run_command.lower()
    return any(pattern in cmd_lower for pattern in DEV_SERVER_COMMANDS)


def detect_errors_in_output(stdout, stderr):
    """
    Analyze stdout and stderr for error patterns.
    Returns (has_error: bool, error_text: str)
    """
    combined = (stdout + "\n" + stderr).strip()
    if not combined:
        return False, ""

    # Check stderr first — if it has real content, it's likely an error
    if stderr.strip():
        noise_patterns = ['npm warn', 'deprecation', 'experimentalwarning', 'debugger listening']
        is_just_noise = all(
            line.strip() == '' or any(noise in line.lower() for noise in noise_patterns)
            for line in stderr.strip().split('\n')
        )
        if not is_just_noise:
            return True, stderr.strip()

    # Check critical patterns first — these are ALWAYS errors, no false-positive check
    for pattern in CRITICAL_ERROR_PATTERNS:
        if pattern in combined:
            return True, combined

    # Check general patterns with false-positive filtering
    for pattern in GENERAL_ERROR_PATTERNS:
        if pattern in combined:
            # Check each line containing the pattern for false positives
            error_lines = [l for l in combined.split('\n') if pattern in l]
            for line in error_lines:
                is_fp = any(fp in line for fp in ERROR_FALSE_POSITIVES)
                if not is_fp:
                    return True, combined

    return False, ""


def _kill_process_tree(pid):
    """Kill an entire process tree on Windows using taskkill."""
    try:
        subprocess.run(
            f'taskkill /T /F /PID {pid}',
            capture_output=True, shell=True, timeout=10
        )
    except:
        pass


def _read_stream(stream, output_list):
    """Thread target: reads all lines from a stream into a list."""
    try:
        for line in iter(stream.readline, ''):
            output_list.append(line)
        stream.close()
    except:
        pass


def execute_project(folder_path, run_command):
    """
    Smart project executor. Handles both:
    - Regular scripts (waits for completion)
    - Dev servers like 'npm start' (captures early output then terminates)
    Returns (success, stdout, stderr, is_server)
    """
    import threading

    is_server = is_dev_server_command(run_command)

    if is_server:
        # ── Dev Server Mode ──
        # Start process, read output with threads, wait for compile result, then kill tree
        try:
            process = subprocess.Popen(
                run_command,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                cwd=folder_path, shell=True, text=True,
                bufsize=1  # Line-buffered
            )

            stdout_lines = []
            stderr_lines = []

            # Start reader threads (non-blocking)
            t_out = threading.Thread(target=_read_stream, args=(process.stdout, stdout_lines), daemon=True)
            t_err = threading.Thread(target=_read_stream, args=(process.stderr, stderr_lines), daemon=True)
            t_out.start()
            t_err.start()

            # Wait up to 30 seconds, checking every second for:
            # - Process exit (crash)
            # - Compilation result (success or failure pattern in output)
            max_wait = 30
            for i in range(max_wait):
                time.sleep(1)

                # Check if process exited early (crash / quick error)
                if process.poll() is not None:
                    t_out.join(timeout=3)
                    t_err.join(timeout=3)
                    break

                # Check output so far for known result patterns
                current_output = ''.join(stdout_lines) + ''.join(stderr_lines)

                # *** CHECK FAILURES FIRST *** (before success)
                if any(p in current_output for p in [
                    'Failed to compile', 'Compilation failed',
                    'Module not found', 'SyntaxError',
                    'Cannot find module', 'Error:',
                    'ERROR in', 'error TS',
                    'Something is already running on port',
                    'webpack compiled with',  # "webpack compiled with 1 error"
                ]):
                    # Compilation/startup error — kill and report failure
                    _kill_process_tree(process.pid)
                    t_out.join(timeout=3)
                    t_err.join(timeout=3)
                    stdout = ''.join(stdout_lines)
                    stderr = ''.join(stderr_lines)
                    error_text = (stdout + "\n" + stderr).strip()
                    return False, stdout, error_text, True

                # Check success indicators (only if no failure found)
                if any(p in current_output for p in [
                    'Compiled successfully', 'compiled successfully',
                    'ready on', 'Ready on', 'Server running',
                    'Listening on', 'listening on', 'started server',
                    'Local:',
                ]):
                    _kill_process_tree(process.pid)
                    t_out.join(timeout=3)
                    t_err.join(timeout=3)
                    stdout = ''.join(stdout_lines)
                    stderr = ''.join(stderr_lines)
                    return True, stdout, stderr, True

            # Timeout reached — kill process tree and analyze what we got
            _kill_process_tree(process.pid)
            t_out.join(timeout=2)
            t_err.join(timeout=2)

            stdout = ''.join(stdout_lines)
            stderr = ''.join(stderr_lines)

            has_error, error_text = detect_errors_in_output(stdout, stderr)
            if has_error:
                return False, stdout, error_text, True
            else:
                return True, stdout, stderr, True

        except Exception as e:
            return False, "", str(e), True
    else:
        # ── Regular Script Mode ── (runs to completion)
        try:
            result = subprocess.run(
                run_command, capture_output=True, text=True,
                cwd=folder_path, shell=True, timeout=60
            )
            if result.returncode != 0:
                return False, result.stdout, result.stderr, False

            # Even with exit code 0, check output for errors
            has_error, error_text = detect_errors_in_output(result.stdout, result.stderr)
            if has_error:
                return False, result.stdout, error_text, False

            return True, result.stdout, result.stderr, False

        except subprocess.TimeoutExpired:
            return False, "", "ERROR: Script timed out after 60 seconds.", False
        except Exception as e:
            return False, "", str(e), False


# ══════════════════════════════════════════════════════════
# PROJECT CONTEXT BUILDER
# ══════════════════════════════════════════════════════════

def read_file_safe(filepath, max_chars=10000):
    """Reads a file safely, truncating if too large."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read(max_chars)
    except:
        return None


def build_project_context(folder_path, source_files, max_total_chars=80000):
    """
    Build a complete project context string from source files.
    This becomes the AI agent's "knowledge" of the project.
    """
    context_parts = []
    chars_used = 0

    # Build file tree first
    tree_lines = ["PROJECT FILE TREE:"]
    for f in source_files:
        rel = os.path.relpath(f, folder_path)
        tree_lines.append(f"  📄 {rel}")
    tree_str = "\n".join(tree_lines)
    context_parts.append(tree_str)
    chars_used += len(tree_str)

    # Then include file contents
    context_parts.append("\n\nPROJECT SOURCE FILES:\n")
    for f in source_files:
        if chars_used >= max_total_chars:
            context_parts.append(f"\n[... {len(source_files)} total files, truncated for context limit ...]")
            break
        content = read_file_safe(f, max_chars=8000)
        if content:
            rel = os.path.relpath(f, folder_path)
            block = f"\n═══ FILE: {rel} ═══\n{content}\n═══ END: {rel} ═══\n"
            context_parts.append(block)
            chars_used += len(block)

    return "\n".join(context_parts)


# ══════════════════════════════════════════════════════════
# AI AGENT (Conversational Chat with Gemini)
# ══════════════════════════════════════════════════════════

class ALOAAgent:
    """
    The ALOA AI Agent — a conversational debugger that understands your project.
    Maintains chat history and can diagnose/fix errors through conversation.
    """

    def __init__(self, folder_path, source_files, proj_type, run_command):
        self.folder_path = folder_path
        self.source_files = source_files
        self.proj_type = proj_type
        self.run_command = run_command
        self.last_fix_file = None
        self.last_fix_code = None

        # Build project context
        self.project_context = build_project_context(folder_path, source_files)

        # Store system prompt so we can rebuild the chat on key rotation
        self.system_prompt = f"""You are ALOA, an Expert AI Coding Agent and Debugger. You are currently working on a {proj_type.upper()} project located at '{os.path.basename(folder_path)}'.

You have FULL knowledge of every source file in this project. Here is the complete project:

{self.project_context}

YOUR CAPABILITIES:
1. Answer any question about this project's code, architecture, or logic.
2. When given an error message or traceback, identify the EXACT file and line causing it, explain the root cause, and provide the fix.
3. When providing a code fix, you MUST format it EXACTLY like this:

FIX_FILE: <relative path to the file>
FIXED_CODE:
```
<complete corrected file content>
```

4. You can explain code, suggest improvements, find bugs, and help debug.
5. Be concise but thorough. Speak in a helpful, professional tone.
6. If the user says "run" or asks you to run the project, respond with: RUN_PROJECT

IMPORTANT RULES:
- When fixing code, ALWAYS output the COMPLETE file content, never partial.
- ALWAYS use the FIX_FILE and FIXED_CODE format when suggesting fixes.
- If you're not sure which file has the error, analyze the traceback carefully.
- Be conversational and helpful, like a senior developer pair-programming.
"""
        self.model = None
        self.chat = None
        self._init_chat()

    def _init_chat(self, api_key=None):
        """Initialize (or re-initialize) the Gemini chat with a specific API key."""
        key = api_key or API_KEY_CHAT
        genai.configure(api_key=key)
        self.model = None
        self.chat = None
        self._active_key = key
        for model_name in GEMINI_MODELS:
            try:
                self.model = genai.GenerativeModel(
                    model_name,
                    system_instruction=self.system_prompt
                )
                self.chat = self.model.start_chat(history=[])
                break
            except Exception:
                continue

    def _is_quota_error(self, error):
        """Check if the error is a 429 quota/rate-limit error."""
        err_str = str(error).lower()
        return '429' in err_str or 'quota' in err_str or 'rate' in err_str or 'resource has been exhausted' in err_str

    def _extract_retry_delay(self, error):
        """Extract retry delay in seconds from a 429 error, default to 15s."""
        err_str = str(error)
        match = re.search(r'retry.*?(\d+\.?\d*)s', err_str, re.IGNORECASE)
        if match:
            return min(float(match.group(1)) + 2, 30)
        return 15

    def _call_openrouter(self, user_message):
        """
        Call OpenRouter API (OpenAI-compatible) as a reliable fallback.
        Uses urllib so no extra dependencies needed.
        """
        try:
            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://aloa-agent.local",
                "X-Title": "ALOA Code Healer",
            }
            body = json.dumps({
                "model": OPENROUTER_MODEL,
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_message}
                ],
                "max_tokens": 4096,
            }).encode('utf-8')

            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                data=body, headers=headers, method='POST'
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                return result['choices'][0]['message']['content']
        except Exception as e:
            return f"AI ERROR: {str(e)}"

    def send_message(self, user_message, purpose='chat'):
        """
        Send a message to the AI agent.
        - 'fix' purpose: goes directly to OpenRouter (unlimited)
        - 'chat' purpose: tries Gemini first, falls back to OpenRouter
        """
        # For error fixing: go straight to OpenRouter (no quota issues)
        if purpose == 'fix':
            return self._call_openrouter(user_message)

        # For chat: try Gemini first
        if self.chat:
            gemini_keys = [API_KEY_CHAT, API_KEY_INIT]
            for key in gemini_keys:
                if key != self._active_key:
                    self._init_chat(api_key=key)
                try:
                    response = self.chat.send_message(user_message)
                    return response.text
                except Exception as e:
                    if self._is_quota_error(e):
                        continue  # Try next Gemini key
                    else:
                        break  # Non-quota error, fall through to OpenRouter

        # Gemini failed — fall back to OpenRouter
        return self._call_openrouter(user_message)

    def parse_fix_from_response(self, response_text):
        """
        Parse a fix suggestion from the AI response.
        Returns (fix_file_rel, fixed_code) or (None, None).
        """
        fix_file = None
        fixed_code = None

        # Extract FIX_FILE
        file_match = re.search(r"FIX_FILE:\s*(.+?)(?:\n|$)", response_text)
        if file_match:
            fix_file = file_match.group(1).strip().strip('`')

        # Extract code from code block
        code_match = re.search(r"FIXED_CODE:\s*```\w*\s*(.*?)\s*```", response_text, re.DOTALL)
        if code_match:
            fixed_code = code_match.group(1).strip()
        else:
            # Fallback: any code block after FIX_FILE
            code_match = re.search(r"```\w*\s*(.*?)\s*```", response_text, re.DOTALL)
            if code_match and fix_file:
                fixed_code = code_match.group(1).strip()

        if fix_file and fixed_code and len(fixed_code) > 5:
            self.last_fix_file = fix_file
            self.last_fix_code = fixed_code
            return fix_file, fixed_code

        return None, None

    def apply_fix(self):
        """Apply the last suggested fix."""
        if not self.last_fix_file or not self.last_fix_code:
            return False, "No fix available to apply."

        fix_path = os.path.join(self.folder_path, self.last_fix_file)
        if not os.path.isfile(fix_path):
            return False, f"File '{self.last_fix_file}' not found."

        try:
            backup_path = fix_path + ".bak"
            if not os.path.exists(backup_path):
                shutil.copy2(fix_path, backup_path)
            with open(fix_path, 'w', encoding='utf-8') as f:
                f.write(self.last_fix_code)
            return True, f"Fixed '{self.last_fix_file}' successfully. Backup saved as .bak"
        except Exception as e:
            return False, str(e)

    def run_project(self):
        """Run the project and return results (success, stdout, stderr, is_server)."""
        if not self.run_command:
            return False, "", "No run command detected.", False
        return execute_project(self.folder_path, self.run_command)
