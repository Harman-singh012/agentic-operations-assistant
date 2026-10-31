from pathlib import Path
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma

BASE = Path(__file__).resolve().parent.parent
POLICY_DIR = BASE / "policies"
CHROMA_DIR = str(BASE / "chroma_db")

embeddings = OllamaEmbeddings(model="nomic-embed-text")


def _load_texts():
    """Return a list of (text, source_name) from .pdf and .txt files."""
    items = []
    for f in sorted(POLICY_DIR.glob("*")):
        if f.suffix.lower() == ".pdf":
            reader = PdfReader(str(f))
            for i, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                if text.strip():
                    items.append((text, f"{f.name} p.{i + 1}"))
        elif f.suffix.lower() in (".txt", ".md"):
            items.append((f.read_text(encoding="utf-8"), f.name))
    return items


def build_index():
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=80)
    texts, metas = [], []
    for text, source in _load_texts():
        for chunk in splitter.split_text(text):
            texts.append(chunk)
            metas.append({"source": source})
    if not texts:
        print("No documents found in", POLICY_DIR)
        return
    Chroma.from_texts(texts, embeddings, metadatas=metas, persist_directory=CHROMA_DIR)
    print(f"Indexed {len(texts)} chunks from {POLICY_DIR}")


def search(query: str, k: int = 3):
    store = Chroma(persist_directory=CHROMA_DIR, embedding_function=embeddings)
    return store.similarity_search(query, k=k)