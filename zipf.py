# python zipf.py
import matplotlib.pyplot as plt
import numpy as np

freqs = []

with open("term_freq.tsv", encoding="utf-8") as f:
    for line in f:
        parts = line.rstrip().split("\t")
        if len(parts) != 2:
            continue
        try:
            freq = int(parts[1])
            freqs.append(freq)
        except ValueError:
            continue


freqs.sort(reverse=True)

ranks = np.arange(1, len(freqs) + 1)
freqs = np.array(freqs)

C = freqs[0]

plt.figure(figsize=(8, 6))
plt.loglog(ranks, freqs, label="Corpus")
plt.loglog(ranks, C / ranks, linestyle="--", label="Zipf: C / r")

plt.xlabel("Rank")
plt.ylabel("Frequency")
plt.title("Zipf Law for Stemmed Tokens")
plt.legend()
plt.grid(True, which="major", linestyle="--", alpha=0.6)

plt.tight_layout()
plt.show()

