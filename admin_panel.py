"""
admin_panel.py
Admin-only panel: manage knowledge base entries, upload documents,
view conversation logs, feedback, and usage stats.
"""

import streamlit as st
import pandas as pd
import os
import tempfile
import database as db
import rag_pipeline as rag


def render_admin_panel():
    st.header("🛠️ Admin Panel")
    tabs = st.tabs(["📚 Knowledge Base", "📄 Upload Documents", "💬 Conversation Logs",
                     "👍 Feedback", "📊 Usage Stats", "❓ Manage FAQs"])

    # ---------- Knowledge Base CRUD ----------
    with tabs[0]:
        st.subheader("Add New Entry")
        with st.form("add_kb_form", clear_on_submit=True):
            title = st.text_input("Title")
            content = st.text_area("Content", height=150)
            submitted = st.form_submit_button("Add Entry")
            if submitted and title and content:
                db.add_kb_entry(title, content, source="manual")
                _rebuild_index()
                st.success(f"Added '{title}' and rebuilt the search index.")
                st.rerun()

        st.subheader("Existing Entries")
        entries = db.get_all_kb_entries()
        if not entries:
            st.info("No knowledge base entries yet.")
        for entry in entries:
            with st.expander(f"{entry['title']}  ·  ({entry['source']})"):
                new_title = st.text_input("Title", value=entry["title"], key=f"t_{entry['id']}")
                new_content = st.text_area("Content", value=entry["content"], key=f"c_{entry['id']}", height=150)
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Save Changes", key=f"save_{entry['id']}"):
                        db.update_kb_entry(entry["id"], new_title, new_content)
                        _rebuild_index()
                        st.success("Updated and re-indexed.")
                        st.rerun()
                with col2:
                    if st.button("Delete", key=f"del_{entry['id']}"):
                        db.delete_kb_entry(entry["id"])
                        _rebuild_index()
                        st.warning("Deleted and re-indexed.")
                        st.rerun()

    # ---------- Document Upload (bonus: PDF KB) ----------
    with tabs[1]:
        st.subheader("Upload a PDF to extend the knowledge base")
        uploaded_pdf = st.file_uploader("Choose a PDF", type=["pdf"])
        if uploaded_pdf and st.button("Ingest PDF"):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(uploaded_pdf.read())
                tmp_path = tmp.name
            with st.spinner("Extracting and indexing PDF content..."):
                text = rag.add_pdf_to_kb(tmp_path, uploaded_pdf.name)
                db.add_kb_entry(uploaded_pdf.name, text, source="pdf")
                _rebuild_index()
            os.remove(tmp_path)
            st.success(f"Ingested '{uploaded_pdf.name}' into the knowledge base.")
            st.rerun()

    # ---------- Conversation Logs ----------
    with tabs[2]:
        st.subheader("All Conversation Logs")
        logs = db.get_all_chat_logs()
        if logs:
            df = pd.DataFrame(logs)[["timestamp", "username", "session_id", "role", "message"]]
            st.dataframe(df, use_container_width=True, height=400)
        else:
            st.info("No conversations yet.")

    # ---------- Feedback ----------
    with tabs[3]:
        st.subheader("User Feedback")
        stats = db.get_feedback_stats()
        col1, col2 = st.columns(2)
        col1.metric("👍 Likes", stats.get("like", 0))
        col2.metric("👎 Dislikes", stats.get("dislike", 0))

        feedback_rows = db.get_all_feedback()
        if feedback_rows:
            df = pd.DataFrame(feedback_rows)[["timestamp", "username", "rating", "bot_message"]]
            st.dataframe(df, use_container_width=True, height=350)
        else:
            st.info("No feedback submitted yet.")

    # ---------- Usage Stats ----------
    with tabs[4]:
        st.subheader("Usage Overview")
        logs = db.get_all_chat_logs()
        if logs:
            df = pd.DataFrame(logs)
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Messages", len(df))
            col2.metric("Unique Users", df["username"].nunique())
            col3.metric("Total Sessions", df["session_id"].nunique())

            df["date"] = pd.to_datetime(df["timestamp"]).dt.date
            daily_counts = df.groupby("date").size()
            st.bar_chart(daily_counts)
        else:
            st.info("No usage data yet.")

    # ---------- Manage FAQs ----------
    with tabs[5]:
        st.subheader("Add FAQ")
        with st.form("add_faq_form", clear_on_submit=True):
            q = st.text_input("Question")
            a = st.text_area("Answer", height=100)
            if st.form_submit_button("Add FAQ") and q and a:
                db.add_faq(q, a)
                st.success("FAQ added.")
                st.rerun()

        st.subheader("Existing FAQs")
        for faq in db.get_all_faqs():
            col1, col2 = st.columns([5, 1])
            col1.markdown(f"**Q:** {faq['question']}  \n**A:** {faq['answer']}")
            if col2.button("Delete", key=f"faq_del_{faq['id']}"):
                db.delete_faq(faq["id"])
                st.rerun()


def _rebuild_index():
    entries = db.get_all_kb_entries()
    rag.build_index_from_kb_entries(entries)
