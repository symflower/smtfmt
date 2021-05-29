#!/usr/bin/env python3

import re
import sys
from typing import Tuple

######################################################################
# Generic parser builders
######################################################################
# Here, a parser is a function of the following form:
# f(input: str) -> (success: bool, output: str, value)

def regex(pat: str, func=lambda m: None):
    def f(s: str):
        m = re.compile(pat).match(s)
        if m:
            return True, s[m.end(0) :], func(m)
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
        parser = regex(r"^\s*;.*", lambda m: [";", m.group(0).strip()[1:]])
        return parser(s)
    return f

def raw_comment():
    def f(s: str):
        parser = regex(r"^([ \t]*;.*)?", lambda m: m.group(0) or "")
        return parser(s)
    return f

def blankline():
    def f(s: str):
        parser = regex(r"^(\s*?\n){2,}", lambda m: m.group(0).count("\n") - 2)
        return parser(s)
    return f

def sexpr():
    def f(s: str):
        parser = seq(lparen(), zeroOrMore(expr()), rparen(), raw_comment())
        return parser(s)
    return f

def expr():
    def f(s: str):
        parser = choice(blankline(), comment(), sexpr(), atom())
        return parser(s)
    return f

def atom():
    def f(s: str):
        def parse_atom(pattern):
            return regex(r"^\s*(" + pattern + r")", lambda m: m.group(1))
        numeral = parse_atom(r"(?:0|[1-9][0-9]*)")
        decimal = parse_atom(r"(?:0|[1-9][0-9]*)\.[0-9]+")
        hexadecimal = parse_atom(r"#x[0-9a-fA-F]+")
        binary = parse_atom(r"#b[0-1]+")
        string = parse_atom(r'"(?:""|[^"])*"')
        # This includes "keyword", which is just ":" followed by a "simple_symbol".
        simple_symbol = parse_atom(r"(?![0-9]):?[+\-*=%?!.$_~&^<>@0-9a-zA-Z]+")
        quoted_symbol = parse_atom(r"\|[^|\\]*\|")
        any_atom = choice(
            numeral, decimal, hexadecimal, binary, string, simple_symbol, quoted_symbol
        )
        return seq(any_atom, raw_comment())(s)
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
    return isinstance(xs, list) and len(xs) in (1, 2) and isinstance(xs[0], str)

def issexpr(xs) -> bool:
    return isinstance(xs, list) and (len(xs) == 0 or isinstance(xs[0], list))

def isblankline(xs) -> bool:
    return isinstance(xs, int)

def format_atom(xs):
    return "".join(xs)

def decode_attached_comment(xs) -> tuple[list, str]:
    if len(xs) == 0:
        return [], ""
    attached_comment = ""
    if len(xs) == 2:
        attached_comment = xs[1]
    return xs[0], attached_comment

def format_term(xs, first: bool) -> str:
    if isblankline(xs):
        return "\n" * xs
    # Insert comments at the current indentation level.
    if iscomment(xs):
        return "".join(xs)
    # Atoms are easy, always print them as-is.
    if isatom(xs):
        return format_atom(xs)
    xs, attached_comment = decode_attached_comment(xs)
    ok, oneline = format_term_oneline([xs])
    if ok and len(oneline) < SMALL_EXPRESSION_MAX_LENGTH:  # Small terms on one line
        return oneline + attached_comment
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
        if (
            i != len(xs) - 1
            or iscomment(x)
            or ((isatom(x) or issexpr(x)) and len(x) == 2)
        ):
            s += "\n"
    s += ")"
    if attached_comment:
        s += attached_comment
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
    xs0, attached_comment = decode_attached_comment(xs)
    if isatom(xs):
        return not attached_comment, format_atom(xs)
    if attached_comment:
        return False, ""
    terms = []
    for x in xs0:
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

def test_attached_comment():
    assert format_lisp("(1 ; comment\n)") == "(1 ; comment\n  )\n"
    assert format_lisp("(1 ; comment\n2)") == "(1 ; comment\n  2)\n"
    assert format_lisp("(1  ;   comment\n2)") == "(1  ;   comment\n  2)\n"

    assert format_lisp("(1) ; comment\n(2)") == "(1) ; comment\n(2)\n"
    assert format_lisp("(1) ; comment\n\n(2)") == "(1) ; comment\n\n(2)\n"

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
