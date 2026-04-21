"""
╔══════════════════════════════════════════════════════════════════╗
║  ALOA CLOUD HEALER — Feature 7 Runner (v3.0)                    ║
║  Interactive CLI with Double-Lock Permission System              ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import re
import sys
import time
import json
import shutil

from features.feature_7.core import (
    setup_cloud_workspace,
    push_to_cloud,
    CloudHealerAgent,
)


# ──────────────────────────────────────────────────────────
# UI HELPERS
# ──────────────────────────────────────────────────────────

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


def cprint(text, color=""):
    """Print with optional ANSI color."""
    print(f"{color}{text}{RESET}")


def show_progress(text, steps=3, delay=0.35):
    """Animated progress indicator."""
    print(f"   {text}", end="", flush=True)
    for _ in range(steps):
        time.sleep(delay)
        print(".", end="", flush=True)
    print()


def print_divider():
    print("─" * 60)


def print_boxed(lines, color=CYAN):
    """Print lines inside a box."""
    width = max(len(line) for line in lines) + 4
    print(f"{color}  ┌{'─' * width}┐{RESET}")
    for line in lines:
        padded = line.ljust(width - 2)
        print(f"{color}  │  {padded}│{RESET}")
    print(f"{color}  └{'─' * width}┘{RESET}")


def get_multiline_input():
    """
    Reads multi-line input from the user.
    Single-word commands submit instantly.
    Content submits on a blank line after text.
    """
    lines = []
    empty_count = 0
    first_prompt = True

    while True:
        try:
            prompt = f"  {GREEN}You ➤{RESET} " if first_prompt else f"  {DIM}    ➤{RESET} "
            first_prompt = False
            line = input(prompt)
        except (EOFError, KeyboardInterrupt):
            return None

        # Single-word commands on the first line — instant submit
        if len(lines) == 0 and line.strip().lower() in ['exit', 'quit', 'accept', 'deny', 'y', 'n', 'push', 'status', 'help']:
            return line.strip()

        # Empty line handling
        if line.strip() == '':
            empty_count += 1
            if empty_count >= 1 and len(lines) > 0:
                break
            continue
        else:
            empty_count = 0
            lines.append(line)

    return '\n'.join(lines).strip()


def display_diff(diff_text, filename):
    """Displays a colorized diff in the terminal."""
    if not diff_text or not diff_text.strip():
        cprint(f"\n  📄 Full rewrite of {filename} (diff too large to display inline)\n", YELLOW)
        return

    cprint(f"\n  {'─' * 50}", DIM)
    cprint(f"  📄 Proposed changes to: {filename}", BOLD)
    cprint(f"  {'─' * 50}", DIM)

    line_count = 0
    for line in diff_text.split('\n'):
        if line_count > 60:
            cprint(f"  {DIM}... ({len(diff_text.splitlines()) - line_count} more lines){RESET}")
            break

        if line.startswith('+++') or line.startswith('---'):
            cprint(f"  {line}", BOLD)
        elif line.startswith('+'):
            cprint(f"  {line}", GREEN)
        elif line.startswith('-'):
            cprint(f"  {line}", RED)
        elif line.startswith('@@'):
            cprint(f"  {line}", CYAN)
        else:
            print(f"  {line}")
        line_count += 1

    cprint(f"  {'─' * 50}\n", DIM)


def extract_explanation(ai_response):
    """
    Extracts the human-readable explanation from the AI response,
    stripping out code blocks and formatting markers.
    """
    # Remove code blocks
    cleaned = re.sub(r'```[\s\S]*?```', '', ai_response)
    # Remove markers
    cleaned = re.sub(r'(FILE|FIX_FILE|SEARCH|REPLACE|FULL_REWRITE|READ_FILE):.*', '', cleaned, flags=re.IGNORECASE)
    # Clean up multiple blank lines
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned).strip()

    if not cleaned:
        return "Changes proposed."

    # Truncate if too long for terminal display
    lines = cleaned.split('\n')
    result_lines = []
    char_count = 0
    for line in lines:
        result_lines.append(line)
        char_count += len(line)
        if char_count > 800:
            result_lines.append("...")
            break

    return '\n'.join(result_lines)


# ──────────────────────────────────────────────────────────
# CREDENTIALS MANAGEMENT
# ──────────────────────────────────────────────────────────

def load_config():
    """Load saved repo URL and PAT from local config."""
    config_path = os.path.join(os.getcwd(), ".aloa_cloud_config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                cfg = json.load(f)
                return cfg.get("repo_url", ""), cfg.get("pat", "")
        except Exception:
            pass
    return "", ""


def save_config(repo_url, pat):
    """Save repo URL and PAT to local config."""
    config_path = os.path.join(os.getcwd(), ".aloa_cloud_config.json")
    with open(config_path, "w") as f:
        json.dump({"repo_url": repo_url, "pat": pat}, f)


def get_credentials():
    """Interactive credential collection with saved config support."""
    saved_url, saved_pat = load_config()

    if saved_url and saved_pat:
        # Mask the PAT for display (show first 8 and last 4 chars)
        masked_pat = saved_pat[:8] + "..." + saved_pat[-4:] if len(saved_pat) > 12 else "***"
        cprint(f"   📂 Saved repo: {saved_url}", CYAN)
        cprint(f"   🔑 Saved PAT:  {masked_pat}", DIM)
        print()
        cprint(f"   Press {GREEN}Enter{RESET} to continue with this repo", "")
        cprint(f"   Type  {YELLOW}n{RESET}     to switch to a different repo", "")
        use_saved = input(f"   ➤ ").strip().lower()
        if use_saved != 'n':
            return saved_url, saved_pat
        print()

    repo_url = input("   📂 Enter GitHub Repository URL: ").strip()
    if not repo_url:
        return None, None

    pat = input("   🔑 Enter GitHub Personal Access Token (PAT): ").strip()
    if not pat:
        return None, None

    save_config(repo_url, pat)
    return repo_url, pat


# ──────────────────────────────────────────────────────────
# MAIN RUNNER
# ──────────────────────────────────────────────────────────

def run():
    print()
    cprint("  ╔══════════════════════════════════════════════════════════╗", CYAN)
    cprint("  ║       ☁️  ALOA CLOUD HEALER v3.0 — AI Agent Mode       ║", CYAN)
    cprint("  ╚══════════════════════════════════════════════════════════╝", CYAN)
    print()

    # ── 1. Credentials ──
    repo_url, pat = get_credentials()
    if not repo_url or not pat:
        cprint("   ℹ️  Missing credentials. Returning to Main Menu...", YELLOW)
        return

    # ── 2. Clone ──
    print()
    show_progress("🚀 Cloning repository into secure workspace")

    temp_workspace = os.path.join(os.getcwd(), ".aloa_cloud_temp")
    success, msg = setup_cloud_workspace(repo_url, pat, temp_workspace)
    if not success:
        cprint(f"   ❌ {msg}", RED)
        return

    cprint("   ✅ Repository cloned successfully.", GREEN)

    # ── 3. Initialize Agent ──
    show_progress("🧠 Initializing AI Agent with project awareness")
    agent = CloudHealerAgent(temp_workspace)
    cprint(f"   ✅ Agent loaded. {len(agent.source_files)} source files detected.\n", GREEN)

    # ── 4. Welcome ──
    print_boxed([
        "🤖 Cloud Healer Agent Ready",
        "─" * 40,
        "📝 Paste error logs from your deployment",
        "💬 Type modification requests in plain English",
        "❓ Ask questions about your code",
        "🚪 Type 'exit' to clean up and leave",
    ])
    print()

    # ── 5. Agent Chat Loop ──
    while True:
        print_divider()
        cprint("  What would you like me to do?", DIM)
        cprint("  (Press Enter on an empty line to submit)\n", DIM)

        user_input = get_multiline_input()

        if user_input is None or user_input.lower() in ['exit', 'quit']:
            break

        if not user_input:
            continue

        if user_input.lower() == 'help':
            print_boxed([
                "Available Commands:",
                "  'exit'   — Clean up and return to main menu",
                "  'help'   — Show this help message",
                "  'status' — Show project file tree",
                "",
                "Or just type naturally:",
                "  • Paste error logs and I'll fix them",
                "  • 'Change the button color to green'",
                "  • 'Add logging to the main function'",
                "  • 'Explain how the auth system works'",
            ])
            continue

        if user_input.lower() == 'status':
            cprint(f"\n  📁 Project File Tree:\n{agent.file_tree}\n", DIM)
            continue

        # ── Direct Push/Commit Commands (intercept before sending to AI) ──
        push_keywords = ['commit', 'push', 'push again', 'try again', 'retry push',
                         'try commit', 'push to github', 'git push', 'try commit again',
                         'retry', 'push it', 'deploy']
        if user_input.lower().strip() in push_keywords:
            cprint("\n  🔄 Retrying push to GitHub...", YELLOW)
            commit_msg = input(f"  {DIM}Commit message (Enter for default):{RESET} ").strip()
            if not commit_msg:
                commit_msg = "ALOA Cloud Healer: Applied fix"
            show_progress("🔄 Committing and pushing to GitHub")
            push_ok, push_msg = push_to_cloud(temp_workspace, commit_msg)
            if push_ok:
                cprint(f"  ✅ {push_msg}", GREEN)
                cprint(f"  🚀 Changes are live! Check your CI/CD for redeployment.", GREEN)
            else:
                cprint(f"  ❌ {push_msg}", RED)
                cprint(f"  💡 If permission denied: update your PAT with 'Contents: Read and Write' on GitHub.", YELLOW)
            continue

        # ── Send to AI Agent ──
        show_progress("🧠 Agent is thinking", steps=4, delay=0.5)

        ai_response, has_changes = agent.chat(user_input)

        if not has_changes:
            # No code changes — just an informational response
            explanation = extract_explanation(ai_response)
            cprint(f"\n  🤖 {explanation}\n", "")
            continue

        # ── Code changes detected! ──
        explanation = extract_explanation(ai_response)
        cprint(f"\n  🤖 {explanation}", "")

        # Show the diff
        diff = agent.get_pending_diff()
        filename = agent.get_pending_file()
        display_diff(diff, filename)

        # ═══════════════════════════════════════════
        # GATE 1: Accept or Deny code changes
        # ═══════════════════════════════════════════
        cprint(f"  ┌─────────────────────────────────────────┐", YELLOW)
        cprint(f"  │  Apply these changes to: {filename:<15s}│", YELLOW)
        cprint(f"  │  Type {GREEN}'accept'{YELLOW} or {RED}'deny'{YELLOW}                 │", YELLOW)
        cprint(f"  └─────────────────────────────────────────┘", YELLOW)

        gate1 = input(f"  {YELLOW}Decision ➤{RESET} ").strip().lower()

        if gate1 not in ['accept', 'y', 'yes']:
            cprint("  ❌ Changes denied. No files were modified.\n", RED)
            continue

        # Apply the changes locally
        success, apply_msg = agent.apply_pending_changes()

        if not success:
            cprint(f"  ⚠️  {apply_msg}", RED)

            # If syntax error, auto-retry with the AI
            if "syntax error" in apply_msg.lower():
                cprint("  🔄 Asking AI to fix the syntax error...\n", YELLOW)
                retry_response, retry_has_changes = agent.retry_with_feedback(apply_msg)

                if retry_has_changes:
                    explanation = extract_explanation(retry_response)
                    cprint(f"\n  🤖 {explanation}", "")
                    display_diff(agent.get_pending_diff(), agent.get_pending_file())

                    gate1_retry = input(f"  {YELLOW}Accept retry? [Y/n] ➤{RESET} ").strip().lower()
                    if gate1_retry not in ['n', 'no', 'deny']:
                        success, apply_msg = agent.apply_pending_changes()
                        if not success:
                            cprint(f"  ❌ Retry also failed: {apply_msg}", RED)
                            continue
                    else:
                        cprint("  ❌ Retry denied.\n", RED)
                        continue
                else:
                    cprint(f"  ❌ AI could not produce a valid fix on retry.\n", RED)
                    continue
            else:
                continue

        cprint(f"  ✅ {apply_msg}", GREEN)

        # ═══════════════════════════════════════════
        # GATE 2: Push to GitHub or keep local only
        # ═══════════════════════════════════════════
        print()
        cprint(f"  ┌─────────────────────────────────────────┐", CYAN)
        cprint(f"  │  📤 Push changes to GitHub?             │", CYAN)
        cprint(f"  │  Type {GREEN}'y'{CYAN} to push, {RED}'n'{CYAN} to keep local     │", CYAN)
        cprint(f"  └─────────────────────────────────────────┘", CYAN)

        gate2 = input(f"  {CYAN}Push ➤{RESET} ").strip().lower()

        if gate2 in ['y', 'yes', 'push']:
            commit_msg = input(f"  {DIM}Commit message (Enter for default):{RESET} ").strip()
            if not commit_msg:
                commit_msg = f"ALOA Cloud Healer: Fixed {filename}"

            show_progress("🔄 Committing and pushing to GitHub")
            push_ok, push_msg = push_to_cloud(temp_workspace, commit_msg)

            if push_ok:
                cprint(f"  ✅ {push_msg}", GREEN)
                cprint(f"  🚀 Changes are live! Check your CI/CD for redeployment.", GREEN)
            else:
                cprint(f"  ❌ {push_msg}", RED)
        else:
            cprint("  ℹ️  Changes applied locally only. Not pushed to GitHub.\n", DIM)

    # ── 6. Cleanup ──
    print()
    show_progress("🧹 Cleaning up temporary workspace")
    try:
        def remove_readonly(func, path, excinfo):
            import stat
            os.chmod(path, stat.S_IWRITE)
            func(path)
        shutil.rmtree(temp_workspace, onerror=remove_readonly)
        cprint("  ✅ Workspace wiped completely.", GREEN)
    except Exception as e:
        cprint(f"  ⚠️ Could not delete workspace: {e}", YELLOW)

    cprint("  [ALOA] Returning to Main Menu...\n", DIM)
