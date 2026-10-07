# json2dir-cow

json2dir in COW. `json2dir.cow` is `json2dir.bf` from [json2dir-brainfuck](https://github.com/json2dir-guru/json2dir-brainfuck), converted by `tools/bf2cow.py`. COW's cells are C ints, so the converter emulates 8-bit cells. The program runs on BigZaphod's reference `cow` interpreter, built with `-DNO_GREETINGS`. The POSIX sh launcher `json2dir` only frames stdin (one decimal-digit character per line) and runs the generated script.

    python3 tools/bf2cow.py ../json2dir-brainfuck/json2dir.bf > json2dir.cow
    JSON2DIR_COW=/path/to/cow ./json2dir < tree.json
