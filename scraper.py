import os
import re
import base64
from urllib.parse import quote_plus, urlparse, parse_qs, unquote

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

NHK_SEARCH_URL = "https://www3.nhk.or.jp/nhkworld/en/search/?q={}"
BING_SEARCH_URL = "https://www.bing.com/search?q={}"
DDG_SEARCH_URL = "https://html.duckduckgo.com/html/?q={}"

# NHK article URLs, new and old formats:
#   https://www3.nhk.or.jp/nhkworld/news/20261029de67448/index.html  (new)
#   https://www3.nhk.or.jp/nhkworld/en/news/20261030_12/             (old)
# The (?!search) part skips the /news/search/ link
ARTICLE_PATTERN = re.compile(r"nhk\.or\.jp/nhkworld/(en/)?news/(?!search)[\w/-]*\d")


def log(msg):
    print(f"[scraper] {msg}", flush=True)


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
        "--lang=en-US",
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    ]:
        opts.add_argument(arg)
    service = Service(os.getenv("CHROMEDRIVER", "/usr/bin/chromedriver"))
    driver = webdriver.Chrome(service=service, options=opts)
    driver.set_page_load_timeout(45)
    return driver


def _real_url(href):
    """Unwrap redirect links from DuckDuckGo and Bing."""
    if not href:
        return ""
    if "uddg=" in href:  # DuckDuckGo
        return unquote(parse_qs(urlparse(href).query).get("uddg", [""])[0])
    if "bing.com/ck/a" in href:  # Bing: u=a1<base64url>
        u = parse_qs(urlparse(href).query).get("u", [""])[0]
        if u.startswith("a1"):
            b64 = u[2:] + "=" * (-len(u[2:]) % 4)
            try:
                return base64.urlsafe_b64decode(b64).decode("utf-8", "ignore")
            except Exception:
                return ""
    return href


def _find_article_link(driver):
    """Return the first link on the page that points to an NHK news article."""
    for a in driver.find_elements(By.TAG_NAME, "a"):
        try:
            href = _real_url(a.get_attribute("href"))
        except WebDriverException:
            continue
        if ARTICLE_PATTERN.search(href):
            return href.split("#")[0]
    return None


def _try(driver, name, url, wait=20):
    """Open a search page and wait for an article link to appear."""
    try:
        driver.get(url)
        link = WebDriverWait(driver, wait).until(_find_article_link)
        log(f"{name}: found {link}")
        return link
    except (TimeoutException, WebDriverException) as e:
        try:
            n = len(driver.find_elements(By.TAG_NAME, "a"))
            log(f"{name}: no article link (page title='{driver.title}', links={n}) {type(e).__name__}")
        except Exception:
            log(f"{name}: failed {type(e).__name__}")
        return None


def search_first_result(driver, keyword):
    """Search NHK World for the keyword and return the first article URL."""
    q = quote_plus(keyword)
    site_q = quote_plus(f"site:www3.nhk.or.jp/nhkworld/news {keyword}")
    return (
        _try(driver, "NHK search", NHK_SEARCH_URL.format(q))
        or _try(driver, "Bing", BING_SEARCH_URL.format(site_q))
        or _try(driver, "DuckDuckGo", DDG_SEARCH_URL.format(site_q))
    )

BOILERPLATE = (
    "cookie", "privacy", "you will leave", "japan's only public media",
    "all rights reserved", "copyright", "javascript", "consent",
    "by clicking", "terms of use",
)


def _clean(paragraphs):
    """Drop short, duplicate and boilerplate paragraphs."""
    out, seen = [], set()
    for p in paragraphs:
        t = " ".join((p or "").split())
        low = t.lower()
        if len(t) < 40 or t in seen or any(b in low for b in BOILERPLATE):
            continue
        seen.add(t)
        out.append(t)
    return out


def fetch_article_text(driver, url):
    """Open the article and return (title, body_text)."""
    driver.get(url)

    # Wait until real article paragraphs appear (not just the cookie banner)
    try:
        WebDriverWait(driver, 25).until(
            lambda d: _clean([e.text for e in d.find_elements(By.TAG_NAME, "p")])
        )
    except TimeoutException:
        log("article: real paragraphs did not load in time")

    title = ""
    h1 = driver.find_elements(By.TAG_NAME, "h1")
    if h1:
        title = h1[0].text.strip()

    # Prefer paragraphs inside the article area of the page
    body = ""
    for sel in ["article p", "main p", "[class*='article'] p",
                "[class*='body'] p", "[class*='content'] p", "p"]:
        paras = _clean([e.text for e in driver.find_elements(By.CSS_SELECTOR, sel)])
        if paras:
            body = " ".join(paras)
            log(f"article: selector '{sel}' gave {len(paras)} paragraphs")
            break

    # If the body is still short, add the page's meta description
    if len(body) < 150:
        for m in driver.find_elements(
            By.CSS_SELECTOR, "meta[property='og:description'], meta[name='description']"
        ):
            desc = (m.get_attribute("content") or "").strip()
            if desc and desc not in body:
                body = (desc + " " + body).strip()
                break

    if not body:
        body = title

    log(f"article: title='{title}', chars={len(body)}")
    return title, body