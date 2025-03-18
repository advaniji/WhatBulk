import random
import time
import pandas as pd
import urllib
import os
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

def ensure_chrome_profile_dir(profile_dir):
    if not os.path.exists(profile_dir):
        try:
            os.makedirs(profile_dir)
            print(f"Created directory: {profile_dir}")
        except Exception as e:
            raise PermissionError(f"Unable to create directory {profile_dir}: {e}")
    if not os.access(profile_dir, os.W_OK):
        raise PermissionError(f"Directory {profile_dir} is not writable. Please check permissions.")

class Whatsapp:
    def __init__(self, message_file='message.txt'):
        self.message_template = self.load_message_template(message_file)
        self.driver = None
        self.is_driver_available = False
        logging.basicConfig(filename='whatsapp.log', level=logging.INFO,
                            format='%(asctime)s - %(levelname)s - %(message)s')
        print("Whatsapp instance created.")
    
    def load_message_template(self, file_name):
        if os.path.exists(file_name):
            with open(file_name, 'r', encoding='utf-8') as f:
                template = f.read().strip()
                print(f"Loaded message template from {file_name}.")
                return template
        else:
            error_msg = f"Message file {file_name} not found. Using default message."
            logging.error(error_msg)
            print(error_msg)
            return "Hello {first_name}, this is a default message."
    
    def format_phone_number(self, number):
        number = str(number).strip().replace(" ", "")
        if number.startswith('+'):
            return number
        if number.startswith('0'):
            number = number.lstrip('0')
        return f"+91{number}"
    
    def extract_greeting_name(self, full_name):
        if not isinstance(full_name, str) or not full_name.strip():
            return "there"
        tokens = full_name.strip().split()
        if len(tokens) == 0:
            return "there"
        # Use the first token unless it's only 1-2 characters; then use the second token if available.
        if len(tokens[0]) <= 2 and len(tokens) > 1:
            return tokens[1]
        return tokens[0]
    
    def open_whatsapp(self):
        profile_dir = os.path.abspath('./chrome_profile')
        ensure_chrome_profile_dir(profile_dir)
        options = Options()
        options.add_argument(f"--user-data-dir={profile_dir}")
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.get('https://web.whatsapp.com')
        self.is_driver_available = True
        print("WhatsApp Web opened. Please scan the QR code if required (or ensure you're already logged in).")
        WebDriverWait(self.driver, 60).until(
            EC.presence_of_element_located((By.XPATH, "//div[@title='Chats']"))
        )
        print("Chats loaded successfully.")
    
    def send_message_to_contact(self, number, greeting_name):
        # Build personalized message
        if "{first_name}" in self.message_template:
            personalized_message = self.message_template.replace("{first_name}", greeting_name)
        else:
            personalized_message = f"Hello {greeting_name}, " + self.message_template
        encoded_message = urllib.parse.quote(personalized_message)
        url = f"https://web.whatsapp.com/send?phone={number}&text={encoded_message}"
        
        # Load the contact's chat page
        self.driver.get(url)
        time.sleep(5)  # Wait for the page to load
        
        delay = 30  # Time to wait for send button elements
        send_button_xpaths = [
            "//button[@data-testid='compose-btn-send']",
            "//span[@data-icon='send']",
            "//span[@data-testid='send']",
            "//button[contains(@class, 'send')]",
            "//*[@id='main']/footer/div[1]/div/span[2]/div/div[2]/div[2]/button"
        ]
        sent = False
        for xpath in send_button_xpaths:
            try:
                send_btn = WebDriverWait(self.driver, delay).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                time.sleep(2)  # Ensure the button is ready
                send_btn.click()
                sent = True
                time.sleep(3)  # Wait after sending
                print(f"Message sent to {number} ({greeting_name})")
                logging.info(f"Message sent to {number} ({greeting_name})")
                break
            except Exception:
                continue
        if not sent:
            try:
                input_box = WebDriverWait(self.driver, delay).until(
                    EC.presence_of_element_located((By.XPATH, "//div[@contenteditable='true']"))
                )
                from selenium.webdriver.common.keys import Keys
                input_box.send_keys(Keys.ENTER)
                sent = True
                time.sleep(3)
                print(f"Message sent to {number} ({greeting_name}) using Enter key")
                logging.info(f"Message sent to {number} ({greeting_name}) using Enter key")
            except Exception as e:
                print(f"Failed to send message to {number}: {str(e)}")
                logging.error(f"Failed to send message to {number}: {str(e)}")
        return sent
    
    def load_contacts(self, file_name):
        try:
            df = pd.read_csv(file_name)
            if 'Name' not in df.columns or 'Contact No' not in df.columns:
                raise ValueError("CSV must have 'Name' and 'Contact No' columns.")
            df['Contact No'] = df['Contact No'].astype(str).apply(self.format_phone_number)
            print(f"Loaded contacts from {file_name}.")
            return df
        except Exception as e:
            logging.error(f"Error loading CSV {file_name}: {str(e)}")
            print(f"Error loading CSV {file_name}: {str(e)}")
            raise
    
    def close_driver(self):
        if self.driver:
            self.driver.quit()
            self.is_driver_available = False
            print("WebDriver closed.")

if __name__ == "__main__":
    try:
        instance = Whatsapp(message_file='message.txt')
        instance.open_whatsapp()
        contacts = instance.load_contacts('contacts.csv')
        for index, row in contacts.iterrows():
            full_name = row['Name']
            number = row['Contact No']
            greeting_name = instance.extract_greeting_name(full_name)
            print(f"Sending message to {number} ({greeting_name})")
            instance.send_message_to_contact(number, greeting_name)
            time.sleep(random.uniform(1, 2))  # Brief delay between contacts
    except Exception as e:
        print(f"Script failed: {str(e)}")
        logging.error(f"Script terminated due to: {str(e)}")
    finally:
        instance.close_driver()
