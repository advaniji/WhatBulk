import random
import time
import pandas as pd
import urllib.parse
import os
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (TimeoutException, NoSuchElementException,
                                        WebDriverException, UnexpectedAlertPresentException)
from webdriver_manager.chrome import ChromeDriverManager

class WhatsAppSender:
    def __init__(self, 
                 message_files=('message1.txt', 'message2.txt'),
                 media_path=None,
                 message_type="text",  # Options: "text" or "media"
                 short_delay=(0.5, 2),
                 long_break=(30, 60),
                 message_threshold=(10, 15),
                 debug=True):
        # Basic settings and debug flag
        self.debug = debug
        self.debug_print("Debug mode enabled.")
        self.message_count = 0
        self.short_delay_range = short_delay
        self.long_break_range = long_break
        self.message_threshold_range = message_threshold
        self.random_break_threshold = random.randint(*self.message_threshold_range)
        # Load message templates from the specified files
        self.message_templates = [self.load_message_template(f) for f in message_files]
        self.media_path = media_path  # Set to a valid file path when sending media
        self.message_type = message_type.lower()  # "text" or "media"
        self.driver = None
        self.is_driver_active = False
        
        # Detailed contact handling: DataFrames to store outcomes
        self.sent_numbers_df = pd.DataFrame(columns=['number', 'name', 'timestamp'])
        self.invalid_numbers_df = pd.DataFrame(columns=['number', 'name', 'timestamp', 'error'])
        self.failed_numbers_df = pd.DataFrame(columns=['number', 'name', 'timestamp', 'error'])
        
        # Configure logging for debugging and error tracking
        logging.basicConfig(filename='whatsapp.log', level=logging.INFO,
                            format='%(asctime)s - %(levelname)s - %(message)s')
        print("WhatsAppSender initialized.")

    # Debug print helper: prints only if debug mode is enabled.
    def debug_print(self, message):
        if self.debug:
            print("[DEBUG]", message)

    # Load a message template from a text file.
    def load_message_template(self, filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                self.debug_print(f"Loaded template: {filename}")
                return content
        except FileNotFoundError:
            logging.error(f"Message file {filename} not found. Using default.")
            print(f"Warning: {filename} not found. Using default message.")
            return "Hello {first_name}, this is a default message."

    # Format the phone number, adding the +91 country code when needed.
    def format_number(self, number):
        number = str(number).strip().replace(" ", "").replace("-", "")
        if number.startswith('+'):
            return number
        if number.startswith('0'):
            number = number[1:]
        return f"+91{number}"

    # Extract the greeting name from the full name.
    def get_greeting_name(self, full_name):
        if not isinstance(full_name, str) or not full_name.strip():
            return "there"
        parts = full_name.strip().split()
        return parts[0] if len(parts[0]) > 2 else (parts[1] if len(parts) > 1 else "there")

    # Initialize the Chrome driver using a dedicated profile.
    def init_driver(self):
        profile_dir = os.path.abspath('./chrome_profile')
        if not os.path.exists(profile_dir):
            try:
                os.makedirs(profile_dir)
                print(f"Created directory: {profile_dir}")
            except Exception as e:
                raise PermissionError(f"Unable to create directory {profile_dir}: {e}")
        if not os.access(profile_dir, os.W_OK):
            raise PermissionError(f"Directory {profile_dir} is not writable. Please check permissions.")
        
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument(f"--user-data-dir={profile_dir}")
        chrome_options.add_argument("--remote-debugging-port=9222")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
        
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.is_driver_active = True
            print("Chrome driver initialized successfully.")
        except Exception as e:
            logging.critical(f"Driver initialization failed: {str(e)}")
            raise

    # Wait for the user to log in via WhatsApp Web.
    def wait_for_login(self):
        self.driver.get('https://web.whatsapp.com')
        print("Please scan the QR code if required. Waiting for WhatsApp Web login...")
        try:
            WebDriverWait(self.driver, 120).until(
                EC.presence_of_element_located((By.XPATH, "//div[@title='Chats']"))
            )
            print("Login successful. WhatsApp chats loaded.")
        except TimeoutException:
            logging.error("Login timeout. QR code not scanned.")
            raise

    # Introduce a randomized delay to mimic human behavior.
    def randomized_delay(self):
        delay = random.uniform(*self.short_delay_range)
        print(f"Waiting for {delay:.2f} seconds before next action.")
        time.sleep(delay)
        self.message_count += 1
        if self.message_count >= self.random_break_threshold:
            pause = random.randint(*self.long_break_range)
            print(f"Anti-ban mechanism: Pausing for {pause} seconds.")
            time.sleep(pause)
            self.message_count = 0
            self.random_break_threshold = random.randint(*self.message_threshold_range)

    # Find the send button using multiple XPath strategies.
    def find_send_button(self):
        xpath_strategies = [
            "//button[@aria-label='Send']",
            "//button[@data-testid='compose-btn-send']",
            "//span[@data-icon='send']",
            "//button[contains(@class, 'send')]",
            "//div[@contenteditable='true']"  # Fallback for Enter key simulation
        ]
        for xpath in xpath_strategies:
            try:
                element = WebDriverWait(self.driver, 15).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                self.debug_print(f"Send button found using XPath: {xpath}")
                return element
            except (TimeoutException, NoSuchElementException):
                continue
        logging.warning("Send button not found using any strategy.")
        return None

    # Send a text message using the found send button.
    def send_text_message(self):
        send_element = self.find_send_button()
        if send_element:
            try:
                if send_element.tag_name.lower() == 'div':
                    send_element.send_keys(Keys.ENTER)
                    print("Text message sent using Enter key.")
                else:
                    send_element.click()
                    print("Text message sent by clicking the send button.")
                self.randomized_delay()
                return True
            except Exception as e:
                logging.error(f"Failed to send text message: {str(e)}")
                print(f"Error: {str(e)}")
                return False
        else:
            print("Send button not found.")
            return False

    # Send a media message (e.g., an image) with an optional accompanying text.
    def send_media_message(self, message=""):
        # Click the attachment (clip) icon.
        try:
            attachment_button = WebDriverWait(self.driver, 15).until(
                EC.element_to_be_clickable((By.XPATH, "//span[@data-icon='clip']"))
            )
            attachment_button.click()
            print("Attachment button clicked.")
        except Exception as e:
            logging.error(f"Attachment button not found: {str(e)}")
            print(f"Error finding attachment button: {str(e)}")
            return False
        
        # Locate the file input element and upload the media.
        try:
            file_input = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//input[@accept='image/*,video/mp4,video/3gpp,video/quicktime']")
                )
            )
            file_input.send_keys(self.media_path)
            print(f"Media file '{self.media_path}' uploaded.")
            time.sleep(1)  # Wait for the media preview to load
        except Exception as e:
            logging.error(f"Error uploading media: {str(e)}")
            print(f"Error uploading media: {str(e)}")
            return False
        
        # If an accompanying text is provided, add it.
        if message:
            try:
                text_box = WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.XPATH, "//div[@title='Type a message']"))
                )
                text_box.send_keys(message)
                print("Accompanying message added with media.")
            except Exception as e:
                logging.error(f"Accompanying text box not found: {str(e)}")
                print(f"Error adding accompanying message: {str(e)}")
        
        # Click the send button.
        try:
            send_button = WebDriverWait(self.driver, 15).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Send']"))
            )
            send_button.click()
            print("Media message sent.")
            self.randomized_delay()
            return True
        except Exception as e:
            logging.error(f"Failed to send media message: {str(e)}")
            print(f"Error sending media message: {str(e)}")
            return False

    # Check if an invalid number prompt appears on the page.
    def is_invalid_number(self):
        try:
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'invalid')]"))
            )
            return True
        except TimeoutException:
            return False

    # Close the current browser tab and return to the main tab.
    def close_current_tab(self):
        if len(self.driver.window_handles) > 1:
            self.driver.close()
            self.driver.switch_to.window(self.driver.window_handles[0])
            time.sleep(0.5)
            print("Closed current tab and switched back to main tab.")

    # Helper method to add a contact's result into a DataFrame.
    def add_contact_result(self, df, number, name, error=""):
        # If an error message is provided, include it in the DataFrame.
        if error:
            new_row = pd.DataFrame([[number, name, pd.Timestamp.now(), error]], 
                                   columns=df.columns)
        else:
            new_row = pd.DataFrame([[number, name, pd.Timestamp.now()]], 
                                   columns=df.columns)
        return pd.concat([df, new_row], ignore_index=True)

    # Handle an individual contact by opening a chat and sending the appropriate message.
    def handle_contact(self, number, name):
        greeting = self.get_greeting_name(name)
        template = random.choice(self.message_templates)
        formatted_message = template.replace("{first_name}", greeting)
        encoded_message = urllib.parse.quote(formatted_message)
        print(f"Processing contact: {number} (Greeting: {greeting})")

        # Build the WhatsApp Web URL based on the message type.
        if self.message_type == "text":
            url = f'https://web.whatsapp.com/send?phone={number}&text={encoded_message}'
        elif self.message_type == "media":
            url = f'https://web.whatsapp.com/send?phone={number}&text='  # Open chat with empty text field
        else:
            url = f'https://web.whatsapp.com/send?phone={number}&text={encoded_message}'

        try:
            print(f"Opening chat for {number}...")
            self.driver.execute_script(f"window.open('{url}');")
            self.driver.switch_to.window(self.driver.window_handles[-1])
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "//div[@title='Type a message']"))
            )
            
            if self.is_invalid_number():
                print(f"Invalid number detected: {number}")
                self.invalid_numbers_df = self.add_contact_result(self.invalid_numbers_df, number, name, "Invalid number")
                return "invalid"
            
            # Send the message based on the selected type.
            if self.message_type == "text":
                success = self.send_text_message()
            elif self.message_type == "media":
                success = self.send_media_message(message=formatted_message)
            else:
                success = self.send_text_message()
            
            if success:
                print(f"Message successfully sent to {number}.")
                self.sent_numbers_df = self.add_contact_result(self.sent_numbers_df, number, name)
                return "success"
            else:
                print(f"Failed to send message to {number}.")
                self.failed_numbers_df = self.add_contact_result(self.failed_numbers_df, number, name, "Failed to send")
                return "failed"
        except Exception as e:
            logging.error(f"Error handling contact {number}: {str(e)}")
            print(f"Error handling contact {number}: {str(e)}")
            self.failed_numbers_df = self.add_contact_result(self.failed_numbers_df, number, name, str(e))
            return "error"
        finally:
            self.close_current_tab()

    # Process all contacts from a CSV file.
    def process_contacts(self, csv_file):
        try:
            df = pd.read_csv(csv_file)
            print(f"Loaded contacts from {csv_file}. Total contacts: {len(df)}")
        except Exception as e:
            print(f"Error reading CSV file: {str(e)}")
            return
        
        results = []
        for index, row in df.iterrows():
            number = self.format_number(row['Contact No'])
            name = row.get('Name', '')
            print(f"Processing row {index + 1}: {number}, {name}")
            result = self.handle_contact(number, name)
            results.append({
                'number': number,
                'name': name,
                'status': result,
                'timestamp': pd.Timestamp.now()
            })
            time.sleep(random.uniform(0.5, 1.5))  # Delay between processing contacts
        
        result_df = pd.DataFrame(results)
        result_df.to_csv('send_results.csv', index=False)
        print("All contacts processed. Results saved to send_results.csv")
        
        # Save detailed logs for further analysis.
        self.sent_numbers_df.to_csv('sent_numbers.csv', index=False)
        self.invalid_numbers_df.to_csv('invalid_numbers.csv', index=False)
        self.failed_numbers_df.to_csv('failed_numbers.csv', index=False)
        print("Detailed logs saved: sent_numbers.csv, invalid_numbers.csv, failed_numbers.csv")

    # Safely shutdown the driver.
    def shutdown(self):
        if self.is_driver_active and self.driver:
            self.driver.quit()
            self.is_driver_active = False
            print("Driver safely closed.")

# Main execution block
if __name__ == "__main__":
    try:
        # Uncomment the configuration you want to use:
        # For text messages:
        sender = WhatsAppSender(message_files=('message1.txt', 'message2.txt'),
                                message_type="text", debug=True)
        # For media messages (ensure media_path points to a valid file):
        # sender = WhatsAppSender(message_files=('message1.txt', 'message2.txt'),
        #                         media_path="/path/to/your/image.jpg", message_type="media", debug=True)
        
        sender.init_driver()
        sender.wait_for_login()
        sender.process_contacts('contacts.csv')
    except Exception as e:
        logging.critical(f"Main execution failed: {str(e)}")
        print(f"Critical error: {str(e)}")
    finally:
        sender.shutdown()
