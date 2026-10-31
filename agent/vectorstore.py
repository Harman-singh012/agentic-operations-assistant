"""ChromaDB policy store (uses Chroma's built-in local embedding model, no extra API key)."""
import re
from functools import lru_cache
from pathlib import Path

import chromadb
from django.conf import settings


@lru_cache(maxsize=1)
def _collection():
    client = chromadb.PersistentClient(path=str(settings.CHROMA_DIR))
    return client.get_or_create_collection("policies", metadata={"hnsw:space": "cosine"})


def _chunks(text: str, size: int = 700) -> list[str]:
    out, cur = [], ""
    for para in (p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()):
        if cur and len(cur) + len(para) > size:
            out.append(cur)
            cur = para
        else:
            cur = f"{cur}\n\n{para}" if cur else para
    if cur:
        out.append(cur)
    return out


def ingest(directory) -> int:
    """Chunk every *.md file in `directory` and upsert into Chroma. Returns chunk count."""
    ids, docs, metas = [], [], []
    for path in sorted(Path(directory).glob("*.md")):
        for i, chunk in enumerate(_chunks(path.read_text(encoding="utf-8"))):
            ids.append(f"{path.stem}-{i}")
            docs.append(chunk)
            metas.append({"source": path.name})
    if ids:
        _collection().upsert(ids=ids, documents=docs, metadatas=metas)
    return len(ids)


def search(query: str, k: int = 4) -> list[dict]:
    col = _collection()
    if col.count() == 0:
        return []
    res = col.query(query_texts=[query], n_results=min(k, col.count()))
    return [
        {"text": d, "source": m["source"], "distance": dist}
        for d, m, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0])
    ]
