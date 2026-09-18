from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from sqlalchemy import select

from .db import get_pricing_engine, get_session
from .models_db import OrderFormDependencyCell, OrderFormInventoryRule


class FormulaEvaluationError(ValueError):
    pass


@dataclass(frozen=True)
class _Token:
    kind: str
    value: str


_TOKEN_RE = re.compile(
    r"\s*(?:(?P<number>\d+(?:\.\d+)?)|(?P<string>\"(?:\"\"|[^\"])*\")|"
    r"(?P<reference>(?:\[[^\]]+\])?[A-Za-z][A-Za-z0-9_]*!\$?[A-Z]{1,3}\$?\d+|"
    r"\$?[A-Z]{1,3}\$?\d+(?::\$?[A-Z]{1,3}\$?\d+)?)|"
    r"(?P<identifier>[A-Za-z][A-Za-z0-9_]*)|(?P<operator><>|>=|<=|[=<>+*/-])|"
    r"(?P<lparen>\()|(?P<rparen>\))|(?P<comma>,))"
)


def _tokenize(formula: str) -> list[_Token]:
    text = formula.strip()
    if text.startswith("="):
        text = text[1:]
    tokens: list[_Token] = []
    position = 0
    while position < len(text):
        match = _TOKEN_RE.match(text, position)
        if not match:
            raise FormulaEvaluationError(f"Unsupported formula near: {text[position:position + 30]}")
        kind = match.lastgroup
        tokens.append(_Token(kind or "", match.group(kind or "")))
        position = match.end()
    return tokens


def _number(value: Any) -> Decimal | None:
    if value is None or value == "":
        return Decimal("0")
    if isinstance(value, bool):
        return Decimal("1") if value else Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _truthy(value: Any) -> bool:
    number = _number(value)
    if number is not None and not isinstance(value, str):
        return number != 0
    return bool(value)


def _normalize_reference(reference: str) -> str:
    return reference.replace("$", "").replace("[1]", "")


class _Parser:
    def __init__(self, tokens: list[_Token], resolve: Callable[[str], Any], resolve_range: Callable[[str], list[Any]]):
        self.tokens = tokens
        self.resolve = resolve
        self.resolve_range = resolve_range
        self.position = 0

    def _peek(self, kind: str | None = None) -> _Token | None:
        token = self.tokens[self.position] if self.position < len(self.tokens) else None
        return token if kind is None or (token and token.kind == kind) else None

    def _take(self, kind: str | None = None) -> _Token:
        token = self._peek(kind)
        if token is None:
            expected = kind or "token"
            raise FormulaEvaluationError(f"Expected {expected}")
        self.position += 1
        return token

    def parse(self) -> Any:
        value = self._comparison()
        if self.position != len(self.tokens):
            raise FormulaEvaluationError(f"Unexpected token: {self.tokens[self.position].value}")
        return value

    def _comparison(self) -> Any:
        left = self._expression()
        token = self._peek("operator")
        if token is None or token.value not in {"=", "<>", ">", "<", ">=", "<="}:
            return left
        self.position += 1
        right = self._expression()
        if token.value == "=":
            return left == right or (_number(left) is not None and _number(right) is not None and _number(left) == _number(right))
        if token.value == "<>":
            return not self._compare(left, right, "=")
        return self._compare(left, right, token.value)

    @staticmethod
    def _compare(left: Any, right: Any, operator: str) -> bool:
        left_number = _number(left)
        right_number = _number(right)
        a, b = (left_number, right_number) if left_number is not None and right_number is not None else (str(left), str(right))
        return {"=": a == b, ">": a > b, "<": a < b, ">=": a >= b, "<=": a <= b}[operator]

    def _expression(self) -> Any:
        value = self._term()
        while self._peek("operator") and self._peek("operator").value in {"+", "-"}:
            operator = self._take("operator").value
            right = self._term()
            left_number = _number(value)
            right_number = _number(right)
            if left_number is None or right_number is None:
                raise FormulaEvaluationError("Arithmetic requires numeric values")
            value = left_number + right_number if operator == "+" else left_number - right_number
        return value

    def _term(self) -> Any:
        value = self._factor()
        while self._peek("operator") and self._peek("operator").value in {"*", "/"}:
            operator = self._take("operator").value
            right = self._factor()
            left_number = _number(value)
            right_number = _number(right)
            if left_number is None or right_number is None:
                raise FormulaEvaluationError("Arithmetic requires numeric values")
            if operator == "/" and right_number == 0:
                raise FormulaEvaluationError("Division by zero")
            value = left_number * right_number if operator == "*" else left_number / right_number
        return value

    def _factor(self) -> Any:
        if self._peek("operator") and self._peek("operator").value == "-":
            self._take("operator")
            value = _number(self._factor())
            if value is None:
                raise FormulaEvaluationError("Unary minus requires a number")
            return -value
        if self._peek("lparen"):
            self._take("lparen")
            value = self._comparison()
            self._take("rparen")
            return value
        if self._peek("number"):
            return Decimal(self._take("number").value)
        if self._peek("string"):
            return self._take("string").value[1:-1].replace('""', '"')
        if self._peek("reference"):
            reference = _normalize_reference(self._take("reference").value)
            if ":" in reference:
                return self.resolve_range(reference)
            return self.resolve(reference)
        if self._peek("identifier"):
            name = self._take("identifier").value.upper()
            self._take("lparen")
            arguments = []
            if not self._peek("rparen"):
                while True:
                    arguments.append(self._function_argument())
                    if not self._peek("comma"):
                        break
                    self._take("comma")
            self._take("rparen")
            if name == "IF":
                if len(arguments) not in {2, 3}:
                    raise FormulaEvaluationError("IF requires two or three arguments")
                return arguments[1] if _truthy(arguments[0]) else (arguments[2] if len(arguments) == 3 else False)
            if name == "AND":
                return all(_truthy(argument) for argument in arguments)
            if name == "OR":
                return any(_truthy(argument) for argument in arguments)
            if name == "SUM":
                values = [value for argument in arguments for value in (argument if isinstance(argument, list) else [argument])]
                return sum((_number(value) or Decimal("0") for value in values), Decimal("0"))
            raise FormulaEvaluationError(f"Unsupported Excel function: {name}")
        raise FormulaEvaluationError("Expected formula value")

    def _function_argument(self) -> Any:
        return self._comparison()


def evaluate_formula(
    formula: str,
    cells: dict[str, Any],
    current_sheet: str | None = None,
    active: set[str] | None = None,
) -> Any:
    normalized_cells = {_normalize_reference(str(key)): value for key, value in cells.items()}
    active = active if active is not None else set()

    def resolve(reference: str) -> Any:
        reference = _normalize_reference(reference)
        candidates = [reference]
        if "!" not in reference and current_sheet:
            candidates.insert(0, f"{current_sheet}!{reference}")
        key = next((candidate for candidate in candidates if candidate in normalized_cells), reference)
        if key in active:
            raise FormulaEvaluationError(f"Circular dependency at {key}")
        value = normalized_cells.get(key, "")
        if isinstance(value, str) and value.startswith("="):
            active.add(key)
            try:
                nested_sheet = key.split("!", 1)[0] if "!" in key else current_sheet
                return evaluate_formula(value, normalized_cells, nested_sheet, active)
            finally:
                active.remove(key)
        return value

    def resolve_range(reference: str) -> list[Any]:
        start, end = reference.split(":", 1)
        start_match = re.fullmatch(r"([A-Z]+)(\d+)", start, re.IGNORECASE)
        end_match = re.fullmatch(r"([A-Z]+)(\d+)", end, re.IGNORECASE)
        if not start_match or not end_match or start_match.group(1).upper() != end_match.group(1).upper():
            raise FormulaEvaluationError(f"Unsupported range: {reference}")
        column = start_match.group(1).upper()
        return [
            resolve(f"{column}{row}")
            for row in range(int(start_match.group(2)), int(end_match.group(2)) + 1)
        ]

    return _Parser(_tokenize(formula), resolve, resolve_range).parse()


def evaluate_inventory_rules(rules: list[dict[str, Any]], cells: dict[str, Any]) -> list[dict[str, Any]]:
    evaluated = []
    for rule in rules:
        allocation = evaluate_formula(rule["allocation_formula"], cells)
        number = _number(allocation)
        if number is None or number == 0:
            continue
        item = dict(rule)
        item["allocated"] = format(number, "f")
        evaluated.append(item)
    return evaluated


_DATA_INPUT_KEYS = {
    "B2": "quantity",
    "B3": "series",
    "B4": "bore",
    "B5": "mount",
    "B6": "rod_diameter",
    "B7": "cushion",
    "B8": "stroke",
    "B9": "special_parts",
    "B10": "seal_code",
    "B11": "rod_extension",
    "B12": "stop_tube",
    "B13": "extra_ports",
    "B14": "bumper_piston",
    "B15": "brass_wiper",
    "B16": "ultraox",
    "B17": "ss_rod",
    "B18": "transducer",
    "B19": "prox_switch",
    "B20": "gland_drain",
    "B21": "chrome_bore",
    "B22": "prep_for_transducer",
    "B23": "air_bleed",
    "B24": "sensor_cover",
    "B25": "extra_tie_rod_qty",
    "B26": "valve_manifold",
    "B27": "extra_thread",
}


def evaluate_database_inventory_rules(inputs: dict[str, Any], quantity: int = 1) -> list[dict[str, Any]]:
    """Evaluate imported workbook rules against current Order Form inputs."""
    get_pricing_engine()
    with get_session() as session:
        rules = session.execute(select(OrderFormInventoryRule)).scalars().all()
        if not rules:
            return []
        dependency_cells = session.execute(select(OrderFormDependencyCell)).scalars().all()

    cells = {
        cell.cell_key: cell.formula or cell.value_text or cell.value_number
        for cell in dependency_cells
    }
    cells.update({
        f"Data!{coordinate}": "" if inputs.get(key) in (None, False) else inputs.get(key)
        for coordinate, key in _DATA_INPUT_KEYS.items()
    })
    cells["Data!B2"] = quantity
    rule_values = [
        {
            "part_number": rule.part_number,
            "description": rule.description,
            "unit_price": rule.unit_price,
            "allocation_formula": rule.allocation_formula,
            "source_sheet": rule.source_sheet,
        }
        for rule in rules
    ]
    evaluated = []
    for rule in rule_values:
        try:
            allocation = evaluate_formula(
                rule["allocation_formula"],
                cells,
                current_sheet=rule["source_sheet"],
            )
        except FormulaEvaluationError:
            continue
        number = _number(allocation)
        if number is None or number == 0:
            continue
        item = dict(rule)
        item["allocated"] = format(number, "f")
        evaluated.append(item)
    return evaluated
