import tkinter as tk
from tkinter import filedialog
from datetime import datetime
from features.feature_3.core import *

def select_file_dialog():
    """Opens file dialog ON TOP of all other windows."""
    root = tk.Tk()
    root.withdraw() # Main window hide karo
    
    # --- MAGIC LINE: Force Window to Top ---
    root.wm_attributes('-topmost', 1) 
    
    file_path = filedialog.askopenfilename(
        title="Select Attendance Sheet", 
        filetypes=[("Excel Files", "*.xlsx *.xls")]
    )
    
    root.destroy() # Kaam khatam, window destroy
    return file_path

def run():
    print("\n" + "█"*70)
    print(" 🎓 ALOA ATTENDANCE SYSTEM (Auto-Focus Mode)")
    print("█"*70)
    
    # 1. Load File
    print("\n[SYSTEM] 📂 Initiating File Selection...")
    
    # Ab window khud upar aayegi
    path = select_file_dialog()
    
    if not path:
        print("[SYSTEM] ⚠️ Operation Cancelled: No file selected.")
        return

    student_list, msg = load_and_view_data(path)
    if not student_list:
        print(msg)
        return

    # --- DATE SELECTION ---
    today_str = datetime.now().strftime("%d/%m/%Y")
    print(f"\n[SYSTEM] {msg}")
    print("-" * 60)
    
    date_input = input(f"[INPUT] Enter Date (DD/MM/YYYY) [Default: {today_str}]: ").strip()
    if date_input.lower() in ['exit', 'quit', '0', 'back']: return
    if not date_input:
        date_input = today_str 
    
    print(f"[SYSTEM] 📅 Selected Date: {date_input}")
    print("-" * 60)

    # 2. Display List
    for i in range(0, len(student_list), 3):
        print("   ".join(f"{x:<25}" for x in student_list[i:i+3]))
    print("-" * 60)

    # 3. Input Loop
    final_absent_indices = set()
    
    print("\n👉 INSTRUCTION: Enter Last 4 Digits or Name of ABSENTEES.")
    print("   Example: '4001 4005 Smith'")
    print(f"   (Date: {date_input} | Default: All others PRESENT)\n")

    while True:
        user_input = input("\n[INPUT ABSENTEES] >> ").strip()
        
        if user_input.lower() in ['exit', 'quit', '0', 'back']: break
        if not user_input: continue
        
        # Process Input
        names, indices, not_found = process_absentees(user_input)
        
        for idx in indices:
            final_absent_indices.add(idx)

        if names:
            print(f"   🔻 Marked Absent: {', '.join(names)}")
        if not_found:
            print(f"   ⚠️ Not Found: {', '.join(not_found)}")

        # 4. Action Menu
        print(f"\n   Absentees: {len(final_absent_indices)} | Date: {date_input}")
        print("   Options: [C]onfirm & Save | [A]dd More | [R]eset List")
        action = input("   Select Option >> ").lower()

        if action in ['exit', 'quit', '0', 'back']:
            break
        elif action == 'c':
            print(f"\n   [SYSTEM] Saving data for {date_input}...")
            res = save_final_attendance(list(final_absent_indices), date_input)
            print(f"   {res}")
            break
            
        elif action == 'r':
            final_absent_indices.clear()
            print("   🔄 List Reset.")
            
        elif action == 'a':
            continue 
        else:
            print("   ⚠️ Invalid Option.")