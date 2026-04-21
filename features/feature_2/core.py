import os
import shutil
import tempfile
import psutil
import subprocess
import urllib.parse

# --- 1. SENSORS (Jasoos) ---

def get_detailed_system_stats():
    """Deep scan for specific heavy apps."""
    try:
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory().percent
        
        # Top 5 Memory Hogs (Detailed)
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'memory_percent', 'cpu_percent']):
            try:
                pinfo = proc.info
                processes.append(pinfo)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # Sort by Memory usage
        sorted_procs = sorted(processes, key=lambda x: x['memory_percent'], reverse=True)[:5]
        
        return {
            "cpu_total": cpu,
            "ram_total": ram,
            "top_apps": sorted_procs # Returns list of dicts with PID and Name
        }
    except Exception as e:
        return f"Error: {e}"

def get_startup_apps():
    """Startup apps fetcher."""
    try:
        cmd = "Get-CimInstance Win32_StartupCommand | Select-Object Name"
        result = subprocess.run(["powershell", "-Command", cmd], capture_output=True, text=True)
        apps = [line.strip() for line in result.stdout.strip().split('\n')[2:] if line.strip()]
        return apps[:10] if apps else ["None"]
    except: return ["Error"]

def audit_junk_files():
    """Junk auditor."""
    temp_path = tempfile.gettempdir()
    temp_size = sum(os.path.getsize(os.path.join(p, f)) for p, d, files in os.walk(temp_path) for f in files if os.path.exists(os.path.join(p, f)))
    return {"text": f"{round(temp_size / (1024**2), 2)} MB"}

# --- 2. ACTUATORS (Hathiyar/Action Takers) ---

def execute_cleanup():
    shutil.rmtree(tempfile.gettempdir(), ignore_errors=True)
    subprocess.run(["powershell", "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"], shell=True)
    return "SUCCESS: System Junk Purged."

def kill_specific_process(app_name):
    """
    OS MANIPULATION: Finds and kills a process by partial name.
    Example: 'chrome' will kill 'chrome.exe'
    """
    killed_count = 0
    try:
        for proc in psutil.process_iter(['pid', 'name']):
            # Case insensitive match
            if app_name.lower() in proc.info['name'].lower():
                try:
                    proc.kill()
                    killed_count += 1
                except psutil.AccessDenied:
                    return f"❌ Access Denied: Cannot kill {proc.info['name']} (System Process)."
        
        if killed_count > 0:
            return f"✅ SUCCESS: Terminated {killed_count} instance(s) of '{app_name}'."
        else:
            return f"⚠️ Process '{app_name}' not found running."
    except Exception as e:
        return f"Error executing kill: {e}"

def open_startup_settings():
    os.system("start ms-settings:startupapps")
    return "Opened Settings."