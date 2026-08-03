"""Pluggable generation backend.

Two modes, controlled by LLM_MODE env var:
  - "extractive" (default): no LLM call at all. Templates the retrieved
    EvidencePackets directly into a cited summary. Zero dependencies, always
    works offline -- this is also the demo's fallback if a live LLM call
    fails mid-workshop (see workflow doc, open questions).
  - "llm": calls an OpenAI-compatible chat endpoint. Point it at anything
    open per the workflow doc's tool stack -- a local Ollama server
    (OPENAI_API_BASE=http://localhost:11434/v1, model llama3.1), a local
    llama.cpp server (run `./build/bin/llama-server -m
    models/Llama-3.1-8B-Instruct-Q4_K_M.gguf`, then
    OPENAI_API_BASE=http://localhost:8080/v1 -- llama-server exposes the
    same OpenAI-compatible /v1/chat/completions route), Groq's free tier
    serving open-weight models, or Hugging Face's Inference API.

Both modes return plain text with inline [n] markers the caller maps back
to EvidencePacket citations -- never an unattributed claim.
"""
from __future__ import annotations

import os
import pathlib

from dotenv import load_dotenv

from rag.retrieve import EvidencePacket

# docker-compose.yml reads .env automatically and injects it as container
# env vars; a plain `streamlit run`/`python` invocation never sees it
# otherwise. Load it explicitly here so LLM_MODE etc. work the same way
# outside Docker. Real shell-exported env vars still win (override=False).
load_dotenv(pathlib.Path(__file__).resolve().parent.parent / ".env")

LLM_MODE = os.environ.get("LLM_MODE", "extractive")


def _extractive_summary(question: str, evidence: list[EvidencePacket]) -> str:
    if not evidence:
        return "No matching evidence found in the DMD corpus for this question."
    lines = [f"Evidence relevant to: \"{question}\""]
    for i, ev in enumerate(evidence, 1):
        snippet = ev.claim_text.strip()
        if len(snippet) > 280:
            snippet = snippet[:280].rsplit(" ", 1)[0] + "..."
        lines.append(f"[{i}] {snippet} (source: {ev.citation})")
    return "\n".join(lines)


def _llm_summary(question: str, evidence: list[EvidencePacket]) -> str:
    from openai import OpenAI  # openai>=1.0 client works against any compatible endpoint

    client = OpenAI(
        base_url=os.environ.get("OPENAI_API_BASE", "http://localhost:11434/v1"),
        api_key=os.environ.get("OPENAI_API_KEY", "not-needed-for-local-ollama"),
    )
    context = "\n".join(f"[{i}] {ev.claim_text} (source: {ev.citation})" for i, ev in enumerate(evidence, 1))
    prompt = (
        "Answer the question using ONLY the numbered evidence below. "
        "Cite evidence with its [n] marker inline for every claim. "
        "If the evidence doesn't support an answer, say so.\n\n"
        f"Evidence:\n{context}\n\nQuestion: {question}"
    )
    resp = client.chat.completions.create(
        model=os.environ.get("MODEL_NAME", "llama3.1"),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )
    return resp.choices[0].message.content


def generate(question: str, evidence: list[EvidencePacket]) -> str:
    if LLM_MODE == "llm":
        try:
            return _llm_summary(question, evidence)
        except Exception as exc:  # network/model unavailable -- fall back rather than crash the demo
            return _extractive_summary(question, evidence) + f"\n\n[LLM backend unavailable, showing extractive fallback: {exc}]"
    return _extractive_summary(question, evidence)


def extract_fields(text: str, fields: list[str]) -> dict[str, str]:
    """Ask the LLM to pull structured fields (e.g. sample size, biomarker)
    out of unstructured text like a PubMed abstract. Only available in
    LLM_MODE=llm -- there's no reliable extractive equivalent, so every
    field comes back "Not available" in the default offline mode."""
    not_available = {f: "Not available (offline mode)" for f in fields}
    if LLM_MODE != "llm":
        return not_available

    import json as _json
    from openai import OpenAI

    client = OpenAI(
        base_url=os.environ.get("OPENAI_API_BASE", "http://localhost:11434/v1"),
        api_key=os.environ.get("OPENAI_API_KEY", "not-needed-for-local-ollama"),
    )
    field_list = ", ".join(fields)
    prompt = (
        f"Extract these fields from the text below: {field_list}. "
        "Respond with ONLY a JSON object mapping each field name to a short value. "
        "If a field isn't mentioned in the text, use the string \"Not stated in source\".\n\n"
        f"Text:\n{text}"
    )
    try:
        resp = client.chat.completions.create(
            model=os.environ.get("MODEL_NAME", "llama3.1"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )
        content = resp.choices[0].message.content.strip()
        content = content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = _json.loads(content)
        return {f: str(parsed.get(f, "Not stated in source")) for f in fields}
    except Exception:
        return {f: "Not available (LLM extraction failed)" for f in fields}
