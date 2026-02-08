import re
from bs4 import BeautifulSoup


def clean_text(text: str) -> str:
    if not text:
        return ""

    # схлопываем пробелы и переносы
    text = re.sub(r"\s+", " ", text)

    # убираем пробелы перед пунктуацией
    text = re.sub(r"\s+([,.:;!?»])", r"\1", text)

    # убираем пробелы после открывающих скобок/кавычек
    text = re.sub(r"([(\[{«„‚])\s+", r"\1", text)

    # убираем пробелы перед закрывающими скобками/кавычками
    text = re.sub(r"\s+([)\]}»“’])", r"\1", text)

    return text.strip()


def get_meta(soup: BeautifulSoup, *, name: str | None = None, prop: str | None = None) -> str | None:
    if name:
        tag = soup.find("meta", attrs={"name": name})
    elif prop:
        tag = soup.find("meta", attrs={"property": prop})
    else:
        return None

    if tag and tag.get("content"):
        return clean_text(tag["content"])
    return None


def remove_noise(article: BeautifulSoup) -> None:

    for bad in article.find_all("div", class_=lambda c: c and (
        "banner-detailed" in c
        or "webinar-banner" in c
        or "promo-banner" in c
        or "share-block" in c
    )):
        bad.decompose()

    for bad in article.find_all(["script", "style", "noscript", "iframe"]):
        bad.decompose()



def parse_title(soup: BeautifulSoup) -> str | None:
    t = get_meta(soup, prop="og:title")
    if t:
        return t

    h1 = soup.find("h1", class_=lambda c: c and "page-title" in c)
    if h1:
        return clean_text(h1.get_text(" ", strip=True))

    if soup.title:
        return clean_text(soup.title.get_text(" ", strip=True))

    return None


def parse_summary(soup: BeautifulSoup) -> str | None:
    article = find_article_container(soup)
    if not article:
        return None

    remove_noise(article)

    # берём первый <p> как lead-аннотацию
    p = article.find("p")
    if not p:
        return None

    txt = clean_text(p.get_text(" ", strip=True))
    return txt if len(txt) >= 10 else None


def find_article_container(soup: BeautifulSoup):
    return soup.select_one('div.articl-text[itemscope]')


def parse_article_text(soup: BeautifulSoup) -> str | None:
    article = find_article_container(soup)
    if not article:
        return None

    remove_noise(article)

    texts: list[str] = []
    seen = set()
    first_p_skipped = False

    for tag in article.find_all(["p", "h2", "h3", "h4", "h5", "h6", "li"]):
        txt = clean_text(tag.get_text(" ", strip=True))

        if not txt:
            continue
        
        if txt in seen:
            continue

        seen.add(txt)

        if tag.name == "p" and not first_p_skipped:
            first_p_skipped = True
            continue

        if tag.name == "p" and len(txt) < 25:
            continue

        if tag.name == "h2":
            texts.append(f"\n# {txt}")
        elif tag.name == "h3":
            texts.append(f"\n## {txt}")
        elif tag.name == "h4":
            texts.append(f"\n### {txt}")
        elif tag.name == "h5":
            texts.append(f"\n#### {txt}")
        elif tag.name == "h6":
            texts.append(f"\n##### {txt}")
        elif tag.name == "li":
            texts.append(f"- {txt}")
        else:
            texts.append(txt)

    out = "\n".join(texts).strip()
    return out or None



def parse_securitylab_article(html: str, base_url: str = "https://www.securitylab.ru") -> dict:
   
    soup = BeautifulSoup(html, "lxml")

    title = parse_title(soup)
    summary = parse_summary(soup)
    text = parse_article_text(soup)

    return {
        "title": title,
        "summary": summary,
        "text": text,
    }



def main():
    filename = "secnews_5.html"

    with open(filename, encoding="utf-8") as f:
        html = f.read()

    data = parse_securitylab_article(html)

    print("=" * 50)
    print("TITLE")
    print(data["title"] or "Not found")

    print("\n" + "=" * 50)
    print("SUMMARY")
    print(data["summary"] or "Not found")

    print("\n" + "=" * 50)
    print("ARTICLE TEXT")
    if data["text"]:
        print(data["text"])
    else:
        print("No article text")

if __name__ == "__main__":
    main()