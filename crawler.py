import sys
import time
import hashlib
import yaml
import requests
import re
import requests
import time
import urllib3
from urllib.parse import urlparse, urlunparse, urljoin, unquote, quote
from pymongo import MongoClient
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def normalize_url(url: str) -> str:
    p = urlparse(url.strip())
    p = p._replace(fragment="")
    netloc = p.netloc.lower()
    path = p.path
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    return urlunparse((p.scheme, netloc, path, p.params, p.query, ""))


def save_article(pages, url, html, source):
    ts = int(time.time())
    content_hash = hashlib.sha256(html.encode("utf-8", errors="ignore")).hexdigest()

    old = pages.find_one({"url": url})
    if old and old.get("content_hash") == content_hash:
        pages.update_one({"url": url}, {"$set": {"fetched_at": ts}})
        print("Not changed:", url)
        return

    pages.update_one(
        {"url": url},
        {"$set": {
            "url": url,
            "html": html,
            "source": source,
            "fetched_at": ts,
            "content_hash": content_hash
        }},
        upsert=True
    )
    print("Saved:", url)

HEADERS = {
    "User-Agent": "WikiCrawler/1.0 (educational project)"
}

API_URL = "https://ru.wikipedia.org/w/api.php"


def normalize_title(title: str) -> str:
    title = title.strip()
    if title.startswith("Категория:"):
        title = title[len("Категория:"):]
    return title.replace(" ", "_")


def fetch_wiki_html(title: str) -> str | None:
    safe = quote(title)

    rest_url = f"https://ru.wikipedia.org/api/rest_v1/page/html/{safe}"
    try:
        r = requests.get(rest_url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            return r.text
    except:
        pass

    classic_url = f"https://ru.wikipedia.org/wiki/{safe}"
    try:
        r = requests.get(classic_url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            return r.text
    except:
        pass

    return None


def get_category_members(category_title: str):
    category_title = normalize_title(category_title)
    full_title = f"Категория:{category_title}"

    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": full_title,
        "cmtype": "page|subcat",
        "cmlimit": 500,
        "format": "json"
    }

    members = []
    session = requests.Session()

    while True:
        r = session.get(API_URL, params=params, headers=HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json()

        members.extend(data["query"]["categorymembers"])

        if "continue" not in data:
            break

        params.update(data["continue"])

    return members


def crawl_wikipedia(cfg, pages, queue, headers):
    delay = cfg["logic"].get("delay", 0.5)
    max_docs = cfg.get("limits", {}).get("wikipedia")
    max_depth = cfg["logic"].get("max_depth", 8)

    task = queue.find_one_and_update(
        {"status": "pending", "source": "wikipedia"},
        {"$set": {"status": "processing"}}
    )

    if not task:
        return False

    title = normalize_title(task["title"])
    depth = task.get("depth", 0)
    cursor = task.get("cursor", 0)

    print(f"\n[WIKI] category={title} depth={depth} cursor={cursor}")

    try:
        members = get_category_members(title)

        total = len(members)
        print(f"    found {total} members")

        for i in range(cursor, total):
            time.sleep(delay)

            m = members[i]

            queue.update_one(
                {"_id": task["_id"]},
                {"$set": {"cursor": i}}
            )

            # Статья
            if m["ns"] == 0:
                if max_docs:
                    count = pages.count_documents({"source": "wikipedia"})
                    if count >= max_docs:
                        print(f"[WIKI] Limit reached: {count}/{max_docs}")
                        return False

                page_title = normalize_title(m["title"])
                url = f"https://ru.wikipedia.org/wiki/{page_title}"

                print(f"    [{i+1}/{total}] ARTICLE {page_title}")

                html = fetch_wiki_html(page_title)
                if not html:
                    print(f"        FAIL")
                    continue

                save_article(pages, url, html, "wikipedia")

            # Подкатегория
            elif m["ns"] == 14 and depth < max_depth:
                subcat = normalize_title(m["title"])

                print(f"    [{i+1}/{total}] SUBCATEGORY {subcat}")

                queue.update_one(
                    {"title": subcat, "source": "wikipedia"},
                    {"$setOnInsert": {
                        "title": subcat,
                        "source": "wikipedia",
                        "status": "pending",
                        "depth": depth + 1,
                        "cursor": 0
                    }},
                    upsert=True
                )

        queue.update_one(
            {"_id": task["_id"]},
            {"$set": {
                "status": "done",
                "cursor": 0,
                "last_crawled": int(time.time())
            }}
        )

        print(f"[WIKI] finished category={title}")
        return True

    except KeyboardInterrupt:
        print("\n[WIKI] Ctrl+C received")

        # возвращаем задачу обратно в очередь
        queue.update_one(
            {"_id": task["_id"]},
            {"$set": {"status": "pending"}}
        )

        raise

    except Exception as e:
        print(f"[WIKI ERROR] {e}")

        # при любой ошибке тоже возвращаем задачу в pending
        queue.update_one(
            {"_id": task["_id"]},
            {"$set": {"status": "pending"}}
        )

        return True

def is_securitylab_article(url: str) -> bool:
    parsed = urlparse(url)

    if parsed.netloc != "www.securitylab.ru":
        return False

    return bool(re.fullmatch(r"/analytics/\d+\.php", parsed.path))


def extract_securitylab_articles(html):
    soup = BeautifulSoup(html, "html.parser")
    links = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        full = normalize_url(urljoin("https://www.securitylab.ru", href))

        if is_securitylab_article(full) and full not in seen:
            links.append(full)
            seen.add(full)

    return links

def is_securitylab_news(url: str) -> bool:
    parsed = urlparse(url)

    if parsed.netloc != "www.securitylab.ru":
        return False

    path = parsed.path

    pattern = r"^/news/\d+\.php$"

    return bool(re.fullmatch(pattern, path))

# Та же функция, что и для articles - наглядно разделяем разделы новостей/статей для удобства
def extract_securitylab_news(html):
    soup = BeautifulSoup(html, "html.parser")
    links = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        full = normalize_url(urljoin("https://www.securitylab.ru", href))

        if is_securitylab_news(full) and full not in seen:
            links.append(full)
            seen.add(full)

    return links


def crawl_securitynews(cfg, pages, state, headers, max_pages=1800):
    delay = cfg["logic"].get("delay", 0.8)
    max_docs = cfg.get("limits", {}).get("securitynews")

    progress = state.find_one({"name": "securitynews"}) or {"page": 1, "index": 0}
    page = progress["page"]
    start_index = progress["index"]

    print(f"[RESUME] securitynews page={page}, index={start_index}")

    try:
        for p in range(page, max_pages + 1):

            url = f"https://www.securitylab.ru/news/page1_{p}.php"
            print(f"\n[PAGE {p}] {url}")

            r = requests.get(url, headers=headers, timeout=10, verify=False)
            if r.status_code != 200:
                print(f"[HTTP {r.status_code}] stopping crawl")
                return

            r.encoding = "utf-8"
            html = r.text
            articles = list(extract_securitylab_news(html))

            print(f"  found articles: {len(articles)}")

            for i in range(start_index, len(articles)):
                if max_docs:
                    count = pages.count_documents({"source": "securitynews"})
                    if count >= max_docs:
                        print(f"[SECURITYNEWS] Limit reached: {count}/{max_docs}")
                        return

                article = articles[i]
                print(f"    [{p}:{i}] {article}")

                r2 = requests.get(article, headers=headers, timeout=10, verify=False)
                if r2.status_code == 200:
                    r2.encoding = "utf-8"
                    save_article(pages, article, r2.text, "securitynews")

                state.update_one(
                    {"name": "securitynews"},
                    {"$set": {"page": p, "index": i + 1}},
                    upsert=True
                )

                time.sleep(delay)

            start_index = 0

    except KeyboardInterrupt:
        print("\n[STOP] Ctrl+C received. Progress already saved. Safe to restart.")
        return


def crawl_securityarticles(cfg, pages, state, headers, max_pages=60):
    delay = cfg["logic"].get("delay", 0.8)
    max_docs = cfg.get("limits", {}).get("securitylab")

    progress = state.find_one({"name": "securitylab"}) or {"page": 1, "index": 0}
    page = progress["page"]
    start_index = progress["index"]

    print(f"[RESUME] securitylab page={page}, index={start_index}")

    try:
        for p in range(page, max_pages + 1):

            url = f"https://www.securitylab.ru/analytics/page1_{p}.php"
            print(f"\n[SECURITYLAB PAGE {p}] {url}")

            r = requests.get(url, headers=headers, timeout=10, verify=False)
            if r.status_code != 200:
                print(f"[HTTP {r.status_code}] stopping crawl")
                return
            r.encoding = "utf-8"
            html = r.text
            articles = list(extract_securitylab_articles(html))

            print(f"  found articles: {len(articles)}")

            for i in range(start_index, len(articles)):
                if max_docs:
                    count = pages.count_documents({"source": "securitylab"})
                    if count >= max_docs:
                        print(f"[SECURITYLAB] Limit reached: {count}/{max_docs}")
                        return

                article = articles[i]
                print(f"    [{p}:{i}] {article}")

                r2 = requests.get(article, headers=headers, timeout=10, verify=False)
                if r2.status_code == 200:
                    save_article(pages, article, r2.text, "securitylab")

                state.update_one(
                    {"name": "securitylab"},
                    {"$set": {"page": p, "index": i + 1}},
                    upsert=True
                )

                time.sleep(delay)

            start_index = 0

    except KeyboardInterrupt:
        print("\n[STOP] SecurityLab interrupted. Progress saved.")
        return

def main():

    with open(sys.argv[1], "r", encoding="utf-8-sig") as f:
        cfg = yaml.safe_load(f)

    client = MongoClient(cfg["db"]["uri"])
    db = client[cfg["db"]["name"]]

    pages = db["pages"]
    queue = db["queue"]
    state = db["state"]

    pages.create_index("url", unique=True)

    queue.create_index(
        [("title", 1), ("source", 1)],
        unique=True,
        partialFilterExpression={"source": "wikipedia"}
    )
    queue.create_index("status")
    queue.create_index("source")

    headers = {"User-Agent": cfg["logic"].get("user_agent", "IR-Crawler")}


    restored = queue.update_many(
        {"status": "processing", "source": "wikipedia"},
        {"$set": {"status": "pending"}}
    )
    if restored.modified_count:
        print(f"[INIT] Restored {restored.modified_count} wiki tasks")


    for seed in cfg.get("seeds", []):
        if seed["source"] != "wikipedia":
            continue

        parsed = urlparse(seed["url"])
        title = unquote(parsed.path.replace("/wiki/", ""))

        queue.update_one(
            {"title": title, "source": "wikipedia"},
            {"$setOnInsert": {
                "title": title,
                "source": "wikipedia",
                "status": "pending",
                "depth": 0,
                "cursor": 0
            }},
            upsert=True
        )
    
    # Wikipedia Recrawl
    recrawl_after = cfg["logic"].get("recrawl_after_seconds", 86400)
    threshold = int(time.time()) - recrawl_after

    recrawl_count = 0

    for doc in pages.find({"fetched_at": {"$lt": threshold}, "source": "wikipedia"}):
        parsed = urlparse(doc["url"])
        title = unquote(parsed.path.replace("/wiki/", ""))

        queue.update_one(
            {"title": title, "source": "wikipedia"},
            {"$set": {"status": "pending"}},
            upsert=True
        )

        recrawl_count += 1

    if recrawl_count:
        print(f"[INIT] Scheduled {recrawl_count} wikipedia docs for recrawl")

    # Security News Recrawl
    recrawl_after = cfg["logic"].get("recrawl_after_seconds", 400000)
    threshold = int(time.time()) - recrawl_after

    recrawl_count = 0

    for doc in pages.find({"source": "securitynews", "fetched_at": {"$lt": threshold}}, {"url": 1}):
        url = doc["url"]

        print(f"[SECURITYLAB RECRAWL] scheduled: {url}")

        state.update_one(
            {"name": "securitynews_force"},
            {"$set": {"url": url}},
            upsert=True
        )

        try:
            r = requests.get(url, headers=headers, timeout=10, verify=False)
            if r.status_code == 200:
                html = r.content.decode("utf-8", errors="replace")
                save_article(pages, url, html, "securitynews")
            else:
                print(f"[SECURITYLAB RECRAWL] status {r.status_code}: {url}")

        except Exception as e:
            print(f"[SECURITYLAB RECRAWL] error for {url}: {e}")

        time.sleep(cfg["logic"].get("delay", 0.8))
        recrawl_count += 1

    if recrawl_count:
        print(f"[INIT] Scheduled {recrawl_count} securitynews documents for recrawl")


    # Security Articles Recrawl
    recrawl_after = cfg["logic"].get("recrawl_after_seconds", 400000)
    threshold = int(time.time()) - recrawl_after

    recrawl_count = 0

    for doc in pages.find({"source": "securitylab", "fetched_at": {"$lt": threshold}}, {"url": 1}):
        url = doc["url"]

        print(f"[SECURITYLAB RECRAWL] scheduled: {url}")

        state.update_one(
            {"name": "securitylab_force"},
            {"$set": {"url": url}},
            upsert=True
        )

        r = requests.get(url, headers=headers, timeout=10, verify=False)
        if r.status_code == 200:
            r.encoding = "utf-8"
            save_article(pages, url, r.text, "securitylab")

        time.sleep(cfg["logic"].get("delay", 0.8))
        recrawl_count += 1

    if recrawl_count:
        print(f"[INIT] Scheduled {recrawl_count} securityarticles documents for recrawl")


    try:
        print("\n[START] Crawling started\n")

        crawl_securityarticles(cfg, pages, state, headers)
        crawl_securitynews(cfg, pages, state, headers)

        while True:
            worked = crawl_wikipedia(cfg, pages, queue, headers)
            if not worked:
                print("\n[STOP] Wikipedia queue empty.")
                break

    except KeyboardInterrupt:
        print("\n[STOP] Interrupted by user. Safe to restart, progress saved.")

if __name__ == "__main__":
    main()