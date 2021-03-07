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
# Paragraph ::= (Comment | SExpr)+
# SExpr     ::= '(' Expr* ')'
# Expr      ::= Comment | SExpr | atom

def lparen():
    return regex(r"^\s*\(")

def rparen():
    return regex(r"^\s*\)")

def paragraph():
    def f(s: str):
        parser = oneOrMore(choice(comment(), sexpr()))
        return parser(s)
    return f

def comment():
    def f(s: str):
        parser = regex(r"^\s*;.*", lambda x: [";", x.strip()[1:]])
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
        parser = choice(comment(), sexpr(), atom())
        return parser(s)
    return f

def atom():
    def f(s: str):
        quoted = regex(r'^\s*".*"', lambda x: x.strip())
        # identifier = all but whitespace and ( or )
        id = regex(r"^\s*[^\s\(\)]+", lambda x: x.strip())
        return choice(quoted, id)(s)
    return f

######################################################################
# Formatter
######################################################################

SMALL_EXPRESSION_MAX_LENGTH = 80
SPACES_PER_INDENT = 2

class FormattingException(Exception):
    pass

def format_lisp(input: str) -> str:
    parser = paragraph()
    in_paragraphs = re.split(r"\n{2,}", input)
    out_paragraphs = []
    for p in in_paragraphs:
        if p.strip() == "":
            continue
        succ, leftover, terms = parser(p)
        if not succ or (leftover and not leftover.isspace()) or terms is None:
            raise FormattingException("smtfmt: error: not formatting, leftover: " + leftover.strip())
        out_paragraphs += [format_terms(terms)]
    return "\n".join(out_paragraphs)

def format_terms(xs) -> str:
    return "".join(format_term(x, 0, False) + "\n" for x in xs)

def iscomment(xs) -> bool:
    return len(xs) == 2 and xs[0] == ";"

def isatom(xs) -> bool:
    return isinstance(xs, str)

def format_term(xs, level: int, first: bool) -> str:
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
        s += format_term(x, level + 1, i == 0)
        if i != len(xs) - 1:
            s += "\n"
    s += ")"
    indented = ""
    first = True
    for line in s.splitlines(keepends=True):
        if not first:
            indented += " " * SPACES_PER_INDENT
        indented += line
        first = False
    return indented

def format_term_oneline(xs) -> Tuple[bool, str]:
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

if __name__ == "__main__":
    if len(sys.argv) > 1:
        usage()
    input = sys.stdin.read()
    try:
        print(format_lisp(input), end="")
    except FormattingException as e:
        print(input)
        print(e, file=sys.stderr)
        sys.exit(1)

######################################################################
# Tests
######################################################################

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

def test_format_lisp():
    assert format_lisp(TESTDATA) == TESTDATA

def test_trailing_paragraph():
    assert format_lisp("()\n\n") == "()\n"

def test_format_invalid():
    try:
        format_lisp("(")
    except FormattingException as e:
        assert e.args == ("smtfmt: error: not formatting, leftover: (", )
        return
    assert False, "expect exception on invalid input"
