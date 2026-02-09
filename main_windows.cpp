#include <iostream>
#include <fstream>
#include <string>
#include <vector>
#include <cstring>
#include <windows.h>
#include <shellapi.h>

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

// Индекс
struct Node {
    std::string term;
    std::vector<std::string> docs;
};

static const int BUCKETS = 100003;
std::vector<Node> table[BUCKETS];

unsigned hash_term(const std::string& s) {
    unsigned h = 0;
    for (unsigned char c : s)
        h = h * 31 + c;
    return h % BUCKETS;
}

void add_to_index(const std::string& term, const std::string& doc_id) {
    unsigned h = hash_term(term);
    for (auto& node : table[h]) {
        if (node.term == term) {
            if (node.docs.empty() || node.docs.back() != doc_id)
                node.docs.push_back(doc_id);
            return;
        }
    }
    table[h].push_back({term, {doc_id}});
}

std::vector<std::string>* get_postings(const std::string& term){
    unsigned h = hash_term(term);
    for (auto& node : table[h])
        if (node.term == term)
            return &node.docs;
    return nullptr;
}

// Операторы поиска
std::vector<std::string> op_and(
    const std::vector<std::string>& a,
    const std::vector<std::string>& b
) {
    std::vector<std::string> res;
    for (const auto& x : a) {
        for (const auto& y : b) {
            if (x == y) {
                res.push_back(x);
                break;
            }
        }
    }
    return res;
}

std::vector<std::string> op_or(
    const std::vector<std::string>& a,
    const std::vector<std::string>& b
) {
    std::vector<std::string> res = a;

    for (const auto& x : b) {
        bool found = false;
        for (const auto& y : res) {
            if (x == y) {
                found = true;
                break;
            }
        }
        if (!found)
            res.push_back(x);
    }
    return res;
}

std::vector<std::string> op_not(
    const std::vector<std::string>& a,
    const std::vector<std::string>& b
) {
    std::vector<std::string> res;
    for (const auto& x : a) {
        bool found = false;
        for (const auto& y : b) {
            if (x == y) {
                found = true;
                break;
            }
        }
        if (!found)
            res.push_back(x);
    }
    return res;
}

// Токенизация и стемминг
void tokenize_and_stem(
    const std::string& text,
    std::vector<std::string>& out_tokens
) {
    std::string token;
    int char_len = 0;

    for (size_t pos = 0; pos < text.size(); pos++) {
        unsigned char c = text[pos];

        // ударение
        if (c == 0xCC && pos + 1 < text.size() && (unsigned char)text[pos + 1] == 0x81) {
            pos++;
            continue;
        }

        // неразрывный пробел
        if (c == 0xC2 && pos + 1 < text.size() && (unsigned char)text[pos + 1] == 0xA0) {
            pos++;
            goto flush;
        }

        if (is_latin(c)) {
            token += to_lower_latin(c);
            char_len++;
        }
        else if (c == 0xD0 || c == 0xD1) {
            if (pos + 1 < text.size()) {
                unsigned char c2 = text[pos + 1];
                if (is_cyrillic(c, c2)) {
                    to_lower_cyrillic(c, c2);
                    token += c;
                    token += c2;
                    char_len++;
                    pos++;
                } else goto flush;
            }
            else {
                goto flush;
            }
        }
        // учет дефиса
        else if (c == '-' && !token.empty()) {
            unsigned char next = (pos + 1 < text.size()) ? text[pos + 1] : 0;
            if (is_latin(next) || next == 0xD0 || next == 0xD1)
                token += c;
            else goto flush;
        }
        else {
        flush:
            if (token == "or" || token == "and" || token == "not") {
                out_tokens.push_back(token);
            }
            else if (char_len >= 3 && char_len <= 40) {
                stem_ru_en(token);
                out_tokens.push_back(token);
            }
            token.clear();
            char_len = 0;
        }
    }
    if (token == "or" || token == "and" || token == "not") {
        out_tokens.push_back(token);
    }
    else if (char_len >= 3 && char_len <= 40) {
        stem_ru_en(token);
        out_tokens.push_back(token);
    }
}

std::vector<std::string> boolean_search(const std::string& query) {
    std::vector<std::string> tokens;
    tokenize_and_stem(query, tokens);

    std::vector<std::string> result;
    bool has_result = false;
    std::string op = "and";

    for (const std::string& t : tokens) {

        if (t == "and" || t == "or" || t == "not") {
            op = t;
            continue;
        }

        std::vector<std::string> docs;
       
        if (auto* p = get_postings(t))
            docs = *p;

        if (!has_result) {
            result = docs;
            has_result = true;
        } else {
            if (op == "and") result = op_and(result, docs);
            else if (op == "or") result = op_or(result, docs);
            else if (op == "not") result = op_not(result, docs);
            op = "and";
        }
    }
    return result;
}

int main() {
    SetConsoleOutputCP(CP_UTF8);

    std::ifstream input("corpus.tsv", std::ios::binary);
    if (!input.is_open()) {
        std::cerr << "Cannot open corpus.tsv\n";
        return 1;
    }

    std::string line;

    while (std::getline(input, line)) {
        size_t tab = line.find('\t');
        if (tab == std::string::npos) {
            continue;
        }

        std::string doc_id = line.substr(0, tab);
        std::string text = line.substr(tab + 1);


        std::vector<std::string> tokens;
        tokenize_and_stem(text, tokens);

        for (const auto& tok : tokens) {
            add_to_index(tok, doc_id);
        }

    }

    // Получение аргументов (UTF-16)
    int argcW = 0;
    LPWSTR* argvW = CommandLineToArgvW(GetCommandLineW(), &argcW);

    if (!argvW || argcW < 2) {
        std::cout << "Usage: main.exe <query>\n";
        std::cout << "Example: main.exe информация AND поиск\n";
        if (argvW) LocalFree(argvW);
        return 0;
    }

    // Конвертация UTF-16 -> UTF-8
    std::string query;

    for (int i = 1; i < argcW; i++) {
        int len = WideCharToMultiByte(
            CP_UTF8, 0,
            argvW[i], -1,
            nullptr, 0,
            nullptr, nullptr
        );

        std::string tmp(len - 1, '\0');

        WideCharToMultiByte(
            CP_UTF8, 0,
            argvW[i], -1,
            tmp.data(), len,
            nullptr, nullptr
        );

        if (i > 1) query += " ";
        query += tmp;
    }

    LocalFree(argvW);

    auto res = boolean_search(query);

    std::cout << "Found: " << res.size() << " documents\n";
    for (int i = 0; i < (int)res.size() && i < 7; i++) {
        std::cout << " - doc_id: " << res[i] << "\n";
    }

    return 0;

}
