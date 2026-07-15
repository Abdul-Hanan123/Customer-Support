# AI Customer Support Chatbot

A production-style RAG-powered customer support chatbot with a company knowledge base,
admin management panel, and context-aware multi-turn responses.

## Features
- User login & registration (SQLite + bcrypt password hashing)
- Clean chat interface (Streamlit `st.chat_message`)
- RAG pipeline: FAISS vector DB + Gemini embeddings + Gemini 1.5 Flash generation
- Context-aware, multi-turn conversation (recent history fed into the prompt)
- FAQ section
- Conversation history tracking, browsing, and resuming
- Suggested starter questions
- Like / Dislike feedback per response
- Export chat history (.txt download)
- Admin panel: KB CRUD, PDF upload/ingestion, conversation logs, feedback stats, usage charts, FAQ management

## Project Structure
```
axorvian_chatbot/
├── app.py              # Main Streamlit entry point / UI
├── auth.py             # Login/register/session logic
├── database.py          # SQLite: users, chat history, feedback, KB, FAQs
├── rag_pipeline.py      # Chunking, embeddings, FAISS index, retrieval
├── llm.py               # Gemini prompt construction + generation
├── admin_panel.py       # Admin-only management UI
├── seed_kb.py           # One-time script to load sample KB data
├── requirements.txt
├── .env.example
├── knowledge_base/
│   └── sample_kb.txt    # Sample seed content
└── data/                 # Created at runtime: app.db, faiss_index/
```

## Setup

1. **Install dependencies**
   ```
   pip install -r requirements.txt
   ```

2. **Add your Gemini API key**
   Copy `.env.example` to `.env` and fill in `GOOGLE_API_KEY`. Get a free key at
   https://aistudio.google.com/app/apikey

3. **(Optional) Seed sample knowledge base**
   ```
   python seed_kb.py
   ```
   Or skip this and add content yourself via the Admin Panel once the app is running.

4. **Run the app**
   ```
   streamlit run app.py
   ```

5. **Log in**
   - Default admin: `admin` / `admin123` (change this in `.env` before first run, or update
     the password immediately via the database)
   - Or register a new regular user account from the login screen

## AI / RAG Architecture

1. **Ingestion**: Admin adds text or uploads a PDF → text is extracted (PyPDFLoader for
   PDFs) → stored as a `kb_entries` row in SQLite.
2. **Chunking**: `RecursiveCharacterTextSplitter` splits each KB entry into ~800-character
   overlapping chunks.
3. **Embedding**: Each chunk is embedded using Gemini's `text-embedding-004` model.
4. **Indexing**: Chunks + embeddings are stored in a FAISS index, rebuilt on every KB
   change and saved to `data/faiss_index/`.
5. **Retrieval**: On each user query, the top-k (default 4) most similar chunks are
   retrieved via FAISS similarity search.
6. **Generation**: Retrieved chunks + last 6 turns of conversation history + a
   support-tone system prompt are assembled and sent to Gemini 1.5 Flash, which
   generates a grounded, context-aware answer.

## Knowledge Base Design
KB content is stored as human-readable entries (title + content) in SQLite, which is
the source of truth. The FAISS index is a derived artifact rebuilt from these entries
whenever they change — so the vector store never drifts out of sync with what the
admin sees and edits.

## Admin Panel
Accessible only to accounts with `role = 'admin'`. Covers:
- Add / edit / delete KB entries (auto re-indexes)
- Upload PDFs to extend the KB
- View all conversation logs across users
- View feedback (like/dislike) with the associated bot response
- Usage stats: total messages, unique users, sessions, daily activity chart
- Add/remove FAQs

## Known Limitations / Future Work
- Single-node FAISS index (fine for demo-scale KBs; would move to a managed vector DB
  like Pinecone/Chroma-server for production scale)
- No streaming tokens yet in the UI (bonus feature — generator supports `stream=True`
  in `llm.py`, wiring into the UI is a straightforward next step)
- No website-URL ingestion yet (bonus feature — would reuse the PDF ingestion pattern
  with a `WebBaseLoader`)
