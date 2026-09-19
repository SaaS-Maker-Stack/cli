import pytest

from saas_maker.fields import DEFAULT_FIELDS, FieldError, parse_fields, parse_status


def test_default_fields_parse():
    fields = parse_fields(DEFAULT_FIELDS)
    assert [(f.name, f.kind, f.optional) for f in fields] == [
        ("name", "str", False),
        ("description", "text", True),
    ]
    assert fields[0].label == "Nombre"
    assert fields[1].label == "Descripción"


def test_every_kind_renders_consistent_snippets():
    spec = "title:str,notes:text?,qty:int,price:float?,done:bool,due:date?,at:datetime"
    fields = {f.name: f for f in parse_fields(spec)}

    assert fields["title"].model_line == "title: str = Field(max_length=100, nullable=False)"
    assert "Column(Text, nullable=True)" in fields["notes"].model_line
    assert fields["qty"].create_line == "qty: int"
    assert fields["price"].create_line == "price: float | None = None"
    assert fields["done"].create_line == "done: bool = False"
    assert fields["due"].migration_column == "sa.Column('due', sa.Date(), nullable=True)"
    assert fields["at"].migration_column == "sa.Column('at', sa.DateTime(), nullable=False)"

    assert fields["price"].ts_type == "number | null"
    assert fields["done"].ts_create_line == "done?: boolean;"
    assert fields["qty"].zod.startswith("z.string().regex(")
    assert fields["price"].to_payload_expr("data") == (
        "data.price.trim() === '' ? null : Number(data.price)"
    )
    assert fields["at"].to_form_expr("item") == "item.at.slice(0, 16)"
    assert fields["due"].cell_jsx("item").startswith("{item.due ? dateFormatter")
    assert fields["done"].cell_jsx("item") == "{item.done ? 'Sí' : 'No'}"

    assert fields["qty"].test_expected == "3"
    assert fields["price"].test_expected == "null"
    assert fields["at"].test_expected == "'2026-09-10T10:00'"


def test_field_labels_default_to_humanized_names():
    (field,) = parse_fields("work_title:str")
    assert field.label == "Work title"


@pytest.mark.parametrize(
    "spec",
    [
        "",
        "name:text",  # first must be str
        "name:str?",  # first must be required
        "id:str",  # reserved
        "name:str,name:str",  # duplicate
        "name:str,x:uuid",  # unknown kind
        "name:str,kind:choice",  # choice needs options
        "name:str,kind:choice(only_one)",  # at least two
        "name:str,kind:choice(a=A|a=B)",  # duplicate option
        "name:str,kind:choice(Bad Value=A|b=B)",  # snake_case options
        "name:str,qty:int(1|2)",  # options only for choice
        "name:choice(a|b)",  # first must be str
        "Name:str",  # not snake_case
        "name:str:Nombre:extra",
    ],
)
def test_parse_fields_rejects(spec):
    with pytest.raises(FieldError):
        parse_fields(spec)


def test_parse_status():
    assert parse_status(None) is None
    assert parse_status("  ") is None
    status = parse_status("draft=Borrador,done")
    assert [(v.value, v.label) for v in status.values] == [("draft", "Borrador"), ("done", "Done")]
    assert status.default == "draft" and status.last == "done"
    assert status.ts_union == "'draft' | 'done'"
    assert status.py_values == '"draft", "done"'
    assert "muted" in status.badge_style("draft") or "info" in status.badge_style("draft")
    assert "success" in status.badge_style("done")
    assert "destructive" in parse_status("ok,cancelled").badge_style("cancelled")
    assert parse_status("weird,active").unmapped_values == ["weird"]
    with pytest.raises(FieldError):
        parse_status("only_one")


def test_str_and_text_samples_are_unique_per_field():
    spec = "name:str:Nombre,phone:str?:Teléfono,city:str,notes:text?:Notas,bio:text?"
    fields = {f.name: f for f in parse_fields(spec)}
    samples = {f.ts_sample for f in fields.values()}
    assert len(samples) == 5
    assert fields["notes"].ts_sample == "'Notas de prueba'"
    assert fields["name"].ts_sample == "'Nombre de prueba'"
    assert fields["name"].py_sample == '"Nombre de prueba"'
    assert fields["city"].test_typed == "City de prueba"


def test_choice_kind_parses_options_and_renders_a_select():
    spec = (
        "name:str,doc:choice(national_id=Documento nacional|passport=Pasaporte)?:Documento,"
        "kind:choice(person|company=Empresa):Tipo"
    )
    fields = {f.name: f for f in parse_fields(spec)}
    doc, kind = fields["doc"], fields["kind"]
    assert [(c.value, c.label) for c in doc.choices] == [
        ("national_id", "Documento nacional"),
        ("passport", "Pasaporte"),
    ]
    assert [(c.value, c.label) for c in kind.choices] == [
        ("person", "Person"),
        ("company", "Empresa"),
    ]
    assert doc.optional and not kind.optional

    doc.prefix = kind.prefix = "Customer"
    assert doc.choice_alias == "CustomerDoc"
    assert doc.model_line == "doc: str | None = Field(default=None, max_length=50, nullable=True)"
    assert doc.migration_column == "sa.Column('doc', sa.String(length=50), nullable=True)"
    assert doc.create_line == "doc: CustomerDoc | None = None"
    assert kind.create_line == "kind: CustomerKind"
    assert kind.response_line == "kind: CustomerKind"
    assert kind.py_choices == '"person", "company"'
    assert kind.py_sample == '"person"' and kind.ts_sample == "'person'"

    assert kind.ts_type == "CustomerKind" and doc.ts_type == "CustomerDoc | null"
    assert kind.ts_choice_union == "'person' | 'company'"
    assert kind.zod == "z.enum(['person', 'company'])"
    assert doc.zod == "z.enum([NONE, 'national_id', 'passport'])"
    assert kind.form_empty == "'person'" and doc.form_empty == "NONE"
    assert doc.to_form_expr("item") == "item.doc ?? NONE"
    assert doc.to_payload_expr("data") == "data.doc === NONE ? null : data.doc"
    assert kind.cell_jsx("item") == "{kindLabels[item.kind]}"
    assert doc.cell_jsx("item") == "{item.doc ? docLabels[item.doc] : '—'}"
    assert kind.has_form_default and kind.test_expected == "'person'"
    assert doc.test_expected == "null"


def test_money_kind_is_decimal_on_the_backend_and_a_number_in_the_api():
    fields = {f.name: f for f in parse_fields("name:str,price:money:Precio,fee:money?")}
    price, fee = fields["price"], fields["fee"]
    assert price.model_line == (
        "price: Decimal = Field(sa_column=Column(Numeric(14, 2), nullable=False))"
    )
    assert "Numeric(14, 2), nullable=True" in fee.model_line
    assert price.migration_column == (
        "sa.Column('price', sa.Numeric(precision=14, scale=2), nullable=False)"
    )
    assert price.create_line == "price: Price"
    assert fee.create_line == "fee: Price | None = None"
    assert price.update_line == "price: Price | None = None"
    assert price.response_line == "price: PriceOut"
    assert fee.response_line == "fee: PriceOut | None"

    assert price.ts_type == "number" and fee.ts_create_line == "fee?: number | null;"
    assert price.zod.startswith("z.string().trim().min(1, 'Requerido').regex(")
    assert fee.zod.startswith("z.string().trim().regex(/^(")
    assert price.input_jsx == (
        '<Input inputMode="decimal" placeholder="0.00" autoComplete="off" {...field} />'
    )
    assert price.to_payload_expr("data") == "Number(data.price.trim().replace(',', '.'))"
    assert fee.to_payload_expr("data") == (
        "data.fee.trim() === '' ? null : Number(data.fee.trim().replace(',', '.'))"
    )
    assert price.to_form_expr("item") == "String(item.price)"
    assert price.cell_jsx("item") == "{moneyFormatter.format(item.price)}"
    assert fee.cell_jsx("item") == "{item.fee === null ? '—' : moneyFormatter.format(item.fee)}"
    assert price.cell_class == "tabular-nums"
    assert price.test_uses_type and price.test_typed == "99.90" and price.test_expected == "99.9"
    assert fee.test_expected == "null"
