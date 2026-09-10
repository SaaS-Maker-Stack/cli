import pytest

from saas_maker.naming import Names, NamingError, pluralize


def test_pluralize_rules():
    assert pluralize("invoice") == "invoices"
    assert pluralize("box") == "boxes"
    assert pluralize("category") == "categories"
    assert pluralize("day") == "days"


def test_names_identifiers():
    n = Names.build(
        "work_order", label="Orden de trabajo", label_plural="Órdenes de trabajo", feminine=True
    )
    assert n.camel == "WorkOrder"
    assert n.camel_plural == "WorkOrders"
    assert n.lower_camel_plural == "workOrders"
    assert n.kebab_plural == "work-orders"
    assert n.api_prefix == "/work-orders"
    assert n.table == "work_orders"
    assert n.upper_snake == "WORK_ORDER"


def test_names_spanish_gender():
    f = Names.build("invoice", label="Factura", feminine=True)
    assert (f.new_word, f.article, f.article_plural) == ("Nueva", "la", "las")
    assert f.created_word == "creada"
    assert f.not_found == "Factura no encontrada"
    assert f.label_plural == "Facturas"
    m = Names.build("project", label="Proyecto")
    assert (m.new_word, m.first_word, m.deleted_word) == ("Nuevo", "el primer", "eliminado")
    assert m.label_plural == "Proyectos"


def test_names_defaults_and_overrides():
    n = Names.build("sheep", plural="sheep_flock")
    assert n.label == "Sheep"
    assert n.plural_snake == "sheep_flock"


def test_names_rejects_bad_input():
    with pytest.raises(NamingError):
        Names.build("Bad-Name")
    with pytest.raises(NamingError):
        Names.build("news", plural="news")
