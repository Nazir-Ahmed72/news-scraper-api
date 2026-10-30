import os
import re
from urllib.parse import quote_plus, urlparse, parse_qs, unquote

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

NHK_SEARCH_URL = "https://www3.nhk.or.jp/nhkworld/en/search/?q={}"
DDG_SEARCH_URL = "https://html.duckduckgo.com/html/?q={}"
# NHK article URLs look like /nhkworld/en/news/20261030_12/ or /news/backstories/1234/
ARTICLE_PATTERN = re.compile(r"nhk\.or\.jp/nhkworld/en/news/(\d{8}_\w+|backstories/\d+)")


def make_driver():
    """Start headless Chrome inside the container."""
    opts = Options()
    opts.binary_location = os.getenv("CHROME_BIN", "/usr/bin/chromium")
    for arg in [
        "--headless=new",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--window-size=1366,900",
        "user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    ]:
        opts.add_argument(arg)
    service = Service(os.getenv("CHROMEDRIVER", "/usr/bin/chromedriver"))
    driver = webdriver.Chrome(service=service, options=opts)
    driver.set_page_load_timeout(45)
    return driver


def _find_article_link(driver):
    """Return the first link on the page that points to an NHK news article."""
    for a in driver.find_elements(By.TAG_NAME, "a"):
        href = a.get_attribute("href") or ""
        # DuckDuckGo wraps links like //duckduckgo.com/l/?uddg=<real-url>
        if "uddg=" in href:
            href = unquote(parse_qs(urlparse(href).query).get("uddg", [""])[0])
        if ARTICLE_PATTERN.search(href):
            return href
    return None


def search_first_result(driver, keyword):
    """Search NHK World for the keyword and return the first article URL."""
    # Attempt 1: NHK World's own search page
    try:
        driver.get(NHK_SEARCH_URL.format(quote_plus(keyword)))
        return WebDriverWait(driver, 20).until(_find_article_link)
    except (TimeoutException, WebDriverException):
        pass

    # Attempt 2: site-restricted search engine query
    try:
        query = f"site:www3.nhk.or.jp/nhkworld/en/news {keyword}"
        driver.get(DDG_SEARCH_URL.format(quote_plus(query)))
        return WebDriverWait(driver, 20).until(_find_article_link)
    except (TimeoutException, WebDriverException):
        return None


def fetch_article_text(driver, url):
    """Open the article and return (title, body_text)."""
    driver.get(url)
    WebDriverWait(driver, 20).until(
        lambda d: len(d.find_elements(By.TAG_NAME, "p")) > 0
    )
    title = ""
    headings = driver.find_elements(By.TAG_NAME, "h1")
    if headings:
        title = headings[0].text.strip()

    paragraphs = [p.text.strip() for p in driver.find_elements(By.TAG_NAME, "p")]
    paragraphs = [p for p in paragraphs if len(p) > 40]  # skip menus / captions
    body = " ".join(paragraphs)

    if not body:  # fallback to meta description
        metas = driver.find_elements(By.CSS_SELECTOR, "meta[name='description']")
        if metas:
            body = metas[0].get_attribute("content") or ""
    return title, body