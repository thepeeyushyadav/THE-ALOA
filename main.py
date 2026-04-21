import sys
import os
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8') 

from dotenv import load_dotenv
load_dotenv()

# --- IMPORT FEATURES ---


from features import feature_1
from features.feature_2 import runner as feature_2_runner
from features.feature_3 import runner as feature_3_runner
from features.feature_4 import runner as feature_4_runner
from features.feature_5 import runner as feature_5_runner
from features.feature_6 import runner as feature_6_runner
from features.feature_7 import runner as feature_7_runner
from features.feature_8 import runner as feature_8_runner
from features.feature_9 import runner as feature_9_runner
from features.feature_10 import runner as feature_10_runner

def main():
    print()
    print("=" * 60)
    print("      THE ALOA - Agentic AI Assistant (v2.0)")
    print("=" * 60)
    print(" System: Online | Phase 2: Intelligence Layer Active")
    print()

    while True:
        print("\n  Available Features:")

        print("  [1] App Manager (Open / Install / Uninstall)")
        print("  [2] System Doctor (Health Check / Junk Clean)")
        print("  [3] Attendance Automator 🎓 (Excel)")
        print("  [4] YouTube Note Generator 📝 (Video -> PDF)")
        print("  [5] Exam Pilot 🤖 (Quiz Automation)")
        print("  [6] Code Healer 🛠️ (Auto Debug & Fix)")
        print("  [7] Cloud Healer ☁️ (GitHub Auto Debug)")
        print("  [8] Auto-Deployer 🚀 (GitHub + Vercel/Render)")
        print("  [9] Resume Engine 📄 (Generate & Analyze)")
        print("  [10] ALOA Radar 📡 (Daily Intel Brief)")
        print("-" * 40)
        print("  [X] Exit")
        print()

        choice = input("  Select Feature: ").strip().upper()

        if choice == "1":
            result = feature_1.run()
            if result == "exit":
                break
        elif choice == "2":
            feature_2_runner.run()
        elif choice == "3":
            feature_3_runner.run()
        elif choice == "4":
            feature_4_runner.run()
        elif choice == "5":
            feature_5_runner.run()
        elif choice == "6":
            feature_6_runner.run()
        elif choice == "7":
            feature_7_runner.run()
        elif choice == "8":
            feature_8_runner.run()
        elif choice == "9":
            feature_9_runner.run()
        elif choice == "10":
            feature_10_runner.run()
        elif choice == "X":
            print("  Goodbye! Shutting down ALOA...")
            break
        else:
            print("  ❌ Invalid choice. Please select a valid option or X.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  [Force Exit] ALOA Terminated by User.")
        sys.exit()
