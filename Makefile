CXX = g++
CXXFLAGS = -std=c++17 -O2 -Wall

MAIN = main
TOKENIZER = tokenizer

all: $(MAIN) $(TOKENIZER)

$(MAIN): main.cpp
	$(CXX) $(CXXFLAGS) main.cpp -o $(MAIN)

$(TOKENIZER): tokenizer.cpp
	$(CXX) $(CXXFLAGS) tokenizer.cpp -o $(TOKENIZER)

# Очистка для Windows
clean:
	del /Q $(MAIN).exe $(TOKENIZER).exe 2>nul

# Очистка для Linux:
# clean:
# 	rm -f main tokenizer main.exe tokenizer.exe
