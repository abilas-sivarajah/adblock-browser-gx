import os
import sys
import win32com.client

def create_desktop_shortcut():
    shell = win32com.client.Dispatch('WScript.Shell')
    desktop = shell.SpecialFolders('Desktop')  # real desktop, also when redirected (e.g. OneDrive)
    shortcut_path = os.path.join(desktop, 'AdBlock Browser.lnk')

    python_dir = os.path.dirname(sys.executable)
    pythonw = os.path.join(python_dir, 'pythonw.exe')
    if not os.path.exists(pythonw):
        pythonw = sys.executable

    base_dir = os.path.dirname(os.path.abspath(__file__))
    main_script = os.path.join(base_dir, 'main.py')
    icon_path = os.path.join(base_dir, 'assets', 'icon.ico')

    shortcut = shell.CreateShortCut(shortcut_path)
    shortcut.TargetPath = pythonw
    shortcut.Arguments = f'"{main_script}"'
    shortcut.WorkingDirectory = base_dir
    shortcut.IconLocation = f'{icon_path},0'
    shortcut.Description = 'AdBlock Browser mit integriertem Werbeblocker'
    shortcut.Save()

    print(f'Desktop-Verknüpfung erfolgreich erstellt: {shortcut_path}')
    print(f'Icon: {icon_path}')

if __name__ == '__main__':
    create_desktop_shortcut()
