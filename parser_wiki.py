import re
from bs4 import BeautifulSoup

def parse_title(soup):
    if soup.title:
        return soup.title.get_text(strip=True)
    return None

def parse_summary(soup):
    texts = []

    for tag in soup.find_all(["p", "h2"]):

        if tag.name == "h2":
            break

        if tag.find_parent(class_="ambox"):
            continue

        text = clean_text(tag.get_text(" ", strip=True))
        if not text:
            continue

        if len(text) < 30:
            continue

        texts.append(text)

    return "\n\n".join(texts)

def parse_article_text(soup):
    texts = []
    in_article = False  # False до первого h2

    stop_sections = {
        "См. также",
        "Примечания",
        "Ссылки",
        "Список литературы",
    }

    for tag in soup.find_all(["p", "h2", "h3", "h4", "h5", "h6", "li", "dd", "pre", "code"]):

        if tag.find_parent(class_="ambox"):
            continue

        text = clean_text(tag.get_text(" ", strip=True))
        if not text:
            continue
        
        if text.lower() == "содержание":
            continue

        if re.match(r"^\d+(\.\d+)*\s+", text):
            continue
        
        if tag.name == "h2":
            if text in stop_sections:
                break

            in_article = True
            texts.append(f"\n# {text}")
            continue

        if not in_article:
            continue

        if tag.name == "h3":
            texts.append(f"\n## {text}")
            continue

        if tag.name == "h4":
            texts.append(f"\n### {text}")
            continue

        if tag.name == "h5":
            texts.append(f"\n#### {text}")
            continue

        if tag.name == "h6":
            texts.append(f"\n##### {text}")
            continue

        # элементы списков
        if tag.name == "li":
            texts.append(f"- {text}")
            continue

        # обычные абзацы
        if tag.name == "p":
            if len(text) < 30:
                continue
            texts.append(text)
            
        # кодовые блоки
        if tag.name in {"pre", "code"}:
            code_text = tag.get_text()
            if code_text.strip():
                texts.append(f"\n```\n{code_text.strip()}\n```")
            continue

        # определения
        if tag.name == "dd":
            texts.append(f"- {text}")
            continue

    return "\n".join(texts)


def clean_text(text: str) -> str:

    # убираем сноски вида [1], [ 2 ] и т д
    text = re.sub(r"\[\s*\d+\s*\]", "", text)

    text = re.sub(r"\[\s*[A-Za-zА-Яа-я]\s*\d+\s*\]", "", text)
    
    
    text = re.sub(r"\[(источник не указан|не подтверждено|уточнить)[^\]]*\]", "", text, flags=re.IGNORECASE)

    # убираем пробелы перед пунктуацией
    text = re.sub(r"\s+([,.:;!?»])", r"\1", text)

    # убираем пробелы после открывающих скобок и кавычек
    text = re.sub(r"([(\[{«„‚])\s+", r"\1", text)

    # убираем пробелы перед закрывающими скобками и кавычками
    text = re.sub(r"\s+([)\]}»“’])", r"\1", text)

    text = re.sub(r"\{\\displaystyle.*?\}", "", text)

    # схлопываем все лишние пробелы
    text = re.sub(r"\s+", " ", text).strip()

    return text.strip()

def main():
    with open("wiki_0.html", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "lxml")

    print("=" * 50)
    print("TITLE")
    title = parse_title(soup)
    print(title if title else "Title Not found")

    print("\n" + "=" * 50)
    print("SUMMARY")
    summary = parse_summary(soup)
    print(summary if summary else "Not found")

    print("\n" + "=" * 50)
    print("ARTICLE TEXT")
    text = parse_article_text(soup)
    if text:
        print(text)
    else:
        print("No article text")

if __name__ == "__main__":
    main()
