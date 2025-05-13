import pytest
from uuid import uuid4
from app.tasks.bookmark_save_task import _save_bookmark_logic

HTML_CONTENT = """
<html>
  <head><meta property="og:image" content="thumb.jpg"></head>
  <body>
    <p>First paragraph.</p>
    <p>Second paragraph.</p>
  </body>
</html>
"""

class DummyVectorStore:
    def __init__(self, persist_directory, embedding_function, collection_name):
        self.persist_directory = persist_directory
        self.embedding_function = embedding_function
        self.collection_name = collection_name
        self._deleted = []
        self._added = []
        self._persisted = False
        self._existing_ids = [f"star123-0", "other-1"]

    @property
    def _collection(self):

        class C:
            def __init__(self, ids):
                self._ids = ids
            def get(self, include=None):
                return {"ids": self._ids}
        return C(self._existing_ids)

    def delete(self, ids):
        self._deleted.extend(ids)

    def add_texts(self, texts, ids, metadatas, embedding):
        self._added.append({
            "texts": texts,
            "ids": ids,
            "metadatas": metadatas,
            "embedding": embedding
        })

    def persist(self):
        self._persisted = True


@pytest.fixture(autouse=True)
def patch_deps(monkeypatch):
    monkeypatch.setattr(
        "app.tasks.bookmark_save_task.download_html_from_s3",
        lambda k: HTML_CONTENT
    )
    dummy = DummyVectorStore(None, None, None)
    monkeypatch.setattr(
        "app.tasks.bookmark_save_task.Chroma",
        lambda *args, **kwargs: dummy
    )
    return dummy

def test_logic(patch_deps):
    dv = patch_deps
    res = _save_bookmark_logic("u1", "star1", "key", ["x","y"], "memo", "sum")

    texts = dv._added[0]["texts"]
    ids   = dv._added[0]["ids"]

    assert res["inserted"] == len(texts)
    assert len(ids) == len(texts)
    assert ids[0].startswith("star1-")