# tools/app_manager.py
import subprocess
from langchain_core.tools import tool

@tool
def install_application(app_name: str) -> str:
    """
    Downloads and installs an application on Windows using Winget.
    Useful when the user asks to download, install, or get a software/app.
    Input should be the name of the application (e.g., 'vscode', 'chrome', 'python').
    """
    print(f"\n[AGENT ACTION] Searching and Installing: {app_name}...")
    
    try:
        # Winget command to install silently and accept agreements
        # --id helps if we knew the exact ID, but name search works mostly
        command = [
            "winget", "install", 
            "-e",  # Exact match koshish karega
            "--id", app_name, # Pehle ID try karega, agar fail hua toh search karega
            "--silent", 
            "--accept-package-agreements", 
            "--accept-source-agreements"
        ]
        
        # Note: Hum search query ko direct pass kar rahe hain. 
        # Better accuracy ke liye hum pehle 'winget search' bhi karwa sakte hain.
        # Simple rakhne ke liye direct install command modify kar rahe hain:
        
        real_command = f'winget install "{app_name}" --silent --accept-package-agreements --accept-source-agreements'
        
        # Subprocess run karna
        result = subprocess.run(
            real_command, 
            shell=True, 
            capture_output=True, 
            text=True
        )

        if result.returncode == 0:
            return f"Success: {app_name} has been successfully installed."
        else:
            # Agar error aaya toh error return karo taaki LLM padh sake
            return f"Error installing {app_name}. Winget Output: {result.stderr or result.stdout}"

    except Exception as e:
        return f"System Error: {str(e)}"