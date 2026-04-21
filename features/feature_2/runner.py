import json
import os
import datetime
import psutil
from langchain_groq import ChatGroq
from features.feature_2.core import *
import urllib.request
import urllib.error

class FallbackMessage:
    def __init__(self, content):
        self.content = content

class DualModelChat:
    def __init__(self, groq_chat, temperature):
        self.groq_chat = groq_chat
        self.temperature = temperature
        
    def invoke(self, prompt_text):
        try:
            if self.groq_chat:
                return self.groq_chat.invoke(prompt_text)
        except Exception as e:
            err_str = str(e).lower()
            if "403" in err_str or "429" in err_str or "access denied" in err_str:
                print(f"\n  [System Doctor] Groq API blocked by Network. Falling back to OpenRouter...")
                return self.openrouter_fallback(prompt_text)
            else:
                print(f"\n  [System Doctor] Groq Error: {e}. Falling back to OpenRouter...")
                return self.openrouter_fallback(prompt_text)
        return self.openrouter_fallback(prompt_text)

    def openrouter_fallback(self, prompt_text):
        key = os.environ.get("OPENROUTER_API_KEY", "")
        if not key:
            raise RuntimeError("OPENROUTER_API_KEY missing. Cannot fallback.")
            
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://aloa.local",
            "X-Title": "ALOA System Doctor",
        }
        body = json.dumps({
            "model": "openrouter/auto",
            "messages": [
                {"role": "user", "content": prompt_text}
            ],
            "temperature": self.temperature
        }).encode('utf-8')

        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=body, headers=headers, method='POST'
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                return FallbackMessage(result['choices'][0]['message']['content'])
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode('utf-8')
            raise RuntimeError(f"OpenRouter Fallback Failed (HTTP {e.code}): {err_msg}")
        except Exception as e:
            raise RuntimeError(f"OpenRouter Fallback also failed: {e}")

# ============================================================
# AI Setup — Dual Model Fallback
# ============================================================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

llm_brain = None
llm_writer = None
if GROQ_API_KEY:
    try:
        # Brain: Strict JSON output
        base_brain = ChatGroq(
            model="llama-3.1-8b-instant",
            temperature=0,
            api_key=GROQ_API_KEY
        )
        llm_brain = DualModelChat(base_brain, temperature=0.0)
        # Writer: Slightly creative
        base_writer = ChatGroq(
            model="llama-3.1-8b-instant",
            temperature=0.3,
            api_key=GROQ_API_KEY
        )
        llm_writer = DualModelChat(base_writer, temperature=0.3)
    except Exception as e:
        print(f"[System Doctor] Warning: Groq init failed: {e}")
        llm_brain = DualModelChat(None, temperature=0.0)
        llm_writer = DualModelChat(None, temperature=0.3)
else:
    llm_brain = DualModelChat(None, temperature=0.0)
    llm_writer = DualModelChat(None, temperature=0.3)

# --- 🎨 TACTICAL VISUAL ENGINE (Grid Design) ---

def format_bytes(size):
    """Converts raw bytes to readable GB/MB"""
    power = 2**10
    n = 0
    power_labels = {0: '', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.1f} {power_labels[n]}"

def create_tactical_bar(percent, length=15):
    """Creates the sharp ▰▰▱▱ style bar"""
    filled = int(length * percent // 100)
    bar = "▰" * filled + "▱" * (length - filled)
    return bar

def render_tactical_grid(stats, advice):
    """Renders the Exact User Requested Design."""
    time_now = datetime.datetime.now().strftime("%I:%M %p")  # 12:45 PM format

    cpu_val = stats['cpu_total']
    ram_val = stats['ram_total']

    # Status Logic
    cpu_status = "(Stable)" if cpu_val < 50 else "(Load High) ⚠️"
    ram_status = "(Stable)" if ram_val < 70 else "(Load High) ⚠️"

    print("\n" + "╔" + "═"*60 + "╗")
    print(f"║  ⚡ ALOA SYSTEM OVERWATCH              [ STATUS: ONLINE 🟢 ]  ║")
    print("╚" + "═"*60 + "╝")
    print(f"     🕒 TIME: {time_now}")

    print("\n  [ SYSTEM VITALS ]")
    print(f"  {create_tactical_bar(cpu_val)} CPU : {cpu_val}%  {cpu_status}")
    print(f"  {create_tactical_bar(ram_val)} RAM : {ram_val}%  {ram_status}")

    print("\n  [ TOP RESOURCE CONSUMERS ]")
    print("  " + "─"*60)
    print(f"   {'PID':<7} | {'PROCESS NAME':<21} | {'MEMORY':<8} | {'IMPACT'}")
    print("  " + "─"*60)

    total_ram_bytes = psutil.virtual_memory().total

    for app in stats['top_apps'][:4]:
        name = app['name'].replace(".exe", "").capitalize()[:20]
        pid = str(app['pid'])

        mem_bytes = (app['memory_percent'] / 100) * total_ram_bytes
        mem_str = format_bytes(mem_bytes)

        if mem_bytes > (1024**3):
            impact = "🔥 CRITICAL"
        elif mem_bytes > (500 * 1024**2):
            impact = "🔸 MODERATE"
        else:
            impact = "🔹 NORMAL"

        print(f"   {pid:<7} | {name:<21} | {mem_str:<8} | {impact}")

    print("  " + "─"*60)
    print(f"\n  💡 INTEL:")
    print(f"  {advice.strip()}")
    print("\n")


# --- 🧠 MAIN AGENT LOGIC ---
def run():
    print("\n" + "█"*62)
    print(" ⚡ ALOA INTELLIGENT OS AGENT (vFinal - Tactical Grid)")
    print("█"*62)

    if not GROQ_API_KEY and not os.environ.get("OPENROUTER_API_KEY"):
        print("\n  ⚠️  WARNING: Neither GROQ_API_KEY nor OPENROUTER_API_KEY is set.")
        print("  Get a free key at https://console.groq.com or set OpenRouter.\n")

    while True:
        try:
            user_input = input("[ALOA] >> ").strip()
            if user_input.lower() in ["exit", "back", "0"]:
                break
            if not user_input:
                continue

            # --- STEP 1: DECODE INTENT ---
            intent = user_input.lower()
            if intent in ["check health", "system check", "check my system"]:
                action = "CHECK_HEALTH"
                target = None
            elif intent in ["clean junk", "clean system", "clear junk"]:
                action = "CLEAN_JUNK"
                target = None
            else:
                brain_prompt = (
                    "Role: OS Kernel.\n"
                    "Task: Map input to JSON.\n"
                    "Categories:\n"
                    "1. CHECK_HEALTH (\"check\", \"slow\", \"status\", \"report\", \"health\")\n"
                    "2. KILL_PROCESS (\"kill\", \"stop\", \"band karo\", \"end\") -> Extract 'target'\n"
                    "3. CLEAN_JUNK (\"clean\", \"junk\", \"space\", \"trash\")\n\n"
                    "Output ONLY valid JSON, nothing else. Example: {\"action\": \"CHECK_HEALTH\", \"target\": null}\n\n"
                    f"Input: {user_input}"
                )
    
                try:
                    raw_json = llm_brain.invoke(brain_prompt).content.strip()
                    # Strip markdown code fences if present
                    raw_json = raw_json.replace("```json", "").replace("```", "").strip()
                    data = json.loads(raw_json)
                    action = data.get("action", "UNKNOWN")
                    target = data.get("target")
                except Exception:
                    action = "UNKNOWN"
                    target = None

            # --- STEP 2: EXECUTE ---

            # A. TACTICAL GRID DASHBOARD
            if action == "CHECK_HEALTH":
                print("\n  ⚡ Scanning Kernel...")
                stats = get_detailed_system_stats()

                ram = stats['ram_total']
                heavy_app_name = stats['top_apps'][0]['name'].replace(".exe", "") if stats['top_apps'] else "Unknown"

                if ram > 85:
                    situation = f"CRITICAL: RAM is {ram}%. {heavy_app_name} is using massive memory."
                elif ram > 65:
                    situation = f"HEAVY LOAD: RAM is {ram}%. {heavy_app_name} is the heaviest app."
                else:
                    situation = f"STABLE: RAM is {ram}%. System is running efficiently."

                advice_prompt = (
                    f"SITUATION: {situation}\n"
                    f"USER INPUT: \"{user_input}\"\n\n"
                    "TASK: Reply with ONE single sentence.\n"
                    "RULES:\n"
                    "1. If user speaks English -> Reply in Professional English.\n"
                    "2. If user speaks Hinglish/Hindi -> Reply in Casual Hinglish.\n"
                    "3. NO prefixes like 'Answer:'. Just the sentence."
                )
                advice = llm_writer.invoke(advice_prompt).content
                advice = advice.replace('"', '').split("\n")[0]

                render_tactical_grid(stats, advice)

            # B. KILL PROTOCOL
            elif action == "KILL_PROCESS":
                if target and target != "null":
                    print(f"  ⚠️  SECURITY ALERT: Targeting '{target}'")
                    if input("  Confirm Kill? (y/n): ").lower() == 'y':
                        print(f"  [EXEC] 🔫 {kill_specific_process(target)}")
                else:
                    print("  [ERR] Target Missing. Try 'Kill Chrome'.")

            # C. CLEAN PROTOCOL
            elif action == "CLEAN_JUNK":
                audit = audit_junk_files()
                print(f"\n  🗑️  STORAGE SCAN: {audit['text']} Junk Files Found.")
                if input("  Initiate Purge? (y/n): ").lower() == 'y':
                    print(f"  [EXEC] 🧹 {execute_cleanup()}")

            else:
                print(f"  [LOG] Unknown Directive. Try: 'check health', 'kill chrome', 'clean junk'")

        except Exception as e:
            print(f"System Error: {e}")