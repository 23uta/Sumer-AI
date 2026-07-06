"""
ragtools.py
نظام بحث في المراجع (RAG) — يسمح للبوت بالإجابة من ملفات/كتب يرفعها المستخدم
مع ذكر مصدر المعلومة (اسم الملف + رقم الصفحة).

يتطلب:
    pip install chromadb pypdf python-docx
"""

import os
import re
from google.genai import types

CHROMA_DIR = "rag_store"
COLLECTION_NAME = "references"
EMBED_MODEL = "gemini-embedding-001"
_resolved_embed_model = None  # يُحدَّد تلقائياً أول مرة

EMBED_CANDIDATES = [
    "gemini-embedding-001",          # ← النموذج الرسمي الحالي (GA)
    "models/gemini-embedding-001",   # بديل بصيغة المسار القديمة
]

def _resolve_embed_model(client):
    """يكتشف أول نموذج embedding متاح ويحفظه"""
    global _resolved_embed_model
    if _resolved_embed_model:
        return _resolved_embed_model
    for model in EMBED_CANDIDATES:
        try:
            result = client.models.embed_content(model=model, contents="test")
            if result and result.embeddings:
                _resolved_embed_model = model
                print(f"[RAG] Using embedding model: {model}")
                return model
        except Exception:
            continue
    raise RuntimeError(
        "No embedding model available. Make sure your Gemini API key supports embeddings."
    )

CHUNK_SIZE = 800     # عدد الأحرف التقريبي لكل قطعة
CHUNK_OVERLAP = 120  # تداخل بين القطع لتجنب قطع الجمل

try:
    import chromadb
    _chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
except Exception as e:
    chromadb = None
    _chroma_client = None
    _chroma_error = e


# ═══════════════════════════════════════════════
#  استخراج النص من الملفات
# ═══════════════════════════════════════════════
def extract_text_with_pages(file_path):
    """يرجع قائمة [(رقم الصفحة, النص), ...]"""
    ext = os.path.splitext(file_path)[1].lower()
    pages = []

    if ext == ".pdf":
        import pypdf
        reader = pypdf.PdfReader(file_path)
        for i, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            pages.append((i, text))

    elif ext == ".docx":
        import docx
        doc = docx.Document(file_path)
        full_text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        pages.append((1, full_text))

    elif ext in (".txt", ".md"):
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            pages.append((1, f.read()))

    elif ext == ".csv":
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            pages.append((1, f.read()))

    else:
        raise ValueError(f"Unsupported reference file type: {ext}")

    return pages


# ═══════════════════════════════════════════════
#  التقطيع (Chunking)
# ═══════════════════════════════════════════════
def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    text = re.sub(r'\s+', ' ', text).strip()
    if not text:
        return []

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = end - overlap
    return chunks


# ═══════════════════════════════════════════════
#  Embeddings via Gemini
# ═══════════════════════════════════════════════
def embed_texts(client, texts, is_query=False):
    """يحسب embeddings — يكتشف النموذج المتاح تلقائياً"""
    model = _resolve_embed_model(client)
    embeddings = []

    for t in texts:
        try:
            result = client.models.embed_content(
                model=model,
                contents=t,
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_QUERY" if is_query else "RETRIEVAL_DOCUMENT"
                )
            )
            embeddings.append(result.embeddings[0].values)
        except Exception:
            # fallback بدون task_type
            result = client.models.embed_content(model=model, contents=t)
            embeddings.append(result.embeddings[0].values)

    return embeddings


# ═══════════════════════════════════════════════
#  إدارة المراجع
# ═══════════════════════════════════════════════
def _get_collection():
    if _chroma_client is None:
        raise RuntimeError(
            "chromadb غير مثبت. شغّل: pip install chromadb pypdf python-docx"
        )
    return _chroma_client.get_or_create_collection(COLLECTION_NAME)


def add_reference(client, file_path):
    """يضيف ملفاً مرجعياً: يقطعه ويحسب embeddings ويخزنه. يرجع عدد القطع المضافة."""
    collection = _get_collection()

    pages = extract_text_with_pages(file_path)
    doc_name = os.path.basename(file_path)

    chunks, metadatas, ids = [], [], []
    for page_num, page_text in pages:
        for j, chunk in enumerate(chunk_text(page_text)):
            chunks.append(chunk)
            metadatas.append({"source": doc_name, "page": page_num})
            ids.append(f"{doc_name}::p{page_num}::c{j}::{len(chunks)}")

    if not chunks:
        return 0

    # Gemini embed_content batch limit safety: نقسم لمجموعات صغيرة
    BATCH = 90
    for i in range(0, len(chunks), BATCH):
        batch_chunks = chunks[i:i+BATCH]
        batch_meta = metadatas[i:i+BATCH]
        batch_ids = ids[i:i+BATCH]
        embeddings = embed_texts(client, batch_chunks, is_query=False)
        collection.add(
            documents=batch_chunks,
            embeddings=embeddings,
            metadatas=batch_meta,
            ids=batch_ids,
        )

    return len(chunks)


def search_reference(client, query, top_k=4):
    """يبحث عن أقرب القطع للسؤال. يرجع (نص_السياق, [مصادر]) أو (None, [])"""
    if _chroma_client is None:
        return None, []

    collection = _get_collection()
    if collection.count() == 0:
        return None, []

    query_embedding = embed_texts(client, [query], is_query=True)[0]
    results = collection.query(query_embeddings=[query_embedding], n_results=top_k)

    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]

    if not docs:
        return None, []

    context_parts = []
    sources = []
    for doc, meta in zip(docs, metas):
        src = meta.get("source", "unknown")
        page = meta.get("page", "?")
        context_parts.append(f"[Source: {src}, page {page}]\n{doc}")
        label = f"{src} — p.{page}"
        if label not in sources:
            sources.append(label)

    return "\n\n---\n\n".join(context_parts), sources


def has_references():
    if _chroma_client is None:
        return False
    try:
        collection = _get_collection()
        return collection.count() > 0
    except Exception:
        return False


def list_reference_files():
    """يرجع قائمة أسماء الملفات المضافة كمراجع (بدون تكرار)"""
    if _chroma_client is None:
        return []
    try:
        collection = _get_collection()
        if collection.count() == 0:
            return []
        data = collection.get()
        names = set()
        for meta in data.get("metadatas", []):
            if meta and "source" in meta:
                names.add(meta["source"])
        return sorted(names)
    except Exception:
        return []


def clear_references():
    """يحذف كل المراجع المخزنة"""
    if _chroma_client is None:
        return
    try:
        _chroma_client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass


def remove_reference_file(file_name):
    """يحذف ملف مرجعي معين بالاسم"""
    if _chroma_client is None:
        return
    try:
        collection = _get_collection()
        collection.delete(where={"source": file_name})
    except Exception:
        pass
