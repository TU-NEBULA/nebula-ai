import pytest
import asyncio
from types import SimpleNamespace

import app.services.chat as chat_mod 

class DummyDoc:
    def __init__(self, metadata, content):
        self.metadata = metadata
        self.page_content = content
        self.snippet = content[:100]

@pytest.fixture(autouse=True)
def mock_chroma(monkeypatch):
    """
    * ChromaDBClient → 파일 접근 없는 더미
    * Chroma → similarity_search_with_score 결과를 store_holder에 저장
    """
    class DummyChromaDBClient:
        def __init__(self, *a, **kw):
            self.client = None
        def get_or_create_collection(self, *a, **kw):
            return SimpleNamespace(name="test_coll")
    monkeypatch.setattr(chat_mod, "ChromaDBClient", DummyChromaDBClient)

    store_holder = {}

    def fake_chroma_init(self, *a, **kw):
        self._dummy_key = "ok"

    async def fake_async_search(*a, **kw):
        return store_holder["docs"]

    def fake_search(self, query, k=10):
        return store_holder["docs"]

    monkeypatch.setattr(chat_mod.Chroma, "__init__", fake_chroma_init, raising=True)
    monkeypatch.setattr(chat_mod.Chroma, "similarity_search_with_score", fake_search, raising=False)

    return store_holder

@pytest.fixture(autouse=True)
def mock_llm(monkeypatch):
    class DummyLLM:
        def __call__(self, *a, **kw):
            class Msg: content = "LLM 응답\nGRAPH_PAYLOAD: {...}"
            return Msg()
    monkeypatch.setattr(chat_mod, "ChatOpenAI", lambda *a, **kw: DummyLLM())

@pytest.mark.asyncio
async def test_process_chat_success(mock_chroma):
    d1 = DummyDoc({"id":"d1","user_id":1,"title":"T1","url":"U1","keywords":["a"]}, "내용1")
    d2 = DummyDoc({"id":"d2","user_id":1,"title":"T2","url":"U2","keywords":["a","b"]}, "내용2")
    mock_chroma["docs"] = [(d1,0.1),(d2,0.2)]

    res = await chat_mod.process_chat_request(1, "spring boot")

    assert res["graphPayload"]["nodes"][0]["label"] == "T1"
    assert any(res["graphPayload"]["edges"])

@pytest.mark.asyncio
async def test_process_chat_no_result(mock_chroma):
    mock_chroma["docs"] = []

    res = await chat_mod.process_chat_request(1, "nothing")

    assert res["graphPayload"]["nodes"] == []
    assert res["answer"].startswith("관련 자료가 없어요")
