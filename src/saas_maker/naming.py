"""Names derived from a module name: identifiers, paths and Spanish copy.

`saas-maker generate module work_order` -> WorkOrder / work_orders /
/work-orders / useWorkOrders / WorkOrdersPage … and the UI words that depend
on grammatical gender ("Nueva orden" vs "Nuevo proyecto").
"""

import re
from dataclasses import dataclass

SNAKE_RE = re.compile(r"^[a-z][a-z0-9_]*$")

_ES_IRREGULAR_PLURALS = {"s", "x", "z", "ch", "sh"}


class NamingError(ValueError):
    pass


def pluralize(word: str) -> str:
    """English plural for identifiers (override with --plural)."""
    if any(word.endswith(s) for s in _ES_IRREGULAR_PLURALS):
        return word + "es"
    if word.endswith("y") and word[-2:-1] not in "aeiou":
        return word[:-1] + "ies"
    return word + "s"


def camel(snake: str) -> str:
    return "".join(part.capitalize() for part in snake.split("_"))


def lower_first(text: str) -> str:
    return text[:1].lower() + text[1:] if text else text


def humanize(snake: str) -> str:
    """work_order -> Work order (a placeholder label when none is given)."""
    return snake.replace("_", " ").capitalize()


@dataclass
class Names:
    snake: str  # work_order
    plural_snake: str  # work_orders
    label: str  # "Orden de trabajo"
    label_plural: str  # "Órdenes de trabajo"
    feminine: bool = False
    icon: str = "FolderKanban"  # lucide-react icon for the sidebar / empty state

    @classmethod
    def build(
        cls,
        name: str,
        *,
        plural: str | None = None,
        label: str | None = None,
        label_plural: str | None = None,
        feminine: bool = False,
        icon: str = "FolderKanban",
    ) -> "Names":
        if not SNAKE_RE.match(name):
            raise NamingError(
                f"'{name}' is not a valid module name — use snake_case, singular "
                "(e.g. invoice, work_order)"
            )
        plural_snake = plural or pluralize(name)
        if not SNAKE_RE.match(plural_snake):
            raise NamingError(f"'{plural_snake}' is not a valid plural (snake_case)")
        if plural_snake == name:
            raise NamingError(f"plural '{plural_snake}' equals the singular — pass --plural")
        label = label or humanize(name)
        label_plural = label_plural or (label + ("es" if label[-1] not in "aeiou" else "s"))
        return cls(name, plural_snake, label, label_plural, feminine, icon)

    # --- identifiers -------------------------------------------------------
    @property
    def camel(self) -> str:
        return camel(self.snake)

    @property
    def camel_plural(self) -> str:
        return camel(self.plural_snake)

    @property
    def lower_camel(self) -> str:
        return lower_first(self.camel)

    @property
    def lower_camel_plural(self) -> str:
        return lower_first(self.camel_plural)

    @property
    def kebab(self) -> str:
        return self.snake.replace("_", "-")

    @property
    def kebab_plural(self) -> str:
        return self.plural_snake.replace("_", "-")

    @property
    def table(self) -> str:
        return self.plural_snake

    @property
    def api_prefix(self) -> str:
        return f"/{self.kebab_plural}"

    @property
    def upper_snake(self) -> str:
        return self.snake.upper()

    # --- Spanish copy (gender-aware) ----------------------------------------
    @property
    def label_lower(self) -> str:
        return lower_first(self.label)

    @property
    def label_plural_lower(self) -> str:
        return lower_first(self.label_plural)

    @property
    def new_word(self) -> str:
        return "Nueva" if self.feminine else "Nuevo"

    @property
    def article(self) -> str:
        return "la" if self.feminine else "el"

    @property
    def article_plural(self) -> str:
        return "las" if self.feminine else "los"

    @property
    def first_word(self) -> str:
        return "la primera" if self.feminine else "el primer"

    @property
    def created_word(self) -> str:
        return "creada" if self.feminine else "creado"

    @property
    def updated_word(self) -> str:
        return "actualizada" if self.feminine else "actualizado"

    @property
    def deleted_word(self) -> str:
        return "eliminada" if self.feminine else "eliminado"

    @property
    def not_found(self) -> str:
        return f"{self.label} no {'encontrada' if self.feminine else 'encontrado'}"
