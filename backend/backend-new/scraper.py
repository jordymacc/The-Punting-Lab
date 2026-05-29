import time
import json
import csv
import random
from datetime import datetime
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

class RacingScraper:
    def __init__(self, target_url):
        self.target_url = target_url
        self.options = Options()
        # Headless mode recommended for production, comment out for debugging
        # self.options.add_argument("--headless") 
        self.options.add_argument("--no-sandbox")
        self.options.add_argument("--disable-dev-shm-usage")
        self.options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")
        
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=self.options
        )
        self.wait = WebDriverWait(self.driver, 20)

    def scrape_meeting_data(self):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Navigating to {self.target_url}...")
        try:
            self.driver.get(self.target_url)
            
            # Handle cookie consent or popups if present
            self.handle_popups()

            # Wait for the main odds table to be present
            self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "form-table")))
            
            # Scroll to bottom to trigger lazy loading if necessary
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(2)

            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            meeting_name = soup.select_one(".meeting-header__title").text.strip() if soup.select_one(".meeting-header__title") else "Unknown Meeting"
            race_info = soup.select_one(".race-header__race-number").text.strip() if soup.select_one(".race-header__race-number") else "Race X"
            
            results = []
            
            # Target the horse rows in the form table
            horse_rows = soup.select("tr.form-table__row")
            
            for row in horse_rows:
                try:
                    horse_num = row.select_one(".form-table__horse-number").text.strip()
                    horse_name = row.select_one(".form-table__horse-name").text.strip()
                    jockey_trainer = row.select_one(".form-table__jockey-trainer").text.strip().split('/')
                    jockey = jockey_trainer[0].strip()
                    trainer = jockey_trainer[1].strip() if len(jockey_trainer) > 1 else "N/A"
                    
                    # Live Odds extraction (Win/Place)
                    # Note: Selectors may change based on site updates
                    win_odds = row.select_one(".odds-button--win").text.strip() if row.select_one(".odds-button--win") else "N/A"
                    place_odds = row.select_one(".odds-button--place").text.strip() if row.select_one(".odds-button--place") else "N/A"

                    entry = {
                        "timestamp": datetime.now().isoformat(),
                        "meeting": meeting_name,
                        "race": race_info,
                        "horse_number": horse_num,
                        "horse_name": horse_name,
                        "jockey": jockey,
                        "trainer": trainer,
                        "win_odds": win_odds,
                        "place_odds": place_odds
                    }
                    results.append(entry)
                except Exception as e:
                    continue # Skip malformed rows
            
            return results

        except Exception as e:
            print(f"Error during extraction: {str(e)}")
            return None

    def handle_popups(self):
        # Basic popup handling logic
        try:
            close_buttons = self.driver.find_elements(By.CLASS_NAME, "close-button")
            for btn in close_buttons:
                if btn.is_displayed():
                    btn.click()
        except:
            pass

    def save_to_csv(self, data, filename="racing_odds.csv"):
        keys = data[0].keys()
        file_exists = False
        try:
            with open(filename, 'r') as f:
                file_exists = True
        except FileNotFoundError:
            pass

        with open(filename, 'a', newline='') as output_file:
            dict_writer = csv.DictWriter(output_file, fieldnames=keys)
            if not file_exists:
                dict_writer.writeheader()
            dict_writer.writerows(data)

    def run_monitor(self, interval_seconds=30):
        print(f"Starting monitor on {self.target_url}")
        print(f"Refresh Interval: {interval_seconds}s")
        
        try:
            while True:
                data = self.scrape_meeting_data()
                if data:
                    print(f"Successfully scraped {len(data)} horses. Saving data...")
                    self.save_to_csv(data)
                
                # Randomize sleep to avoid detection
                jitter = random.uniform(-2.0, 5.0)
                sleep_time = max(5, interval_seconds + jitter)
                print(f"Sleeping for {round(sleep_time, 2)}s...")
                time.sleep(sleep_time)
                
        except KeyboardInterrupt:
            print("\nMonitoring stopped by user.")
        finally:
            self.driver.quit()

if __name__ == "__main__":
    # EXAMPLE URL: Replace with actual meeting URL
    URL = "https://www.racing.com/form/2026-05-24/caulfield/race/1"
    
    scraper = RacingScraper(URL)
    scraper.run_monitor(interval_seconds=30)