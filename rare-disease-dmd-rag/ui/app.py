"""Streamlit UI. Top bar with a brand badge, source-count tiles, a query box
with a per-source evidence table, dedicated trial/literature comparison
tables, a regulatory insights table, and an executive dashboard. Every
table has a "Download as PDF" button (see reports/pdf.py).

Run: streamlit run ui/app.py
"""
from __future__ import annotations

import pathlib
import sys

import streamlit as st

# Make the project root importable regardless of the working directory
# `streamlit run` was launched from -- Streamlit doesn't always add it to
# sys.path the way `python -m` would, which otherwise breaks the
# `agents`/`rag`/`reports` imports below with a ModuleNotFoundError.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from agents import comparison
from rag.corpus import counts_by_source
from rag.pipeline import ask
from reports import pdf as pdf_report
from monitoring.feedback import log_feedback

BRAND_NAME = "Rare Disease DMD RAG"
BRAND_NAVY = "#0C447C"
# Optional: point this at your own logo image to show it in the top bar
# instead of the generic badge below.
LOGO_PATH = pathlib.Path(__file__).parent.parent / "logo" / "brand_logo.png"

st.set_page_config(page_title=BRAND_NAME, layout="wide")

if "query_count" not in st.session_state:
    st.session_state.query_count = 0
if "last_report" not in st.session_state:
    st.session_state.last_report = None


def _logo_html() -> str:
    if LOGO_PATH.exists():
        import base64
        encoded = base64.b64encode(LOGO_PATH.read_bytes()).decode()
        return f'<img src="data:image/png;base64,{encoded}" style="height:32px;" />'
    return (
        f'<div style="width:36px;height:36px;border-radius:8px;background:{BRAND_NAVY};'
        'display:flex;align-items:center;justify-content:center;color:white;font-weight:600;">DMD</div>'
    )


st.markdown(
    f"""
    <div style="display:flex;align-items:center;gap:12px;padding:12px 16px;
                background:#F1EFE8;border-radius:12px;margin-bottom:16px;">
      <div style="background:white;border-radius:8px;padding:4px 10px;display:flex;align-items:center;">
        {_logo_html()}
      </div>
      <div>
        <div style="font-weight:600;font-size:16px;color:{BRAND_NAVY};">{BRAND_NAME}</div>
        <div style="font-size:13px;color:#5F5E5A;">Clinical trial intelligence -- DMD</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

SOURCE_COLORS = {
    "literature": "#7F77DD", "trial": "#1D9E75",
    "biomarker": "#D4537E", "regulatory": "#D85A30",
}
_corpus_counts = counts_by_source()
cols = st.columns(len(_corpus_counts))
for i, (name, count) in enumerate(_corpus_counts.items()):
    with cols[i]:
        color = SOURCE_COLORS.get(name, "#5F5E5A")
        st.markdown(
            f"<div style='border-radius:8px;padding:8px;background:{color}22;'>"
            f"<span style='color:{color};font-weight:600;font-size:13px;'>{name.title()} ({count})</span></div>",
            unsafe_allow_html=True,
        )

tab_ask, tab_trials, tab_lit, tab_reg, tab_dash = st.tabs(
    ["Ask a Question", "Compare Trials", "Compare Literature", "Regulatory Insights",
     "Executive Dashboard"]
)

# ---------------------------------------------------------------- Ask a Question
with tab_ask:
    question = st.text_input(
        "Ask a question about DMD trials, literature, regulatory history, or biomarkers",
        placeholder="Compare exon-skipping trial endpoints for DMD across phase 2 vs phase 3",
    )
    top_k = st.slider(
        "Sources to retrieve", min_value=3, max_value=25, value=10,
        help="How many top-matching records across the whole corpus (trials, literature, "
             "biomarker, regulatory) to ground the answer in.",
    )

    if st.button("Run query", type="primary") and question:
        st.session_state.query_count += 1
        with st.spinner("Retrieving evidence..."):
            st.session_state.last_report = ask(question, top_k=top_k)

    report = st.session_state.last_report
    if report:
        st.markdown("**Grounded answer**")
        st.write(report.summary)
        if report.note:
            st.caption(f"ℹ️ {report.note}")

        st.markdown(f"**Evidence ({len(report.citations)} source{'s' if len(report.citations) != 1 else ''})**")
        by_source: dict[str, list] = {}
        for c in report.citations:
            by_source.setdefault(c["source_type"], []).append(c)
        if by_source:
            for source_type, rows in by_source.items():
                with st.expander(f"{source_type.title()} ({len(rows)})", expanded=True):
                    st.dataframe(
                        [{"Citation": r["citation"], "URL": r["url"] or "-"} for r in rows],
                        width='stretch', hide_index=True,
                    )
        else:
            st.caption("No matching evidence found.")

        pdf_bytes = pdf_report.answer_pdf(report.question, report.summary, report.citations, report.note)
        st.download_button("📄 Download answer as PDF", pdf_bytes,
                            file_name="dmd_answer.pdf", mime="application/pdf")

        st.markdown("**Was this answer helpful?**")
        fb_up, fb_down, _ = st.columns([1, 1, 6])
        if fb_up.button("👍 Helpful", key="fb_up"):
            log_feedback(report.question, rating=5)
            st.toast("Thanks for the feedback!")
        if fb_down.button("👎 Not helpful", key="fb_down"):
            log_feedback(report.question, rating=1)
            st.toast("Thanks for the feedback!")

# ---------------------------------------------------------------- Compare Trials
with tab_trials:
    st.markdown("Search for two trials, then compare them side by side.")
    search_col, _ = st.columns([3, 1])
    trial_query = search_col.text_input("Search trials (optional)", key="trial_search",
                                          placeholder="eteplirsen, exon 51, phase 3...")
    sl = comparison.shortlist("trial", trial_query or None, top_k=10)
    if sl.note:
        st.caption(f"ℹ️ {sl.note}")
    options = {f"{d.doc_id} -- {d.title[:70]}": d.doc_id for d in sl.items}

    c1, c2 = st.columns(2)
    with c1:
        label_a = st.selectbox("Trial A", options=list(options.keys()), key="trial_a") if options else None
    with c2:
        label_b = st.selectbox("Trial B", options=list(options.keys()),
                                index=min(1, len(options) - 1) if len(options) > 1 else 0,
                                key="trial_b") if options else None

    if st.button("Compare trials", type="primary") and label_a and label_b:
        st.session_state.query_count += 1
        try:
            result = comparison.compare_trials(options[label_a], options[label_b])
            st.markdown("**AI summary**")
            st.write(result.summary)
            table = [
                {"Parameter": r.parameter, f"Trial A ({result.label_a})": r.value_a,
                 f"Trial B ({result.label_b})": r.value_b, "AI Observation": r.ai_observation}
                for r in result.rows
            ]
            st.dataframe(table, width='stretch', hide_index=True)

            import csv
            import io
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=list(table[0].keys()))
            writer.writeheader()
            writer.writerows(table)
            dl1, dl2 = st.columns(2)
            dl1.download_button("Download table as CSV", buf.getvalue(),
                                 file_name=f"trial_comparison_{result.label_a}_vs_{result.label_b}.csv")
            pdf_bytes = pdf_report.comparison_pdf("Trial", result.label_a, result.label_b,
                                                   result.rows, result.summary, result.caveat)
            dl2.download_button("📄 Download as PDF", pdf_bytes,
                                 file_name=f"trial_comparison_{result.label_a}_vs_{result.label_b}.pdf",
                                 mime="application/pdf")
        except ValueError as exc:
            st.error(str(exc))

# ------------------------------------------------------------- Compare Literature
with tab_lit:
    st.markdown("Search for two articles, then compare them side by side.")
    lit_query = st.text_input("Search literature (optional)", key="lit_search",
                                placeholder="exon skipping, dystrophin, gene therapy...")
    sl_lit = comparison.shortlist("literature", lit_query or None, top_k=10)
    if sl_lit.note:
        st.caption(f"ℹ️ {sl_lit.note}")
    lit_options = {f"{d.citation} -- {d.title[:70]}": d.doc_id.replace("PMID", "") for d in sl_lit.items}

    c1, c2 = st.columns(2)
    with c1:
        lit_label_a = st.selectbox("Paper A", options=list(lit_options.keys()), key="lit_a") if lit_options else None
    with c2:
        lit_label_b = st.selectbox("Paper B", options=list(lit_options.keys()),
                                    index=min(1, len(lit_options) - 1) if len(lit_options) > 1 else 0,
                                    key="lit_b") if lit_options else None

    if st.button("Compare papers", type="primary") and lit_label_a and lit_label_b:
        st.session_state.query_count += 1
        try:
            result = comparison.compare_literature(lit_options[lit_label_a], lit_options[lit_label_b])
            st.markdown("**AI summary**")
            st.write(result.summary)
            if result.caveat:
                st.caption(f"⚠️ {result.caveat}")
            table = [
                {"Parameter": r.parameter, f"Paper A ({result.label_a})": r.value_a,
                 f"Paper B ({result.label_b})": r.value_b, "AI Observation": r.ai_observation}
                for r in result.rows
            ]
            st.dataframe(table, width='stretch', hide_index=True)

            pdf_bytes = pdf_report.comparison_pdf("Literature", result.label_a, result.label_b,
                                                   result.rows, result.summary, result.caveat)
            st.download_button("📄 Download as PDF", pdf_bytes,
                                file_name=f"literature_comparison_{result.label_a}_vs_{result.label_b}.pdf".replace(" ", "_"),
                                mime="application/pdf")
        except ValueError as exc:
            st.error(str(exc))

# ---------------------------------------------------------- Regulatory Insights
with tab_reg:
    guidance = comparison.load_regulatory_guidance()
    st.caption(guidance.get("note", ""))
    rows = [
        {"Guidance/Update": item["guidance"], "Agency": item["agency"], "Date": item["date"],
         "Status": item["status"], "Impact Area": item["impact_area"], "AI Insight": item["ai_insight"]}
        for item in guidance.get("items", [])
    ]
    st.dataframe(rows, width='stretch', hide_index=True)

    pdf_bytes = pdf_report.guidance_pdf(guidance.get("items", []), guidance.get("note"))
    st.download_button("📄 Download as PDF", pdf_bytes,
                        file_name="regulatory_insights.pdf", mime="application/pdf")

    st.caption(
        "A protocol-level gap-analysis table (protocol attribute vs. regulatory expectation vs. "
        "recommendation) is planned for a follow-up pass -- it needs a specific protocol to compare against."
    )

# ---------------------------------------------------------------- Executive Dashboard
with tab_dash:
    counts = counts_by_source()
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Trials indexed", counts.get("trial", 0))
    m2.metric("Publications indexed", counts.get("literature", 0))
    m3.metric("Regulatory documents indexed", counts.get("regulatory", 0))
    m4.metric("Biomarker records indexed", counts.get("biomarker", 0))
    m5.metric("Queries performed (this session)", st.session_state.query_count)

    st.markdown("**Latest FDA/EMA guidance**")
    guidance = comparison.load_regulatory_guidance()
    latest = sorted(guidance.get("items", []), key=lambda i: i["date"], reverse=True)[:5]
    st.dataframe(
        [{"Guidance/Update": i["guidance"], "Agency": i["agency"], "Date": i["date"],
          "Impact Area": i["impact_area"]} for i in latest],
        width='stretch', hide_index=True,
    )
    st.caption("See the Regulatory Insights tab for the full table with AI-generated impact notes, "
               "and Compare Trials/Compare Literature for the comparison tables.")
