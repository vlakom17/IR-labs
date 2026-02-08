from pymongo import MongoClient
import unicodedata

client = MongoClient("mongodb://localhost:27017")
db = client["ir_corpus"]
collection = db["docs"]

out = open("corpus.tsv", "w", encoding="utf-8")

count = 0

for doc in collection.find({}, {"title": 1, "summary": 1, "text": 1}):
    doc_id = str(doc["_id"])

    title = doc.get("title", "")
    summary = doc.get("summary", "")
    text = doc.get("text", "")

    title = title if title else ""
    summary = summary if summary else ""
    text = text if text else ""

    full_text = title + "\n" + summary + "\n" + text

    full_text = full_text.replace("\t", " ")
    full_text = full_text.replace("\n", " ")
    full_text = unicodedata.normalize("NFC", full_text)
    out.write(doc_id + "\t" + full_text + "\n")
    count += 1

    if count % 1000 == 0:
        print("Exported:", count)

out.close()
print("Done. Total documents:", count)
