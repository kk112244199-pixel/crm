"""Host-side ragas import shims.

ragas 0.4 still does `from langchain_community.chat_models.vertexai import ChatVertexAI`.
Newer langchain-community dropped that module; we only need the class for isinstance checks.
"""
from __future__ import annotations
import sys
import types


def patch_langchain_vertex_stubs() -> None:
    if "langchain_community.chat_models.vertexai" in sys.modules:
        return
    mod = types.ModuleType("langchain_community.chat_models.vertexai")

    class ChatVertexAI:  # noqa: N801 — ragas expects this name
        pass

    mod.ChatVertexAI = ChatVertexAI
    sys.modules["langchain_community.chat_models.vertexai"] = mod


def import_ragas_evaluate():
    patch_langchain_vertex_stubs()
    from ragas import evaluate
    from ragas.metrics import answer_relevancy, context_recall, faithfulness

    return evaluate, faithfulness, answer_relevancy, context_recall
