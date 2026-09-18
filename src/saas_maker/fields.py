"""The `--fields` and `--status` mini-DSL and the per-kind code snippets.

    --fields "name:str:Nombre,notes:text?:Notas,amount:float:Monto,due:date?:Vence"
    --status "draft=Borrador,active=Activo,done=Terminado"

Each field is `name:kind[?][:Label]`. Kinds: str, text, int, float, bool,
date, datetime. `?` makes it optional (nullable). The FIRST field must be a
required `str`: it is the title shown in the table, searched by `q`, and
used in the delete confirmation.

Every code fragment the templates need per field lives here, so the Jinja
templates stay flat.
"""

import json
import re
from dataclasses import dataclass

KINDS = ("str", "text", "int", "float", "bool", "date", "datetime")
RESERVED = {
    "id",
    "organization_id",
    "created_by",
    "created_at",
    "updated_at",
    "status",
    "q",
    "page",
    "page_size",
}
NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
STR_MAX = 100
TEXT_MAX = 2000

_SAMPLES = {
    # kind: (python literal, ts literal, typed string in the form)
    "str": ('"Sitio web"', "'Sitio web'", "Sitio web"),
    "text": ('"Rediseño completo"', "'Rediseño completo'", "Rediseño completo"),
    "int": ("3", "3", "3"),
    "float": ("9.5", "9.5", "9.5"),
    "bool": ("True", "true", ""),
    "date": ('"2026-09-10"', "'2026-09-10'", "2026-09-10"),
    "datetime": ('"2026-09-10T10:00:00"', "'2026-09-10T10:00:00'", "2026-09-10T10:00"),
}


def _ts_str(value: str) -> str:
    """A single-quoted TypeScript string literal."""
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


class FieldError(ValueError):
    pass


@dataclass
class Field:
    name: str
    kind: str
    optional: bool = False
    label: str = ""

    def __post_init__(self) -> None:
        if not self.label:
            self.label = self.name.replace("_", " ").capitalize()

    # --- Python ----------------------------------------------------------
    @property
    def py_type(self) -> str:
        return {
            "str": "str",
            "text": "str",
            "int": "int",
            "float": "float",
            "bool": "bool",
            "date": "date",
            "datetime": "datetime",
        }[self.kind]

    @property
    def py_annot(self) -> str:
        return f"{self.py_type} | None" if self.optional else self.py_type

    @property
    def model_line(self) -> str:
        n, k = self.name, self.kind
        if k == "str":
            return (
                f"{n}: str | None = Field(default=None, max_length={STR_MAX}, nullable=True)"
                if self.optional
                else f"{n}: str = Field(max_length={STR_MAX}, nullable=False)"
            )
        if k == "text":
            return (
                f"{n}: str | None = Field(default=None, sa_column=Column(Text, nullable=True))"
                if self.optional
                else f"{n}: str = Field(sa_column=Column(Text, nullable=False))"
            )
        if k == "bool":
            return f"{n}: bool = Field(default=False, nullable=False)"
        return (
            f"{n}: {self.py_type} | None = Field(default=None, nullable=True)"
            if self.optional
            else f"{n}: {self.py_type} = Field(nullable=False)"
        )

    @property
    def migration_column(self) -> str:
        sa = {
            "str": f"sa.String(length={STR_MAX})",
            "text": "sa.Text()",
            "int": "sa.Integer()",
            "float": "sa.Float()",
            "bool": "sa.Boolean()",
            "date": "sa.Date()",
            "datetime": "sa.DateTime()",
        }[self.kind]
        nullable = "True" if (self.optional and self.kind != "bool") else "False"
        return f"sa.Column('{self.name}', {sa}, nullable={nullable})"

    @property
    def uses_pydantic_field(self) -> bool:
        return self.kind in ("str", "text")

    @property
    def create_line(self) -> str:
        n, k = self.name, self.kind
        if k in ("str", "text"):
            mx = STR_MAX if k == "str" else TEXT_MAX
            return (
                f"{n}: str | None = Field(None, max_length={mx})"
                if self.optional
                else f"{n}: str = Field(..., min_length=1, max_length={mx})"
            )
        if k == "bool":
            return f"{n}: bool = False"
        return f"{n}: {self.py_type} | None = None" if self.optional else f"{n}: {self.py_type}"

    @property
    def update_line(self) -> str:
        n, k = self.name, self.kind
        if k in ("str", "text"):
            mx = STR_MAX if k == "str" else TEXT_MAX
            minimum = "" if self.optional else "min_length=1, "
            return f"{n}: str | None = Field(None, {minimum}max_length={mx})"
        return f"{n}: {self.py_type} | None = None"

    @property
    def response_line(self) -> str:
        annot = "bool" if self.kind == "bool" else self.py_annot
        return f"{self.name}: {annot}"

    def _sample(self, i: int) -> str:
        """Sample values; `str` fields get a unique one so tests can `getByText` it."""
        if self.kind in ("str", "text"):
            typed = f"{self.label} de prueba"
            return (json.dumps(typed, ensure_ascii=False), _ts_str(typed), typed)[i]
        return _SAMPLES[self.kind][i]

    @property
    def py_sample(self) -> str:
        return self._sample(0)

    # --- TypeScript ------------------------------------------------------
    @property
    def ts_base(self) -> str:
        return {
            "str": "string",
            "text": "string",
            "int": "number",
            "float": "number",
            "bool": "boolean",
            "date": "string",
            "datetime": "string",
        }[self.kind]

    @property
    def ts_type(self) -> str:
        if self.kind == "bool":
            return "boolean"
        return f"{self.ts_base} | null" if self.optional else self.ts_base

    @property
    def ts_create_line(self) -> str:
        if self.kind == "bool":
            return f"{self.name}?: boolean;"
        return (
            f"{self.name}?: {self.ts_base} | null;"
            if self.optional
            else f"{self.name}: {self.ts_base};"
        )

    @property
    def ts_sample(self) -> str:
        return self._sample(1)

    @property
    def form_empty(self) -> str:
        return "false" if self.kind == "bool" else "''"

    @property
    def zod(self) -> str:
        k = self.kind
        if k in ("str", "text"):
            mx = STR_MAX if k == "str" else TEXT_MAX
            required = "" if self.optional else ".trim().min(1, 'Requerido')"
            return f"z.string(){required}.max({mx}, 'Máximo {mx} caracteres')"
        if k == "int":
            pattern = r"/^-?\d*$/" if self.optional else r"/^-?\d+$/"
            return f"z.string().regex({pattern}, 'Debe ser un número entero')"
        if k == "float":
            cond = (
                "v.trim() === '' || !Number.isNaN(Number(v))"
                if self.optional
                else "v.trim() !== '' && !Number.isNaN(Number(v))"
            )
            return f"z.string().refine((v) => {cond}, 'Debe ser un número')"
        if k == "bool":
            return "z.boolean()"
        return "z.string()" if self.optional else "z.string().min(1, 'Requerido')"

    def to_form_expr(self, item: str) -> str:
        """Response value -> form value (strings everywhere but booleans)."""
        v, k = f"{item}.{self.name}", self.kind
        if k == "bool":
            return v
        if k in ("str", "text", "date"):
            return f"{v} ?? ''" if self.optional else v
        if k == "datetime":
            return f"{v} ? {v}.slice(0, 16) : ''" if self.optional else f"{v}.slice(0, 16)"
        # numbers
        return f"{v} === null ? '' : String({v})" if self.optional else f"String({v})"

    def to_payload_expr(self, data: str) -> str:
        """Form value -> API payload value."""
        v, k = f"{data}.{self.name}", self.kind
        if k == "bool":
            return v
        if k in ("str", "text"):
            return f"{v}.trim() || null" if self.optional else f"{v}.trim()"
        if k in ("date", "datetime"):
            return f"{v} || null" if self.optional else v
        return f"{v}.trim() === '' ? null : Number({v})" if self.optional else f"Number({v})"

    @property
    def input_jsx(self) -> str:
        k = self.kind
        if k == "text":
            return (
                '<Textarea placeholder="Opcional" rows={3} {...field} />'
                if self.optional
                else "<Textarea rows={3} {...field} />"
            )
        if k == "int":
            return '<Input type="number" step="1" {...field} />'
        if k == "float":
            return '<Input type="number" step="any" {...field} />'
        if k == "date":
            return '<Input type="date" {...field} />'
        if k == "datetime":
            return '<Input type="datetime-local" {...field} />'
        placeholder = ' placeholder="Opcional"' if self.optional else ""
        return f"<Input{placeholder} {{...field}} />"

    def cell_jsx(self, item: str) -> str:
        v, k = f"{item}.{self.name}", self.kind
        if k == "bool":
            return f"{{{v} ? 'Sí' : 'No'}}"
        if k == "date":
            expr = f"dateFormatter.format(new Date(`${{{v}}}T00:00:00`))"
            return f"{{{v} ? {expr} : '—'}}" if self.optional else f"{{{expr}}}"
        if k == "datetime":
            expr = f"dateTimeFormatter.format(new Date({v}))"
            return f"{{{v} ? {expr} : '—'}}" if self.optional else f"{{{expr}}}"
        return f"{{{v} ?? '—'}}" if self.optional else f"{{{v}}}"

    @property
    def cell_class(self) -> str:
        return "tabular-nums" if self.kind in ("int", "float") else ""

    # --- tests -----------------------------------------------------------
    @property
    def test_typed(self) -> str:
        """What the frontend test types into this field's input."""
        return self._sample(2)

    @property
    def test_uses_type(self) -> bool:
        return self.kind in ("str", "text")

    @property
    def test_expected(self) -> str:
        """The payload value the test expects after typing `test_typed`."""
        if self.kind == "bool":
            return "false"
        if self.optional:
            return "null"
        k = self.kind
        if k in ("int", "float"):
            return self.test_typed
        return f"'{self.test_typed}'"


_BADGE_CLASSES = {
    "muted": "bg-muted text-muted-foreground [&>span]:bg-muted-foreground",
    "success": "bg-success/10 text-success [&>span]:bg-success",
    "info": "bg-info/10 text-info [&>span]:bg-info",
    "warning": "bg-warning/10 text-warning [&>span]:bg-warning",
    "destructive": "bg-destructive/10 text-destructive [&>span]:bg-destructive",
}

# status value -> tone. Values not listed here render muted; the CLI asks to review them.
BADGE_TONES = {
    **dict.fromkeys(
        ["active", "paid", "confirmed", "published", "done", "completed", "approved", "open"],
        "success",
    ),
    **dict.fromkeys(
        ["draft", "pending", "in_progress", "quoted", "new", "scheduled", "sent", "review"],
        "info",
    ),
    **dict.fromkeys(["on_hold", "overdue", "expired", "warning", "partial"], "warning"),
    **dict.fromkeys(["cancelled", "canceled", "failed", "rejected", "blocked"], "destructive"),
    **dict.fromkeys(["archived", "inactive", "closed", "disabled"], "muted"),
}


@dataclass
class StatusValue:
    value: str
    label: str


@dataclass
class Status:
    values: list[StatusValue]

    @property
    def default(self) -> str:
        return self.values[0].value

    @property
    def last(self) -> str:
        return self.values[-1].value

    @property
    def py_values(self) -> str:
        return ", ".join(f'"{v.value}"' for v in self.values)

    @property
    def ts_union(self) -> str:
        return " | ".join(f"'{v.value}'" for v in self.values)

    @property
    def ts_enum(self) -> str:
        return ", ".join(f"'{v.value}'" for v in self.values)

    def badge_style(self, value: str) -> str:
        """Semantic tint for a status value, by meaning (see BADGE_TONES); muted otherwise."""
        return _BADGE_CLASSES[BADGE_TONES.get(value, "muted")]

    @property
    def unmapped_values(self) -> list[str]:
        return [v.value for v in self.values if v.value not in BADGE_TONES]


def parse_fields(spec: str) -> list[Field]:
    fields: list[Field] = []
    for raw in (part.strip() for part in spec.split(",")):
        if not raw:
            continue
        bits = raw.split(":")
        if len(bits) < 2 or len(bits) > 3:
            raise FieldError(f"bad field '{raw}' — expected name:kind[?][:Label]")
        name, kind = bits[0].strip(), bits[1].strip()
        label = bits[2].strip() if len(bits) == 3 else ""
        optional = kind.endswith("?")
        kind = kind.rstrip("?")
        if not NAME_RE.match(name):
            raise FieldError(f"bad field name '{name}' — use snake_case")
        if name in RESERVED:
            raise FieldError(f"'{name}' is reserved (added automatically)")
        if kind not in KINDS:
            raise FieldError(f"unknown kind '{kind}' for '{name}' — one of {', '.join(KINDS)}")
        if any(f.name == name for f in fields):
            raise FieldError(f"duplicate field '{name}'")
        fields.append(Field(name, kind, optional, label))
    if not fields:
        raise FieldError("at least one field is required")
    first = fields[0]
    if first.kind != "str" or first.optional:
        raise FieldError(
            f"the first field ('{first.name}') must be a required str — it is the title "
            "shown in the table and searched by `q`"
        )
    return fields


def parse_status(spec: str | None) -> Status | None:
    if not spec or not spec.strip():
        return None
    values: list[StatusValue] = []
    for raw in (part.strip() for part in spec.split(",")):
        if not raw:
            continue
        value, _, label = raw.partition("=")
        value = value.strip()
        if not NAME_RE.match(value):
            raise FieldError(f"bad status value '{value}' — use snake_case")
        if any(v.value == value for v in values):
            raise FieldError(f"duplicate status '{value}'")
        values.append(StatusValue(value, label.strip() or value.replace("_", " ").capitalize()))
    if len(values) < 2:
        raise FieldError("--status needs at least two values (e.g. draft=Borrador,done=Hecho)")
    return Status(values)


DEFAULT_FIELDS = "name:str:Nombre,description:text?:Descripción"
