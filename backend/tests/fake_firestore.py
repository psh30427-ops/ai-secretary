"""테스트용 인메모리 Firestore 대역. 이 프로젝트가 쓰는 API만 흉내 낸다."""
import copy
import itertools

_OPS = {
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    "==": lambda a, b: a == b,
}
_ids = itertools.count(1)


class _Snap:
    def __init__(self, doc_id, data):
        self.id = doc_id
        self._data = data

    @property
    def exists(self):
        return self._data is not None

    def to_dict(self):
        return copy.deepcopy(self._data)


class _DocRef:
    def __init__(self, store, doc_id):
        self._store, self.id = store, doc_id

    def get(self):
        return _Snap(self.id, self._store.get(self.id))

    def set(self, data):
        self._store[self.id] = copy.deepcopy(data)

    def update(self, data):
        if self.id not in self._store:
            raise KeyError(self.id)
        self._store[self.id].update(copy.deepcopy(data))

    def delete(self):
        self._store.pop(self.id, None)


class _Query:
    def __init__(self, store, filters=(), order=None):
        self._store, self._filters, self._order = store, list(filters), order

    def where(self, filter):
        return _Query(self._store, self._filters + [filter], self._order)

    def order_by(self, field, direction="ASCENDING"):
        return _Query(self._store, self._filters, (field, direction))

    def select(self, fields):
        return self

    def stream(self):
        rows = [
            (k, v)
            for k, v in self._store.items()
            if all(_OPS[f.op_string](v.get(f.field_path), f.value) for f in self._filters)
        ]
        if self._order:
            field, direction = self._order
            rows.sort(key=lambda kv: kv[1].get(field), reverse=str(direction).upper() == "DESCENDING")
        return [_Snap(k, copy.deepcopy(v)) for k, v in rows]


class _Collection(_Query):
    def document(self, doc_id=None):
        return _DocRef(self._store, doc_id or f"doc{next(_ids)}")


class _Batch:
    def __init__(self):
        self._ops = []

    def set(self, ref, data):
        self._ops.append((ref, data))

    def commit(self):
        for ref, data in self._ops:
            ref.set(data)


class FakeFirestore:
    def __init__(self):
        self.collections: dict[str, dict] = {}

    def collection(self, name):
        return _Collection(self.collections.setdefault(name, {}))

    def batch(self):
        return _Batch()
