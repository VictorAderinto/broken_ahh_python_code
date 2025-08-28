import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import json
import cohere
import pandas as pd
import PyPDF2
from io import BytesIO


co = cohere.ClientV2(
    "yKJqWEwcoD5FXaArm70AjnqV4QRglvDP5yzLPuf8"
)


BASE_URL = ['https://www.canada.ca/en/services/immigration-citizenship.html', 'https://www.ontario.ca/page/immigrate-to-ontario', 'https://immigratemanitoba.com/', 
            'https://www.welcomebc.ca/immigrate-to-b-c', 'https://www.princeedwardisland.ca/en/topic/immigrate', 'https://www.alberta.ca/immigration', 
            'https://liveinnovascotia.com/nova-scotia-nominee-program', 'https://www.saskatchewan.ca/residents/moving-to-saskatchewan','https://www.quebec.ca/en/immigration', 
            'https://www2.gnb.ca/content/gnb/en/corporate/promo/immigration.html', 'https://www.gov.nl.ca/immigration/', 'https://www.gov.nu.ca/en/immigration', 
            'https://yukon.ca/en/immigration', 'https://www.immigratenwt.ca/']

avoid_links = set([
    'https://www.canada.ca/en/services/defence.html', 'https://www.canada.ca/en.html', 'https://www.canada.ca/en/services/indigenous-peoples.html', 
    'https://www.canada.ca/en/services/environment.html','https://www.canada.ca/en/services/culture.html', 'https://www.canada.ca/en/services/health.html', 
    'https://www.canada.ca/en/services/health.html', 'https://www.canada.ca/en/services/youth.html'
])
# Define maximum depth (e.g., 3 levels)
MAX_DEPTH = 3
visited_urls = set()

def visit_url(url):

    if any(url.lower().endswith(ext) for ext in ['.jpg', 'pdf', '.png', '.css', '.ico', '.svg']):
        return False
    
    # Avoid social media
    social_domains = ['facebook.com', 'twitter.com', 'instagram.com', 'linkedin.com', 'youtube.com']
    if any(domain in url for domain in social_domains):
        return False

    # Avoid explicitly listed URLs
    if url in avoid_links:
        return False

    # Optional: Avoid mailto or tel links
    if url.startswith('mailto:') or url.startswith('tel:'):
        return False

    # Optional: Block query strings or fragments if not useful
    parsed = urlparse(url)
    if parsed.query or parsed.fragment:
        return False

    return True

def is_pdf(url):
    return url.lower().endswith('.pdf')

def extract_pdf_text(url):

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        with BytesIO(response.content) as f:
            reader = PyPDF2.PdfReader(f)
            text = ''
            for page in reader.pages:
                text += page.extract_text() or ''
            return text.strip()
    except Exception as e:
        print(f"Failed to extract PDF from {url} : {e}")


def get_soup(url):
    """Fetches and parses a page."""
    headers = {
        'Accept-Language': 'en'  # Prefer English content
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200 and '/fr/' not in response.url:
            return BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        print(f"Exception occured while fetching {url}, skipping")
        return None

def extract_links(soup, base_url):
    """Extracts links from a page and returns their text and full URL."""
    links = []
    for a_tag in soup.find_all('a'):
        href = a_tag.get('href')

        if href:
            if href.startswith(('javascript:', 'mailto', 'tel:', '#', 'fax')):
                continue
        else:
            continue

        if ' ' in href or any(c in href for c in ['{', '}', '|', '\\', '^', '[', ']', '`']):
            continue

        full_url = urljoin(base_url, href)

        # Further check if the resulting URL is valid
        parsed = urlparse(full_url)
        if not parsed.scheme.startswith("http"):
            continue

        if any(keyword in full_url.lower() for keyword in ['login', 'logon', 'signin', 'auth']):
            continue
        links.append((a_tag.get_text(strip=True), full_url))

    return list(set(links))  # Remove duplicates

def extract_text_from_page(url):
    """Extracts text content from the page."""
    soup = get_soup(url)
    if soup:
        text_blocks = soup.find_all(['p', 'h1', 'h2', 'h3', 'li'])  # Collect relevant tags
        return '\n'.join([t.get_text(strip=True) for t in text_blocks])
    return ''

def scrape_page(url, base_url, depth=0):
    
    """Scrapes a page and follows links up to MAX_DEPTH."""
    if depth > MAX_DEPTH or url in visited_urls:
        return []
    
    if any(url.lower().endswith(ext) for ext in ['.pdf', '.doc', '.docx', '.jpg', '.png', '.zip']):
        print(f"Skipping binary file: {url}")
        return []
    
    if not visit_url(url):
        return []
    
    # if is_pdf(url):
    #     pdf_text = extract_pdf_text(url)
    #     return [{'url': url, 'content': pdf_text}]

    visited_urls.add(url)
    print(f"Scraping {url} at depth {depth}")
    soup = get_soup(url)
    if not soup:
        return []

    # Extract links on the current page
    sublinks = extract_links(soup, base_url)
    page_content = extract_text_from_page(url)

    data = [{"title": title, "url": link, "content": page_content} for title, link in sublinks]

    # Recursively scrape the sublinks
    for title, link in sublinks:
        data.extend(scrape_page(link, base_url, depth + 1))

    return data

def save_to_json(data):
    """Saves the scraped data to a JSON file."""
    with open('immigration_data.json', 'a', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

def main():
    # Start scraping from the base URL
    for url in BASE_URL:
        base_url = url
        scraped_data = scrape_page(url, base_url)
        save_to_json(scraped_data)

if __name__ == '__main__':
    main()
    print(visited_urls)




# file_path = "C:/Users/vaderinto/Downloads/Personal/immigration_content.json"

# # Read and parse the JSON file

# with open(file_path, 'r', encoding='utf-8') as file:
#     documents = json.load(file)

# previous_entry = None

# for entry in documents[:]:

#     entry['data'] = entry.pop('content')
    
#     if previous_entry and previous_entry['data'] == entry['data']:
#         documents.remove(previous_entry)
        
#     previous_entry = entry

# print(len(documents))

# text = ""
# for entry in documents:
#     text = text + " " + entry['data']

# item = co.tokenize(
#     text=text, model="command-a-03-2025"
# )
# print(item.token_strings)
# print(len(item.tokens))


# message = "What does it mean to go through the provincial nominee program?"

# messages = [{"role": "user", "content": message}]

# response = co.chat(
#     model="command-a-03-2025",
#     messages=messages,
#     documents=documents,
# )
# print(response.message.content[0].text)
# print(response.message.citations)






# import requests
# from bs4 import BeautifulSoup
# from urllib.parse import urljoin
# import json

# main_url = 'https://www.canada.ca/en/services/immigration-citizenship.html'

# max_depth = 4
# visited_urls = set()

# def get_soup(url):
#     headers = {
#         'Accept-Language': 'en'
#     }

#     try:
#         response = requests.get(url, headers=headers, timeout=5)

#         if response.status_code == 200 and '/fr/' not in response.url:
#             return BeautifulSoup(response.text, 'html.parser')
#         else:
#             print("Skipped (non-English or failed): {url}")
#     except Exception as e:
#         print("Request failed for {url} : {e}")

#     return None

# def extract_links(soup):

#     links = []
#     for a_tag in soup.find_all('a'):
#         href = a_tag.get('href')
#         full_url =  urljoin(main_url, href)
#         links.append((a_tag.get_text(strip = True), full_url))

#     return list(set(links))

# def extract_text_from_page(url):
    
#     soup = get_soup(url)
#     if soup:
#         text_blocks = soup.find_all(['p', 'h1', 'h2', 'h3', 'li'])  # Collect relevant tags
#         return '\n'.join([t.get_text(strip=True) for t in text_blocks])
#     return ''

# def extract_text_from_page(url, depth=0):

#     if depth > max_depth or url in visited_urls:
#         return []
    
#     visited_urls.add(url)
#     soup = get_soup(url)
#     if not soup:
#         return []

#     sublinks = extract_links(soup) 
#     page_content = extract_text_from_page(url)

# def main():

#     main_soup = get_soup(main_url)

#     if not main_soup:
#         print("Could not load the main page")
#         return
    
    



# if __name__ == "__main__":
#     main()

# # main_url = 'https://www.canada.ca/en/services/immigration-citizenship.html'
# # response = requests.get(main_url)

# # if response.status_code == 200:
# #     soup = BeautifulSoup(response.text, 'html.parser')

# #     paragraphs = soup.find_all('p')
# #     for p in paragraphs:
# #         print(p.get_text())

# # # Function to fetch and parse a webpage
# # def fetch_and_parse(url):
# #     response = requests.get(url)
# #     return BeautifulSoup(response.content, 'html.parser')

# # # URL of the main page
# # # main_url = 'https://www.canada.ca/en/immigration-refugees-citizenship/services/work-canada.html'
# # main_soup = fetch_and_parse('https://www.canada.ca/en/immigration-refugees-citizenship/services/study-canada/work/after-graduation.html')

# # # Find all links on the main page
# # links = main_soup.find_all('a')

# # linked_soup = fetch_and_parse(href)
        
# #         # # Example: Extract all paragraphs from the linked page
# # paragraphs = linked_soup.find_all('p')
# # for paragraph in paragraphs:
# #     print(paragraph.text)


# # # print(links[1])
# # # print(type(links))
# # # Iterate over each link and extract items
# # # for link in links[2:]:
# # #     href = link.get('href')
# # #     if href:
# # #         # print(href)
# # #         # Fetch and parse the linked page
# # #         # print(href)
# # #         linked_soup = fetch_and_parse(href)
        
# # #         # # Example: Extract all paragraphs from the linked page
# # #         paragraphs = linked_soup.find_all('p')
# # #         for paragraph in paragraphs:
# # #             print(paragraph.text)

# # # Save the extracted items to a file
# # # with open('extracted_items.txt', 'w') as file:
# # #     for link in links:
# # #         href = link.get('href')
# # #         if href:
# # #             linked_soup = fetch_and_parse(href)
# # #             paragraphs = linked_soup.find_all('p')
# # #             for paragraph in paragraphs:
# # #                 file.write(paragraph.text + '\n')
