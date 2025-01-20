﻿import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import re
import pandas as pd
import time
from fuzzywuzzy import fuzz
from datetime import datetime
from selenium.webdriver.chrome.options import Options
import zipfile
import io
import os

# Function to run the web scraping for exact matches
def scrape_facebook_marketplace_exact(city, product, min_price, max_price, city_code_fb):
    return scrape_facebook_marketplace(city, product, min_price, max_price, city_code_fb, exact=True)

# Function to run the web scraping for partial matches
def scrape_facebook_marketplace_partial(city, product, min_price, max_price, city_code_fb):
    return scrape_facebook_marketplace(city, product, min_price, max_price, city_code_fb, exact=False)

# Main scraping function with an exact match flag
def scrape_facebook_marketplace(city, product, min_price, max_price, city_code_fb, exact, sleep_time=3):
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Enables headless mode
    chrome_options.add_argument("--disable-gpu")  # Disable GPU acceleration (optional, good for headless)
    chrome_options.add_argument("--no-sandbox")  # Recommended for Linux systems
    chrome_options.add_argument("--disable-dev-shm-usage")  # Avoid issues with /dev/shm on Linux
    chrome_options.add_argument("--disable-quic")

    browser = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    # Setup URL
    exact_param = 'true' if exact else 'false'
    url = f"https://www.facebook.com/marketplace/{city_code_fb}/search?query={product}&minPrice={min_price}&maxPrice={max_price}&daysSinceListed=1&exact={exact_param}"
    browser.get(url)

    time.sleep(4)

    # Close cookies and pop-ups
    try:
        close_btn = browser.find_element(By.XPATH, '//div[@aria-label="Decline optional cookies" and @role="button"]')
        close_btn.click()
    except:
        pass

    try:
        close_btn = browser.find_element(By.XPATH, '//div[@aria-label="Close" and @role="button"]')
        close_btn.click()
    except:
        pass

    # Scroll down to load more items
    count = 0
    last_height = browser.execute_script("return document.body.scrollHeight")
    while True:
        browser.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(sleep_time)
        new_height = browser.execute_script("return document.body.scrollHeight")
        if (new_height == last_height) or count == 8:
            break
        last_height = new_height
        count = count + 1

    # Retrieve the HTML
    html = browser.page_source
    browser.close()

    # Use BeautifulSoup to parse the HTML
    soup = BeautifulSoup(html, 'html.parser')
    links = soup.find_all('a')

    # Filter links based on search criteria
    if exact:
        final_links = []
        for link in links:
            if fuzz.partial_ratio(product.lower(), link.text.lower()) >= 70:
                if fuzz.partial_ratio(city.lower().rstrip(), link.text.lower()) >= 50:
                    final_links.append(link)
    else:
        fuzz_threshold = 50
        final_links = [
            link for link in links
            if fuzz.partial_ratio(product.lower(), link.text.lower()) > fuzz_threshold and city.lower() in link.text.lower()
        ]

    # Extract product data using enhanced logic
    extracted_data = []
    for prod_link in final_links:
        url = prod_link.get('href')
        text = '\n'.join(prod_link.stripped_strings)
        lines = text.split('\n')

        numeric_pattern = re.compile(r'\d[\d, •]*')  # Pattern to find prices
        price = None

        for line in lines:
            match = numeric_pattern.search(line)
            if match:
                price_str = match.group()
                price = float(price_str.replace(',', '').replace('•', '').strip())
                break

        # Title and location extraction
        title = ""
        location = ""
        for i, line in enumerate(lines):
            if i == 1:  # Assume the first line is the title
                title = line.strip()
            elif "km" in line.lower() or "miles" in line.lower():  # Distance pattern for location
                location = line.strip()
            elif len(lines) > 1 and i == len(lines) - 1:  # Fallback for last line as location
                location = line.strip()

        extracted_data.append({
            'title': title,
            'price': price,
            'location': location,
            'url': url
        })

    base = "https://web.facebook.com/"
    for items in extracted_data:
        items['url'] = base + items['url']

    # Create a DataFrame
    items_df = pd.DataFrame(extracted_data)
    return items_df, len(links)

# Streamlit UI
st.set_page_config(page_title="Facebook Marketplace Scraper", layout="wide")
st.title("🏷️ Facebook Marketplace Scraper")
st.markdown("""Welcome to the Facebook Marketplace Scraper!  
Easily find products in your city and filter by price.""")

# Initialize session state for storing marketplaces and results
if "marketplaces" not in st.session_state:
    st.session_state["marketplaces"] = []

if "scraped_data" not in st.session_state:
    st.session_state["scraped_data"] = None

# Input fields with better layout and styling
with st.form(key='input_form'):
    col1, col2 = st.columns(2)
    
    with col1:
        city = st.text_input("City", placeholder="Enter city name...")
        product = st.text_input("Product", placeholder="What are you looking for?")
    
    with col2:
        min_price = st.number_input("Minimum Price", min_value=0, value=0, step=1)
        max_price = st.number_input("Maximum Price", min_value=0, value=1000, step=1)
    
    city_code_fb = st.text_input("City Code for Facebook Marketplace", placeholder="Enter city code...")

    col3, col4 = st.columns([3, 1])
    with col3:
        submit_button = st.form_submit_button(label="🔍 Scrape Data")
    with col4:
        add_button = st.form_submit_button(label="🟢 Add")

# Handle adding a new marketplace
if add_button:
    if city and product and min_price <= max_price and city_code_fb:
        st.session_state["marketplaces"].append({
            "city": city,
            "product": product,
            "min_price": min_price,
            "max_price": max_price,
            "city_code_fb": city_code_fb,
        })
        st.success("Marketplace added successfully!")
    else:
        st.error("Please fill all fields correctly.")

# Show the current list of marketplaces
if st.session_state["marketplaces"]:
    st.write("### Current Marketplaces:")
    for i, entry in enumerate(st.session_state["marketplaces"]):
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        col1.write(entry["city"])
        col2.write(entry["product"])
        col3.write(entry["min_price"])
        col4.write(entry["max_price"])
        col5.write(entry["city_code_fb"])
        if col6.button("❌ Remove", key=f"remove_{i}"):
            st.session_state["marketplaces"].pop(i)

# Handle scraping data
if submit_button:
    st.session_state["scraped_data"] = None
    individual_files = []

    if not st.session_state["marketplaces"]:
        st.error("Please add at least one marketplace to scrape data.")
    else:
        combined_df = pd.DataFrame()
        for marketplace in st.session_state["marketplaces"]:
            with st.spinner(f"Scraping data for {marketplace['city']}..."):
                items_df, total_links = scrape_facebook_marketplace_exact(
                    marketplace["city"],
                    marketplace["product"],
                    marketplace["min_price"],
                    marketplace["max_price"],
                    marketplace["city_code_fb"]
                )

            if not items_df.empty:
                if "scraped_data" not in st.session_state:
                    st.session_state["scraped_data"] = pd.DataFrame()

                st.session_state["scraped_data"] = pd.concat([st.session_state["scraped_data"], items_df], ignore_index=True)

                # Save individual result for each marketplace
                individual_file = io.StringIO()
                items_df.to_csv(individual_file, index=False)
                individual_file.seek(0)
                individual_files.append({
                    'name': f"{marketplace['city']}_{marketplace['product']}_result.csv",
                    'file': individual_file
                })

        if st.session_state["scraped_data"] is not None and not st.session_state["scraped_data"].empty:
            st.write("### Combined Match Results:")
            st.dataframe(st.session_state["scraped_data"])

            # Save combined CSV file
            combined_file = io.StringIO()
            st.session_state["scraped_data"].to_csv(combined_file, index=False)
            combined_file.seek(0)

            # Zip all individual and combined files into one package
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for file_data in individual_files:
                    zip_file.writestr(file_data['name'], file_data['file'].getvalue())
                zip_file.writestr("combined_results.csv", combined_file.getvalue())

            zip_buffer.seek(0)

            # Add download button
            st.download_button(
                label="Download All Results",
                data=zip_buffer,
                file_name="scraped_results.zip",
                mime="application/zip"
            )
