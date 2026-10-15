"""Small Firestore stand-in for service tests. Not a network client."""


class FakeSnapshot:
    def __init__(self, doc_id: str, data: dict | None):
        self.id = doc_id
        self._data = None if data is None else dict(data)
        self.exists = data is not None

    def to_dict(self):
        if self._data is None:
            return None
        return dict(self._data)


class FakeQuery:
    def __init__(self, docs: list[FakeSnapshot]):
        self._docs = docs
        self._limit = None

    def order_by(self, field: str, direction: str = "ASCENDING"):
        reverse = str(direction).upper() == "DESCENDING"
        self._docs.sort(
            key=lambda doc: (doc.to_dict() or {}).get(field) or "",
            reverse=reverse,
        )
        return self

    def limit(self, count: int):
        self._limit = count
        return self

    def stream(self):
        docs = self._docs
        if self._limit is not None:
            docs = docs[: self._limit]
        return iter(docs)


class FakeDocument:
    def __init__(self, store: "FakeDB", collection_path: str, doc_id: str | None):
        self.store = store
        self.collection_path = collection_path
        self.id = doc_id or store.new_id()
        self.full_path = f"{collection_path}/{self.id}"

    def collection(self, name: str) -> "FakeCollection":
        return FakeCollection(self.store, f"{self.full_path}/{name}")

    def set(self, data: dict) -> None:
        self.store.docs[self.full_path] = dict(data)

    def get(self) -> FakeSnapshot:
        return FakeSnapshot(self.id, self.store.docs.get(self.full_path))


class FakeCollection:
    def __init__(self, store: "FakeDB", path: str):
        self.store = store
        self.path = path

    def document(self, doc_id: str | None = None) -> FakeDocument:
        return FakeDocument(self.store, self.path, doc_id)

    def _snapshots(self) -> list[FakeSnapshot]:
        prefix = f"{self.path}/"
        found = []
        for key, data in self.store.docs.items():
            if key.startswith(prefix) and "/" not in key[len(prefix) :]:
                found.append(FakeSnapshot(key[len(prefix) :], data))
        return found

    def order_by(self, field: str, direction: str = "ASCENDING") -> FakeQuery:
        return FakeQuery(self._snapshots()).order_by(field, direction)

    def limit(self, count: int) -> FakeQuery:
        return FakeQuery(self._snapshots()).limit(count)

    def stream(self):
        return FakeQuery(self._snapshots()).stream()


class FakeDB:
    def __init__(self):
        self.docs: dict[str, dict] = {}
        self._next_id = 0

    def new_id(self) -> str:
        self._next_id += 1
        return f"id-{self._next_id}"

    def collection(self, name: str) -> FakeCollection:
        return FakeCollection(self, name)


class BoomDB:
    """Client whose first call fails the way a down Firestore project would."""

    def collection(self, name: str):
        raise RuntimeError(f"firestore unavailable for {name}")
