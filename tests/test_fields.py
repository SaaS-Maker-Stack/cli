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
        "name:str,x:money",  # unknown kind
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
    assert "success" in status.badge_style(1)
    with pytest.raises(FieldError):
        parse_status("only_one")


def test_str_samples_are_unique_per_field():
    fields = {f.name: f for f in parse_fields("name:str:Nombre,phone:str?:Teléfono,city:str")}
    samples = {f.ts_sample for f in fields.values()}
    assert len(samples) == 3
    assert fields["name"].ts_sample == "'Nombre de prueba'"
    assert fields["name"].py_sample == '"Nombre de prueba"'
    assert fields["city"].test_typed == "City de prueba"
