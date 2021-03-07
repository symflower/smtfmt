#!/usr/bin/env python3

from pyparsing import (
    ZeroOrMore,
    Group,
    Optional,
    restOfLine,
    nestedExpr,
    quotedString,
    Forward,
    ParseResults,
)
from typing import Tuple
import re
import sys
from os.path import basename

COLUMN_LIMIT = 80
INDENT = " " * 2

USAGE = f"""\
usage: {basename(sys.argv[0])} < input.lisp

Pretty-print a balanced set of parentheses.

Short expressions (< {COLUMN_LIMIT} characters) are printed inline.
Larger expressions are broken up in lines and aligned.
"""

def format_lisp(input: str) -> str:
    parser = lisp_parser()
    paragraphs = re.split(r'\n{2,}', input)
    return "\n".join(format_terms(parser.parseString(p)) for p in paragraphs)

def lisp_parser() -> Forward:
    comment = Group(";" + Optional(restOfLine))
    return ZeroOrMore(nestedExpr(ignoreExpr=(quotedString | comment)) ^ comment)

def format_terms(xs: ParseResults) -> str:
    return "".join(format_term(x, 0, False) + "\n" for x in xs)

def iscomment(xs: ParseResults) -> bool:
    return len(xs) == 2 and xs[0] == ";"

def isatom(xs: ParseResults) -> bool:
    return isinstance(xs, str)

def format_term(xs: ParseResults, level: int, first: bool) -> str:
    # Insert comments at the current indentation level.
    if iscomment(xs):
        return "".join(xs)
    # Atoms are easy, always print them as-is.
    if isatom(xs):
        return xs
    ok, oneline = format_term_oneline(xs)
    if ok and len(oneline) < COLUMN_LIMIT:  # Small terms on one line
        return oneline
    # Long expression, break lines and align subexpressions on the same level.
    s = "("
    if not iscomment(xs[0]) and not isatom(xs[0]):
        s += "\n"
    # General lists with line breaks after each element.
    for i in range(len(xs)):
        x = xs[i]
        s += format_term(x, level + 1, i == 0)
        if i != len(xs) - 1:
            s += "\n"
    s += ")"
    indented = ""
    first = True
    for line in s.splitlines(keepends=True):
        if not first:
            indented += INDENT
        indented += line
        first = False
    return indented

def format_term_oneline(xs: ParseResults) -> Tuple[bool, str]:
    if iscomment(xs):
        return False, ""
    if isatom(xs):
        return True, xs
    terms = []
    for x in xs:
        ok, s = format_term_oneline(x)
        if not ok:
            return False, ""
        terms += [s]
    return True, "(" + " ".join(terms) + ")"

if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(USAGE)
        sys.exit(1)
    else:
        print(format_lisp(sys.stdin.read()), end="")

TESTDATA = (
    """
(simple x)

(list (list (fun) (number 0.0.0.0:5900) atom))

;; comment

(list
  ; Comments are aligned too!
  (string "string literal with("))

(let
  ; List of lists.
  ((x y) (y x)))

; Short expressions on one line
(let ((x y) (y x)))

; Longer expressions are broken up and aligned.
(assert
  (=
    x
    (Pointer
      true
      #x00000002
      (variant_node1 (Pointer true #x00000001 variant_leaf1)))))

(declare-datatypes
  ((Pointer 0) (Any 0))
  (
    ((Pointer (? Bool) (address (_ BitVec 32)) (* Any)))
    (
      (variant_leaf1)
      (variant_leaf2)
      (variant_node1 (node1.next Pointer))
      (variant_node2 (node2.next Pointer)))))
""".strip()
    + "\n"
)

def test_format_lisp() -> None:
    assert format_lisp(TESTDATA) == TESTDATA
