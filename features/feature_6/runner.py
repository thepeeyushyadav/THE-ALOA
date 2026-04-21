import time
import os
import re
import subprocess
from features.feature_6.core import (
    detect_project_type,
    scan_source_files,
    auto_detect_run_command,
    ALOAAgent,
)


# ══════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ══════════════════════════════════════════════════════════

def kill_port_process(port):
    """Finds and kills the process occupying a given port on Windows."""
    try:
        result = subprocess.run(
            f'netstat -ano | findstr :{port}',
            capture_output=True, text=True, shell=True
        )
        if not result.stdout.strip():
            return False, f"No process found on port {port}."

        pids = set()
        for line in result.stdout.strip().split('\n'):
            parts = line.split()
            if len(parts) >= 5 and parts[-1].isdigit():
                pids.add(parts[-1])

        if not pids:
            return False, "Could not extract PID."

        killed = []
        for pid in pids:
            kill_result = subprocess.run(
                f'taskkill /PID {pid} /F',
                capture_output=True, text=True, shell=True
            )
            if kill_result.returncode == 0:
                killed.append(pid)

        if killed:
            return True, f"Cleared port {port} (PID {', '.join(killed)})"
        return False, f"Failed to kill process on port {port}."
    except Exception as e:
        return False, str(e)


def open_folder_explorer():
    """Opens a Windows Folder picker dialog using PowerShell."""
    try:
        ps_script = (
            '[System.Reflection.Assembly]::LoadWithPartialName("System.Windows.Forms") | Out-Null;'
            '$dialog = New-Object System.Windows.Forms.FolderBrowserDialog;'
            '$dialog.Description = "ALOA - Select Project Folder to Debug";'
            '$dialog.ShowNewFolderButton = $false;'
            'if ($dialog.ShowDialog() -eq "OK") { $dialog.SelectedPath } else { "" }'
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True, text=True, timeout=120
        )
        folder_path = result.stdout.strip()
        return folder_path if folder_path else None
    except Exception as e:
        print(f"   ⚠️ Could not open folder explorer: {e}")
        return None


# ══════════════════════════════════════════════════════════
# OUTPUT FORMATTING — Clean, Agent-like display
# ══════════════════════════════════════════════════════════

# Lines to strip from terminal output (noise)
NOISE_PATTERNS = [
    'DeprecationWarning:', '(Use `node --trace',
    'Search for the keywords to learn more',
    'Note that the development build is not optimized',
    'To create a production build',
    'WARNING in [eslint]', 'npm warn',
    'ExperimentalWarning',
]


def clean_terminal_output(text):
    """Strip noise from terminal output, return only the essential lines."""
    lines = text.strip().split('\n')
    cleaned = []
    skip_next_empty = False

    for line in lines:
        stripped = line.strip()

        # Skip noise lines
        if any(noise in line for noise in NOISE_PATTERNS):
            skip_next_empty = True
            continue

        # Skip empty lines after noise
        if skip_next_empty and stripped == '':
            skip_next_empty = False
            continue
        skip_next_empty = False

        cleaned.append(line)

    # Remove trailing empty lines
    while cleaned and cleaned[-1].strip() == '':
        cleaned.pop()

    return '\n'.join(cleaned)


def extract_error_summary(error_text):
    """Extract a short, clean error summary from verbose output."""
    lines = error_text.strip().split('\n')
    key_lines = []

    for line in lines:
        stripped = line.strip()
        # Skip noise
        if any(noise in line for noise in NOISE_PATTERNS):
            continue
        if stripped == '' and key_lines and key_lines[-1] == '':
            continue
        # Skip duplicate "Search for keywords..." type lines
        if 'Search for the keywords' in line:
            continue
        # Keep error-relevant lines
        if any(kw in line for kw in [
            'Error', 'error', 'ERROR', 'Failed', 'failed',
            'not found', 'not defined', 'Module', 'Cannot',
            'Line ', 'Traceback', 'File ', 'import',
            'compiled with', 'no-undef', 'no-unused',
            'SyntaxError', 'TypeError', 'NameError',
        ]):
            key_lines.append(stripped)
        elif stripped.endswith('.js') or stripped.endswith('.py') or stripped.endswith('.ts'):
            key_lines.append(stripped)

    # If we got good key lines, return those; otherwise return first few lines
    if key_lines:
        return '\n'.join(key_lines[:8])
    else:
        # Just return first 5 non-empty meaningful lines
        meaningful = [l.strip() for l in lines if l.strip() and not any(n in l for n in NOISE_PATTERNS)]
        return '\n'.join(meaningful[:5])


def extract_ai_summary(ai_response):
    """
    Extract just the diagnosis from a verbose AI response.
    Returns a short, clean summary without code blocks or long explanations.
    """
    # Remove code blocks
    cleaned = re.sub(r'```[\s\S]*?```', '', ai_response)

    # Remove FIX_FILE / FIXED_CODE lines
    cleaned = re.sub(r'FIX_FILE:.*', '', cleaned)
    cleaned = re.sub(r'FIXED_CODE:.*', '', cleaned)

    # Split into sentences/lines
    lines = cleaned.strip().split('\n')

    # Get first meaningful paragraph (skip empty lines at start)
    summary_lines = []
    char_count = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if summary_lines:
                break  # Stop at first blank line after content
            continue
        # Skip numbered lists that are too detailed
        if stripped.startswith(('1.', '2.', '3.', '4.')) and char_count > 200:
            break
        summary_lines.append(stripped)
        char_count += len(stripped)
        if char_count > 300:
            break

    result = ' '.join(summary_lines)
    # Truncate if still too long
    if len(result) > 400:
        result = result[:397] + "..."
    return result if result else "Analyzing and preparing fix..."


def show_progress(text, steps=3, delay=0.4):
    """Show an animated progress indicator."""
    print(f"   {text}", end="", flush=True)
    for _ in range(steps):
        time.sleep(delay)
        print(".", end="", flush=True)
    print()


# ══════════════════════════════════════════════════════════
# MAIN RUNNER
# ══════════════════════════════════════════════════════════

def run():
    print()
    print("  ╔══════════════════════════════════════════════════════════╗")
    print("  ║         🤖  ALOA CODE HEALER — AI Agent v3.0           ║")
    print("  ╚══════════════════════════════════════════════════════════╝")
    print()

    # ── Step 1: Open Folder Explorer ──
    print("   📂 Select your project folder...")
    folder_path = open_folder_explorer()

    if not folder_path:
        print("   ℹ️  No folder selected.")
        print("[ALOA] Returning to Main Menu...")
        return

    project_name = os.path.basename(folder_path)
    print(f"   ✅ Project: {project_name}")

    # ── Step 2: Detect & Scan ──
    show_progress("🔍 Scanning project")
    proj_type, default_run_cmd = detect_project_type(folder_path)
    source_files = scan_source_files(folder_path)

    if not source_files:
        print("   ❌ No source code files found.")
        print("[ALOA] Returning to Main Menu...")
        return

    # Summary line
    ext_groups = {}
    for f in source_files:
        ext = os.path.splitext(f)[1]
        ext_groups[ext] = ext_groups.get(ext, 0) + 1
    ext_summary = ", ".join(f"{count}{ext}" for ext, count in sorted(ext_groups.items(), key=lambda x: -x[1])[:4])
    print(f"   📄 {len(source_files)} files ({ext_summary})")
    print(f"   🏷️  {proj_type.upper()}")

    # ── Step 3: Auto-detect run command ──
    run_command, entry = auto_detect_run_command(folder_path, source_files, proj_type, default_run_cmd)
    if run_command:
        print(f"   ▶️  {run_command}")

    # ── Step 4: Initialize AI Agent ──
    show_progress("🧠 Loading project into AI brain")
    agent = ALOAAgent(folder_path, source_files, proj_type, run_command)

    if not agent.chat:
        print("   ❌ AI agent failed to initialize. Check API key.")
        print("[ALOA] Returning to Main Menu...")
        return

    # ── Step 5: Chat Loop ──
    print()
    print("  ┌──────────────────────────────────────────────────────┐")
    print(f"  │  🤖 ALOA is ready. Project: {project_name[:30]:<30s} │")
    print("  ├──────────────────────────────────────────────────────┤")
    print("  │  💬 Chat   ─ Ask anything about your code           │")
    print("  │  ▶️  run    ─ Execute & auto-fix errors              │")
    print("  │  ✅ apply  ─ Apply last suggested fix                │")
    print("  │  🚪 exit   ─ Return to main menu                    │")
    print("  └──────────────────────────────────────────────────────┘")
    print()

    while True:
        print("─" * 58)
        try:
            user_input = input("  You ➤ ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input:
            continue

        # ── Exit ──
        if user_input.lower() in ['exit', 'quit', 'back', '0']:
            break

        # ══════════════════════════════════════
        # RUN COMMAND
        # ══════════════════════════════════════
        if user_input.lower() == 'run':
            if not run_command:
                print("  ⚠️  No run command detected.")
                continue

            show_progress(f"🚀 Executing: {run_command}")
            success, stdout, stderr, is_server = agent.run_project()

            if success:
                print(f"  ✅ Project compiled & running successfully!")
                # Show only the essential output (URLs, etc.)
                if stdout.strip():
                    clean_out = clean_terminal_output(stdout)
                    # Extract just URLs and key info
                    for line in clean_out.split('\n'):
                        stripped = line.strip()
                        if any(kw in stripped for kw in ['http://', 'https://', 'Compiled', 'compiled', 'Local:', 'Network:']):
                            print(f"     {stripped}")
            else:
                error_text = stderr.strip() if stderr.strip() else stdout.strip()

                # ── Handle port conflict ──
                port_match = re.search(r'(?:already running on port|EADDRINUSE.*?:)(\s*\d+)', error_text)
                if port_match:
                    port = port_match.group(1).strip()
                    show_progress(f"🔌 Port {port} occupied — clearing")
                    killed, msg = kill_port_process(port)
                    if killed:
                        print(f"  ✅ {msg}")
                        show_progress("🔄 Retrying")
                        time.sleep(1)
                        s2, out2, err2, srv2 = agent.run_project()
                        if s2:
                            print("  ✅ Project running successfully!")
                        else:
                            e2 = err2.strip() if err2.strip() else out2.strip()
                            print(f"  ❌ {extract_error_summary(e2)}")
                    else:
                        print(f"  ❌ {msg}")
                    continue

                # ── Show clean error summary ──
                error_summary = extract_error_summary(error_text)
                print(f"  ❌ Error detected:\n")
                for line in error_summary.split('\n'):
                    print(f"     {line}")
                print()

                # ── Auto-send to AI ──
                show_progress("🧠 AI is analyzing the error")
                ai_response = agent.send_message(
                    f"I just ran the project with '{run_command}' and got this error:\n\n{error_text}\n\nPlease identify the bug and provide the fix.",
                    purpose='fix'
                )

                # Show clean summary (not the full wall of text)
                summary = extract_ai_summary(ai_response)
                print(f"  🤖 {summary}")

                # Check if AI suggested a fix
                fix_file, fix_code = agent.parse_fix_from_response(ai_response)
                if fix_file:
                    show_progress(f"💾 Fixing: {fix_file}")
                    applied, msg = agent.apply_fix()
                    if applied:
                        print(f"  ✅ Fixed! Backup saved as .bak")
                        print(f"  🔄 Type 'run' to verify.")
                    else:
                        print(f"  ❌ Could not apply: {msg}")
                else:
                    print("  ℹ️  No auto-fix available. Try describing the error.")

            continue

        # ══════════════════════════════════════
        # APPLY COMMAND
        # ══════════════════════════════════════
        if user_input.lower() == 'apply':
            if not agent.last_fix_file:
                print("  ⚠️  No pending fix.")
                continue

            print(f"  📄 Fix: {agent.last_fix_file}")
            while True:
                confirm = input("  [Y] Apply  [N] Cancel  [V] View? ").strip().upper()
                if confirm == 'V':
                    print(f"\n  ── {agent.last_fix_file} ──")
                    for line in agent.last_fix_code.split('\n')[:25]:
                        print(f"  │ {line}")
                    if len(agent.last_fix_code.split('\n')) > 25:
                        print(f"  │ ... ({len(agent.last_fix_code.split(chr(10)))} lines total)")
                    print()
                    continue
                elif confirm == 'Y':
                    ok, msg = agent.apply_fix()
                    print(f"  {'✅' if ok else '❌'} {msg}")
                    break
                elif confirm == 'N':
                    print("  🚫 Cancelled.")
                    break
                else:
                    print("  ⚠️  Type Y, N, or V.")
            continue

        # ══════════════════════════════════════
        # VIEW COMMAND
        # ══════════════════════════════════════
        if user_input.lower() == 'view':
            if agent.last_fix_code:
                print(f"\n  ── {agent.last_fix_file} ──")
                for line in agent.last_fix_code.split('\n')[:25]:
                    print(f"  │ {line}")
                if len(agent.last_fix_code.split('\n')) > 25:
                    print(f"  │ ... ({len(agent.last_fix_code.split(chr(10)))} lines total)")
                print()
            else:
                print("  ⚠️  No fix to view.")
            continue

        # ══════════════════════════════════════
        # CHAT — Normal conversation with AI
        # ══════════════════════════════════════
        show_progress("🧠 Thinking", steps=2, delay=0.3)
        ai_response = agent.send_message(user_input)

        # For chat responses, show a cleaner version too
        # But don't strip too much — user asked a question, they want the answer
        print(f"\n  🤖 {ai_response}\n")

        # Check if AI's response contains a fix
        fix_file, fix_code = agent.parse_fix_from_response(ai_response)
        if fix_file:
            print(f"  💡 Fix ready: {fix_file}  →  Type 'apply' to apply.")

    print("[ALOA] Returning to Main Menu...")
