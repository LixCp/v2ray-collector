import requests
from bs4 import BeautifulSoup
import os
import time
import ipaddress  # To validate IP addresses
import pycountry  # To get country information
import geoip2.database  # To use the GeoLite2 database
import socket  # To check IP and port reachability
from urllib.parse import urlparse  # To parse URLs
import json  # To handle JSON files
import random  # To select random entries

# Define path to the GeoLite2 Country database
GEOIP_DB_PATH = 'GeoLite2-Country.mmdb'

# Function to download GeoLite2 Country database
def download_geoip_db(url, filename):
    if not os.path.exists(filename):
        print(f"Downloading GeoLite2 Country database from {url}...")
        response = requests.get(url, stream=True)
        with open(filename, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        print("Download complete.")

# Function to get the country code for a given IP address using GeoLite2 database
def get_country_by_ip(ip, reader):
    try:
        response = reader.country(ip)
        return response.country.iso_code
    except geoip2.errors.AddressNotFoundError:
        print(f"IP address {ip} not found in the GeoLite2 database.")
        return None
    except Exception as e:
        print(f"Error fetching country for IP {ip}: {e}")
        return None

# Function to convert a country code to a flag emoji
def country_code_to_flag(country_code):
    if not country_code:
        return ""
    # Convert country code to flag emoji
    return ''.join(chr(127397 + ord(c)) for c in country_code.upper())

# Function to extract V2Ray links from a given URL
def extract_v2ray_links(url, timeout=15, retries=5, retry_delay=8):
    attempt = 0
    while attempt < retries:
        try:
            response = requests.get(url, timeout=timeout)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                v2ray_links = []

                # Find all divs with the specific class and extract the links
                for div in soup.find_all('div', class_='tgme_widget_message_text js-message_text'):
                    code_tag = div.find('code')
                    if code_tag:
                        link_text = code_tag.text.strip()
                        # Ensure only one type of V2Ray link is in each line
                        valid_protocols = ['vless://', 'vmess://', 'trojan://', 'ss://']
                        found_protocols = [protocol for protocol in valid_protocols if protocol in link_text]
                        
                        if len(found_protocols) == 1:  # Only one valid protocol is allowed
                            v2ray_links.append(link_text)
                        elif len(found_protocols) > 1:  # More than one protocol found
                            # Keep only the first valid protocol and discard the rest
                            for protocol in valid_protocols:
                                if protocol in link_text:
                                    single_protocol_link = link_text.split(protocol, 1)[0] + protocol + link_text.split(protocol, 1)[1]
                                    v2ray_links.append(single_protocol_link)
                                    break

                return v2ray_links
            else:
                print(f"Failed to fetch URL: {url}, status code = {response.status_code}")
                return []
        except requests.exceptions.Timeout as e:
            print(f"Timeout error on attempt {attempt + 1} for {url}: {e}")
        except requests.exceptions.RequestException as e:
            print(f"Request error on attempt {attempt + 1} for {url}: {e}")
        attempt += 1
        time.sleep(retry_delay)

    print(f"All {retries} attempts to collect failed for {url}")
    return []

# Function to save V2Ray links to a file, avoiding duplicates
def save_v2ray_links(links, filename):
    if links:
        # Read existing links if file exists
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as file:
                existing_links = set(file.read().splitlines())
        else:
            existing_links = set()

        # Determine new links to add
        new_links = set(links) - existing_links
        with open(filename, 'a', encoding='utf-8') as file:
            for link in new_links:
                file.write(link + '\n')

# Function to check if IP and port are reachable
def is_ip_port_reachable(ip, port, timeout=5):
    try:
        # Attempt to create a socket connection to the IP and port
        with socket.create_connection((ip, int(port)), timeout) as sock:
            return True
    except (socket.timeout, socket.error) as e:
        print(f"IP {ip} with port {port} is not reachable: {e}")
        return False

# Function to update text after the '#' symbol in each line of the file and check IP and port
def update_text_after_hash(filename, vmess_filename, geoip_reader, output_file='reachable_links.txt'):
    # Read all lines from the file
    with open(filename, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    # List to hold modified lines
    modified_lines = []
    vmess_lines = []  # To store lines that start with vmess://
    reachable_lines = []  # To store reachable IP and port lines

    # Process each line
    for line in lines:
        if line.startswith('vmess://'):
            # Save vmess links to a separate file
            vmess_lines.append(line)
        elif '#' in line:
            try:
                # Split the line to extract IP or domain between @ and :
                before_hash, after_hash = line.split('#', 1)
                ip_port = before_hash.split('@')[-1].split(':')
                
                if len(ip_port) != 2:
                    print(f"Skipping line due to invalid format: {line}")
                    continue

                ip, port = ip_port  # Extract IP and port

                # Check if the extracted part is a valid IP address
                try:
                    ip = ipaddress.ip_address(ip)
                    if is_ip_port_reachable(str(ip), port):
                        reachable_lines.append(line)  # If reachable, add to the reachable list
                        if len(reachable_lines) >= 25:  # Limit to 25 valid IPs
                            break
                    country_code = get_country_by_ip(ip, geoip_reader)
                    flag_emoji = country_code_to_flag(country_code)
                    new_text = f"{flag_emoji} {country_code}"
                except ValueError:
                    # If not a valid IP, use the existing after_hash content
                    new_text = after_hash.strip()

                # Remove 't.me' or 'کانال' from the text after '#'
                if 't.me' in new_text or 'کانال' in new_text:
                    new_text = f"{flag_emoji} {country_code}"

                modified_lines.append(f"{before_hash}#{new_text}\n")
            except Exception as e:
                print(f"Error processing line: {line}. Error: {e}")
                continue
        else:
            # If there's no '#', keep the line unchanged
            modified_lines.append(line)

    # Write the modified lines back to the main file
    with open(filename, 'w', encoding='utf-8') as file:
        file.writelines(modified_lines)

    # Write vmess links to a separate file with a limit of 25 random entries
    if len(vmess_lines) > 25:
        vmess_lines = random.sample(vmess_lines, 25)
    with open(vmess_filename, 'w', encoding='utf-8') as vmess_file:
        vmess_file.writelines(vmess_lines)
    
    # Write reachable IP and port lines to a separate file
    with open(output_file, 'w', encoding='utf-8') as output:
        output.writelines(reachable_lines)


def main():
    # Download GeoLite2 Country database if not already present
    geoip_db_url = 'https://git.io/GeoLite2-Country.mmdb'
    download_geoip_db(geoip_db_url, GEOIP_DB_PATH)

    # Load GeoLite2 Country database
    geoip_reader = geoip2.database.Reader(GEOIP_DB_PATH)

    # Load channel names from JSON file
    with open('telegram-channels.json', 'r', encoding='utf-8') as file:
        channels = json.load(file)

    # Construct Telegram URLs from channel names
    telegram_urls = [f"https://t.me/s/{channel}" for channel in channels]

    all_links = []
    # Extract V2Ray links from each URL
    for url in telegram_urls:
        links = extract_v2ray_links(url)
        all_links.extend(links)

    # Save the extracted links to a file
    output_file = '2.txt'
    vmess_file = 'vmess.txt'
    save_v2ray_links(all_links, output_file)

    # Update text after '#' symbol in the file, handle vmess links separately, and check IP and port
    update_text_after_hash(output_file, vmess_file, geoip_reader)

    # Close the GeoLite2 database reader
    geoip_reader.close()

if __name__ == "__main__":
    main()
