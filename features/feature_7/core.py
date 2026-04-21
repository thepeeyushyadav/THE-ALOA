"""
╔══════════════════════════════════════════════════════════════════╗
║  ALOA CLOUD HEALER — Feature 7 Core Engine (v3.0)               ║
║  A True AI Agent for Cloud-Deployed GitHub Projects              ║
║                                                                  ║
║  Architecture:                                                   ║
║    1. Multi-turn conversation memory                             ║
║    2. Intelligent file reading (reads only what's needed)        ║
║    3. Syntax validation before applying any changes              ║
║    4. Fuzzy diff-based patching (never fails on whitespace)      ║
║    5. Full-rewrite fallback for major refactors                  ║
║    6. Double-lock permission system (Accept/Deny → Push Y/N)     ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import ast
import shutil
import subprocess
import urllib.request
import json
import re
import difflib

from features.feature_6.core import scan_source_files, SOURCE_EXTENSIONS, SKIP_DIRS


# ──────────────────────────────────────────────────────────
# AI API Configuration (Bedrock Primary → OpenRouter Fallback)
# ──────────────────────────────────────────────────────────

BEDROCK_API_KEY = os.environ.get("BEDROCK_API_KEY", "")
BEDROCK_REGION = "ap-southeast-2"
BEDROCK_MODEL_ID = "anthropic.claude-3-5-sonnet-20241022-v2:0"

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = "openrouter/auto"


def _call_bedrock(messages, system_prompt):
    """Calls Claude directly via AWS Bedrock InvokeModel REST API."""
    url = f"https://bedrock-runtime.{BEDROCK_REGION}.amazonaws.com/model/{BEDROCK_MODEL_ID}/invoke"
    headers = {
        "Authorization": f"Bearer {BEDROCK_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "system": system_prompt,
        "messages": messages
    }).encode("utf-8")

    req = urllib.request.Request(url, data=body, headers=headers, method='POST')
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read().decode('utf-8'))
        if 'content' in result and len(result['content']) > 0:
            return result['content'][0]['text']
        raise ValueError("Unrecognized Bedrock response format.")


def _call_openrouter(messages, system_prompt):
    """Fallback: Calls Claude via OpenRouter (OpenAI-compatible API)."""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://aloa-agent.local",
        "X-Title": "ALOA Cloud Healer",
    }
    openai_messages = [{"role": "system", "content": system_prompt}] + messages
    body = json.dumps({
        "model": OPENROUTER_MODEL,
        "messages": openai_messages,
        "max_tokens": 4096,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=body, headers=headers, method='POST'
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read().decode('utf-8'))
        return result['choices'][0]['message']['content']


def call_ai(messages, system_prompt):
    """
    Smart AI caller with multi-turn messages support.
    Tries Bedrock first, falls back to OpenRouter.
    """
    bedrock_error = None
    try:
        return _call_bedrock(messages, system_prompt)
    except Exception as e:
        bedrock_error = str(e)

    try:
        return _call_openrouter(messages, system_prompt)
    except Exception as e:
        raise ConnectionError(f"Both AI backends failed.\n  Bedrock: {bedrock_error}\n  OpenRouter: {e}")


# ══════════════════════════════════════════════════════════
# GITHUB OPERATIONS
# ══════════════════════════════════════════════════════════

def build_auth_url(repo_url, pat):
    """Injects the PAT into the HTTPS repo URL for secure, headless git operations."""
    repo_url = repo_url.strip()
    if repo_url.startswith("https://"):
        return repo_url.replace("https://", f"https://{pat}@", 1)
    elif repo_url.startswith("http://"):
        return repo_url.replace("http://", f"http://{pat}@", 1)
    return repo_url


def setup_cloud_workspace(repo_url, pat, dest_folder):
    """Clones the repository into a hidden local temp folder."""
    if os.path.exists(dest_folder):
        try:
            def remove_readonly(func, path, excinfo):
                import stat
                os.chmod(path, stat.S_IWRITE)
                func(path)
            shutil.rmtree(dest_folder, onerror=remove_readonly)
        except Exception:
            pass

    auth_url = build_auth_url(repo_url, pat)

    try:
        result = subprocess.run(
            ['git', 'clone', auth_url, dest_folder],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            return True, "Cloned successfully."
        else:
            return False, f"Git Clone Failed: {result.stderr.strip()}"
    except Exception as e:
        return False, f"System Error cloning repo: {str(e)}"


def push_to_cloud(dest_folder, commit_message="ALOA Cloud Healer: Applied fix"):
    """Adds tracked/untracked files, commits, and pushes to remote."""
    try:
        subprocess.run(['git', 'add', '.'], cwd=dest_folder, capture_output=True, text=True)

        res_commit = subprocess.run(
            ['git', 'commit', '-m', commit_message],
            cwd=dest_folder, capture_output=True, text=True
        )
        if "nothing to commit" in res_commit.stdout:
            return False, "No changes detected to push."

        res_push = subprocess.run(
            ['git', 'push', 'origin', 'HEAD'],
            cwd=dest_folder, capture_output=True, text=True
        )

        if res_push.returncode == 0:
            return True, "Successfully pushed fixes to GitHub."
        else:
            return False, f"Git Push Failed: {res_push.stderr.strip()}"
    except Exception as e:
        return False, f"System Error pushing repo: {str(e)}"


# ══════════════════════════════════════════════════════════
# FILE UTILITIES
# ══════════════════════════════════════════════════════════

def read_file_safe(filepath, max_chars=15000):
    """Reads a file safely with encoding fallback."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            return f.read(max_chars)
    except Exception:
        return None


def build_file_tree(folder_path):
    """Builds a lightweight file tree string (filenames + sizes only, no content)."""
    tree_lines = []
    for root, dirs, files in os.walk(folder_path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in SOURCE_EXTENSIONS:
                full_path = os.path.join(root, f)
                rel = os.path.relpath(full_path, folder_path)
                try:
                    size = os.path.getsize(full_path)
                    lines_count = sum(1 for _ in open(full_path, 'r', encoding='utf-8', errors='replace'))
                    tree_lines.append(f"  📄 {rel}  ({lines_count} lines, {size} bytes)")
                except Exception:
                    tree_lines.append(f"  📄 {rel}")
    return "\n".join(tree_lines)


def validate_python_syntax(code_string):
    """Validates Python code for syntax errors using ast.parse()."""
    try:
        ast.parse(code_string)
        return True, "Syntax OK"
    except SyntaxError as e:
        return False, f"SyntaxError at line {e.lineno}: {e.msg}"


# ══════════════════════════════════════════════════════════
# DIFF ENGINE — Intelligent Patching
# ══════════════════════════════════════════════════════════

def apply_search_replace(file_content, search_block, replace_block):
    """
    Applies a single SEARCH/REPLACE block to file content.
    Uses 3-tier matching: exact → stripped → fuzzy.
    Returns (new_content, success, message).
    """
    # Tier 1: exact match
    if search_block in file_content:
        return file_content.replace(search_block, replace_block, 1), True, "Exact match applied."

    # Tier 2: stripped match (remove trailing spaces per line)
    stripped_search = "\n".join(line.rstrip() for line in search_block.split("\n"))
    stripped_content = "\n".join(line.rstrip() for line in file_content.split("\n"))
    if stripped_search in stripped_content:
        # Find position in stripped content and map back
        idx = stripped_content.index(stripped_search)
        end = idx + len(stripped_search)
        # Rebuild using original content lines
        content_lines = file_content.split("\n")
        stripped_lines = stripped_search.split("\n")
        search_line_count = len(stripped_lines)

        # Map character position to line numbers
        char_count = 0
        start_line = 0
        for i, line in enumerate(stripped_content.split("\n")):
            if char_count >= idx:
                start_line = i
                break
            char_count += len(line) + 1

        replace_lines = replace_block.split("\n")
        new_lines = content_lines[:start_line] + replace_lines + content_lines[start_line + search_line_count:]
        return "\n".join(new_lines), True, "Stripped match applied."

    # Tier 3: fuzzy match using difflib
    content_lines = file_content.split("\n")
    search_lines = search_block.strip().split("\n")

    if not search_lines:
        return file_content, False, "Search block is empty."

    best_ratio = 0
    best_idx = -1
    search_len = len(search_lines)

    for i in range(len(content_lines) - search_len + 1):
        chunk = content_lines[i:i + search_len]
        ratio = difflib.SequenceMatcher(
            None, "\n".join(chunk), "\n".join(search_lines)
        ).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_idx = i

    if best_ratio >= 0.60:
        replace_lines = replace_block.strip().split("\n")
        new_lines = content_lines[:best_idx] + replace_lines + content_lines[best_idx + search_len:]
        return "\n".join(new_lines), True, f"Fuzzy match applied (similarity: {best_ratio:.0%})."

    return file_content, False, f"No match found. Best similarity was only {best_ratio:.0%}."


def generate_unified_diff(old_content, new_content, filename):
    """Generates a readable unified diff between two file contents."""
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)
    diff = difflib.unified_diff(old_lines, new_lines, fromfile=f"a/{filename}", tofile=f"b/{filename}", lineterm="")
    return "\n".join(diff)


# ══════════════════════════════════════════════════════════
# THE CLOUD HEALER AI AGENT
# ══════════════════════════════════════════════════════════

class CloudHealerAgent:
    """
    A multi-turn, tool-using AI Agent for debugging and modifying
    cloud-deployed GitHub projects.

    Key capabilities:
      - Maintains conversation history (memory)
      - Reads individual files on demand (not all at once)
      - Validates Python syntax before applying changes
      - Uses 3-tier diff patching (exact → stripped → fuzzy)
      - Supports full-file rewrite for major refactors
      - Double-lock permission system
    """

    def __init__(self, folder_path):
        self.folder_path = folder_path
        self.source_files = scan_source_files(folder_path)
        self.file_tree = build_file_tree(folder_path)
        self.conversation_history = []  # Multi-turn memory

        # Pending changes (set after AI proposes a fix)
        self.pending_file = None
        self.pending_diff = None        # Human-readable diff
        self.pending_new_content = None  # Full new file content to write
        self.pending_mode = None        # "patch" or "rewrite"

        # Build the system prompt with the file tree (lightweight)
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self):
        """Builds the agent's system prompt with project awareness."""

        # Read key project files automatically (small ones like requirements.txt, package.json, etc.)
        key_files_content = ""
        key_file_names = [
            'requirements.txt', 'package.json', 'Pipfile',
            'pyproject.toml', '.env.example', 'Dockerfile',
            'docker-compose.yml', 'README.md'
        ]
        for src in self.source_files:
            basename = os.path.basename(src).lower()
            if basename in [k.lower() for k in key_file_names]:
                content = read_file_safe(src, max_chars=3000)
                if content:
                    rel = os.path.relpath(src, self.folder_path)
                    key_files_content += f"\n═══ {rel} ═══\n{content}\n"

        return f"""You are ALOA Cloud Healer — an autonomous AI Agent for debugging and modifying cloud-deployed GitHub projects.

You are working inside a cloned GitHub repository. You have tools to explore and understand the codebase.

══════════════════════════════════
PROJECT FILE TREE:
══════════════════════════════════
{self.file_tree}

══════════════════════════════════
KEY PROJECT FILES:
══════════════════════════════════
{key_files_content if key_files_content else "(none found)"}

══════════════════════════════════
YOUR TOOLS & CAPABILITIES:
══════════════════════════════════

1. READ_FILE: If you need to see a file's content to understand the code, write:
   READ_FILE: <relative path>
   I will show you the file content, and you can continue your analysis.

2. PATCH A FILE: For targeted changes (fixing a bug, changing a value, etc.):
   FILE: <relative path>
   SEARCH:
   ```
   <exact lines from the original file you want to replace>
   ```
   REPLACE:
   ```
   <the new lines>
   ```
   You can include multiple SEARCH/REPLACE blocks for the same file.

3. REWRITE A FILE: For major refactoring or when there are too many issues:
   FILE: <relative path>
   FULL_REWRITE:
   ```
   <the entire new file content from line 1 to the end>
   ```

══════════════════════════════════
BEHAVIORAL RULES:
══════════════════════════════════

- ALWAYS read a file with READ_FILE before modifying it. Never guess file content.
- When using SEARCH blocks, copy the exact lines from the file I showed you.
- Explain what the problem is and what your fix does BEFORE showing the code blocks.
- If the user asks a question (not requesting a change), just answer — don't output any code blocks.
- If there are multiple errors, fix them ALL in one response using multiple SEARCH/REPLACE blocks.
- Be a senior developer. Be precise. Be thorough. Never hallucinate code.
"""

    def chat(self, user_message):
        """
        Main entry point. Sends a message to the AI and processes the response.
        Handles READ_FILE tool calls automatically (agentic loop).

        Returns: (ai_text, has_changes)
        """
        self.conversation_history.append({"role": "user", "content": user_message})

        # Agentic loop: keep going until the AI stops asking to read files
        max_iterations = 5
        for iteration in range(max_iterations):
            try:
                ai_response = call_ai(self.conversation_history, self.system_prompt)
            except ConnectionError as e:
                return str(e), False

            if "AI ERROR" in ai_response:
                return ai_response, False

            # Check if AI wants to read a file (tool use)
            read_requests = re.findall(r"READ_FILE:\s*(.+?)(?:\n|$)", ai_response, re.IGNORECASE)

            if read_requests and iteration < max_iterations - 1:
                # Fulfill the READ_FILE requests and feed the content back
                self.conversation_history.append({"role": "assistant", "content": ai_response})

                file_contents = []
                for req_path in read_requests:
                    req_path = req_path.strip().strip('`').strip('*')
                    full_path = os.path.join(self.folder_path, req_path)
                    if os.path.isfile(full_path):
                        content = read_file_safe(full_path, max_chars=15000)
                        if content:
                            file_contents.append(f"═══ CONTENT OF {req_path} ═══\n{content}\n═══ END OF {req_path} ═══")
                        else:
                            file_contents.append(f"⚠️ Could not read '{req_path}' (encoding issue or empty file).")
                    else:
                        file_contents.append(f"⚠️ File '{req_path}' not found in the repository.")

                tool_response = "\n\n".join(file_contents)
                self.conversation_history.append({"role": "user", "content": f"[SYSTEM] Here are the file contents you requested:\n\n{tool_response}\n\nNow continue with your analysis and provide the fix."})

                continue  # Let the AI continue with the new context

            # No more READ_FILE — this is the final response
            self.conversation_history.append({"role": "assistant", "content": ai_response})

            # Parse for code changes
            has_changes = self._parse_changes(ai_response)
            return ai_response, has_changes

        # Exhausted iterations
        return ai_response, self._parse_changes(ai_response)

    def _parse_changes(self, response_text):
        """
        Parses the AI response for PATCH or REWRITE blocks.
        If found, prepares the pending changes (but does NOT apply them yet).
        Returns True if changes were found.
        """
        self.pending_file = None
        self.pending_diff = None
        self.pending_new_content = None
        self.pending_mode = None

        # Find the targeted file
        file_patterns = [
            r"FILE:\s*(.+?)(?:\n|$)",
            r"FIX_FILE:\s*(.+?)(?:\n|$)",
        ]
        fix_file = None
        for pattern in file_patterns:
            m = re.search(pattern, response_text, re.IGNORECASE)
            if m:
                fix_file = m.group(1).strip().strip('`').strip('*')
                break

        if not fix_file:
            return False

        fix_path = os.path.join(self.folder_path, fix_file)
        if not os.path.isfile(fix_path):
            return False

        original_content = read_file_safe(fix_path, max_chars=500000) or ""

        # ── Check for FULL_REWRITE ──
        full_pattern = r"FULL_REWRITE:\s*```[a-z]*\n(.*?)\n```"
        full_match = re.search(full_pattern, response_text, re.DOTALL | re.IGNORECASE)
        if full_match:
            new_content = full_match.group(1)
            diff_text = generate_unified_diff(original_content, new_content, fix_file)
            self.pending_file = fix_file
            self.pending_new_content = new_content
            self.pending_diff = diff_text
            self.pending_mode = "rewrite"
            return True

        # ── Check for SEARCH/REPLACE blocks ──
        block_pattern = r"SEARCH:\s*```[a-z]*\n(.*?)\n```\s*REPLACE:\s*```[a-z]*\n(.*?)\n```"
        matches = list(re.finditer(block_pattern, response_text, re.DOTALL | re.IGNORECASE))

        if not matches:
            return False

        new_content = original_content
        all_succeeded = True
        messages = []

        for match in matches:
            search_str = match.group(1)
            replace_str = match.group(2)
            new_content, success, msg = apply_search_replace(new_content, search_str, replace_str)
            messages.append(msg)
            if not success:
                all_succeeded = False

        if not all_succeeded:
            # Even if some blocks failed, proceed with what we could apply
            pass

        diff_text = generate_unified_diff(original_content, new_content, fix_file)
        self.pending_file = fix_file
        self.pending_new_content = new_content
        self.pending_diff = diff_text
        self.pending_mode = "patch"
        return True

    def get_pending_diff(self):
        """Returns the human-readable diff of pending changes."""
        return self.pending_diff

    def get_pending_file(self):
        """Returns the filename of the pending change."""
        return self.pending_file

    def apply_pending_changes(self):
        """
        Applies the pending changes to the local workspace.
        Validates Python syntax before writing.
        Returns (success, message).
        """
        if not self.pending_file or not self.pending_new_content:
            return False, "No pending changes to apply."

        fix_path = os.path.join(self.folder_path, self.pending_file)

        # Validate Python syntax (only for .py files)
        if self.pending_file.endswith('.py'):
            is_valid, syntax_msg = validate_python_syntax(self.pending_new_content)
            if not is_valid:
                return False, f"⚠️ Fix has a syntax error! {syntax_msg}\n   The AI will be asked to retry."

        try:
            with open(fix_path, 'w', encoding='utf-8') as f:
                f.write(self.pending_new_content)

            mode = self.pending_mode
            filename = self.pending_file

            # Clear pending state
            self.pending_file = None
            self.pending_new_content = None
            self.pending_diff = None
            self.pending_mode = None

            return True, f"Successfully {'rewrote' if mode == 'rewrite' else 'patched'} {filename}"
        except Exception as e:
            return False, f"Failed to write file: {str(e)}"

    def retry_with_feedback(self, error_message):
        """
        If a fix had a syntax error or patch failure,
        feeds the error back to the AI and asks it to retry.
        """
        retry_msg = f"""[SYSTEM] Your previous fix could not be applied. Here is the error:

{error_message}

Please carefully re-read the file, fix your mistake, and provide the corrected SEARCH/REPLACE or FULL_REWRITE block.
Remember: SEARCH blocks must match the file content EXACTLY."""

        return self.chat(retry_msg)
