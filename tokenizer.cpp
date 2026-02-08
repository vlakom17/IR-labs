#include <iostream>
#include <fstream>
#include <string>
#include <chrono>
#include <vector>
#include <cstring>
#include <cstdlib>

// Подсчет частот
struct FreqNode {
    char* key;
    int key_len;
    unsigned int cnt;
    FreqNode* next;
};

static const int FREQ_BUCKETS = 500009;
FreqNode* freq_table[FREQ_BUCKETS] = {0};

unsigned int hash_bytes(const char* s, int len) {
    unsigned int h = 2166136261u;
    for (int i = 0; i < len; ++i) {
        h ^= (unsigned char)s[i];
        h *= 16777619u;
    }
    return h;
}

void freq_add(const char* s, int len) {
    unsigned int h = hash_bytes(s, len);
    int idx = (int)(h % FREQ_BUCKETS);

    for (FreqNode* p = freq_table[idx]; p; p = p->next) {
        if (p->key_len == len && std::memcmp(p->key, s, len) == 0) {
            p->cnt++;
            return;
        }
    }

    FreqNode* n = (FreqNode*)std::malloc(sizeof(FreqNode));
    n->key = (char*)std::malloc(len);
    std::memcpy(n->key, s, len);
    n->key_len = len;
    n->cnt = 1;
    n->next = freq_table[idx];
    freq_table[idx] = n;
}

void freq_dump(const char* filename) {
    std::ofstream out(filename, std::ios::binary);
    for (int i = 0; i < FREQ_BUCKETS; ++i) {
        for (FreqNode* p = freq_table[i]; p; p = p->next) {
            out.write(p->key, p->key_len);
            out << "\t" << p->cnt << "\n";
        }
    }
}


void stem_ru_en(std::string& w) {
    int n = (int)w.size();

    if (n > 4) {
        if (w.compare(n - 3, 3, "ing") == 0) {
            w.resize(n - 3);
            return;
        }
        if (w.compare(n - 3, 3, "ion") == 0) {
            w.resize(n - 3);
            return;
        }
        if (w.compare(n - 2, 2, "ed") == 0) {
            w.resize(n - 2);
            return;
        }
        if (w.compare(n - 2, 2, "er") == 0) {
            w.resize(n - 2);
            return;
        }
        if (w[n - 1] == 's') {
            w.resize(n - 1);
            return;
        }
    }

    static const char* ru_endings[] = {
        "ами","ями","ого","его","ому","ему",
        "ыми","ими","ете","ие","ые","ов","ев",
        "ий","ия","ая","ой","ую","ое","ым",
        "ью","ом","ем","ых","ет","ют","ть", 
        "ый","ок","ам","ах","их",
        "ей","им","ям","ях",
        "а","у","е","и","ы","о","ю","я"
        
    };

    for (const char* e : ru_endings) {
        int elen = (int)std::strlen(e);
        if (n > elen + 2 && w.compare(n - elen, elen, e) == 0) {
            w.resize(n - elen);
            return;
        }
    }
}

bool is_latin(unsigned char c) {
    return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z');
}

bool is_cyrillic(unsigned char c1, unsigned char c2) {
    if (c1 == 0xD0 && (c2 >= 0x90 && c2 <= 0xBF)) return true;
    if (c1 == 0xD1 && (c2 >= 0x80 && c2 <= 0x8F)) return true;
    if (c1 == 0xD0 && c2 == 0x81) return true;
    if (c1 == 0xD1 && c2 == 0x91) return true;
    return false;
}

void to_lower_cyrillic(unsigned char &c1, unsigned char &c2) {
    // от а до п
    if (c1 == 0xD0 && c2 >= 0x90 && c2 <= 0x9F) {
        c2 += 0x20;
    }
    // от р до я
    else if (c1 == 0xD0 && c2 >= 0xA0 && c2 <= 0xAF) {
        c1 = 0xD1;
        c2 -= 0x20;
    }
    // ё
    else if (c1 == 0xD0 && c2 == 0x81) {
        c1 = 0xD1;
        c2 = 0x91;
    }
}

unsigned char to_lower_latin(unsigned char c) {
    if (c >= 'A' && c <= 'Z') return c + 32;
    return c;
}

int main() {
    std::ifstream input("corpus.tsv", std::ios::binary);
    if (!input.is_open()) {
        std::cerr << "Не удалось открыть corpus.tsv\n";
        return 1;
    }

    size_t total_tokens = 0;
    size_t total_length = 0;
    bool skip_id = true;
    std::string word;
    int current_len = 0;
    auto start = std::chrono::high_resolution_clock::now();

    unsigned char c;
    while (input.read((char*)&c, 1)) {
        if (skip_id) {
            if (c == '\t') skip_id = false;
            continue;
        }

        if (c == '\n') {
            skip_id = true;
            goto flush;
        }

        // убираем ударение
        if (c == 0xCC) {
            unsigned char c2;
            if (input.read((char*)&c2, 1) && c2 == 0x81)
                continue;
        }

        // убираем неразрывный пробел
        if (c == 0xC2) {
            unsigned char c2;
            if (input.read((char*)&c2, 1) && c2 == 0xA0)
                goto flush;
        }

        if (is_latin(c)) {
            word += to_lower_latin(c);
            current_len++;

        }
        else if (c == 0xD0 || c == 0xD1) {
            unsigned char c2;
            if (input.read((char*)&c2, 1) && is_cyrillic(c, c2)) {

                to_lower_cyrillic(c, c2);

                word += c;
                word += c2;
                current_len++;
            }
            else goto flush;
        }
        // обрабатываем дефис по правилам токенизации
        else if (c == '-' && !word.empty()) {
            unsigned char next = input.peek();
            if (is_latin(next) || next == 0xD0 || next == 0xD1)
                word += c;
            else goto flush;
        }
        else {
        flush:
            if (current_len >= 3 && current_len <= 40) {
                //stem_ru_en(word);
                total_tokens++;
                total_length += current_len;
                //std::vector<char> buf(word.begin(), word.end());
                //freq_add(buf.data(), (int)buf.size());

            }
            word.clear();
            current_len = 0;
        }
    }

    // финальный токен
    if (current_len >= 3 && current_len <= 40) {
        //stem_ru_en(word);
        total_tokens++;
        total_length += current_len;
        //std::vector<char> buf(word.begin(), word.end());
        //freq_add(buf.data(), (int)buf.size());

    }


    auto end = std::chrono::high_resolution_clock::now();
    double seconds = std::chrono::duration<double>(end - start).count();

    input.clear();
    input.seekg(0, std::ios::end);
    size_t bytes = input.tellg();

    double kb = bytes / 1024.0;

    std::cout << "\n=== Tokenizer ===\n";
    std::cout << "Количество токенов: " << total_tokens << "\n";
    std::cout << "Средняя длина токена: "
              << (total_tokens ? (double)total_length / total_tokens : 0) << "\n";
    std::cout << "Время выполнения: " << seconds << " сек\n";
    std::cout << "Объём текста: " << kb << " KB\n";
    std::cout << "Скорость: " << kb / seconds << " KB/сек\n";
    //freq_dump("term_freq.tsv");
    //std::cout << "Сохранение в файл term_freq.tsv завершено\n";
    return 0;
}