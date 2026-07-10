"""In-memory fakes for the Mongo/Motor seam.

Implements only the surface TreeBuilder and its collaborators actually use:
`find_one`, `find` (-> a cursor with `.sort()`/`.limit()`/`.to_list()`/`async for`),
the `$elemMatch` positional-arg matcher `find_descendants` relies on, and the
`col.database[...]` / `.get_collection(...)` sideways hops used by
`_expand_compound_edges` (etymology_edges) and `lang_cache` (languages).

Per the bdd-tiered-testing skill: this fake models only what's called today; its
`$elemMatch`/sort semantics should eventually get a paired Tier-1 contract test
against real Mongo (not yet added in this pass).
"""

from __future__ import annotations

import re
from typing import Any


def _get_path(doc: dict, path: str) -> Any:
    """Resolve a dotted field path (e.g. 'args.2') against a document."""
    value: Any = doc
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _op_regex(value: Any, operand: Any, condition: dict) -> bool:
    flags = re.IGNORECASE if "i" in condition.get("$options", "") else 0
    return isinstance(value, str) and re.search(operand, value, flags) is not None


def _op_elem_match(value: Any, operand: Any, _condition: dict) -> bool:
    elems = value if isinstance(value, list) else []
    return any(_matches_elem_match(elem, operand) for elem in elems)


# Operators the services actually issue; each returns whether the value matches.
_OPERATORS = {
    "$in": lambda value, operand, _cond: value in operand,
    "$ne": lambda value, operand, _cond: value != operand,
    "$exists": lambda value, operand, _cond: (value is not None) == operand,
    "$regex": _op_regex,
    "$elemMatch": _op_elem_match,
}


def _matches_field(value: Any, condition: Any) -> bool:
    """Match one field value against a condition: scalar equality, or an
    operator dict ($in/$ne/$exists/$regex/$elemMatch).

    Unknown operators fall back to whole-dict equality, so a query using an
    operator the fake doesn't model fails loudly in a test rather than silently
    matching everything.
    """
    if not isinstance(condition, dict):
        return value == condition
    for op, operand in condition.items():
        if op == "$options":
            continue  # consumed alongside $regex
        handler = _OPERATORS.get(op)
        if handler is None:
            return value == condition
        if not handler(value, operand, condition):
            return False
    return True


def _matches_elem_match(elem: Any, conditions: dict) -> bool:
    if not isinstance(elem, dict):
        return False
    return all(_matches_field(_get_path(elem, key), cond) for key, cond in conditions.items())


def _matches_filter(doc: dict, filt: dict) -> bool:
    for key, condition in filt.items():
        if key == "$or":
            if not any(_matches_filter(doc, sub) for sub in condition):
                return False
            continue
        if not _matches_field(_get_path(doc, key), condition):
            return False
    return True


def _project(doc: dict, projection: dict | None) -> dict:
    if not projection:
        return dict(doc)
    included = {k for k, v in projection.items() if v and k != "_id"}
    if not included:
        return dict(doc)
    return {k: doc[k] for k in included if k in doc}


def _sort_key_for(spec: list[tuple[str, int]]):
    """Build a sort key matching Mongo's ascending-sort semantics: missing/null
    fields sort before present ones, never raising on cross-doc type mismatches."""

    def key(doc: dict) -> tuple:
        parts = []
        for field, _direction in spec:
            value = _get_path(doc, field)
            parts.append((value is not None, value if value is not None else ""))
        return tuple(parts)

    return key


class FakeCursor:
    """Mimics the subset of an AsyncIOMotorCursor that tree_builder.py uses."""

    def __init__(self, docs: list[dict]):
        self._docs = docs

    def sort(self, spec: list[tuple[str, int]]) -> FakeCursor:
        self._docs = sorted(self._docs, key=_sort_key_for(spec))
        return self

    def limit(self, n: int) -> FakeCursor:
        self._docs = self._docs[:n]
        return self

    async def to_list(self, length: int | None = None) -> list[dict]:
        return self._docs[:length] if length is not None else list(self._docs)

    def __aiter__(self) -> FakeCursor:
        self._iter = iter(self._docs)
        return self

    async def __anext__(self) -> dict:
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration from None


class FakeCollection:
    """A single fake collection: matches filters, returns cursors, no indexes."""

    def __init__(self, docs: list[dict] | None = None, database: FakeDatabase | None = None):
        self._docs = docs or []
        self.database = database if database is not None else FakeDatabase()

    async def find_one(self, filt: dict, projection: dict | None = None) -> dict | None:
        for doc in self._docs:
            if _matches_filter(doc, filt):
                return _project(doc, projection)
        return None

    def find(self, filt: dict, projection: dict | None = None) -> FakeCursor:
        matched = [_project(doc, projection) for doc in self._docs if _matches_filter(doc, filt)]
        return FakeCursor(matched)

    async def replace_one(self, filt: dict, replacement: dict, upsert: bool = False) -> None:
        """Replace the first matching doc, or insert on upsert.

        Enough of Motor's replace_one for the SPC-00021 layouts write-through
        cache (keyed by ``{"_id": ...}``); return value is unused by callers so
        it is omitted.
        """
        for idx, doc in enumerate(self._docs):
            if _matches_filter(doc, filt):
                self._docs[idx] = dict(replacement)
                return
        if upsert:
            self._docs.append(dict(replacement))


class FakeDatabase:
    """Dict-and-attribute-style access to sibling fake collections (`col.database[...]`,
    `col.database.get_collection(...)`), matching the real Motor database interface."""

    def __init__(self, collections: dict[str, FakeCollection] | None = None):
        self._collections = collections or {}

    def __getitem__(self, name: str) -> FakeCollection:
        return self._collections.setdefault(name, FakeCollection())

    def get_collection(self, name: str) -> FakeCollection:
        return self[name]


class FakeWordsCollection(FakeCollection):
    """The `words` collection fake, with `etymology_edges`/`languages` siblings
    wired through `.database` exactly as the real Motor collection exposes them."""

    def __init__(
        self,
        docs: list[dict],
        etymology_edges: list[dict] | None = None,
        languages: list[dict] | None = None,
    ):
        database = FakeDatabase(
            {
                "etymology_edges": FakeCollection(etymology_edges or []),
                "languages": FakeCollection(languages or []),
            }
        )
        super().__init__(docs, database=database)
