import random
import time
import pandas as pd
import urllib
import os
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException, UnexpectedAlertPresentException
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
    def __init__(self, 
                 message_file1='message1.txt', 
                 message_file2='message2.txt',
                 short_delay_range=(0.5, 2),
                 long_break_range=(30, 60),
                 message_threshold_range=(10, 15)):
        self.message_count = 0
        self.short_delay_range = short_delay_range
        self.long_break_range = long_break_range
        self.message_threshold_range = message_threshold_range
        self.random_break_threshold = random.randint(*self.message_threshold_range)
        self.message_templates = [
            self.load_message_template(message_file1),
            self.load_message_template(message_file2)
        ]
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
        if not tokens:
            return "there"
        if len(tokens[0]) <= 2 and len(tokens) > 1:
            return tokens[1]
        return tokens[0]

    def open_whatsapp(self):
        try:
            profile_dir = os.path.abspath('./chrome_profile')
            ensure_chrome_profile_dir(profile_dir)
            
            chrome_options = webdriver.ChromeOptions()
            chrome_options.add_argument(f"--user-data-dir={profile_dir}")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.get('https://web.whatsapp.com')
            self.is_driver_available = True
            print("WhatsApp Web opened. Please scan the QR code if required (or ensure you're already logged in).")
            logging.info("WhatsApp Web opened. Waiting for chats to load.")
            
            WebDriverWait(self.driver, 60).until(
                EC.presence_of_element_located((By.XPATH, "//div[@title='Chats']"))
            )
            print("Chats loaded successfully.")
            logging.info("Chats are visible. Proceeding with messaging.")
        except TimeoutException:
            error_msg = "Timeout: Chats did not load. Ensure you are logged in and have scanned the QR code."
            logging.error(error_msg)
            print(error_msg)
            raise
        except Exception as e:
            logging.error(f"Failed to open WhatsApp Web: {str(e)}")
            print(f"Error opening WhatsApp Web: {str(e)}")
            raise

    def randomized_delay(self):
        short_delay = random.uniform(*self.short_delay_range)
        time.sleep(short_delay)
        self.message_count += 1
        if self.message_count >= self.random_break_threshold:
            long_delay = random.randint(*self.long_break_range)
            logging.info(f"Anti-ban: Taking a break for {long_delay} seconds after {self.message_count} messages.")
            print(f"Taking a break for {long_delay} second(s) after {self.message_count} messages.")
            time.sleep(long_delay)
            self.message_count = 0
            self.random_break_threshold = random.randint(*self.message_threshold_range)

    def find_send_button(self, wait_time=15):
        try:
            print("Trying to find send button using aria-label='Send'...")
            button = WebDriverWait(self.driver, wait_time).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Send']"))
            )
            print("Send button found using aria-label.")
            return button
        except (TimeoutException, NoSuchElementException):
            print("Send button not found with aria-label, trying alternative locators...")
        alternative_xpaths = [
            "//button[@data-testid='compose-btn-send']",
            "//span[@data-icon='send']",
            "//button[contains(@class, 'send')]"
        ]
        for xpath in alternative_xpaths:
            try:
                button = WebDriverWait(self.driver, wait_time).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                print(f"Send button found using xpath: {xpath}")
                return button
            except (TimeoutException, NoSuchElementException):
                continue
        warning_msg = "Warning: Send button not found using any locator."
        logging.warning(warning_msg)
        print(warning_msg)
        return None

    def open_contact_in_new_tab(self, number, message):
        """Open a new tab for the given contact with a pre-filled message."""
        url = f'https://web.whatsapp.com/send?phone={number}&text={urllib.parse.quote(message)}'
        try:
            # Open new tab
            self.driver.execute_script(f"window.open('{url}', '_blank');")
            # Switch to the new tab (the last tab)
            self.driver.switch_to.window(self.driver.window_handles[-1])
            logging.info(f"Opened new tab for contact: {number}")
            print(f"Opened new tab for contact: {number}")
            # Allow extra time for WhatsApp to load the chat
            time.sleep(random.uniform(2, 4))
        except Exception as e:
            logging.error(f"Error opening contact in new tab for {number}: {str(e)}")
            print(f"Error opening contact in new tab for {number}: {str(e)}")
            raise

    def load_csv_to_dataframe(self, file_name):
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

    def send_message(self):
        """Send the pre-filled message on the current tab."""
        try:
            send_button = self.find_send_button()
            if send_button:
                try:
                    send_button.click()
                except UnexpectedAlertPresentException:
                    alert = self.driver.switch_to.alert
                    print(f"Unexpected alert during send: {alert.text}")
                    alert.accept()
                    time.sleep(1)
                    send_button.click()
                # Extra delay to ensure message is delivered
                time.sleep(random.uniform(1, 2))
                self.randomized_delay()
                logging.info("Message sent successfully.")
                print("Message sent successfully.")
                return True
            logging.warning("Send button not clickable.")
            print("Warning: Send button not clickable.")
            return False
        except Exception as e:
            logging.error(f"Error sending message: {str(e)}")
            print(f"Error sending message: {str(e)}")
            return False

    def handle_invalid_number(self, number):
        invalid_text = "Phone number shared via url is invalid."
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, f"//*[contains(text(), '{invalid_text}')]"))
            )
            logging.info(f"Invalid number detected: {number}")
            print(f"Invalid number detected: {number}")
            return True
        except TimeoutException:
            return False

    def close_current_tab_and_switch_back(self):
        """Close the current tab and switch back to the first tab."""
        if len(self.driver.window_handles) > 1:
            self.driver.close()
            self.driver.switch_to.window(self.driver.window_handles[0])
            print("Closed current tab and switched back to main tab.")

    def close_driver(self):
        if self.is_driver_available and self.driver:
            self.driver.quit()
            self.is_driver_available = False
            logging.info("WebDriver closed.")
            print("WebDriver closed.")

# Usage example
if __name__ == "__main__":
    try:
        instance = Whatsapp()
        instance.open_whatsapp()
        
        contacts = instance.load_csv_to_dataframe('contacts.csv')
        invalid = pd.DataFrame(columns=['number', 'reason'])
        
        for index, row in contacts.iterrows():
            try:
                full_name = row['Name']
                number = row['Contact No']
                greeting_name = instance.extract_greeting_name(full_name)
                chosen_template = random.choice(instance.message_templates)
                if "{first_name}" in chosen_template:
                    personalized_message = chosen_template.replace("{first_name}", greeting_name)
                else:
                    personalized_message = f"Hello {greeting_name}, " + chosen_template

                print(f"Processing {index+1}/{len(contacts)}: {number} ({greeting_name})")
                instance.open_contact_in_new_tab(number, personalized_message)
                
                if instance.handle_invalid_number(number):
                    new_row = pd.DataFrame([[number, 'Invalid number']], columns=['number', 'reason'])
                    invalid = pd.concat([invalid, new_row], ignore_index=True)
                    instance.close_current_tab_and_switch_back()
                    continue

                if instance.send_message():
                    print(f"Message sent to {number} ({greeting_name})")
                else:
                    print(f"Failed to send message to {number} ({greeting_name})")
                    new_row = pd.DataFrame([[number, 'Send failed']], columns=['number', 'reason'])
                    invalid = pd.concat([invalid, new_row], ignore_index=True)
                    
                instance.close_current_tab_and_switch_back()
                    
            except Exception as e:
                error_str = f"Error with {number}: {str(e)}"
                print(error_str)
                new_row = pd.DataFrame([[number, str(e)]], columns=['number', 'reason'])
                invalid = pd.concat([invalid, new_row], ignore_index=True)
                try:
                    instance.close_current_tab_and_switch_back()
                except Exception:
                    pass
        
        invalid.to_csv('invalid_numbers.csv', index=False)
        print("Process completed. Check 'invalid_numbers.csv' for any issues.")
        
    except Exception as e:
        print(f"Script failed: {str(e)}")
        logging.error(f"Script terminated due to: {str(e)}")
    finally:
        instance.close_driver()
