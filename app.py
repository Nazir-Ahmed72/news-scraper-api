from flask import Flask, jsonify, request

from scraper import make_driver, search_first_result, fetch_article_text
from summarizer import summarize

REGISTRATION = "FA23-BDS-032"
NEWS_SOURCE = "NHK World Japan"

app = Flask(__name__)
app.json.sort_keys = False  # keep keys in the order of the spec


@app.get("/")
def home():
    return f"""
    <html><head><title>{REGISTRATION} - News API</title></head>
    <body style="font-family:sans-serif;padding:40px">
      <h1>Registration Number: {REGISTRATION}</h1>
      <p>News Source: {NEWS_SOURCE}</p>
      <p>Usage: <code>/get?keyword=japan</code></p>
    </body></html>
    """


@app.get("/get")
def get_news():
    keyword = request.args.get("keyword", "").strip()
    result = {
        "registration": REGISTRATION,
        "newssource": NEWS_SOURCE,
        "keyword": keyword,
        "url": "",
        "summary": "",
    }
    if not keyword:
        result["summary"] = "Please provide a keyword, e.g. /get?keyword=japan"
        return jsonify(result), 400

    driver = None
    try:
        driver = make_driver()
        url = search_first_result(driver, keyword)
        if not url:
            result["summary"] = f"No {NEWS_SOURCE} article found for '{keyword}'."
            return jsonify(result)

        title, body = fetch_article_text(driver, url)
        result["url"] = url
        result["summary"] = summarize(body)
        return jsonify(result)
    except Exception as e:
        result["summary"] = f"Error while scraping: {e}"
        return jsonify(result), 500
    finally:
        if driver:
            driver.quit()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7000)