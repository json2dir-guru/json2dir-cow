#!/usr/bin/env python3
"""bf2cow.py -- transliterate a pure 8-command Brainfuck program into COW.

    python3 tools/bf2cow.py ../json2dir-brainfuck/json2dir.bf > json2dir.cow

Target: BigZaphod's reference interpreter (cow.cpp).  Two of its properties
shape the translation:

1. Cells are C ints (no 8-bit wrap-around), but json2dir.bf needs 8-bit wrapping
   cells.  So every Brainfuck cell becomes a block of four COW cells (after
   one unused COW cell at the start of the tape)

       A  X  Y  B        X = the byte (always 0..255), Y = 255 - X,
                         A = B = 0 (scratch)

   and each command is replaced by a fixed COW sequence:

       >  ->  moO x4                <  ->  mOo x4
       +  ->  if Y == 0 { move X into Y (X = 0, Y = 255) } else { X++; Y-- }
       -  ->  if X == 0 { move Y into X (X = 255, Y = 0) } else { X--; Y++ }
       [  ->  MOO (tests X)         ]  ->  moo
       .  ->  Moo  (X is nonzero, so Moo prints it)
       [-]   ->  move X into Y (X = 0, Y = 255)
       [-],  ->  the same, then Moo (X is 0, so Moo reads one byte), Y -= X

   The zero tests use the usual non-destructive if/else idiom: X is tested
   with A and the previous block's B, Y with B and the next block's A.  A '-' right after '[' needs
   no test (X is nonzero there).  A run of k > 1 '+' (or '-') becomes
   "n = k; while n { +; n-- }" with n in A (or B).  A prologue sets Y = 255 in
   the first TAPE blocks (json2dir.bf needs fewer than 30000 cells).

2. MOO, when its cell is 0, skips the instruction right after it WITHOUT looking
   at it before searching forward for the matching moo, and moo searches back
   skipping the instruction right before it.  So a MOO directly followed by
   MOO/moo, or a moo directly preceded by one, gets the no-op pair "moO mOo" in
   between; then "[[", "]]" and "[]" nest right.

A Brainfuck ',' is only accepted directly after "[-]" (json2dir.bf always reads
with "[-],").
"""

import re
import sys

TAPE = 30000          # Brainfuck cells that get Y = 255 in the prologue
A, X, Y, B = 0, 1, 2, 3
W = 4                 # COW cells per Brainfuck cell
PB = B - W            # the previous block's B (the unused cell for block 0)
NA = A + W            # the next block's A


def go(frm, to):
    return ">" * (to - frm) if to > frm else "<" * (frm - to)


def move(pos, src, dst):
    """dst += src; src = 0.  Pointer pos -> pos."""
    return go(pos, src) + "[-" + go(src, dst) + "+" + go(dst, src) + "]" + go(src, pos)


def if_zero(cell, flag, zero, then, other):
    """if cell == 0 { then } else { other }, cell preserved; flag and zero are
    the scratch cells at cell+d and cell+2d (d = +1 or -1).  Pointer at cell."""
    return (go(cell, flag) + "+" + go(flag, cell)
            + "[" + other + go(cell, flag) + "-]"
            + go(cell, flag) + "[" + go(flag, cell) + then + go(cell, flag) + "-" + go(flag, zero) + "]"
            + go(zero, cell))


# Each expansion starts and ends with the pointer on X.  'M' = Moo.
DEC = if_zero(X, A, PB, then=move(X, Y, X), other="-" + go(X, Y) + "+" + go(Y, X))
INC = go(X, Y) + if_zero(Y, B, NA, then=move(Y, X, Y),
                         other="-" + go(Y, X) + "+" + go(X, Y)) + go(Y, X)
LOOP_DEC = "-" + go(X, Y) + "+" + go(Y, X)
CLEAR = move(X, X, Y)
READ = CLEAR + "M" + "[-" + go(X, Y) + "-" + go(Y, A) + "+" + go(A, X) + "]" + move(X, A, X)


def repeat(k, step, n, helper):
    """step k times, counted down in n (helper builds big k; both 0 after)."""
    if k == 1:
        return step
    if k <= 16:
        count = go(X, n) + "+" * k
    else:
        a, r = divmod(k, 8)
        count = (go(X, helper) + "+" * 8 + "[" + go(helper, n) + "+" * a + go(n, helper) + "-]"
                 + go(helper, n) + "+" * r)
    return count + "[" + go(n, X) + step + go(X, n) + "-]" + go(n, X)


def prologue():
    # The pointer starts on the unused cell (PB of block 0).  B0 = 1 marks
    # block 0; walk to the last block and fill Y leftwards, A is the loop flag.
    def set255(pos):          # Y = 255, built in B's loop
        return go(pos, B) + "+" * 15 + "[" + go(B, Y) + "+" * 17 + go(Y, B) + "-]" + go(B, pos)
    body = ("-" + set255(A)                   # A = 0, Y = 255
            + "<" * W + "+"                   # previous block: A = 1
            + go(A, B) + "[-" + go(B, A) + "-" + go(A, B) + "]" + go(B, A))  # unless block 0
    return (go(PB, B) + "+" + ">" * (W * (TAPE - 1)) + go(B, A) + "+[" + body + "]"
            + set255(A) + go(A, X))


def expand(bf):
    code = "".join(ch for ch in bf if ch in "><+-.,[]")
    out = [prologue()]
    i = 0
    while i < len(code):
        ch = code[i]
        if code.startswith("[-],", i):
            out.append(READ)
            i += 4
        elif code.startswith("[-]", i):
            out.append(CLEAR)
            i += 3
        elif ch == ",":
            raise SystemExit("bf2cow: ',' at command %d is not preceded by [-]" % i)
        elif code.startswith("[-", i):
            out.append("[" + LOOP_DEC)
            i += 2
        elif ch in "+-":
            j = i
            while j < len(code) and code[j] == ch:
                j += 1
            if ch == "+":
                out.append(repeat(j - i, INC, A, B))
            else:
                out.append(repeat(j - i, DEC, B, A))
            i = j
        else:
            out.append({">": ">" * W, "<": "<" * W, ".": "M", "[": "[", "]": "]"}[ch])
            i += 1
    return "".join(out)


def cancel_moves(s):
    def fold(m):
        run = m.group(0)
        n = run.count(">") - run.count("<")
        return ">" * n if n > 0 else "<" * -n
    return re.sub(r"[<>]+", fold, s)


def pad(s):
    """Insert "><" (moO mOo) between a '[' and a following bracket and between
    a bracket and a following ']' (see note 2)."""
    return re.sub(r"(?<=\[)(?=[\[\]])|(?<=[\[\]])(?=\])", "><", s)


COW = {">": "moO", "<": "mOo", "+": "MoO", "-": "MOo", "M": "Moo", "[": "MOO", "]": "moo"}


def translate(bf):
    s = pad(cancel_moves(expand(bf)))
    depth = 0
    for ch in s:
        depth += (ch == "[") - (ch == "]")
        if depth < 0:
            raise SystemExit("bf2cow: unmatched ]")
    if depth:
        raise SystemExit("bf2cow: unmatched [")
    ops = [COW[ch] for ch in s]
    # No separators needed: every instruction is exactly three letters.
    return "\n".join("".join(ops[i:i + 32]) for i in range(0, len(ops), 32)) + "\n"


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: bf2cow.py program.bf > program.cow")
    with open(sys.argv[1], encoding="ascii") as f:
        sys.stdout.write(translate(f.read()))


if __name__ == "__main__":
    main()
