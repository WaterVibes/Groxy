import os
import subprocess
import sys
import winreg

def find_chrome_path():
    """Find Chrome installation path"""
    possible_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expanduser("~") + r"\AppData\Local\Google\Chrome\Application\chrome.exe"
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
            
    # Try registry
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe") as key:
            return winreg.QueryValue(key, None)
    except WindowsError:
        pass
        
    return None

def get_chrome_version(chrome_path):
    """Get Chrome version using wmic"""
    try:
        cmd = f'wmic datafile where name="{chrome_path.replace("\\", "\\\\")}" get Version /value'
        output = subprocess.check_output(cmd, shell=True).decode()
        version = output.strip().split("=")[-1]
        return version
    except Exception as e:
        print(f"Error getting Chrome version: {e}")
        return None

def main():
    print("Checking Chrome installation...")
    chrome_path = find_chrome_path()
    
    if chrome_path:
        print(f"Chrome found at: {chrome_path}")
        version = get_chrome_version(chrome_path)
        if version:
            print(f"Chrome version: {version}")
        else:
            print("Could not determine Chrome version")
    else:
        print("Chrome not found in common locations")
        print("Please install Chrome from: https://www.google.com/chrome/")

if __name__ == "__main__":
    main() 