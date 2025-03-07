from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import time
import os
import requests
import zipfile
import io

def download_chromedriver(version="131.0.6778.265"):
    """Download Chrome driver manually"""
    try:
        print(f"Downloading Chrome driver version {version}...")
        base_url = "https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing"
        platform = "win64"  # Windows 64-bit
        
        # Create drivers directory if it doesn't exist
        os.makedirs("drivers", exist_ok=True)
        
        # Download URL
        url = f"{base_url}/{version}/{platform}/chromedriver-{platform}.zip"
        print(f"Download URL: {url}")
        
        # Download the file
        response = requests.get(url)
        if response.status_code != 200:
            raise Exception(f"Failed to download Chrome driver: {response.status_code}")
        
        # Extract the zip file
        with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
            zip_file.extractall("drivers")
        
        driver_path = os.path.join("drivers", "chromedriver-win64", "chromedriver.exe")
        if not os.path.exists(driver_path):
            raise Exception("Chrome driver not found after extraction")
            
        print(f"Chrome driver downloaded to: {driver_path}")
        return driver_path
        
    except Exception as e:
        print(f"Error downloading Chrome driver: {e}")
        return None

def test_selenium():
    try:
        print("Setting up Chrome options...")
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--disable-popup-blocking")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
        
        # Set Chrome binary location
        chrome_path = r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
        if os.path.exists(chrome_path):
            chrome_options.binary_location = chrome_path
            print(f"Using Chrome from: {chrome_path}")
        
        print("Setting up Chrome driver...")
        driver_path = download_chromedriver()
        if not driver_path:
            raise Exception("Failed to download Chrome driver")
        
        print("Creating Chrome driver...")
        service = Service(driver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Set page load timeout
        driver.set_page_load_timeout(30)
        
        # Execute CDP commands to prevent detection
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            """
        })
        
        print("Testing with a simple website...")
        driver.get("https://example.com")
        print(f"Page title: {driver.title}")
        
        print("Testing with Dutchie website...")
        driver.get("https://dutchie.com/dispensary/mission-catonsville")
        time.sleep(5)
        print(f"Page source length: {len(driver.page_source)}")
        print(f"Current URL: {driver.current_url}")
        
        # Save page source for inspection
        with open("dutchie_page.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print("Saved page source to dutchie_page.html")
        
        driver.quit()
        print("Test completed successfully!")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        if "driver" in locals():
            driver.quit()
        raise

if __name__ == "__main__":
    test_selenium() 