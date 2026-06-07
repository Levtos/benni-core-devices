"""Sichere Mini-Expression-Engine für Combined v1.0 (HA-frei, testbar).

Eigener AST — KEIN eval/Jinja. Unterstützt:
- Literale: Zahlen, Strings ("..."/'...'), true/false/null
- Referenzen: ${src_key} / ${node_name} / ${self}
- Operatoren: + - * / ( ), Vergleiche == != < <= > >=, Logik and/or/not
- Funktionen (Whitelist): min, max, abs, round(x[,n]), clamp(x, lo, hi),
  any([...])/all([...])/not(x)
- Listen-Literale [a, b, ...] (für any/all)

None-Propagation: jeder None-Operand → None (→ fail_safe beim Node). Division
durch 0 → None. Robuste Koerzierung: Zahlen ↔ Bool ↔ String je Kontext.
"""

from __future__ import annotations

from typing import Any

_TRUTHY = frozenset({"on", "true", "yes", "1", "open", "home", "playing", "active", "heat", "cool"})
_FALSY = frozenset({"off", "false", "no", "0", "closed", "not_home", "idle", "standby", "unavailable", "unknown", "offline"})
_FUNCS = frozenset({"min", "max", "abs", "round", "clamp", "any", "all", "not"})


class ExprError(ValueError):
    """Syntax-/Parsefehler in einem Expression-String."""


# ─────────────────────────────────────────────────────────────────────────────
# TOKENIZER
# ─────────────────────────────────────────────────────────────────────────────

_TWO_CHAR = {"==", "!=", "<=", ">="}


def _tokenize(s: str) -> list[tuple[str, Any]]:
    toks: list[tuple[str, Any]] = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c.isspace():
            i += 1
            continue
        if c == "$" and i + 1 < n and s[i + 1] == "{":
            j = s.find("}", i + 2)
            if j == -1:
                raise ExprError("unterminated ${ref}")
            name = s[i + 2:j].strip()
            if not name:
                raise ExprError("empty ${}")
            toks.append(("ref", name))
            i = j + 1
            continue
        if c in ('"', "'"):
            j = s.find(c, i + 1)
            if j == -1:
                raise ExprError("unterminated string")
            toks.append(("str", s[i + 1:j]))
            i = j + 1
            continue
        if c.isdigit() or (c == "." and i + 1 < n and s[i + 1].isdigit()):
            j = i
            while j < n and (s[j].isdigit() or s[j] == "."):
                j += 1
            try:
                toks.append(("num", float(s[i:j])))
            except ValueError as err:
                raise ExprError(f"bad number {s[i:j]!r}") from err
            i = j
            continue
        if c.isalpha() or c == "_":
            j = i
            while j < n and (s[j].isalnum() or s[j] == "_"):
                j += 1
            word = s[i:j]
            lw = word.lower()
            if lw in ("and", "or", "not", "true", "false", "null"):
                toks.append((lw, word))
            else:
                toks.append(("name", word))
            i = j
            continue
        two = s[i:i + 2]
        if two in _TWO_CHAR:
            toks.append((two, two))
            i += 2
            continue
        if c in "+-*/()[],<>":
            toks.append((c, c))
            i += 1
            continue
        raise ExprError(f"unexpected char {c!r}")
    return toks


# ─────────────────────────────────────────────────────────────────────────────
# PARSER (recursive descent)
# ─────────────────────────────────────────────────────────────────────────────


class _Parser:
    def __init__(self, toks: list[tuple[str, Any]]) -> None:
        self.toks = toks
        self.pos = 0

    def _peek(self) -> tuple[str, Any] | None:
        return self.toks[self.pos] if self.pos < len(self.toks) else None

    def _next(self) -> tuple[str, Any]:
        t = self._peek()
        if t is None:
            raise ExprError("unexpected end")
        self.pos += 1
        return t

    def _expect(self, kind: str) -> tuple[str, Any]:
        t = self._next()
        if t[0] != kind:
            raise ExprError(f"expected {kind!r}, got {t[0]!r}")
        return t

    def parse(self) -> Any:
        node = self._or()
        if self._peek() is not None:
            raise ExprError(f"trailing tokens at {self._peek()}")
        return node

    def _or(self) -> Any:
        node = self._and()
        while self._peek() and self._peek()[0] == "or":
            self._next()
            node = ("or", node, self._and())
        return node

    def _and(self) -> Any:
        node = self._not()
        while self._peek() and self._peek()[0] == "and":
            self._next()
            node = ("and", node, self._not())
        return node

    def _not(self) -> Any:
        if self._peek() and self._peek()[0] == "not":
            self._next()
            return ("not", self._not())
        return self._cmp()

    def _cmp(self) -> Any:
        node = self._add()
        t = self._peek()
        if t and t[0] in ("==", "!=", "<", "<=", ">", ">="):
            self._next()
            return ("cmp", t[0], node, self._add())
        return node

    def _add(self) -> Any:
        node = self._mul()
        while self._peek() and self._peek()[0] in ("+", "-"):
            op = self._next()[0]
            node = ("bin", op, node, self._mul())
        return node

    def _mul(self) -> Any:
        node = self._unary()
        while self._peek() and self._peek()[0] in ("*", "/"):
            op = self._next()[0]
            node = ("bin", op, node, self._unary())
        return node

    def _unary(self) -> Any:
        if self._peek() and self._peek()[0] == "-":
            self._next()
            return ("neg", self._unary())
        return self._atom()

    def _atom(self) -> Any:
        t = self._next()
        kind = t[0]
        if kind == "num":
            return ("num", t[1])
        if kind == "str":
            return ("str", t[1])
        if kind == "ref":
            return ("ref", t[1])
        if kind == "true":
            return ("const", True)
        if kind == "false":
            return ("const", False)
        if kind == "null":
            return ("const", None)
        if kind == "(":
            node = self._or()
            self._expect(")")
            return node
        if kind == "[":
            items: list[Any] = []
            if self._peek() and self._peek()[0] != "]":
                items.append(self._or())
                while self._peek() and self._peek()[0] == ",":
                    self._next()
                    items.append(self._or())
            self._expect("]")
            return ("list", items)
        if kind == "name":
            fname = t[1].lower()
            if self._peek() and self._peek()[0] == "(":
                self._next()
                args: list[Any] = []
                if self._peek() and self._peek()[0] != ")":
                    args.append(self._or())
                    while self._peek() and self._peek()[0] == ",":
                        self._next()
                        args.append(self._or())
                self._expect(")")
                if fname not in _FUNCS:
                    raise ExprError(f"unknown function {t[1]!r}")
                return ("call", fname, args)
            raise ExprError(f"bare name {t[1]!r} (use ${{...}} for refs)")
        raise ExprError(f"unexpected token {t}")


_CACHE: dict[str, Any] = {}


def parse(expr: str) -> Any:
    if expr not in _CACHE:
        _CACHE[expr] = _Parser(_tokenize(str(expr))).parse()
    return _CACHE[expr]


def refs(ast: Any) -> set[str]:
    """Alle ${...}-Referenznamen im AST (für Topo-Sort + Validierung)."""
    out: set[str] = set()
    def walk(node: Any) -> None:
        if not isinstance(node, tuple):
            return
        if node[0] == "ref":
            out.add(node[1])
            return
        for part in node[1:]:
            if isinstance(part, list):
                for p in part:
                    walk(p)
            else:
                walk(part)
    walk(ast)
    return out


def func_names(ast: Any) -> set[str]:
    out: set[str] = set()
    def walk(node: Any) -> None:
        if not isinstance(node, tuple):
            return
        if node[0] == "call":
            out.add(node[1])
        for part in node[1:]:
            if isinstance(part, list):
                for p in part:
                    walk(p)
            elif isinstance(part, tuple):
                walk(part)
    walk(ast)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# COERCION
# ─────────────────────────────────────────────────────────────────────────────


def as_num(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def as_bool(v: Any) -> bool | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    s = str(v).strip().lower()
    if s in _TRUTHY:
        return True
    if s in _FALSY:
        return False
    return None


# ─────────────────────────────────────────────────────────────────────────────
# EVALUATOR
# ─────────────────────────────────────────────────────────────────────────────


def _eval(node: Any, env: dict[str, Any]) -> Any:
    kind = node[0]
    if kind == "num":
        return node[1]
    if kind == "str":
        return node[1]
    if kind == "const":
        return node[1]
    if kind == "ref":
        return env.get(node[1])
    if kind == "list":
        return [_eval(x, env) for x in node[1]]
    if kind == "neg":
        v = as_num(_eval(node[1], env))
        return None if v is None else -v
    if kind == "not":
        b = as_bool(_eval(node[1], env))
        return None if b is None else (not b)
    if kind == "and":
        a = as_bool(_eval(node[1], env))
        b = as_bool(_eval(node[2], env))
        if a is None or b is None:
            return None
        return a and b
    if kind == "or":
        a = as_bool(_eval(node[1], env))
        b = as_bool(_eval(node[2], env))
        if a is None or b is None:
            return None
        return a or b
    if kind == "bin":
        op, a, b = node[1], as_num(_eval(node[2], env)), as_num(_eval(node[3], env))
        if a is None or b is None:
            return None
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op == "/":
            return None if b == 0 else a / b
    if kind == "cmp":
        op = node[1]
        la, lb = _eval(node[2], env), _eval(node[3], env)
        if op in ("==", "!="):
            na, nb = as_num(la), as_num(lb)
            if la is None or lb is None:
                return None
            if na is not None and nb is not None:
                eq = na == nb
            else:
                eq = str(la) == str(lb)
            return eq if op == "==" else (not eq)
        na, nb = as_num(la), as_num(lb)
        if na is None or nb is None:
            return None
        if op == "<":
            return na < nb
        if op == "<=":
            return na <= nb
        if op == ">":
            return na > nb
        if op == ">=":
            return na >= nb
    if kind == "call":
        return _eval_call(node[1], node[2], env)
    raise ExprError(f"cannot eval {node!r}")


def _flatten_args(args: list[Any], env: dict[str, Any]) -> list[Any]:
    vals = [_eval(a, env) for a in args]
    if len(vals) == 1 and isinstance(vals[0], list):
        return vals[0]
    return vals


def _eval_call(fname: str, args: list[Any], env: dict[str, Any]) -> Any:
    if fname == "not":
        b = as_bool(_eval(args[0], env)) if args else None
        return None if b is None else (not b)
    if fname in ("any", "all"):
        items = [as_bool(v) for v in _flatten_args(args, env)]
        if any(x is None for x in items):
            return None
        return (any(items) if fname == "any" else all(items))
    nums = [as_num(_eval(a, env)) for a in args]
    if fname == "min":
        return None if not nums or any(x is None for x in nums) else min(nums)
    if fname == "max":
        return None if not nums or any(x is None for x in nums) else max(nums)
    if fname == "abs":
        return None if not nums or nums[0] is None else abs(nums[0])
    if fname == "round":
        if not nums or nums[0] is None:
            return None
        ndig = int(nums[1]) if len(nums) > 1 and nums[1] is not None else 0
        return round(nums[0], ndig)
    if fname == "clamp":
        if len(nums) < 3 or any(x is None for x in nums[:3]):
            return None
        x, lo, hi = nums[0], nums[1], nums[2]
        return max(lo, min(hi, x))
    raise ExprError(f"unknown function {fname!r}")


def eval_expr(expr: str, env: dict[str, Any]) -> Any:
    """Parst + wertet einen Expression-String aus. Rückgabe: float|bool|str|None."""
    return _eval(parse(expr), env)
