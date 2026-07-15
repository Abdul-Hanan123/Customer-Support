"""
app.py
Main entry point for the AI Customer Support Chatbot (Axorvian Task 5).
Run with: streamlit run app.py
"""

import streamlit as st
import uuid
import io
from dotenv import load_dotenv

import database as db
import rag_pipeline as rag
import llm
import auth
import admin_panel

load_dotenv()

st.set_page_config(page_title="AI Customer Support", page_icon="💬", layout="wide")

# ---------- Init ----------
db.init_db()
if rag.load_index() is None:
    rag.build_index_from_kb_entries(db.get_all_kb_entries())

auth.require_login()
user = st.session_state.user

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

SUGGESTED_QUESTIONS = [
    "What services do you offer?",
    "How can I contact support?",
    "What are your business hours?",
    "How do I reset my password?",
]

# ---------- Sidebar ----------
with st.sidebar:
    st.markdown(f"### 👋 Hi, {user['username']}")
    st.caption(f"Role: {user['role']}")

    page = st.radio("Navigate", ["💬 Chat", "❓ FAQ", "🕘 History"] +
                     (["🛠️ Admin Panel"] if user["role"] == "admin" else []))

    st.divider()
    if st.button("➕ New Conversation"):
        st.session_state.session_id = str(uuid.uuid4())
        st.rerun()

    # Export chat history
    history = db.get_session_history(user["id"], st.session_state.session_id)
    if history:
        export_text = "\n".join([f"[{h['role'].upper()}] {h['message']}" for h in history])
        st.download_button("⬇️ Export This Chat", data=export_text,
                            file_name="chat_history.txt", mime="text/plain")

    st.divider()
    if st.button("🚪 Log Out"):
        auth.logout()

# ---------- Chat Page ----------
if page == "💬 Chat":
    st.title("💬 AI Customer Support Chatbot")

    history = db.get_session_history(user["id"], st.session_state.session_id)

    if not history:
        st.markdown("**Try asking:**")
        cols = st.columns(len(SUGGESTED_QUESTIONS))
        for i, q in enumerate(SUGGESTED_QUESTIONS):
            if cols[i].button(q, key=f"sugg_{i}"):
                st.session_state.pending_query = q

    for h in history:
        with st.chat_message(h["role"]):
            st.write(h["message"])
            if h["role"] == "assistant":
                col1, col2, _ = st.columns([1, 1, 10])
                if col1.button("👍", key=f"like_{h['id']}"):
                    db.save_feedback(h["id"], user["id"], "like")
                    st.toast("Thanks for the feedback!")
                if col2.button("👎", key=f"dislike_{h['id']}"):
                    db.save_feedback(h["id"], user["id"], "dislike")
                    st.toast("Thanks — we'll use this to improve.")

    query = st.chat_input("Type your question...")
    if "pending_query" in st.session_state:
        query = st.session_state.pop("pending_query")

    if query:
        with st.chat_message("user"):
            st.write(query)
        db.save_message(user["id"], st.session_state.session_id, "user", query)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                context_chunks = rag.retrieve_context(query, k=4)
                current_history = db.get_session_history(user["id"], st.session_state.session_id)
                answer = llm.generate_response(query, context_chunks, current_history)
                st.write(answer)
        db.save_message(user["id"], st.session_state.session_id, "assistant", answer)
        st.rerun()

# ---------- FAQ Page ----------
elif page == "❓ FAQ":
    st.title("❓ Frequently Asked Questions")
    faqs = db.get_all_faqs()
    if not faqs:
        st.info("No FAQs added yet.")
    for faq in faqs:
        with st.expander(faq["question"]):
            st.write(faq["answer"])

# ---------- History Page ----------
elif page == "🕘 History":
    st.title("🕘 Conversation History")
    sessions = db.get_all_sessions(user["id"])
    if not sessions:
        st.info("No past conversations.")
    for s in sessions:
        with st.expander(f"Session started {s['started']}  ·  {s['msg_count']} messages"):
            msgs = db.get_session_history(user["id"], s["session_id"])
            for m in msgs:
                st.markdown(f"**{m['role'].capitalize()}:** {m['message']}")
            if st.button("Resume this conversation", key=f"resume_{s['session_id']}"):
                st.session_state.session_id = s["session_id"]
                st.rerun()

# ---------- Admin Panel ----------
elif page == "🛠️ Admin Panel":
    admin_panel.render_admin_panel()
