"""
╔══════════════════════════════════════════════════════════════════╗
║  ALOA AUTO-DEPLOYER — Feature 8 Runner (v1.0)                    ║
║  Interactive CLI: Detect → Confirm → Push → Deploy → Live URL    ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import time
import json

from features.feature_8.core import (
    detect_deployment_plan,
    init_and_push_to_github,
    deploy_to_vercel,
    deploy_to_render,
    check_vercel_cli_available,
    ask_deployment_ai,
    generate_render_yaml,
    generate_vercel_json,
    load_deploy_config,
    save_deploy_config,
    mask_token,
    parse_env_file,
    DeploymentPlan,
    DeployResult,
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
MAGENTA = "\033[95m"
BLUE = "\033[94m"
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


def print_big_success(url, platform):
    """Display the final deployment success banner."""
    print()
    cprint("  ╔═══════════════════════════════════════════════════════╗", GREEN)
    cprint("  ║                                                       ║", GREEN)
    cprint("  ║        🎉  DEPLOYMENT SUCCESSFUL!  🎉                ║", GREEN)
    cprint("  ║                                                       ║", GREEN)
    cprint(f"  ║  Platform: {platform.upper():<43s}║", GREEN)
    # Truncate URL if too long for the box
    display_url = url if len(url) <= 45 else url[:42] + "..."
    cprint(f"  ║  🌐 {display_url:<49s}║", GREEN)
    cprint("  ║                                                       ║", GREEN)
    cprint("  ╚═══════════════════════════════════════════════════════╝", GREEN)
    print()


# ──────────────────────────────────────────────────────────
# FOLDER SELECTION
# ──────────────────────────────────────────────────────────

def _open_folder_dialog() -> str:
    """Try to open a native OS folder-picker dialog."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        root.geometry("+0+0")
        root.update()

        folder = filedialog.askdirectory(
            title="📂 Select Project Directory to Deploy",
            parent=root,
        )
        root.destroy()
        return folder if folder else ""
    except Exception:
        return ""


def select_project_folder() -> str:
    """Interactive folder selection."""
    cprint("\n  [STEP 0]  Select the project you want to deploy:", CYAN + BOLD)
    cprint("            (Opening folder browser...)", DIM)

    chosen = _open_folder_dialog()
    if chosen and os.path.isdir(chosen):
        cprint(f"   ✅ Selected: {chosen}", GREEN)
        return chosen

    # Fallback: manual text input
    cprint("   [!] Folder browser unavailable — enter path manually:", YELLOW)
    while True:
        path = input("   > ").strip().strip('"').strip("'")
        if os.path.isdir(path):
            return path
        cprint(f"   [!] '{path}' is not a valid directory. Try again.", RED)


# ──────────────────────────────────────────────────────────
# CREDENTIALS MANAGEMENT
# ──────────────────────────────────────────────────────────

def get_credentials(deploy_target: str) -> dict:
    """
    Interactive credential collection.
    Only asks for tokens relevant to the deployment target.
    """
    saved = load_deploy_config()
    config = {}

    # Always need GitHub PAT
    if saved.get("github_pat"):
        cprint(f"\n   🔑 Saved GitHub PAT: {mask_token(saved['github_pat'])}", DIM)
        cprint(f"   Press {GREEN}Enter{RESET} to use saved, or type {YELLOW}'n'{RESET} to change")
        choice = input("   ➤ ").strip().lower()
        if choice != 'n':
            config["github_pat"] = saved["github_pat"]
        else:
            config["github_pat"] = _ask_for_token("GitHub Personal Access Token (PAT)")
    else:
        cprint("\n   ℹ️  GitHub PAT is required to push your code.", YELLOW)
        cprint("      Get one free at: github.com → Settings → Developer Settings → Personal Access Tokens", DIM)
        config["github_pat"] = _ask_for_token("GitHub PAT")

    if not config["github_pat"]:
        return {}

    # Vercel token (if needed)
    if deploy_target in ("vercel", "both"):
        if saved.get("vercel_token"):
            cprint(f"   🔑 Saved Vercel Token: {mask_token(saved['vercel_token'])}", DIM)
            cprint(f"   Press {GREEN}Enter{RESET} to use saved, or type {YELLOW}'n'{RESET} to change")
            choice = input("   ➤ ").strip().lower()
            if choice != 'n':
                config["vercel_token"] = saved["vercel_token"]
            else:
                config["vercel_token"] = _ask_for_token("Vercel Token")
        else:
            cprint("\n   ℹ️  Vercel Token needed for frontend deployment.", YELLOW)
            cprint("      Get one free at: vercel.com → Settings → Tokens", DIM)
            config["vercel_token"] = _ask_for_token("Vercel Token")

        if not config.get("vercel_token"):
            return {}

    # Render API key (if needed)
    if deploy_target in ("render", "both"):
        if saved.get("render_key"):
            cprint(f"   🔑 Saved Render API Key: {mask_token(saved['render_key'])}", DIM)
            cprint(f"   Press {GREEN}Enter{RESET} to use saved, or type {YELLOW}'n'{RESET} to change")
            choice = input("   ➤ ").strip().lower()
            if choice != 'n':
                config["render_key"] = saved["render_key"]
            else:
                config["render_key"] = _ask_for_token("Render API Key")
        else:
            cprint("\n   ℹ️  Render API Key needed for backend deployment.", YELLOW)
            cprint("      Get one free at: render.com → Account Settings → API Keys", DIM)
            config["render_key"] = _ask_for_token("Render API Key")

        if not config.get("render_key"):
            return {}

    # Save for next time
    save_deploy_config({**saved, **config})
    return config


def _ask_for_token(label: str) -> str:
    """Prompt for a token with nice formatting."""
    token = input(f"   🔑 Enter {label}: ").strip()
    return token


# ──────────────────────────────────────────────────────────
# DEPLOYMENT PLAN DISPLAY
# ──────────────────────────────────────────────────────────

def display_deployment_plan(plan: DeploymentPlan):
    """Show the deployment plan to the user for confirmation."""
    print()
    print_divider()

    lines = [
        "📋 Deployment Plan",
        "─" * 40,
        f"Framework  : {plan.framework_display}",
    ]

    if plan.is_fullstack:
        lines.append(f"Frontend   : {plan.frontend_path}/ → Vercel")
        lines.append(f"Backend    : {plan.backend_path}/ → Render")
    else:
        target_display = {
            "vercel": "☁️  Vercel (Frontend Cloud)",
            "render": "🖥️  Render (Backend Cloud)",
            "both":   "☁️  Vercel + 🖥️  Render",
        }
        lines.append(f"Target     : {target_display.get(plan.deploy_target, plan.deploy_target)}")

    lines.append(f"Project    : {plan.project_name}")
    lines.append("")
    lines.append("Steps:")
    lines.append("  1️⃣  Push code to GitHub")

    if plan.deploy_target in ("vercel", "both"):
        lines.append("  2️⃣  Deploy frontend to Vercel")
    if plan.deploy_target in ("render", "both"):
        step_num = "3️⃣" if plan.deploy_target == "both" else "2️⃣"
        lines.append(f"  {step_num}  Deploy backend to Render")

    lines.append("  🔗  Return live URL(s)")

    print_boxed(lines, CYAN)


# ──────────────────────────────────────────────────────────
# DEPLOYMENT EXECUTION ENGINE
# ──────────────────────────────────────────────────────────

def execute_deployment(
    folder_path: str,
    plan: DeploymentPlan,
    credentials: dict,
) -> list:
    """
    Executes the full deployment pipeline step by step.
    Returns a list of DeployResult objects.
    """
    results = []
    total_steps = 1  # GitHub push is always step 1
    if plan.deploy_target in ("vercel", "both"):
        total_steps += 1
    if plan.deploy_target in ("render", "both"):
        total_steps += 1

    current_step = 0

    # ══════════════════════════════════════════
    # STEP 1: Push to GitHub
    # ══════════════════════════════════════════
    current_step += 1
    cprint(f"\n  [{current_step}/{total_steps}] ⬆️  Pushing to GitHub...", CYAN + BOLD)
    show_progress("📤 Creating repository and pushing code", steps=4, delay=0.4)

    github_result = init_and_push_to_github(
        folder_path=folder_path,
        pat=credentials["github_pat"],
        repo_name=plan.project_name,
    )
    results.append(github_result)

    if github_result.success:
        cprint(f"   ✅ {github_result.message}", GREEN)
    else:
        cprint(f"   ❌ GitHub push failed: {github_result.error}", RED)
        cprint("   💡 Check your PAT has 'repo' scope enabled on GitHub.", YELLOW)
        return results

    # ══════════════════════════════════════════
    # STEP 2: Deploy to Vercel (if applicable)
    # ══════════════════════════════════════════
    if plan.deploy_target in ("vercel", "both"):
        current_step += 1
        cprint(f"\n  [{current_step}/{total_steps}] 🚀 Deploying to Vercel...", CYAN + BOLD)

        # Determine the folder to deploy
        deploy_folder = folder_path
        if plan.is_fullstack and plan.frontend_path:
            deploy_folder = os.path.join(folder_path, plan.frontend_path)
            cprint(f"   📂 Deploying frontend from: {plan.frontend_path}/", DIM)

        # Check if Vercel CLI is available
        if check_vercel_cli_available():
            cprint("   ✅ Vercel CLI detected — using fast local deploy", DIM)
        else:
            cprint("   ℹ️  Vercel CLI not found — using REST API (slower)", DIM)

        show_progress("🔧 Building and deploying to Vercel", steps=6, delay=0.5)

        # Auto-generate vercel.json if not present
        vercel_json_path = os.path.join(deploy_folder, "vercel.json")
        if not os.path.isfile(vercel_json_path):
            try:
                vercel_config = generate_vercel_json(plan)
                with open(vercel_json_path, 'w', encoding='utf-8') as f:
                    f.write(vercel_config)
                cprint("   📝 Auto-generated vercel.json", DIM)
            except Exception:
                pass  # Non-critical

        # Get GitHub repo URL from earlier push
        github_url_for_vercel = ""
        for r in results:
            if r.platform == "github" and r.success:
                github_url_for_vercel = r.url
                break

        vercel_result = deploy_to_vercel(
            folder_path=deploy_folder,
            token=credentials.get("vercel_token", ""),
            project_name=plan.project_name,
            framework=plan.framework,
            github_repo_url=github_url_for_vercel,
            env_vars=plan.env_vars,
        )
        results.append(vercel_result)

        if vercel_result.success:
            cprint(f"   ✅ {vercel_result.message}", GREEN)

            # If deployed via API (not CLI), trigger build via git push
            if not check_vercel_cli_available():
                cprint("   📤 Triggering Vercel build via git push...", DIM)
                from features.feature_8.core import _trigger_deploy_via_git_push
                _trigger_deploy_via_git_push(folder_path)
                cprint("   ✅ Build triggered! Site will be live in 1-3 minutes.", GREEN)
        else:
            cprint(f"   ❌ Vercel deployment failed: {vercel_result.error}", RED)
            # Ask AI for help
            cprint("   🤖 Asking AI advisor for troubleshooting...", YELLOW)
            advice = ask_deployment_ai(
                f"Vercel deployment failed with error: {vercel_result.error}\n"
                f"Project framework: {plan.framework_display}\n"
                f"What should the user check or fix?"
            )
            cprint(f"   💡 {advice[:300]}", DIM)

    # ══════════════════════════════════════════
    # STEP 3: Deploy to Render (if applicable)
    # ══════════════════════════════════════════
    if plan.deploy_target in ("render", "both"):
        current_step += 1
        cprint(f"\n  [{current_step}/{total_steps}] 🖥️  Deploying to Render...", CYAN + BOLD)

        # Auto-generate render.yaml if not present
        render_yaml_path = os.path.join(folder_path, "render.yaml")
        if not os.path.isfile(render_yaml_path):
            try:
                render_config = generate_render_yaml(plan)
                with open(render_yaml_path, 'w', encoding='utf-8') as f:
                    f.write(render_config)
                cprint("   📝 Auto-generated render.yaml", DIM)
            except Exception:
                pass

        show_progress("🔧 Creating Render web service", steps=5, delay=0.5)

        # We need the GitHub repo URL for Render
        github_repo_url = ""
        for r in results:
            if r.platform == "github" and r.success:
                github_repo_url = r.url
                break

        if not github_repo_url:
            cprint("   ❌ Cannot deploy to Render without a GitHub repo URL.", RED)
        else:
            render_service_name = plan.project_name
            if plan.is_fullstack:
                render_service_name = f"{plan.project_name}-api"

            render_result = deploy_to_render(
                github_repo_url=github_repo_url,
                api_key=credentials.get("render_key", ""),
                service_name=render_service_name,
                plan=plan,
            )
            results.append(render_result)

            if render_result.success:
                cprint(f"   ✅ {render_result.message}", GREEN)
            else:
                cprint(f"   ❌ Render deployment failed: {render_result.error}", RED)
                cprint("   🤖 Asking AI advisor for troubleshooting...", YELLOW)
                advice = ask_deployment_ai(
                    f"Render deployment failed with error: {render_result.error}\n"
                    f"Project framework: {plan.framework_display}\n"
                    f"What should the user check or fix?"
                )
                cprint(f"   💡 {advice[:300]}", DIM)

    return results


# ──────────────────────────────────────────────────────────
# MAIN RUNNER
# ──────────────────────────────────────────────────────────

def run():
    print()
    cprint("  ╔══════════════════════════════════════════════════════════╗", CYAN)
    cprint("  ║       🚀  ALOA AUTO-DEPLOYER Advanced v7.3                      ║", CYAN)
    cprint("  ║       Detect → Push → Deploy → Live URL                 ║", CYAN)
    cprint("  ╚══════════════════════════════════════════════════════════╝", CYAN)
    print()

    # ── 1. Select Project Folder ──
    folder_path = select_project_folder()

    # ── 2. Detect Framework & Build Deployment Plan ──
    print()
    show_progress("🔍 Analyzing project structure", steps=3, delay=0.3)
    plan = detect_deployment_plan(folder_path)

    if plan.framework == "unknown":
        cprint("   ⚠️  Could not auto-detect your project framework.", YELLOW)
        cprint("   🤖 Consulting AI advisor...", DIM)

        # List files for AI context
        files_list = []
        try:
            for item in os.listdir(folder_path):
                files_list.append(item)
        except Exception:
            pass

        advice = ask_deployment_ai(
            f"I have a project with these files in root: {files_list[:30]}\n"
            f"What framework is this? Should it deploy to Vercel (frontend) or Render (backend)?\n"
            f"Reply concisely: framework name and recommended platform."
        )
        cprint(f"   💡 AI says: {advice[:200]}", DIM)
        print()

        cprint("   Where should we deploy?", YELLOW)
        cprint("   [1] Vercel (frontend / static site)", "")
        cprint("   [2] Render (backend / API server)", "")
        cprint("   [0] Cancel and return", "")
        choice = input("   ➤ ").strip()

        if choice == "1":
            plan.deploy_target = "vercel"
        elif choice == "2":
            plan.deploy_target = "render"
        else:
            cprint("   ℹ️  Cancelled. Returning to Main Menu.", DIM)
            return

    # ── 3. Show Deployment Plan ──
    display_deployment_plan(plan)

    # ── 4. Confirmation ──
    print()
    cprint(f"  Proceed with this deployment? [{GREEN}Y{RESET}/{RED}n{RESET}]", "")
    confirm = input("  ➤ ").strip().lower()
    if confirm in ('n', 'no'):
        cprint("   ℹ️  Deployment cancelled. Returning to Main Menu.", DIM)
        return

    # Allow user to customize project name
    print()
    cprint(f"  Project name: {BOLD}{plan.project_name}{RESET}", "")
    cprint(f"  Press {GREEN}Enter{RESET} to keep, or type a new name:", "")
    custom_name = input("  ➤ ").strip()
    if custom_name:
        plan.project_name = re.sub(r'[^a-zA-Z0-9-]', '-', custom_name).lower().strip('-')
        cprint(f"   ✅ Project name set to: {plan.project_name}", GREEN)

    # ── 5. Collect Credentials ──
    print()
    cprint("  [CREDENTIALS]  Setting up API access...", CYAN + BOLD)
    credentials = get_credentials(plan.deploy_target)

    if not credentials:
        cprint("   ℹ️  Missing credentials. Returning to Main Menu.", YELLOW)
        return

    # ── 5.5  Detect & Configure Environment Variables ──
    print()
    cprint("  [ENV VARS]  Checking for environment variables...", CYAN + BOLD)
    detected_env = parse_env_file(folder_path)

    if detected_env:
        cprint(f"   📄 Found {len(detected_env)} env variable(s) in .env file:", GREEN)
        print()
        for i, (key, value) in enumerate(detected_env.items(), 1):
            # Mask sensitive values (show first 4 chars only)
            if len(value) > 8:
                masked = value[:4] + "*" * (len(value) - 4)
            else:
                masked = "****"
            cprint(f"      {i}. {key} = {masked}", DIM)

        print()
        cprint(f"  Include these env variables in deployment? [{GREEN}Y{RESET}/{RED}n{RESET}]", "")
        include_env = input("  ➤ ").strip().lower()

        if include_env not in ('n', 'no'):
            plan.env_vars = detected_env
            cprint(f"   ✅ {len(detected_env)} env variable(s) will be deployed.", GREEN)
        else:
            cprint("   ℹ️  Env variables skipped.", DIM)
    else:
        cprint("   ℹ️  No .env file found. Skipping.", DIM)

    # Ask if user wants to add any extra env variables manually
    cprint(f"\n  Add custom env variables? [{GREEN}y{RESET}/{RED}N{RESET}]", "")
    add_custom = input("  ➤ ").strip().lower()

    if add_custom in ('y', 'yes'):
        cprint("   Type KEY=VALUE pairs (one per line, empty line to finish):", DIM)
        while True:
            entry = input("      ➤ ").strip()
            if not entry:
                break
            if '=' in entry:
                key, _, value = entry.partition('=')
                plan.env_vars[key.strip()] = value.strip()
                cprint(f"      ✅ Added: {key.strip()}", GREEN)
            else:
                cprint(f"      ⚠️  Invalid format. Use KEY=VALUE", YELLOW)

    if plan.env_vars:
        cprint(f"\n   📦 Total env variables for deployment: {len(plan.env_vars)}", CYAN)

    # ── 6. Execute Deployment ──
    print()
    print_divider()
    cprint("  🚀 DEPLOYMENT STARTING...", BOLD + GREEN)
    print_divider()

    results = execute_deployment(folder_path, plan, credentials)

    # ── 7. Final Summary ──
    print()
    print_divider()
    cprint("  📊 DEPLOYMENT SUMMARY", BOLD)
    print_divider()
    print()

    all_success = True
    for r in results:
        icon = "✅" if r.success else "❌"
        platform_display = {
            "github": "GitHub",
            "vercel": "Vercel",
            "render": "Render",
        }.get(r.platform, r.platform)

        if r.success:
            cprint(f"   {icon} {platform_display:<10s} → {r.url}", GREEN)
        else:
            cprint(f"   {icon} {platform_display:<10s} → {r.error[:60]}", RED)
            all_success = False

    # Show the big success banner for live deployment URLs
    if all_success:
        for r in results:
            if r.platform in ("vercel", "render") and r.success and r.url:
                print_big_success(r.url, r.platform)
    else:
        print()
        cprint("  ⚠️  Some deployment steps failed. Check the errors above.", YELLOW)
        cprint("  💡 You can re-run this feature after fixing the issues.", DIM)

    print()
    cprint("  [ALOA] Returning to Main Menu...\n", DIM)


# Import re at top level for project name sanitization
import re
