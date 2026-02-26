"""Create a Windows startup shortcut for SKIN1004 AI (full stack)."""
import os
import sys

BAT_PATH = r"C:\Users\DB_PC\Desktop\python_bcj\AI_Agent\start_all.bat"
WORKING_DIR = r"C:\Users\DB_PC\Desktop\python_bcj\AI_Agent"
SHORTCUT_NAME = "SKIN1004 AI"

try:
    import win32com.client
except ImportError:
    print("pywin32 not installed. Creating VBS script instead...")

    startup_dir = os.path.join(
        os.environ["APPDATA"],
        "Microsoft", "Windows", "Start Menu", "Programs", "Startup"
    )

    vbs_path = os.path.join(startup_dir, "start_skin1004_ai.vbs")
    vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.Run """{BAT_PATH}""", 0, False
'''
    with open(vbs_path, "w") as f:
        f.write(vbs_content)

    # Remove old shortcut if exists
    old_vbs = os.path.join(startup_dir, "start_open_webui.vbs")
    if os.path.exists(old_vbs):
        os.remove(old_vbs)
        print(f"Removed old startup script: {old_vbs}")

    print(f"Created VBS startup script: {vbs_path}")
    print("SKIN1004 AI will start silently on Windows boot.")
    sys.exit(0)

startup_dir = os.path.join(
    os.environ["APPDATA"],
    "Microsoft", "Windows", "Start Menu", "Programs", "Startup"
)

shell = win32com.client.Dispatch("WScript.Shell")
shortcut = shell.CreateShortCut(os.path.join(startup_dir, f"{SHORTCUT_NAME}.lnk"))
shortcut.TargetPath = BAT_PATH
shortcut.WorkingDirectory = WORKING_DIR
shortcut.WindowStyle = 7  # Minimized
shortcut.Save()

# Remove old shortcut if exists
old_lnk = os.path.join(startup_dir, "Open WebUI.lnk")
if os.path.exists(old_lnk):
    os.remove(old_lnk)
    print(f"Removed old startup shortcut: {old_lnk}")

print(f"Created startup shortcut in: {startup_dir}")
print("SKIN1004 AI (full stack) will start automatically on Windows boot.")
