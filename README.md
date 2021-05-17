# smtfmt

This is a fun little program to format Lisp programs.
It is designed to pretty-print [SMT-LIB](http://smtlib.cs.uiowa.edu/language.shtml) code.

## Installation

```sh
$ git clone https://github.com/symflower/smtfmt && cd smtfmt
$ ln -s $PWD/smtfmt ~/bin
```

## Usage

```
$ input='(:not (:forall (?x Real) (:forall (?y Real) (impl (< ?x ?y) ( :exists (?z Real) (:and (< ?x ?z) (< ?z ?y)))))))'
$ echo "$input" | smtfmt
(:not
  (:forall
    (?x Real)
    (:forall
      (?y Real)
      (impl (< ?x ?y) (:exists (?z Real) (:and (< ?x ?z) (< ?z ?y)))))))
```

Small expressions are printed inline. Longer expressions are broken up and aligned.

## Tests

Run `pytest smtfmt.py`.

## Style

Format with `black --pyi smtfmt.py`.
