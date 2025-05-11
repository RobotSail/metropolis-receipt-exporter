import os
import json
import time
import argparse
import requests
import base64
from datetime import datetime
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, NoSuchWindowException, TimeoutException
import dotenv

dotenv.load_dotenv()

def parse_args():
    parser = argparse.ArgumentParser(description='Download Metropolis parking receipts for a specific month')
    parser.add_argument('month', help='Month to download receipts for (e.g., "march", "april")')
    parser.add_argument('--browser', choices=['chrome', 'firefox'], default='chrome', 
                      help='Browser to use for automation (default: chrome)')
    parser.add_argument('--force-login', action='store_true', 
                       help='Force manual login even if cookies exist')
    parser.add_argument('--output-dir', '-o', default='~/Documents/parking-receipts',
                       help='Root directory to store receipts (default: ~/Documents/parking-receipts)')
    return parser.parse_args()

def setup_driver(browser_type):
    if browser_type == 'chrome':
        options = Options()
        options.add_argument("--window-size=1920,1080")
        driver = webdriver.Chrome(options=options)
    else:  # firefox
        options = FirefoxOptions()
        driver = webdriver.Firefox(options=options)
    
    return driver

def wait_for_manual_login(driver):
    print("Starting browser for login...")
    
    # Try to load cookies first if they exist
    cookies_file = 'metropolis_cookies.json'
    if os.path.exists(cookies_file):
        try:
            with open(cookies_file, 'r') as f:
                cookies = json.load(f)
            
            # Navigate to a basic page first before adding cookies
            driver.get("https://app.metropolis.io")
            
            # Add all cookies
            for cookie in cookies:
                try:
                    driver.add_cookie(cookie)
                except Exception as e:
                    print(f"Warning: Could not add cookie {cookie.get('name')}: {e}")
            
            # Navigate to dashboard to check if login works
            driver.get("https://app.metropolis.io/dashboard")
            time.sleep(3)
            
            # If we're still on the dashboard, cookies worked
            if "dashboard" in driver.current_url:
                print("Login successful using saved cookies!")
                return next((c['value'] for c in cookies if c['name'] == 'METROPOLIS'), None)
        except Exception as e:
            print(f"Error loading cookies: {e}")
    
    # If we get here, cookies didn't work or don't exist, so go to sign-in
    driver.get("https://app.metropolis.io/sign-in")
    
    print("\n========= MANUAL LOGIN REQUIRED =========")
    print("Please enter your phone number and proceed to verification.")
    print("The script will detect when you've successfully logged in.")
    print("==========================================\n")
    
    # First wait for redirection to dashboard or history page
    max_wait_time = 300  # 5 minutes
    start_time = time.time()
    
    # Wait for successful login (dashboard or history page)
    while True:
        current_url = driver.current_url
        
        # If we're on the dashboard or history page, login is complete
        if "dashboard" in current_url or "history" in current_url:
            print("Login successful!")
            break
            
        # Check for timeout
        if time.time() - start_time > max_wait_time:
            print("Timeout waiting for login. Please try again.")
            return None
            
        # Brief pause to avoid excessive CPU usage
        time.sleep(1)
    
    # Get all cookies
    cookies = driver.get_cookies()
    
    # Save full cookies to file for future use, merging with existing cookies
    cookies_file = 'metropolis_cookies.json'
    existing_cookies = []
    
    # Load existing cookies if file exists
    if os.path.exists(cookies_file):
        try:
            with open(cookies_file, 'r') as f:
                existing_cookies = json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: Could not parse existing cookies file, will create new one")
    
    # Create a dictionary of existing cookies by name and domain for easy lookup
    existing_cookie_dict = {(c['name'], c.get('domain', '')): c for c in existing_cookies}
    
    # Merge cookies, updating only newer ones
    for cookie in cookies:
        key = (cookie['name'], cookie.get('domain', ''))
        existing_cookie_dict[key] = cookie
    
    # Convert back to list
    merged_cookies = list(existing_cookie_dict.values())
    
    # Save merged cookies
    with open(cookies_file, 'w') as f:
        json.dump(merged_cookies, f, indent=4)
    
    print(f"Cookies merged and saved to {cookies_file} for future use")
    # Extract just the METROPOLIS cookie
    metropolis_cookie = None
    for cookie in merged_cookies:
        if cookie['name'] == 'METROPOLIS':
            metropolis_cookie = cookie['value']
            break
    
    if not metropolis_cookie:
        print("ERROR: Could not find METROPOLIS cookie after login")
        return None
    
    return metropolis_cookie


def get_visit_history(metropolis_cookie):
    headers = {
        "content-type": "application/json",
        "cookie": f"METROPOLIS={metropolis_cookie}"
    }
    
    try:
        response = requests.get(
            "https://site.metropolis.io/api/customer/visits/history",
            headers=headers
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error fetching visit history: {response.status_code}")
            print(response.text)
            return None
    except Exception as e:
        print(f"Exception when fetching visit history: {e}")
        return None



def filter_visits_by_month(visit_data, target_month):
    if not visit_data or not visit_data.get('success'):
        return []
    
    target_month = target_month.lower()
    month_mapping = {
        'january': 1, 'february': 2, 'march': 3, 'april': 4,
        'may': 5, 'june': 6, 'july': 7, 'august': 8,
        'september': 9, 'october': 10, 'november': 11, 'december': 12
    }
    
    if target_month not in month_mapping:
        print(f"Invalid month: {target_month}")
        return []
    
    target_month_num = month_mapping[target_month]
    filtered_visits = []
    
    for visit in visit_data['data']['visits']:
        # Convert timestamp to datetime
        start_time = datetime.fromtimestamp(visit['startAt'] / 1000)
        if start_time.month == target_month_num:
            filtered_visits.append(visit)
    
    return filtered_visits


def save_receipt_as_pdf(driver, visit, output_dir):
    # Handle different visit data formats (API vs browser extraction)
    if isinstance(visit, dict) and 'uuid' in visit:
        uuid = visit['uuid']
        
        # If visit is from API
        if 'startAt' in visit and 'totalPrice' in visit and 'site' in visit:
            visit_date = datetime.fromtimestamp(visit['startAt'] / 1000)
            formatted_date = visit_date.strftime('%Y-%m-%d')
            amount = visit['totalPrice']
            site_name = visit['site']['name'].replace('/', '-').replace('\\', '-')
            filename = f"{formatted_date}_{site_name}_{amount:.2f}.pdf"
        # If visit is from browser extraction
        elif 'date' in visit and 'price' in visit:
            # Try to convert browser-extracted date to a standard format
            try:
                date_obj = datetime.strptime(visit['date'], '%b %d, %Y')
                formatted_date = date_obj.strftime('%Y-%m-%d')
            except:
                # If date parsing fails, use current date
                formatted_date = datetime.now().strftime('%Y-%m-%d')
            
            # Clean up price
            amount = visit.get('price', '').replace('$', '').strip()
            filename = f"{formatted_date}_{amount}.pdf"
        else:
            # Generic filename with UUID as fallback
            filename = f"receipt_{uuid}.pdf"
    else:
        # If visit is just a string UUID
        uuid = visit
        filename = f"receipt_{uuid}.pdf"
    
    filepath = os.path.join(output_dir, filename)
    
    # Check if file already exists
    if os.path.exists(filepath):
        print(f"Receipt already exists: {filename}")
        return
    
    # Navigate to receipt page
    receipt_url = f"https://app.metropolis.io/visit/{uuid}"
    driver.get(receipt_url)
    
    # Wait for page to load
    time.sleep(3)
    
    # Use print functionality to save as PDF
    print(f"Saving receipt: {filename}")
    
    try:
        # Set up PDF printing parameters
        print_options = {
            'landscape': False,
            'displayHeaderFooter': False,
            'printBackground': True,
            'preferCSSPageSize': True,
        }
        
        # Create PDF using Chrome's DevTools Protocol
        pdf = driver.execute_cdp_cmd("Page.printToPDF", print_options)
        
        # Save the PDF - Fix the base64 decoding
        with open(filepath, "wb") as f:
            f.write(base64.b64decode(pdf["data"]))
        
        print(f"Saved receipt to {filepath}")
    except Exception as e:
        print(f"Error saving PDF: {e}")
    
    # Add a small delay between requests
    time.sleep(1)

def main():
    args = parse_args()
    target_month = args.month.lower()
    
    # Use the specified output directory
    base_output_dir = os.path.expanduser(args.output_dir)
    output_dir = os.path.join(base_output_dir, target_month)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Setup browser for manual login
    driver = setup_driver(args.browser)
    try:
        print("Manual login required.")
        metropolis_cookie = wait_for_manual_login(driver)

        assert metropolis_cookie is not None
        
        
        print("Fetching visit history from API...")
        visit_data = get_visit_history(metropolis_cookie)
        
        if not visit_data or not visit_data.get('success'):
            print('failed to get visit history')
            return

        # API method worked
        print("Successfully retrieved visit data from API.")
            
        # Filter visits for the target month
        filtered_visits = filter_visits_by_month(visit_data, target_month)
            
        if not filtered_visits:
            print(f"No visits found for {target_month}")
            return
            
        print(f"Found {len(filtered_visits)} visits for {target_month}")
            
        # Save each receipt as PDF
        for visit in filtered_visits:
            save_receipt_as_pdf(driver, visit, output_dir)
            
                
        print(f"All receipts saved to {output_dir}")
        
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
    
