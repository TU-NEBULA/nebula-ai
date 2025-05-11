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
    Chroma 벡터스토어를 파일 I/O 없이 동작하도록 모킹하고,
    similarity_search_with_score 호출 결과를 store_holder에 담아 반환.
    """
    store_holder = {}

    def fake_chroma_init(self, *args, **kwargs):
        pass

    def fake_search(self, query, k=chat_mod.TOP_K):
        return store_holder.get("docs", [])

    monkeypatch.setattr(chat_mod.Chroma, "__init__", fake_chroma_init, raising=True)
    monkeypatch.setattr(chat_mod.Chroma, "similarity_search_with_score", fake_search, raising=True)

    return store_holder

@pytest.fixture(autouse=True)
def mock_llm(monkeypatch):
    """
    ChatOpenAI 를 호출해도 실제 API 호출 없이
    고정된 응답 객체를 반환하도록 모킹.
    """
    class DummyLLM:
        def __call__(self, messages, **kwargs):
            class Msg:
                content = "LLM 응답 텍스트\nGRAPH_PAYLOAD: {...}"
            return Msg()

    monkeypatch.setattr(chat_mod, "ChatOpenAI", lambda *args, **kwargs: DummyLLM())

@pytest.mark.asyncio
async def test_process_chat_success(mock_chroma):
    d1 = DummyDoc(
        {"id": "d1", "user_id": 1, "title": "T1", "url": "U1", "keywords": ["a"]},
        "내용1"
    )
    d2 = DummyDoc(
        {"id": "d2", "user_id": 1, "title": "T2", "url": "U2", "keywords": ["a", "b"]},
        "내용2"
    )

    d3 = DummyDoc(
        {"id": "d3", "user_id": 2, "title": "T3", "url": "U3", "keywords": ["c"]},
        "내용3"
    )

    mock_chroma["docs"] = [(d1, 0.1), (d2, 0.2), (d3, 0.3)]

    res = await chat_mod.process_chat_request(1, "테스트 메시지")

    labels = [n["label"] for n in res["graphPayload"]["nodes"]]
    assert "T1" in labels and "T2" in labels
    assert all(n["label"] in labels for n in res["graphPayload"]["nodes"])

    assert any(edge["source"].startswith("d1") and edge["target"].startswith("d2")
               for edge in res["graphPayload"]["edges"])

    assert res["answer"].startswith("LLM 응답 텍스트")

@pytest.mark.asyncio
async def test_process_chat_no_result(mock_chroma):

    mock_chroma["docs"] = []

    res = await chat_mod.process_chat_request(1, "아무 키워드")

    assert res["graphPayload"]["nodes"] == []
    assert res["answer"].startswith("관련 자료가 없어요")
