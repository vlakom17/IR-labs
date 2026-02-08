from pymongo import MongoClient
from bs4 import BeautifulSoup
from tqdm import tqdm

from parser_securitylab import parse_securitylab_article
from parser_wiki import parse_title, parse_summary, parse_article_text

RAW_DB = "ir_crawler"
RAW_COLLECTION = "pages"

CLEAN_DB = "ir_corpus"
CLEAN_COLLECTION = "docs"


def parse_wikipedia(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    return {
        "title": parse_title(soup),
        "summary": parse_summary(soup),
        "text": parse_article_text(soup),
    }


def main():
    client = MongoClient("mongodb://localhost:27017")

    raw = client[RAW_DB][RAW_COLLECTION]
    clean = client[CLEAN_DB][CLEAN_COLLECTION]

    clean.create_index("url", unique=True)

    total = raw.count_documents({})
    print(f"Found raw documents: {total}")

    ok, skipped = 0, 0

    for doc in tqdm(raw.find({})):
        url = doc.get("url")
        html = doc.get("html")
        source = doc.get("source")

        if not html or not source:
            skipped += 1
            continue

        try:
            if source == "securitylab" or source == "securitynews":
                parsed = parse_securitylab_article(html)
            elif source == "wikipedia":
                parsed = parse_wikipedia(html)
            else:
                skipped += 1
                continue

            title = parsed.get("title")
            text = parsed.get("text")

            if not title or not text or len(text) < 200:
                skipped += 1
                continue

            result = {
                "url": url,
                "source": source,
                "title": title,
                "summary": parsed.get("summary"),
                "text": text,
            }

            clean.update_one(
                {"url": url},
                {"$set": result},
                upsert=True
            )

            ok += 1

        except Exception:
            skipped += 1

    print("\nDone.")
    print(f"Saved: {ok}")
    print(f"Skipped: {skipped}")


if __name__ == "__main__":
    main()
