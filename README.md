<div align="center">

# 𓂀 Sumer AI

**A smart AI desktop assistant — powered by Google Gemini**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square&logo=python)](https://python.org)
[![Gemini](https://img.shields.io/badge/Gemini-API-orange?style=flat-square&logo=google)](https://ai.google.dev)
[![License](https://img.shields.io/badge/License-GPL%20v3-green?style=flat-square)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-lightgrey?style=flat-square)]()

</div>

---

## ✨ Overview

Sumer AI is an open-source AI desktop chat application built for Arabic-speaking students and professionals. It combines the power of Google Gemini with a polished, customizable interface — supporting rich Arabic text, LaTeX math rendering, document generation, and a local RAG knowledge base.

The name is a nod to ancient **Sumerian civilization** — one of humanity's earliest centers of knowledge and writing.

---

## 🖥️ Features

- **Arabic-first UI** — full RTL support with proper reshaping via `arabic_reshaper` + `python-bidi`
- **Gemini-powered chat** — using `gemini-2.5-flash` for fast, intelligent responses
- **LaTeX math rendering** — renders mathematical expressions inline via `matplotlib`
- **RAG system** — upload documents (PDF, DOCX, PPTX) and chat with them; answers include source + page number
- **Persistent chat history** — all conversations saved locally in SQLite
- **Document generation** — generate formatted Word reports and Excel sheets from plain text requests
- **File handling** — open, summarize, and convert files (DOCX → PDF) via natural language
- **Adaptive personality** — the assistant updates its tone and memory based on conversation style
- **Theme customization** — full color theme control with a built-in circle color picker
- **Local Iraqi links** — recognizes Iraqi services (Baly, ZainCash, universities, ministries, etc.) by name
- **Simple Mode** — compact floating window for quick queries

---

## 📁 Project Structure

```
sumer-ai/
├── main.py                  # Login window (activation UI — disabled in this release)
├── nologinmain.py           # Main chat interface
├── configs.py               # Gemini client, Iraqi local links, AI prompts
├── controltools.py          # File handling, browser control, system instruction builder
├── aitools.py               # Word/Excel document generation, PDF conversion
├── ragtools.py              # RAG system — ChromaDB + Gemini embeddings
├── keyssystem.py            # License/activation system (stubbed in open-source release)
├── customization.json       # User personality & memory settings (auto-generated)
├── chat_history.db          # SQLite chat history (auto-generated)
├── rag_store/               # ChromaDB vector store (auto-generated on first upload)
└── AN.png                   # App icon
```

---

## ⚙️ Installation

### 1. Clone the repository
```bash
git clone https://github.com/yourusername/sumer-ai.git
cd sumer-ai
```

### 2. Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Add your Gemini API key

Open `configs.py` and replace the placeholder:
```python
apikey = "YOUR_GEMINI_API_KEY"
```

Get a free key at [https://ai.google.dev](https://ai.google.dev)

### 5. Run the app
```bash
python nologinmain.py
```

---

## 📦 Requirements

```
customtkinter
google-genai
arabic-reshaper
python-bidi
matplotlib
chromadb
sentence-transformers
python-docx
docx2pdf
openpyxl
pillow
pypdf
supabase
```

> Install all at once: `pip install -r requirements.txt`

---

## 🤖 How the RAG System Works

1. Click the **📎 attachment button** to upload a PDF, DOCX, or PPTX file
2. The file is chunked and embedded using `gemini-embedding-001`
3. Vectors are stored locally in ChromaDB (`rag_store/`)
4. On each message, the top relevant chunks are retrieved and injected into the Gemini context
5. Answers include the **source filename and page number**

---

## 🎨 Customization

The assistant's **personality** and **memory** are stored in `customization.json` and update automatically during conversation. You can also edit them manually:

```json
{
  "personality": "Be concise, helpful, and friendly.",
  "memory": "User is a university student studying Optical Communications in Iraq.",
  "adaptive_personality": true,
  "adaptive_memory": true
}
```

---

## 🔑 Activation System

The project includes a complete **HWID-based license system** built with Supabase — covering key generation, device binding, 30-day expiry, and automatic renewal detection.

This system is **stubbed (disabled)** in the open-source release to allow free access. All activation functions return `True` by default. The full implementation is preserved in `keyssystem.py` for reference.

---

## 🌍 Roadmap

- [ ] Voice input support
- [ ] Plugin system for custom tools
- [ ] Cloud sync for chat history
- [ ] Mobile companion app
- [ ] Multi-language UI (EN / AR toggle)

---

## 📄 License

This project is licensed under the **GNU General Public License v3.0**.
See [LICENSE](LICENSE) for details.

---

<div align="center">
Built with ❤️ in Iraq &nbsp;|&nbsp; Inspired by the world's first civilization
</div>
