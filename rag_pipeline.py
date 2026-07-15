"""
rag_pipeline.py
Builds and queries the FAISS vector store for the knowledge base.
Handles chunking, embedding (Gemini embedding model), ingestion from
plain text / KB entries / PDFs, and similarity search for retrieval.
"""

import os
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain.schema import Document

INDEX_DIR = os.path.join(os.path.dirname(__file__), "data", "faiss_index")

_embeddings = None


def get_embeddings():
    global _embeddings
    if _embeddings is None:
        _embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    return _embeddings


def _splitter():
    return RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=120,
        separators=["\n\n", "\n", ". ", " ", ""]
    )


def build_index_from_kb_entries(kb_entries):
    """
    Rebuilds the FAISS index from scratch using all current KB entries
    (each entry is a dict with 'title' and 'content').
    Call this after any KB add/edit/delete in the admin panel.
    """
    docs = []
    splitter = _splitter()
    for entry in kb_entries:
        chunks = splitter.split_text(entry["content"])
        for i, chunk in enumerate(chunks):
            docs.append(Document(
                page_content=chunk,
                metadata={"title": entry["title"], "source": entry.get("source", "manual"), "chunk": i}
            ))

    if not docs:
        # No KB content yet — create an empty placeholder index
        docs = [Document(page_content="No knowledge base content has been added yet.",
                          metadata={"title": "placeholder", "source": "system"})]

    vectorstore = FAISS.from_documents(docs, get_embeddings())
    os.makedirs(INDEX_DIR, exist_ok=True)
    vectorstore.save_local(INDEX_DIR)
    return vectorstore


def load_index():
    if not os.path.exists(INDEX_DIR):
        return None
    return FAISS.load_local(INDEX_DIR, get_embeddings(), allow_dangerous_deserialization=True)


def add_pdf_to_kb(pdf_path, title):
    """Extracts text from a PDF and returns it as a single string, ready
    to be stored as a kb_entries row via database.add_kb_entry()."""
    loader = PyPDFLoader(pdf_path)
    pages = loader.load()
    full_text = "\n\n".join([p.page_content for p in pages])
    return full_text


def retrieve_context(query, k=4):
    """Returns top-k relevant chunks (with titles) for a user query."""
    vectorstore = load_index()
    if vectorstore is None:
        return []
    results = vectorstore.similarity_search(query, k=k)
    return [{"title": r.metadata.get("title", "Unknown"), "content": r.page_content} for r in results]
