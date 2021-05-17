#!/usr/bin/env python3

import re
import sys
from typing import Tuple

######################################################################
# Generic parser builders
######################################################################
# Here, a parser is a function of the following form:
# f(input: str) -> (success: bool, output: str, value)

def regex(pat: str, func=lambda x: None):
    def f(s: str):
        m = re.compile(pat).match(s)
        if m:
            return True, s[m.end(0) :], func(s[: m.end(0)])
        else:
            return False, s, None
    return f

def seq(*parsers):
    def f(s: str):
        cur_s = s
        values = list()
        for parser in parsers:
            succ, cur_s, value = parser(cur_s)
            if not succ:
                return False, s, None
            if value:
                values.append(value)
        return True, cur_s, values
    return f

def choice(*parsers):
    def f(s: str):
        cur_s = s
        for parser in parsers:
            succ, cur_s, value = parser(cur_s)
            if succ:
                return True, cur_s, value
        return False, s, None
    return f

def zeroOrMore(parser):
    def f(s: str):
        cur_s = s
        values = list()
        while True:
            succ, cur_s, value = parser(cur_s)
            if not succ:
                break
            values.append(value)
        return True, cur_s, values
    return f

def oneOrMore(parser):
    def f(s: str):
        if not parser(s)[0]:
            return False, s, None
        return zeroOrMore(parser)(s)
    return f

######################################################################
# Specific parser builders
######################################################################
# Program ::= (blankline | Comment | SExpr)+
# SExpr   ::= '(' Expr* ')'
# Expr    ::= blankline | Comment | SExpr | atom

def lparen():
    return regex(r"^\s*\(")

def rparen():
    return regex(r"^\s*\)")

def program():
    def f(s: str):
        parser = oneOrMore(choice(blankline(), comment(), sexpr()))
        return parser(s)
    return f

def comment():
    def f(s: str):
        parser = regex(r"^\s*;.*", lambda x: [";", x.strip()[1:]])
        return parser(s)
    return f

def blankline():
    def f(s: str):
        parser = regex(r"^(\s*?\n){2,}", lambda x: x.count("\n") - 2)
        return parser(s)
    return f

def sexpr():
    def f(s: str):
        parser = seq(lparen(), zeroOrMore(expr()), rparen())
        succ, cur_s, value = parser(s)
        # Do not wrap Expr* value in another list
        if succ and value:
            return succ, cur_s, value[0]
        return succ, cur_s, value
    return f

def expr():
    def f(s: str):
        parser = choice(blankline(), comment(), sexpr(), atom())
        return parser(s)
    return f

def atom():
    def f(s: str):
        numeral = regex(r'^\s*(?:0|[1-9][0-9]*)', lambda x: x.lstrip())
        decimal = regex(r'^\s*(?:0|[1-9][0-9]*)\.[0-9]+', lambda x: x.lstrip())
        hexadecimal = regex(r'^\s*#x[0-9a-fA-F]+', lambda x: x.lstrip())
        binary = regex(r'^\s*#b[0-1]+', lambda x: x.lstrip())
        string = regex(r'^\s*"(?:""|[^"])*"', lambda x: x.lstrip())
        # This includes "keyword", which is just ":" followed by a "simple_symbol".
        simple_symbol = regex(r'^\s*(?![0-9]):?[+\-*=%?!.$_~&^<>@0-9a-zA-Z]+', lambda x: x.lstrip())
        quoted_symbol = regex(r'^\s*\|[^|\\]*\|', lambda x: x.lstrip())
        return choice(numeral, decimal, hexadecimal, binary, string, simple_symbol, quoted_symbol)(s)
    return f

######################################################################
# Formatter
######################################################################

SMALL_EXPRESSION_MAX_LENGTH = 80
SPACES_PER_INDENT = 2

class FormattingException(Exception):
    pass

def format_lisp(input: str) -> str:
    parser = program()
    succ, leftover, terms = parser(input)
    if not succ or (leftover and not leftover.isspace()) or terms is None:
        raise FormattingException(
            "smtfmt: error: not formatting, leftover: " + leftover.strip()
        )
    return format_terms(terms)

def format_terms(xs) -> str:
    return "".join(format_term(x, False) + "\n" for x in xs)

def iscomment(xs) -> bool:
    return not isblankline(xs) and len(xs) == 2 and xs[0] == ";"

def isatom(xs) -> bool:
    return isinstance(xs, str)

def isblankline(xs) -> bool:
    return isinstance(xs, int)

def format_term(xs, first: bool) -> str:
    if isblankline(xs):
        return "\n" * xs
    # Insert comments at the current indentation level.
    if iscomment(xs):
        return "".join(xs)
    # Atoms are easy, always print them as-is.
    if isatom(xs):
        return xs
    ok, oneline = format_term_oneline(xs)
    if ok and len(oneline) < SMALL_EXPRESSION_MAX_LENGTH:  # Small terms on one line
        return oneline
    # Long expression, break lines and align subexpressions on the same level.
    s = "("
    if not iscomment(xs[0]) and not isatom(xs[0]):
        s += "\n"
    # General lists with line breaks after each element.
    for i in range(len(xs)):
        x = xs[i]
        if i == 0 and iscomment(x):
            s += "\n"
        s += format_term(x, i == 0)
        if i != len(xs) - 1 or iscomment(x):
            s += "\n"
    s += ")"
    indented = ""
    first = True
    for line in s.splitlines(keepends=True):
        if not first and line != "\n":
            indented += " " * SPACES_PER_INDENT
        indented += line
        first = False
    return indented

def format_term_oneline(xs) -> Tuple[bool, str]:
    if isblankline(xs):
        return False, ""
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

def usage():
    print("usage: smtfmt < input.smt")
    sys.exit(1)

def main():
    if len(sys.argv) > 1:
        usage()
    input = sys.stdin.read()
    try:
        print(format_lisp(input), end="")
    except FormattingException as e:
        print(input)
        print(e, file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

######################################################################
# Tests
######################################################################

TESTDATA = (
    """
(simple x)

(list (list (fun) (number 0 .0.0.0 :5900) atom))

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

      ;; Blank lines are preserved.
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

def test_format_lisp():
    assert format_lisp(TESTDATA) == TESTDATA

def test_trailing_paragraph():
    assert format_lisp("()\n\n") == "()\n\n"

def test_trailing_comment():
    assert format_lisp("(1\n;comment\n)") == "(1\n  ;comment\n  )\n"

def test_leading_comment():
    assert format_lisp("(\n;comment\n)") == "(\n  ;comment\n  )\n"

def test_empty_line():
    assert format_lisp("(1\n\n2)") == "(1\n\n  2)\n"

def test_blank_line():
    assert format_lisp("(1\n  \n2)") == "(1\n\n  2)\n"

def test_empty_line_toplevel():
    assert format_lisp("(1)\n\n(2)") == "(1)\n\n(2)\n"
    assert format_lisp("(1)\n\n\n(2)") == "(1)\n\n\n(2)\n"

def test_empty_line_comment():
    assert format_lisp("(1)\n\n; comment\n(2)") == "(1)\n\n; comment\n(2)\n"
    assert format_lisp("(1\n\n; comment\n\n2)") == "(1\n\n  ; comment\n\n  2)\n"

def test_quoted_symbol():
    assert format_lisp("(| single  symbol |)") == "(| single  symbol |)\n"

def test_format_invalid():
    try:
        format_lisp("(")
    except FormattingException as e:
        assert e.args == ("smtfmt: error: not formatting, leftover: (",)
        return
    assert False, "expect exception on invalid input"
