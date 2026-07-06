# ═══════════════════════════════════════════════
#  PART 1 — IMPORTS, THEME SYSTEM, HELPERS
#  (CustomTkinter rebuild — main_ui26.py)
# ═══════════════════════════════════════════════
import os
import sys
import re
import json
import time
import threading
import sqlite3
import unicodedata
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, colorchooser
from google.genai import types
from google.genai.errors import ClientError

from configs import client, locallinks, excel_prompt, report_prompt
import aitools
import controltools

# ── Adaptive Personality: نُلف get_system_instruction لإضافة حقل personality_update ──
_original_get_system_instruction = controltools.get_system_instruction

def _adaptive_get_system_instruction(name, personality, memory, adaptive_personality=True, adaptive_memory=True):
    base = _original_get_system_instruction(name, personality, memory)
    extra = ""
    if adaptive_personality:
        extra += (
            """
ADAPTIVE PERSONALITY RULE:
"
            "In addition to your normal JSON response fields, you MUST include a field called "personality_update".
"
            "- Analyze the conversation tone and any explicit or implicit preference the user shows (e.g. romantic style, harsh tone, formal/casual, specific character traits).
"
            "- If you detect a clear desired personality style, set "personality_update" to a concise English description of the updated personality (e.g. "Be romantic, warm, and poetic in tone.").
"
            "- If the current personality already matches, or you detect no preference, set "personality_update" to null or omit it.
"
            "- Only update when you are confident — do not update randomly.
"
            "- The personality_update value replaces the entire current personality setting."
        """
        )

    if adaptive_memory:
        extra += (
            """

ADAPTIVE MEMORY RULE:
"
            "In addition to your normal JSON response fields, you MUST include a field called "memory_update".
"
            "- Analyze the conversation for any facts worth remembering: user name, age, location, preferences, important personal info, recurring topics, or anything the user explicitly asks you to remember.
"
            "- If you find new or updated info, set "memory_update" to the full updated memory text (combine existing memory with new facts — do not erase old facts unless the user corrects them).
"
            "- If nothing new is learned, set "memory_update" to null or omit it.
"
            "- Only add genuinely useful facts — do not add trivial or one-off statements.
"
            "- Write memory entries as short bullet-style facts in the same language the user uses."
        """
        )
    return base + extra

controltools.get_system_instruction = _adaptive_get_system_instruction
import keyssystem
import ragtools
from keyssystem import get_raw_hwid
from app_secrets import check_easter_egg

# ═══════════════════════════════════════════════
#  COLOR HELPERS
# ═══════════════════════════════════════════════
def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def rgb_to_hex(rgb):
    return "#" + "".join(f"{max(0, min(255, int(c))):02X}" for c in rgb)

def lighten(hex_color, factor):
    r, g, b = hex_to_rgb(hex_color)
    return rgb_to_hex((r + (255 - r) * factor, g + (255 - g) * factor, b + (255 - b) * factor))

def darken(hex_color, factor):
    r, g, b = hex_to_rgb(hex_color)
    return rgb_to_hex((r * (1 - factor), g * (1 - factor), b * (1 - factor)))

def mix(c1, c2, t):
    r1, g1, b1 = hex_to_rgb(c1)
    r2, g2, b2 = hex_to_rgb(c2)
    return rgb_to_hex((r1 + (r2 - r1) * t, g1 + (g2 - g1) * t, b1 + (b2 - b1) * t))

def derive_theme(bg, card, accent, text):
    """يبني مجموعة ألوان كاملة من 4 ألوان أساسية فقط"""
    return {
        "BG_PRIMARY": bg,
        "BG_SECONDARY": lighten(bg, 0.05),
        "BG_CARD": card,
        "ACCENT": accent,
        "ACCENT_LIGHT": lighten(accent, 0.3),
        "ACCENT_GLOW": darken(accent, 0.2),
        "TEXT_PRIMARY": text,
        "TEXT_SECONDARY": mix(text, accent, 0.4),
        "TEXT_MUTED": mix(text, bg, 0.6),
        "BORDER": lighten(bg, 0.12),
        "INPUT_BG": darken(bg, 0.3),
        "BUBBLE_USER": mix(bg, accent, 0.25),
        "BUBBLE_USER_B": accent,
        "BUBBLE_AI": card,
        "BUBBLE_AI_B": lighten(bg, 0.12),
    }

# ═══════════════════════════════════════════════
#  CIRCLE COLOR PICKER — لوحة ألوان دائرية بدل نافذة النظام
# ═══════════════════════════════════════════════
COLOR_PALETTE = [
    "#0A0A0A", "#1A1A1A", "#2A2A2A", "#3A3A3A", "#6B6B6B", "#A0A0A0", "#F5F5F5", "#FFFFFF",
    "#D4AF37", "#F5D060", "#B8960C", "#FFD700",
    "#2E8FFF", "#0A66C2", "#5BC0FF", "#1E3A8A",
    "#2ECC8F", "#0FA968", "#86EFAC", "#0D2D1A",
    "#9B6BFF", "#6D28D9", "#C4B5FD", "#1E1530",
    "#FF5C5C", "#E11D48", "#FCA5A5", "#7F1D1D",
    "#FF8C42", "#F59E0B", "#FFE4B5", "#7C2D12",
    "#EC4899", "#F472B6", "#0EA5E9", "#14B8A6",
]

def _contrast_border(hexcolor):
    """يرجع لون حد فاتح أو غامق بحيث تبقى الدائرة مرئية بوضوح فوق أي خلفية."""
    try:
        r, g, b = hex_to_rgb(hexcolor)
        luminance = (0.299 * r + 0.587 * g + 0.114 * b)
        return "#3A3A3A" if luminance > 150 else "#D9D9D9"
    except Exception:
        return "#999999"

def open_circle_color_picker(parent_win, current_color, title, on_pick):
    """نافذة منتقي ألوان على شكل دوائر — صفوف يدوية بسيطة (بدون grid() نهائياً)
    لتفادي مشكلة تضخم النافذة وانكماش الشبكة التي ظهرت على بعض الأنظمة."""
    pop = ctk.CTkToplevel(parent_win)
    pop.title(title)
    pop.configure(fg_color="#1E1E1E")
    pop.geometry("300x430")
    pop.minsize(300, 430)
    pop.maxsize(300, 430)
    pop.resizable(False, False)

    ctk.CTkLabel(pop, text=title, font=F(13, "bold"), text_color="#FFFFFF",
                fg_color="transparent", wraplength=260).pack(padx=SPACE_MD, pady=(SPACE_MD, 4))

    preview_ring = ctk.CTkFrame(pop, fg_color=_contrast_border(current_color),
                               width=40, height=40, corner_radius=20)
    preview_ring.pack(pady=(0, SPACE_SM))
    preview_ring.pack_propagate(False)
    current_preview = ctk.CTkLabel(preview_ring, text="", fg_color=current_color,
                                   width=36, height=36, corner_radius=18)
    current_preview.place(relx=0.5, rely=0.5, anchor="center")

    palette_area = ctk.CTkFrame(pop, fg_color="transparent")
    palette_area.pack(padx=SPACE_MD)

    def choose(hexcolor):
        on_pick(hexcolor)
        pop.destroy()

    cols = 6
    rows_needed = (len(COLOR_PALETTE) + cols - 1) // cols
    for ridx in range(rows_needed):
        row_frame = ctk.CTkFrame(palette_area, fg_color="transparent")
        row_frame.pack(pady=3)
        for cidx in range(cols):
            i = ridx * cols + cidx
            if i >= len(COLOR_PALETTE):
                break
            hexcolor = COLOR_PALETTE[i]
            is_selected = hexcolor.upper() == current_color.upper()
            dot = ctk.CTkButton(row_frame, text="✓" if is_selected else "",
                                command=lambda h=hexcolor: choose(h),
                                fg_color=hexcolor, hover_color=hexcolor,
                                text_color=_contrast_border(hexcolor),
                                font=F(13, "bold"),
                                width=34, height=34, corner_radius=17,
                                border_width=3 if is_selected else 2,
                                border_color=ACCENT if is_selected else _contrast_border(hexcolor))
            dot.pack(side="left", padx=3)

    def custom_pick():
        result = colorchooser.askcolor(color=current_color, title=title, parent=pop)
        if result and result[1]:
            choose(result[1])

    ctk.CTkButton(pop, text="🎨  Custom color...", command=custom_pick,
                 font=F(11), fg_color="#2A2A2A", hover_color="#3A3A3A",
                 text_color="#FFFFFF", corner_radius=10, height=34,
                 border_width=1, border_color="#555555"
                 ).pack(fill="x", padx=SPACE_MD, pady=(SPACE_SM, SPACE_MD))

    pop.transient(parent_win)
    pop.attributes("-topmost", True)
    pop.lift()
    pop.after(100, pop.focus_force)
    pop.grab_set()

# ═══════════════════════════════════════════════
#  DEFAULT THEME — Luxury Gold
# ═══════════════════════════════════════════════
DEFAULT_THEME = {
    "BG_PRIMARY": "#0A0A0A",
    "BG_SECONDARY": "#111111",
    "BG_CARD": "#1A1A1A",
    "ACCENT": "#D4AF37",
    "ACCENT_LIGHT": "#F5D060",
    "ACCENT_GLOW": "#B8960C",
    "TEXT_PRIMARY": "#F5F5F5",
    "TEXT_SECONDARY": "#A89060",
    "TEXT_MUTED": "#6B6B6B",
    "BORDER": "#2A2A2A",
    "INPUT_BG": "#080808",
    "BUBBLE_USER": "#2A2000",
    "BUBBLE_USER_B": "#D4AF37",
    "BUBBLE_AI": "#161616",
    "BUBBLE_AI_B": "#2A2A2A",
}

PRESET_THEMES = {
    "Luxury Gold": DEFAULT_THEME,
    "Ocean Blue":    derive_theme("#0A0F1C", "#13203A", "#2E8FFF", "#EAF2FF"),
    "Emerald Night": derive_theme("#07140F", "#10261C", "#2ECC8F", "#E8FFF4"),
    "Royal Purple":  derive_theme("#0E0A1A", "#1E1530", "#9B6BFF", "#F3EEFF"),
    "Crimson":       derive_theme("#160A0A", "#2A1313", "#FF5C5C", "#FFEDED"),
    "Gothic":         derive_theme("#0D0010", "#1A0020", "#8B00FF", "#E8D5FF"),
}

THEME_FILE = "theme.json"
CUSTOM_THEMES_FILE = "custom_themes.json"

def _load_custom_themes_raw():
    if os.path.exists(CUSTOM_THEMES_FILE):
        try:
            with open(CUSTOM_THEMES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _current_theme_name():
    if os.path.exists(THEME_FILE):
        try:
            with open(THEME_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get("active", "Luxury Gold")
        except Exception:
            pass
    return "Luxury Gold"

def _load_theme_overrides():
    if not os.path.exists(THEME_FILE):
        return None
    try:
        with open(THEME_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        active = data.get("active")
        if data.get("is_custom"):
            return _load_custom_themes_raw().get(active)
        return PRESET_THEMES.get(active)
    except Exception:
        return None

_ov = _load_theme_overrides()
THEME = dict(DEFAULT_THEME)
if _ov:
    THEME.update(_ov)

# اختصارات مباشرة للألوان المستخدمة بكثرة
BG_PRIMARY    = THEME["BG_PRIMARY"]
BG_SECONDARY  = THEME["BG_SECONDARY"]
BG_CARD       = THEME["BG_CARD"]
ACCENT        = THEME["ACCENT"]
ACCENT_LIGHT  = THEME["ACCENT_LIGHT"]
ACCENT_GLOW   = THEME["ACCENT_GLOW"]
TEXT_PRIMARY  = THEME["TEXT_PRIMARY"]
TEXT_SECONDARY= THEME["TEXT_SECONDARY"]
TEXT_MUTED    = THEME["TEXT_MUTED"]
BORDER        = THEME["BORDER"]
INPUT_BG      = THEME["INPUT_BG"]
BUBBLE_USER   = THEME["BUBBLE_USER"]
BUBBLE_USER_B = THEME["BUBBLE_USER_B"]
BUBBLE_AI     = THEME["BUBBLE_AI"]
BUBBLE_AI_B   = THEME["BUBBLE_AI_B"]

# ═══════════════════════════════════════════════
#  CTK GLOBAL APPEARANCE
# ═══════════════════════════════════════════════
ctk.set_appearance_mode("dark")
ctk.set_widget_scaling(1.0)

# ═══════════════════════════════════════════════
#  FONTS & SPACING
# ═══════════════════════════════════════════════
FONT_FAMILY = "Segoe UI" if os.name == "nt" else "Arial"  # دعم عربي أفضل على لينكس

def F(size=13, weight="normal"):
    return ctk.CTkFont(family=FONT_FAMILY, size=size, weight=weight)

SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG = 6, 12, 20, 32
RADIUS = 14

# ═══════════════════════════════════════════════
#  ARCHIVE HELPERS
# ═══════════════════════════════════════════════
ARCHIVE_FILE = "archive.json"
DOWNLOADS_DIR = os.path.join(os.path.expanduser("~"), "Downloads")

def load_archive():
    if os.path.exists(ARCHIVE_FILE):
        try:
            with open(ARCHIVE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_archive(items):
    try:
        with open(ARCHIVE_FILE, "w", encoding="utf-8") as f:
            json.dump(items[:50], f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("archive save error:", e)

def add_to_archive(path):
    if not path or not os.path.exists(path):
        return
    items = load_archive()
    items = [i for i in items if i.get("path") != path]
    items.insert(0, {
        "name": os.path.basename(path),
        "path": path,
        "time": time.strftime("%Y-%m-%d %H:%M"),
    })
    save_archive(items)

def archive_latest_file(folder, exts):
    try:
        if not os.path.isdir(folder):
            return
        files = [os.path.join(folder, f) for f in os.listdir(folder)
                 if f.lower().endswith(exts)]
        if not files:
            return
        add_to_archive(max(files, key=os.path.getmtime))
    except Exception as e:
        print("archive scan error:", e)

def open_path(path):
    try:
        if os.name == "nt":
            os.startfile(path)
        elif sys.platform == "darwin":
            os.system(f'open "{path}"')
        else:
            os.system(f'xdg-open "{path}"')
    except Exception as e:
        print("open error:", e)

# ═══════════════════════════════════════════════
#  CHAT DATABASE (SQLite)
# ═══════════════════════════════════════════════
DB_FILE = "chat_history.db"
CONTEXT_WINDOW = 20          # عدد الرسائل المرسلة للـ AI كـ context (من المحادثة الحالية فقط)
MATH_CACHE_MAX = 200         # حد أقصى لكاش الصور الرياضية

_db_lock = threading.Lock()
current_conversation_id = None   # المحادثة المفتوحة حالياً — الذاكرة تقتصر عليها فقط

def db_connect():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def db_init():
    with db_connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                title      TEXT    NOT NULL DEFAULT 'New chat',
                created_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now','localtime')),
                updated_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now','localtime'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL DEFAULT 1,
                role            TEXT    NOT NULL,
                content         TEXT    NOT NULL,
                timestamp       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now','localtime'))
            )
        """)
        conn.commit()

        # ── ترحيل: لو الملف قديم وما فيه عمود conversation_id، نضيفه ──
        cols = [r[1] for r in conn.execute("PRAGMA table_info(messages)").fetchall()]
        if "conversation_id" not in cols:
            conn.execute("ALTER TABLE messages ADD COLUMN conversation_id INTEGER NOT NULL DEFAULT 1")
            conn.commit()

        # ── لو ما في محادثات أصلاً، أنشئ واحدة (وأرجع أي رسائل قديمة بدون conversation_id لها) ──
        has_conv = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
        if has_conv == 0:
            cur = conn.execute("INSERT INTO conversations (title) VALUES ('New chat')")
            first_id = cur.lastrowid
            conn.execute("UPDATE messages SET conversation_id = ? WHERE conversation_id IS NULL OR conversation_id = 1",
                         (first_id,))
            conn.commit()

def db_create_conversation(title="New chat"):
    """ينشئ محادثة جديدة ويرجع رقمها (id)."""
    with _db_lock:
        with db_connect() as conn:
            cur = conn.execute("INSERT INTO conversations (title) VALUES (?)", (title,))
            conn.commit()
            return cur.lastrowid

def db_list_conversations():
    """يرجع كل المحادثات، الأحدث تحديثاً أولاً."""
    with db_connect() as conn:
        rows = conn.execute(
            "SELECT id, title, updated_at FROM conversations ORDER BY updated_at DESC"
        ).fetchall()
    return rows  # [(id, title, updated_at), ...]

def db_touch_conversation(conversation_id):
    """يحدّث وقت آخر تعديل للمحادثة (تظهر بالأعلى في القائمة)."""
    with _db_lock:
        with db_connect() as conn:
            conn.execute(
                "UPDATE conversations SET updated_at = strftime('%Y-%m-%d %H:%M:%S','now','localtime') WHERE id = ?",
                (conversation_id,)
            )
            conn.commit()

def db_rename_conversation(conversation_id, title):
    with _db_lock:
        with db_connect() as conn:
            conn.execute("UPDATE conversations SET title = ? WHERE id = ?", (title.strip()[:60], conversation_id))
            conn.commit()

def db_delete_conversation(conversation_id):
    with _db_lock:
        with db_connect() as conn:
            conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
            conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
            conn.commit()

def db_save_message(role, content, conversation_id=None):
    """يحفظ رسالة واحدة في المحادثة المحددة (أو الحالية إن لم تُمرّر)."""
    cid = conversation_id if conversation_id is not None else current_conversation_id
    with _db_lock:
        with db_connect() as conn:
            conn.execute(
                "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
                (cid, role, content)
            )
            conn.commit()
    db_touch_conversation(cid)

def db_load_all(conversation_id=None):
    """يرجع كل رسائل محادثة واحدة، مرتبة من الأقدم للأحدث."""
    cid = conversation_id if conversation_id is not None else current_conversation_id
    with db_connect() as conn:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY id ASC",
            (cid,)
        ).fetchall()
    return rows  # [(role, content), ...]

def db_get_context(n=CONTEXT_WINDOW, conversation_id=None):
    """يرجع آخر n رسالة (user/assistant) من المحادثة المحددة فقط — لا تختلط مع محادثات أخرى."""
    cid = conversation_id if conversation_id is not None else current_conversation_id
    with db_connect() as conn:
        rows = conn.execute(
            """SELECT role, content FROM messages
               WHERE role IN ('user','assistant') AND conversation_id = ?
               ORDER BY id DESC LIMIT ?""",
            (cid, n)
        ).fetchall()
    rows.reverse()
    return rows  # [(role, content), ...]

def db_clear(conversation_id=None):
    """يمسح رسائل محادثة واحدة فقط (وليس كل المحادثات)."""
    cid = conversation_id if conversation_id is not None else current_conversation_id
    with _db_lock:
        with db_connect() as conn:
            conn.execute("DELETE FROM messages WHERE conversation_id = ?", (cid,))
            conn.commit()

# تهيئة قاعدة البيانات عند بدء التشغيل
db_init()
_convs_at_start = db_list_conversations()
current_conversation_id = _convs_at_start[0][0] if _convs_at_start else db_create_conversation()

# ═══════════════════════════════════════════════
#  CUSTOMIZATION (personality / memory)
# ═══════════════════════════════════════════════
CUSTOMIZATION_FILE = "customization.json"

def load_customization():
    if os.path.exists(CUSTOMIZATION_FILE):
        try:
            with open(CUSTOMIZATION_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {
                    "personality": data.get("personality", ""),
                    "memory": data.get("memory", ""),
                    "avatar_path": data.get("avatar_path", ""),
                    "adaptive_personality": data.get("adaptive_personality", True),
                    "adaptive_memory": data.get("adaptive_memory", True),
                }
        except Exception:
            pass
    return {"personality": "", "memory": "", "avatar_path": "", "adaptive_personality": True, "adaptive_memory": True}

def save_customization(personality, memory, avatar_path=None, adaptive_personality=None, adaptive_memory=None):
    try:
        existing = load_customization()
        data = {
            "personality": personality,
            "memory": memory,
            "avatar_path": existing["avatar_path"] if avatar_path is None else avatar_path,
            "adaptive_personality": existing["adaptive_personality"] if adaptive_personality is None else adaptive_personality,
            "adaptive_memory": existing["adaptive_memory"] if adaptive_memory is None else adaptive_memory,
        }
        with open(CUSTOMIZATION_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("customization save error:", e)

# ═══════════════════════════════════════════════
#  AI AVATAR (profile picture in chat bubbles)
# ═══════════════════════════════════════════════
_avatar_ctk_image = None

def _load_avatar_image():
    """يحمّل صورة الـ AI كـ CTkImage بحجم مناسب للأيقونة، أو None لو غير موجودة."""
    global _avatar_ctk_image
    path = load_customization().get("avatar_path", "")
    if not path or not os.path.exists(path):
        _avatar_ctk_image = None
        return None
    try:
        from PIL import Image
        img = Image.open(path).convert("RGBA").resize((34, 34), Image.LANCZOS)
        _avatar_ctk_image = ctk.CTkImage(light_image=img, dark_image=img, size=(34, 34))
        return _avatar_ctk_image
    except Exception as e:
        print("avatar load error:", e)
        _avatar_ctk_image = None
        return None

def set_ai_avatar(file_path):
    """ينسخ الصورة المختارة لمجلد التطبيق ويحفظ مسارها، يرجع True لو نجح."""
    if not file_path or not os.path.exists(file_path):
        return False
    try:
        import shutil
        ext = os.path.splitext(file_path)[1].lower() or ".png"
        dest = os.path.join(os.getcwd(), f"ai_avatar{ext}")
        shutil.copyfile(file_path, dest)
        cur = load_customization()
        save_customization(cur["personality"], cur["memory"], avatar_path=dest)
        _load_avatar_image()
        return True
    except Exception as e:
        print("set_ai_avatar error:", e)
        return False

def remove_ai_avatar():
    cur = load_customization()
    save_customization(cur["personality"], cur["memory"], avatar_path="")
    global _avatar_ctk_image
    _avatar_ctk_image = None

# تحميل الصورة (إن وجدت) عند بدء التشغيل
_load_avatar_image()

def build_system_instruction():
    custom = load_customization()
    adaptive = custom.get("adaptive_personality", True)
    adaptive_mem = custom.get("adaptive_memory", True)
    return controltools.get_system_instruction(
        ai_name, custom["personality"], custom["memory"],
        adaptive_personality=adaptive, adaptive_memory=adaptive_mem
    )

# ═══════════════════════════════════════════════
#  LICENSE CHECK
# ═══════════════════════════════════════════════
hwid = get_raw_hwid()
if not keyssystem.checkactivation(hwid):
    sys.exit()

# ═══════════════════════════════════════════════
#  AI NAME
# ═══════════════════════════════════════════════
if not os.path.exists("ainame"):
    ai_name = "Assistant"
    with open("ainame", "w", encoding="utf-8") as f:
        f.write(ai_name)
else:
    with open("ainame", "r", encoding="utf-8") as f:
        ai_name = f.read().strip()

system_instruction = build_system_instruction()
_send_lock = threading.Lock()   # يمنع إرسال رسالتين بنفس الوقت
# chat_history محذوف — السياق يُقرأ من SQLite عبر db_get_context()

# ═══════════════════════════════════════════════
#  THEME APPLY (restarts app)
# ═══════════════════════════════════════════════
def apply_theme(name, is_custom=False, theme_dict=None):
    if is_custom and theme_dict is not None:
        customs = _load_custom_themes_raw()
        customs[name] = theme_dict
        with open(CUSTOM_THEMES_FILE, "w", encoding="utf-8") as f:
            json.dump(customs, f, ensure_ascii=False, indent=2)
    with open(THEME_FILE, "w", encoding="utf-8") as f:
        json.dump({"active": name, "is_custom": is_custom}, f)
    root.destroy()
    os.execv(sys.executable, [sys.executable] + sys.argv)

# ═══════════════════════════════════════════════
#  END OF PART 1
#  (root window, chat, sidebar, AI logic come in parts 2-5)
# ═══════════════════════════════════════════════
# ═══════════════════════════════════════════════
#  PART 2 — MAIN WINDOW + CHAT AREA
#  (append after Part 1)
# ═══════════════════════════════════════════════

# ═══════════════════════════════════════════════
#  RICH TEXT — Arabic/RTL + Bold/Italic/Code + Math
# ═══════════════════════════════════════════════
ARABIC_RE = re.compile(r'[\u0600-\u06FF\u0750-\u077F]')
# $$ للمعادلات المستقلة، $ للـ inline — كلاهما يسمح بـ newlines داخلهم
MATH_RE = re.compile(r'\$\$(.+?)\$\$|\$(.+?)\$', re.DOTALL)
INLINE_RE = re.compile(r'(\*\*.+?\*\*|\*.+?\*|`.+?`)', re.DOTALL)

def fix_latex(text):
    """
    يصلح مشكلتين شائعتين بعد json.loads:
    1. \\frac تصير chr(12)+'rac'  (لأن \\f = form feed في JSON)
    2. أنماط LaTeX أخرى مكسورة بدون backslash
    3. newlines داخل $ ... $ تكسر matplotlib — نحذفها
    """
    # المشكلة الأولى: form feed chr(12) + rac = \frac مكسور
    # json.loads يحوّل \f في JSON إلى chr(12) في Python
    text = text.replace("\x0crac{", "\\frac{")
    text = text.replace("\x0c", "")  # أي form feed متبقٍّ نحذفه تماماً (مو \f)

    broken_map = {
        "rac{"   : "\\frac{",
        "sqrt{"  : "\\sqrt{",
        "sum_"   : "\\sum_",
        "sum^"   : "\\sum^",
        "int_"   : "\\int_",
        "int^"   : "\\int^",
        "lim_"   : "\\lim_",
        "infty"  : "\\infty",
        "cdot"   : "\\cdot",
        "times"  : "\\times",
        "pm"     : "\\pm",
        "leq"    : "\\leq",
        "geq"    : "\\geq",
        "neq"    : "\\neq",
        "alpha"  : "\\alpha",
        "beta"   : "\\beta",
        "gamma"  : "\\gamma",
        "delta"  : "\\delta",
        "theta"  : "\\theta",
        "lambda" : "\\lambda",
        "sigma"  : "\\sigma",
        "omega"  : "\\omega",
        "left("  : "\\left(",
        "right)" : "\\right)",
    }

    def _fix_block(m):
        is_display = m.group(1) is not None
        content = m.group(1) if is_display else m.group(2)
        # نحذف newlines وform feeds داخل المعادلة (تكسر matplotlib)
        content = content.replace("\n", " ").replace("\x0c", "").strip()
        # نصلح الأنماط المكسورة بـ str.replace (أأمن من re.sub مع backslashes)
        for pat, replacement in broken_map.items():
            idx = 0
            while True:
                i = content.find(pat, idx)
                if i == -1:
                    break
                # لا نستبدل لو في backslash قبله (حرف أو حرفين)
                before = content[max(0, i - 2):i]
                if "\\" not in before:
                    content = content[:i] + replacement + content[i + len(pat):]
                    idx = i + len(replacement)
                else:
                    idx = i + 1
        delim = "$$" if is_display else "$"
        return f"{delim}{content}{delim}"

    return MATH_RE.sub(_fix_block, text)
_math_image_cache = {}   # مقيّد بـ MATH_CACHE_MAX عنصر
_math_render_lock = threading.Lock()

def _math_cache_set(key, img):
    """يضيف صورة للكاش ويحذف الأقدم لو تجاوز الحد."""
    if len(_math_image_cache) >= MATH_CACHE_MAX:
        oldest = next(iter(_math_image_cache))
        del _math_image_cache[oldest]
    _math_image_cache[key] = img

def is_rtl_text(text):
    arabic = len(ARABIC_RE.findall(text))
    total = len(re.findall(r'\S', text))
    return total > 0 and (arabic / total) > 0.3

def apply_bidi(text):
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(text))
    except ImportError:
        return text
def render_math_png_bytes(latex_str, fg="#FFFFFF", fontsize=12):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from io import BytesIO
        with _math_render_lock:
            # figsize صغير جداً ليترك bbox_inches يحسب الأبعاد الحقيقية للنص فقط
            fig = plt.figure(figsize=(0.05, 0.05))
            fig.patch.set_alpha(0)
            
            fig.text(0.5, 0.5, f"${latex_str}$",
                     fontsize=fontsize, color=fg,
                     ha="center", va="center")
            
            buf = BytesIO()
            # استخدام dpi مناسب لـ Tkinter (بين 100 و 110)
            fig.savefig(buf, format="png", dpi=95,
                        transparent=True,
                        bbox_inches="tight",
                        pad_inches=0.02) # هامش صغير جداً لحماية الأطراف من القص
            plt.close(fig)
        buf.seek(0)
        return buf.read()
    except Exception as e:
        print("math render error:", e)
        return None

def render_math_image(latex_str, fg="#FFFFFF", fontsize=13):
    """يستخدم في المسار المتزامن (Main Thread) فقط — تبقى متاحة للتوافق مع الكود القديم."""
    key = (latex_str, fg, fontsize)
    if key in _math_image_cache:
        return _math_image_cache[key]
    png_bytes = render_math_png_bytes(latex_str, fg, fontsize)
    if png_bytes is None:
        return None
    img = tk.PhotoImage(data=png_bytes)
    _math_cache_set(key, img)
    return img

def render_rich_text(parent, text, fg, bg):
    """يعرض النص: عربي RTL صحيح + **bold** + *italic* + `code` + $math$"""
    rtl = is_rtl_text(text)
    has_formatting = bool(INLINE_RE.search(text) or MATH_RE.search(text))

    if not has_formatting:
        display_text = apply_bidi(text) if rtl else text
        anchor = "e" if rtl else "w"
        justify = "right" if rtl else "left"
        lbl = ctk.CTkLabel(parent, text=display_text, font=F(13), text_color=fg,
                            fg_color=bg, wraplength=420, justify=justify, anchor=anchor)
        return lbl

    base_font = F(13)
    bold_font = F(13, "bold")
    
    # تم حذف spacing1 و spacing3 من هنا ليعود النص الطبيعي متناسقاً وبدون مسافات عشوائية
    txt = tk.Text(parent, font=(FONT_FAMILY, 13), fg=fg, bg=bg,
                  wrap="word", relief="flat", bd=0, highlightthickness=0,
                  cursor="arrow", padx=SPACE_SM, pady=SPACE_XS)
                  
    txt.tag_configure("bold", font=(FONT_FAMILY, 13, "bold"))
    txt.tag_configure("italic", font=(FONT_FAMILY, 13, "italic"))
    txt.tag_configure("code", font=("Consolas", 12), background=darken(bg, 0.2))
    txt.tag_configure("rtl", justify="right")
    
    # إنشاء تاغ خاص بالمعادلات الرياضية فقط لحمايتها من القص دون التأثير على بقية النص
    txt.tag_configure("math_line", spacing1=6, spacing3=6)

    def _fix_height(widget=txt):
        if not widget.winfo_exists():
            return
        # حارس يمنع التكرار اللامتناهي: configure(height=..) يولّد حدث Configure جديد
        # وكان يستدعي _fix_height من جديد قبل ما ننتهي من المرة الحالية → حلقة بلا توقف
        if getattr(widget, "_fixing_height", False):
            return
        widget._fixing_height = True
        try:
            try:
                res = widget.count("1.0", "end-1c", "displaylines")
                n_lines = res[0] if res else int(widget.index("end-1c").split(".")[0])
            except Exception:
                n_lines = int(widget.index("end-1c").split(".")[0])

            n_lines = max(1, n_lines)

            if int(widget.cget("height")) != n_lines:
                widget.configure(height=n_lines)
            # (تم حذف الحساب الثاني عبر yview/winfo_height — كان يتعارض مع الحساب
            #  الأول ويسبب تذبذب لا ينتهي بين قيمتين مختلفتين للارتفاع مع رسائل
            #  فيها معادلات، وهذا كان مصدر "Exception in Tkinter callback" المتكرر)
        except Exception:
            pass
        finally:
            widget._fixing_height = False

    pos = 0
    full = text
    parts = []
    last = 0
    for m in re.finditer(r'\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`|\$\$(.+?)\$\$|\$(.+?)\$', full, re.DOTALL):
        if m.start() > last:
            parts.append(("text", full[last:m.start()]))
        if m.group(1) is not None:
            parts.append(("bold", m.group(1)))
        elif m.group(2) is not None:
            parts.append(("italic", m.group(2)))
        elif m.group(3) is not None:
            parts.append(("code", m.group(3)))
        elif m.group(4) is not None:
            parts.append(("math", m.group(4)))
        elif m.group(5) is not None:
            parts.append(("math", m.group(5)))
        last = m.end()
    if last < len(full):
        parts.append(("text", full[last:]))

    for kind, content in parts:
        if kind == "text":
            disp = apply_bidi(content) if is_rtl_text(content) else content
            txt.insert("end", disp)
        elif kind == "bold":
            disp = apply_bidi(content) if is_rtl_text(content) else content
            txt.insert("end", disp, "bold")
        elif kind == "italic":
            disp = apply_bidi(content) if is_rtl_text(content) else content
            txt.insert("end", disp, "italic")
        elif kind == "code":
            txt.insert("end", content, "code")
        elif kind == "math":
            cache_key = (content, fg, 13)
            if cache_key in _math_image_cache:
                img = _math_image_cache[cache_key]
                idx = txt.index("end-1c")
                txt.image_create("end", image=img, align="center")
                # تطبيق تاغ المسافات على كاش الصورة فوراً
                txt.tag_add("math_line", idx, "end-1c")
            else:
                placeholder_mark = f"math_{id(content)}_{last}"
                txt.insert("end", f"[{content}]", ("code", placeholder_mark))

                def _render_in_bg(mark=placeholder_mark, latex=content, color=fg, widget=txt):
                    png_bytes = render_math_png_bytes(latex, fg=color)
                    if png_bytes is None or not widget.winfo_exists():
                        return
                    def _apply():
                        if not widget.winfo_exists():
                            return
                        try:
                            img = tk.PhotoImage(data=png_bytes)
                            _math_cache_set((latex, color, 13), img)
                            ranges = widget.tag_ranges(mark)
                            if ranges:
                                widget.configure(state="normal")
                                start_idx = widget.index(ranges[0])
                                widget.delete(ranges[0], ranges[1])
                                widget.image_create(start_idx, image=img, align="center")
                                
                                # التعديل الجوهري: تطبيق تاغ math_line على موضع الصورة المضافة فقط
                                widget.tag_add("math_line", start_idx, f"{start_idx}+1c")
                                
                                widget.configure(state="disabled")
                                # نؤخر _fix_height لأن Tkinter يحتاج frame إضافياً
                                # بعد image_create ليحسب الأبعاد بشكل صحيح
                                widget.after(30, lambda w=widget: _fix_height(w))
                                widget.after(120, lambda w=widget: _fix_height(w))
                        except Exception:
                            pass
                    widget.after(0, _apply)

                threading.Thread(target=_render_in_bg, daemon=True).start()

    if rtl:
        txt.tag_add("rtl", "1.0", "end")

    txt.configure(state="disabled")
    
    txt.bind("<Configure>", lambda e: _fix_height(txt))
    txt.after_idle(_fix_height)
    return txt

# ═══════════════════════════════════════════════
#  MAIN WINDOW
# ═══════════════════════════════════════════════
root = ctk.CTk()
root.title(ai_name)
root.geometry("1000x720")
root.configure(fg_color=BG_PRIMARY)
root.minsize(560, 420)

# ── أيقونة النافذة ──
try:
    import os as _os
    from PIL import Image as _Image, ImageTk as _ImageTk
    _icon_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "AN.png")
    _pil_icon = _Image.open(_icon_path).resize((32, 32))
    _icon_img = _ImageTk.PhotoImage(_pil_icon)
    root.iconphoto(True, _icon_img)
except Exception:
    pass
try:
    root.state("zoomed")
except Exception:
    try:
        root.attributes("-zoomed", True)
    except Exception:
        pass

simple_mode = False
simple_win = None
simple_entry = None
_simple_real_text = ""   # مصدر الحقيقة للنص في simple mode (مثل _real_text في الـ main entry)
panel_visible = False
current_panel_tab = "archive"
attached_file_path = None  # ملف مرفق بانتظار الإرسال (زر +)

# ═══════════════════════════════════════════════
#  HEADER
# ═══════════════════════════════════════════════
header = ctk.CTkFrame(root, fg_color=BG_SECONDARY, height=72, corner_radius=0)
header.pack(fill="x", side="top")
header.pack_propagate(False)

gold_line = ctk.CTkFrame(root, fg_color=ACCENT, height=2, corner_radius=0)
gold_line.pack(fill="x", side="top")

dot = ctk.CTkLabel(header, text="◆", font=F(16), text_color=ACCENT, fg_color="transparent", width=24)
dot.pack(side="left", padx=(SPACE_MD, 0))

title_label = ctk.CTkLabel(header, text=ai_name, font=F(22, "bold"),
                            text_color=TEXT_PRIMARY, fg_color="transparent")
title_label.pack(side="left", padx=(4, 4))

subtitle_label = ctk.CTkLabel(header, text="AI Assistant", font=F(12),
                               text_color=ACCENT_LIGHT, fg_color="transparent")
subtitle_label.pack(side="left", pady=(8, 0))

status_label = ctk.CTkLabel(header, text="● online", font=F(12),
                             text_color="#34D399", fg_color="transparent")
status_label.pack(side="right", padx=SPACE_MD)

def toggle_simple_mode():
    global simple_mode
    simple_mode = not simple_mode
    if simple_mode:
        enter_simple_mode()
    else:
        exit_simple_mode()

simple_btn = ctk.CTkButton(header, text="✦ Simple", command=toggle_simple_mode,
                            font=F(12), fg_color=BG_CARD, hover_color=BORDER,
                            text_color=ACCENT_LIGHT, corner_radius=12,
                            width=100, height=34,
                            border_width=1, border_color=BORDER)
simple_btn.pack(side="right", padx=(0, SPACE_SM))

def start_new_chat():
    """يفتح محادثة جديدة فاضية، ولا يمسح المحادثات القديمة."""
    global current_conversation_id
    new_id = db_create_conversation("New chat")
    current_conversation_id = new_id
    for widget in chat_scroll.winfo_children():
        widget.destroy()
    add_message_bubble("system", f"New chat started. I am {ai_name} — how can I help?")
    if panel_visible and current_panel_tab == "chats":
        show_panel_tab("chats")

new_chat_btn = ctk.CTkButton(header, text="＋ New chat", command=start_new_chat,
                              font=F(12), fg_color=BG_CARD, hover_color=BORDER,
                              text_color=ACCENT_LIGHT, corner_radius=12,
                              width=110, height=34,
                              border_width=1, border_color=BORDER)
new_chat_btn.pack(side="right", padx=(0, SPACE_SM))

# ═══════════════════════════════════════════════
#  BODY: CONTENT | ICON BAR | SIDE PANEL
# ═══════════════════════════════════════════════
body = ctk.CTkFrame(root, fg_color=BG_PRIMARY, corner_radius=0)
body.pack(fill="both", expand=True)

content_frame = ctk.CTkFrame(body, fg_color=BG_PRIMARY, corner_radius=0)
content_frame.pack(side="left", fill="both", expand=True)

panel_frame = ctk.CTkFrame(body, fg_color=BG_CARD, width=300, corner_radius=0)
panel_frame.pack_propagate(False)
# يظهر فقط عند الضغط على أيقونة (Part 3)

icon_bar = ctk.CTkFrame(body, fg_color=BG_SECONDARY, width=76, corner_radius=0)
icon_bar.pack(side="right", fill="y")
icon_bar.pack_propagate(False)

# ═══════════════════════════════════════════════
#  CHAT AREA (scrollable)
# ═══════════════════════════════════════════════
chat_scroll = ctk.CTkScrollableFrame(content_frame, fg_color=BG_PRIMARY,
                                      scrollbar_button_color=BORDER,
                                      scrollbar_button_hover_color=ACCENT)
chat_scroll.pack(fill="both", expand=True, padx=SPACE_SM, pady=(SPACE_SM, 0))

def add_message_bubble(role, text):
    rtl = is_rtl_text(text)

    if role == "user":
        outer = ctk.CTkFrame(chat_scroll, fg_color="transparent")
        outer.pack(fill="x", pady=(SPACE_SM, 0))
        bubble = ctk.CTkFrame(outer, fg_color=BUBBLE_USER, corner_radius=18,
                              border_width=1, border_color=BUBBLE_USER_B)
        bubble.pack(side="right", padx=(100, SPACE_MD))
        content = render_rich_text(bubble, text, TEXT_PRIMARY, BUBBLE_USER)
        content.pack(padx=SPACE_MD, pady=SPACE_SM)

    elif role == "ai":
        outer = ctk.CTkFrame(chat_scroll, fg_color="transparent")
        outer.pack(fill="x", pady=(SPACE_SM, 0))
        row = ctk.CTkFrame(outer, fg_color="transparent")
        row.pack(side="left", fill="x", padx=(SPACE_MD, 0))

        if _avatar_ctk_image is not None:
            icon = ctk.CTkLabel(row, text="", image=_avatar_ctk_image,
                                fg_color="transparent", corner_radius=16, width=34, height=34)
        else:
            icon = ctk.CTkLabel(row, text="AI", font=F(10, "bold"), text_color="#000000",
                                fg_color=ACCENT, corner_radius=16, width=34, height=34)
        icon.pack(side="left", anchor="n", padx=(0, SPACE_SM), pady=(2, 0))

        bubble = ctk.CTkFrame(row, fg_color=BUBBLE_AI, corner_radius=18,
                              border_width=1, border_color=BUBBLE_AI_B)
        bubble.pack(side="left", padx=(0, 100))
        content = render_rich_text(bubble, text, TEXT_PRIMARY, BUBBLE_AI)
        content.pack(padx=SPACE_MD, pady=SPACE_SM)

    elif role == "system":
        outer = ctk.CTkFrame(chat_scroll, fg_color="transparent")
        outer.pack(fill="x", pady=4)
        ctk.CTkLabel(outer, text=text, font=F(10), text_color=TEXT_MUTED,
                    fg_color="transparent").pack()

    elif role == "error":
        outer = ctk.CTkFrame(chat_scroll, fg_color="transparent")
        outer.pack(fill="x", pady=4)
        frame = ctk.CTkFrame(outer, fg_color="#2D1515", corner_radius=14,
                             border_width=1, border_color="#7F1D1D")
        frame.pack(anchor="center")
        ctk.CTkLabel(frame, text=f"⚠  {text}", font=F(11), text_color="#FCA5A5",
                    fg_color="transparent").pack(padx=SPACE_MD, pady=SPACE_SM)

    elif role == "success":
        outer = ctk.CTkFrame(chat_scroll, fg_color="transparent")
        outer.pack(fill="x", pady=4)
        frame = ctk.CTkFrame(outer, fg_color="#0D2D1A", corner_radius=14,
                             border_width=1, border_color="#14532D")
        frame.pack(anchor="center")
        ctk.CTkLabel(frame, text=f"✓  {text}", font=F(11), text_color="#86EFAC",
                    fg_color="transparent").pack(padx=SPACE_MD, pady=SPACE_SM)

    root.after(50, lambda: chat_scroll._parent_canvas.yview_moveto(1.0))

# ═══════════════════════════════════════════════
#  END OF PART 2
#  (quick actions, input bar with + attach button in Part 3)
# ═══════════════════════════════════════════════
# ═══════════════════════════════════════════════
#  PART 3 — QUICK ACTIONS + INPUT BAR WITH "+" ATTACH
#  (append after Part 2)
# ═══════════════════════════════════════════════

# ═══════════════════════════════════════════════
#  QUICK ACTIONS ROW
# ═══════════════════════════════════════════════
divider1 = ctk.CTkFrame(content_frame, fg_color=BORDER, height=1, corner_radius=0)
divider1.pack(fill="x", padx=SPACE_SM)

actions_frame = ctk.CTkFrame(content_frame, fg_color=BG_PRIMARY, corner_radius=0)
actions_frame.pack(fill="x", padx=SPACE_SM, pady=(SPACE_XS, 0))

ctk.CTkLabel(actions_frame, text="Quick actions", font=F(10),
             text_color=TEXT_MUTED, fg_color="transparent").pack(anchor="w", pady=(4, 4))

btns_row = ctk.CTkFrame(actions_frame, fg_color="transparent")
btns_row.pack(fill="x")

def quick_action(text):
    entry_box.delete(0, "end")
    entry_box.insert(0, text)
    entry_box.focus()
    entry_box.icursor("end")

quick_buttons_data = [
    ("📄  Report", "make a report about "),
    ("📊  Excel",  "make an excel sheet for "),
    ("🔄  To PDF", "convert file to pdf"),
    ("📁  Upload", "upload file"),
]

for label, cmd_text in quick_buttons_data:
    b = ctk.CTkButton(btns_row, text=label, command=lambda t=cmd_text: quick_action(t),
                      font=F(11), fg_color=BG_CARD, hover_color=ACCENT_GLOW,
                      text_color=ACCENT_LIGHT, corner_radius=12, height=34, width=110,
                      border_width=1, border_color=BORDER)
    b.pack(side="left", padx=(0, SPACE_XS))

# ═══════════════════════════════════════════════
#  ATTACHMENT PREVIEW STRIP (shows above input when a file is attached)
# ═══════════════════════════════════════════════
REFERENCE_EXTS = (".pdf", ".docx", ".txt", ".md", ".csv")

attach_strip = ctk.CTkFrame(content_frame, fg_color=BG_SECONDARY, corner_radius=12,
                             border_width=1, border_color=BORDER)
# يُعرض فقط عند إرفاق ملف — pack/pack_forget ديناميكياً

attach_label = ctk.CTkLabel(attach_strip, text="", font=F(11),
                             text_color=TEXT_PRIMARY, fg_color="transparent")
attach_label.pack(side="left", padx=SPACE_SM, pady=6)

def clear_attachment():
    global attached_file_path
    attached_file_path = None
    attach_strip.pack_forget()

# زر "Use as Reference" — يظهر فقط للملفات النصية/المستندات
ref_btn = ctk.CTkButton(
    attach_strip, text="📚 Use as Reference",
    command=lambda: add_as_reference(),
    font=F(10, "bold"), fg_color=ACCENT_GLOW, hover_color=ACCENT,
    text_color=TEXT_PRIMARY, corner_radius=10, height=26, width=140
)

attach_remove_btn = ctk.CTkButton(
    attach_strip, text="✕", command=clear_attachment,
    font=F(10), fg_color="transparent", hover_color=BORDER,
    text_color=TEXT_MUTED, width=26, height=26, corner_radius=8
)
attach_remove_btn.pack(side="right", padx=(0, SPACE_SM), pady=6)


def add_as_reference():
    """يضيف الملف المرفق كمرجع RAG"""
    global attached_file_path
    if not attached_file_path:
        return
    path = attached_file_path
    clear_attachment()
    add_message_bubble("system", f"Adding {os.path.basename(path)} as reference...")
    threading.Thread(target=_add_reference_bg, args=(path,), daemon=True).start()


def _add_reference_bg(path):
    try:
        count = ragtools.add_reference(path)
        append_message("success", f"Reference ready: {os.path.basename(path)} ({count} chunks)")
    except Exception as e:
        append_message("error", f"Reference error: {e}")


def pick_attachment():
    """يفتح نافذة اختيار ملف/صورة وتُعرض كمرفق بانتظار الإرسال"""
    global attached_file_path
    path = filedialog.askopenfilename(
        title="Attach a file or image",
        filetypes=[
            ("All supported", "*.pdf *.docx *.xlsx *.csv *.txt *.png *.jpg *.jpeg *.webp"),
            ("Documents", "*.pdf *.docx *.xlsx *.csv *.txt"),
            ("Images", "*.png *.jpg *.jpeg *.webp"),
            ("All files", "*.*"),
        ]
    )
    if not path:
        return
    attached_file_path = path
    fname = os.path.basename(path)
    ext = os.path.splitext(fname)[1].lower()
    is_img = ext in (".png", ".jpg", ".jpeg", ".webp")
    icon = "🖼️" if is_img else "📎"
    attach_label.configure(text=f"{icon}  {fname}")

    # أظهر زر المرجع فقط للمستندات (مو الصور)
    if ext in REFERENCE_EXTS:
        ref_btn.pack(side="right", padx=(0, SPACE_XS), pady=6)
    else:
        ref_btn.pack_forget()

    attach_strip.pack(fill="x", padx=SPACE_SM, pady=(SPACE_XS, 0), before=divider2_placeholder)


# ═══════════════════════════════════════════════
#  INPUT BAR  ( [+]  [textbox]  [send] )
# ═══════════════════════════════════════════════
divider2_placeholder = ctk.CTkFrame(content_frame, fg_color=BORDER, height=1, corner_radius=0)
divider2_placeholder.pack(fill="x", padx=SPACE_SM, pady=(SPACE_XS, 0))

input_outer = ctk.CTkFrame(content_frame, fg_color=BG_SECONDARY, corner_radius=20,
                            border_width=1, border_color=ACCENT)
input_outer.pack(fill="x", padx=SPACE_SM, pady=SPACE_SM)

# زر "+" لإرفاق ملفات/صور
attach_btn = ctk.CTkButton(input_outer, text="+", command=pick_attachment,
                            font=F(22, "bold"), fg_color=BG_CARD, hover_color=ACCENT_GLOW,
                            text_color=ACCENT_LIGHT, corner_radius=14, width=44, height=44,
                            border_width=1, border_color=BORDER)
attach_btn.pack(side="left", padx=(SPACE_SM, 4), pady=SPACE_SM)

# ── صندوق الإدخال: tk.Text بدل CTkEntry لدعم العربية RTL بشكل صحيح ──
_entry_frame = ctk.CTkFrame(input_outer, fg_color=INPUT_BG, corner_radius=12,
                             border_width=0, height=44)
_entry_frame.pack(side="left", fill="x", expand=True, padx=(0, SPACE_XS), pady=SPACE_SM)
_entry_frame.pack_propagate(False)

entry_box = tk.Text(_entry_frame, font=(FONT_FAMILY, 14), fg=TEXT_PRIMARY,
                    bg=INPUT_BG, insertbackground=TEXT_PRIMARY,
                    relief="flat", bd=0, highlightthickness=0,
                    wrap="none", height=1, cursor="xterm",
                    undo=True)
entry_box.pack(fill="both", expand=True, padx=10, pady=8)
_orig_entry_box = entry_box   # مرجع ثابت للـ tk.Text الحقيقي قبل ما entry_box يتغير

# placeholder منفصل لأن tk.Text لا يدعمه مدمجاً
_PLACEHOLDER = "اكتب رسالتك... / Type a message..."
_placeholder_active = True
_real_text = ""   # النص الأصلي (غير معالج) — هذا ما يُرسل للـ AI

def _entry_set_placeholder():
    global _placeholder_active
    _orig_entry_box.delete("1.0", "end")
    _orig_entry_box.insert("1.0", _PLACEHOLDER)
    _orig_entry_box.configure(fg="#555555")
    _placeholder_active = True

def _entry_clear_placeholder(event=None):
    global _placeholder_active, _real_text
    if _placeholder_active:
        _orig_entry_box.delete("1.0", "end")
        _orig_entry_box.configure(fg=TEXT_PRIMARY)
        _placeholder_active = False
        _real_text = ""

def _entry_check_placeholder(event=None):
    if not _real_text.strip():
        _entry_set_placeholder()

try:
    import arabic_reshaper
    # support_ligatures=False يضمن أن كل حرف عربي يتحول لشكل واحد فقط (presentation form)
    # بدون دمج حروف (مثل لام+ألف) في حرف واحد — هذا يحافظ على تطابق عدد الحروف 1:1
    # بين النص المنطقي والنص المُشكَّل، وهو ما نحتاجه لحساب موضع الكيرسر بدقة.
    _reshaper = arabic_reshaper.ArabicReshaper({
        "delete_harakat": False,
        "support_ligatures": False,
    })
except ImportError:
    arabic_reshaper = None
    _reshaper = None

def _reshape_for_display(text):
    """يربط الحروف العربية ويطبق bidi algorithm للعرض الصحيح RTL في widget اتجاهه LTR."""
    if _reshaper is None:
        return text
    shaped = _reshaper.reshape(text)
    try:
        from bidi.algorithm import get_display
        return get_display(shaped)
    except ImportError:
        return shaped

def _unshape(text):
    """يعكس reshape: يحوّل أشكال الحروف العربية المرسومة (presentation forms, مثل ﺍ ﻻ ﻡ)
    إلى الحرف الأصلي (ا ل م...). نستخدم NFKC لأن presentation forms هي حروف
    "compatibility" أصلاً عندها تفكيك متوافق (compatibility decomposition) يرجعها
    لحرفها الأساسي، وأي حرف آخر (لاتيني/أرقام/علامات) يبقى بلا تغيير.
    هذا هو مصدر النص المنطقي الحقيقي دائماً — لا نعتمد إطلاقاً على ما هو ظاهر في الـ widget."""
    return unicodedata.normalize("NFKC", text)

def _render_entry_from_logical(logical, cursor_offset=None):
    """يعيد رسم محتوى الـ widget بالكامل من النص المنطقي (logical) فقط — هذا هو
    المصدر الوحيد للحقيقة. لا نقرأ أبداً من الـ widget لنعيد تشكيله، لأن هذا هو
    سبب التراكم الذي كان يحصل سابقاً (reshape فوق نص مُشكَّل من قبل).
    cursor_offset: موضع الكيرسر بعدد الحروف من البداية، أو None لوضعه في النهاية."""
    rtl = is_rtl_text(logical)
    shaped = _reshape_for_display(logical) if rtl else logical
    _orig_entry_box.delete("1.0", "end")
    _orig_entry_box.insert("1.0", shaped)
    _orig_entry_box.tag_configure("dir", justify="right" if rtl else "left")
    _orig_entry_box.tag_add("dir", "1.0", "end")
    if rtl:
        # بعد تطبيق bidi، آخر حرف منطقي يظهر في أقصى اليسار (position 0) في الـ widget.
        # الكيرسر يجب أن يبقى في بداية الـ widget (اليسار) وهو ما يقابل نهاية النص
        # العربي بصرياً (أقصى اليمين من منظور القارئ) — هذا السلوك الصحيح لـ RTL input.
        _orig_entry_box.mark_set("insert", "1.0")
    elif cursor_offset is None:
        _orig_entry_box.mark_set("insert", "end")
    else:
        _orig_entry_box.mark_set("insert", f"1.0+{cursor_offset}c")

def _entry_on_char(event=None):
    """يعترض كل حرف قابل للطباعة على مستوى KeyPress — قبل أن يُدرجه tkinter في الـ widget.
    يُضيف الحرف مباشرة إلى _real_text ويُعيد الرسم، ثم يُرجع 'break' لمنع الإدراج المزدوج.
    هذا يتجنب قراءة النص من الـ widget تماماً ويحل مشكلة المكس عربي+إنجليزي."""
    global _real_text
    char = event.char
    if not char or not char.isprintable():
        return  # مفاتيح تحكم (Ctrl، Alt...) — لا تعترض
    if _placeholder_active:
        _entry_clear_placeholder()
    _real_text += char
    _render_entry_from_logical(_real_text)
    return "break"  # امنع tkinter من إدراج الحرف مرة ثانية في الـ widget

def _entry_on_paste(event=None):
    """يعترض Ctrl+V ويضيف المحتوى المنسوخ إلى _real_text مباشرة."""
    global _real_text
    try:
        pasted = _orig_entry_box.clipboard_get()
    except Exception:
        return "break"
    if _placeholder_active:
        _entry_clear_placeholder()
    _real_text += pasted
    _render_entry_from_logical(_real_text)
    return "break"

def _entry_on_backspace(event=None):
    """Backspace: يحذف آخر حرف من _real_text مباشرة بدون قراءة من الـ widget."""
    global _real_text
    if _placeholder_active:
        return "break"
    if _real_text:
        _real_text = _real_text[:-1]
    if not _real_text.strip():
        _real_text = ""
        _entry_set_placeholder()
    else:
        _render_entry_from_logical(_real_text)
    return "break"

_orig_entry_box.bind("<FocusIn>", _entry_clear_placeholder)
_orig_entry_box.bind("<FocusOut>", _entry_check_placeholder)
_orig_entry_box.bind("<BackSpace>", _entry_on_backspace)
_orig_entry_box.bind("<<Paste>>", _entry_on_paste)
_orig_entry_box.bind("<Key>", _entry_on_char)  # يعترض كل حرف قابل للطباعة

_entry_set_placeholder()

# تغليف get/delete/insert/focus بحيث يعمل باقي الكود بدون تغيير

class _EntryBoxCompat:
    """يحاكي واجهة CTkEntry لأن باقي الكود يستخدم .get() و.delete() و.insert()"""
    def get(self, *a):
        if _placeholder_active:
            return ""
        return _real_text   # النص الأصلي قبل apply_bidi
    def delete(self, *a):
        global _placeholder_active, _real_text
        _orig_entry_box.delete("1.0", "end")
        _placeholder_active = False
        _real_text = ""
    def insert(self, pos, text):
        global _real_text
        _entry_clear_placeholder()
        # نلتزم بنفس السلوك السابق: استبدال كامل المحتوى (المستخدِم الفعلي لهذه
        # الدالة يستدعي delete(0,"end") قبلها دائماً)، لكن مع تشكيل صحيح هذه المرة
        # بدل الإدراج الخام الذي كان يتجاوز reshape بالكامل.
        _real_text = _real_text + text
        _render_entry_from_logical(_real_text, cursor_offset=None)
    def focus(self):
        _orig_entry_box.focus_set()
    def icursor(self, pos):
        if pos == "end":
            _orig_entry_box.mark_set("insert", "end")
    def configure(self, **kw):
        pass
    def bind(self, event, func, *a, **kw):
        return _orig_entry_box.bind(event, func, *a, **kw)
    def winfo_exists(self):
        return _orig_entry_box.winfo_exists()

entry_box = _EntryBoxCompat()

def on_send(event=None):
    global attached_file_path

    # منع الإرسال لو يوجد طلب جارٍ
    if not _send_lock.acquire(blocking=False):
        return
    _send_lock.release()  # نطلقه فوراً — process_message هو اللي يمسكه فعلاً

    user_input = entry_box.get().strip()
    has_attachment = attached_file_path is not None

    if not user_input and not has_attachment:
        return

    # تعطيل زر الإرسال بصرياً أثناء الانتظار
    send_btn.configure(state="disabled", text="...")
    entry_box.delete(0, "end")

    def _re_enable():
        send_btn.configure(state="normal", text="Send  ➤")

    if has_attachment:
        fname = os.path.basename(attached_file_path)
        display_text = f"📎 {fname}" + (f"\n{user_input}" if user_input else "")
        add_message_bubble("user", display_text)
        path_to_send = attached_file_path
        prompt_to_send = user_input or "explain and summarize this file"
        clear_attachment()
        def _task():
            process_attached_file(path_to_send, prompt_to_send)
            root.after(0, _re_enable)
        threading.Thread(target=_task, daemon=True).start()
    else:
        if not simple_mode:
            add_message_bubble("user", user_input)
        def _task():
            process_message(user_input)
            root.after(0, _re_enable)
        threading.Thread(target=_task, daemon=True).start()

send_btn = ctk.CTkButton(input_outer, text="Send  ➤", command=on_send,
                          font=F(13, "bold"), fg_color=ACCENT, hover_color=ACCENT_GLOW,
                          text_color="#000000", corner_radius=14, height=44, width=110)
send_btn.pack(side="right", padx=(0, SPACE_SM), pady=SPACE_SM)

entry_box.bind("<Return>", on_send)
# في tk.Text الضغط على Enter يُدرج سطر جديد — نمنعه ونرسل بدلاً منه
_orig_entry_box.bind("<Return>", lambda e: (on_send(), "break")[1])
_orig_entry_box.bind("<KP_Enter>", lambda e: (on_send(), "break")[1])

# ═══════════════════════════════════════════════
#  END OF PART 3
#  process_attached_file() + process_message() defined in Part 5 (AI logic)
#  Sidebar (Archive/Themes panel) comes in Part 4
# ═══════════════════════════════════════════════
# ═══════════════════════════════════════════════
#  PART 4 — ICON BAR + SIDE PANEL (Archive / Themes)
#  (append after Part 3)
# ═══════════════════════════════════════════════

def make_icon_button(parent, icon, label, command):
    f = ctk.CTkFrame(parent, fg_color="transparent")
    f.pack(pady=(6, 2), padx=8, fill="x")
    btn = ctk.CTkButton(
        f, text=icon, command=command,
        font=ctk.CTkFont(size=28),
        fg_color=BG_CARD,
        hover_color=ACCENT_GLOW,
        text_color=ACCENT_LIGHT,
        corner_radius=14,
        width=56, height=54,
        border_width=1,
        border_color=BORDER,
    )
    btn.pack(fill="x")
    ctk.CTkLabel(
        f, text=label, font=F(12),
        text_color=TEXT_MUTED, fg_color="transparent"
    ).pack(pady=(2, 0))
    return btn

icons_col = ctk.CTkFrame(icon_bar, fg_color="transparent")
icons_col.pack(fill="both", expand=True, pady=SPACE_SM)

def toggle_panel(tab):
    global panel_visible, current_panel_tab
    if panel_visible and current_panel_tab == tab:
        panel_frame.pack_forget()
        panel_visible = False
    else:
        current_panel_tab = tab
        panel_visible = True
        panel_frame.pack(side="right", fill="y", before=icon_bar)
        show_panel_tab(tab)

make_icon_button(icons_col, "💬", "Chats", lambda: toggle_panel("chats"))
make_icon_button(icons_col, "📁", "Archive", lambda: toggle_panel("archive"))
make_icon_button(icons_col, "🎨", "Themes", lambda: toggle_panel("themes"))
make_icon_button(icons_col, "🔑", "Account", lambda: open_account_dialog())
make_icon_button(icons_col, "⚙", "Settings", lambda: toggle_panel("settings"))

# spacer + bottom item
ctk.CTkFrame(icons_col, fg_color="transparent").pack(expand=True, fill="both")


def clear_panel():
    for w in panel_frame.winfo_children():
        w.destroy()


def show_panel_tab(tab):
    clear_panel()

    ph = ctk.CTkFrame(panel_frame, fg_color=BG_SECONDARY, height=60, corner_radius=0)
    ph.pack(fill="x")
    ph.pack_propagate(False)
    ctk.CTkFrame(panel_frame, fg_color=ACCENT, height=2, corner_radius=0).pack(fill="x")

    titles = {"chats": "💬  Chats", "archive": "📁  Archive", "themes": "🎨  Themes", "settings": "⚙  Settings"}
    ctk.CTkLabel(ph, text=titles.get(tab, ""), font=F(16, "bold"),
                text_color=TEXT_PRIMARY, fg_color="transparent").pack(side="left", padx=SPACE_MD)

    close_btn = ctk.CTkButton(ph, text="✕", command=lambda: toggle_panel(tab),
                              font=F(13), fg_color="transparent", hover_color=BORDER,
                              text_color=TEXT_MUTED, width=32, height=32, corner_radius=10)
    close_btn.pack(side="right", padx=SPACE_SM)

    body_area = ctk.CTkScrollableFrame(panel_frame, fg_color=BG_CARD,
                                        scrollbar_button_color=BORDER,
                                        scrollbar_button_hover_color=ACCENT)
    body_area.pack(fill="both", expand=True)

    if tab == "chats":
        build_chats_panel(body_area)
    elif tab == "archive":
        build_archive_panel(body_area)
    elif tab == "themes":
        build_themes_panel(body_area)
    else:
        build_settings_panel(body_area)


# ═══════════════════════════════════════════════
#  SWITCH CONVERSATION — تبديل المحادثة المفتوحة
# ═══════════════════════════════════════════════
def switch_conversation(conversation_id):
    """يفتح محادثة محفوظة: يفرّغ الشات الحالي ويحمّل رسائل هذه المحادثة فقط.
    من هذه اللحظة، الذاكرة (context) المرسلة للـ AI تقتصر على هذه المحادثة فقط."""
    global current_conversation_id
    if conversation_id == current_conversation_id:
        return
    current_conversation_id = conversation_id
    for widget in chat_scroll.winfo_children():
        widget.destroy()
    rows = db_load_all(conversation_id)
    if not rows:
        add_message_bubble("system", "This chat is empty. Say something!")
    else:
        for role, content in rows:
            add_message_bubble(role if role != "assistant" else "ai", content)
    if panel_visible and current_panel_tab == "chats":
        show_panel_tab("chats")


# ═══════════════════════════════════════════════
#  CHATS PANEL — كل المحادثات المحفوظة (مثل Claude)
# ═══════════════════════════════════════════════
def build_chats_panel(parent):
    ctk.CTkButton(parent, text="＋ New chat", command=start_new_chat,
                  font=F(12, "bold"), fg_color=ACCENT, hover_color=ACCENT_GLOW,
                  text_color="#000000", corner_radius=10, height=36
                  ).pack(fill="x", padx=SPACE_SM, pady=(SPACE_SM, SPACE_SM))

    convs = db_list_conversations()
    if not convs:
        ctk.CTkLabel(parent, text="No chats yet.",
                     font=F(11), text_color=TEXT_MUTED, fg_color="transparent",
                     justify="center").pack(expand=True, pady=SPACE_LG)
        return

    for conv_id, title, updated_at in convs:
        is_active = (conv_id == current_conversation_id)
        row = ctk.CTkFrame(parent, fg_color=ACCENT_GLOW if is_active else BG_SECONDARY,
                           corner_radius=10, border_width=1,
                           border_color=ACCENT if is_active else BORDER)
        row.pack(fill="x", padx=SPACE_SM, pady=(0, SPACE_XS))

        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True, padx=SPACE_SM, pady=SPACE_XS)
        info.bind("<Button-1>", lambda e, cid=conv_id: switch_conversation(cid))

        title_lbl = ctk.CTkLabel(info, text=title or "New chat", font=F(11, "bold"),
                     text_color=TEXT_PRIMARY, fg_color="transparent",
                     anchor="w", wraplength=170)
        title_lbl.pack(fill="x")
        title_lbl.bind("<Button-1>", lambda e, cid=conv_id: switch_conversation(cid))

        time_lbl = ctk.CTkLabel(info, text=updated_at, font=F(9),
                     text_color=TEXT_MUTED, fg_color="transparent", anchor="w")
        time_lbl.pack(fill="x")
        time_lbl.bind("<Button-1>", lambda e, cid=conv_id: switch_conversation(cid))

        ctk.CTkButton(row, text="✕",
                      command=lambda cid=conv_id: _delete_conv_and_refresh(cid, parent),
                      font=F(10), fg_color="transparent", hover_color=BORDER,
                      text_color=TEXT_MUTED, width=26, height=26, corner_radius=8
                      ).pack(side="right", padx=SPACE_XS)


def _delete_conv_and_refresh(conv_id, parent):
    global current_conversation_id
    was_active = (conv_id == current_conversation_id)
    db_delete_conversation(conv_id)

    remaining = db_list_conversations()
    if not remaining:
        # لا تترك التطبيق بلا محادثات أبداً
        new_id = db_create_conversation("New chat")
        remaining = db_list_conversations()

    if was_active:
        switch_conversation(remaining[0][0])
    else:
        show_panel_tab("chats")


# ═══════════════════════════════════════════════
#  ARCHIVE PANEL
# ═══════════════════════════════════════════════
def build_archive_panel(parent):

    # ── قسم المراجع ──
    ctk.CTkLabel(parent, text="📚  References", font=F(13, "bold"),
                 text_color=TEXT_PRIMARY, fg_color="transparent",
                 anchor="w").pack(fill="x", padx=SPACE_SM, pady=(SPACE_SM, 2))
    ctk.CTkLabel(parent, text="Files the AI searches when answering",
                 font=F(9), text_color=TEXT_MUTED, fg_color="transparent",
                 anchor="w").pack(fill="x", padx=SPACE_SM, pady=(0, SPACE_XS))

    ref_files = ragtools.list_reference_files()
    if not ref_files:
        ctk.CTkLabel(parent,
                     text="No references yet.\nAttach a PDF/Word/text file\nand tap 📚 Use as Reference.",
                     font=F(10), text_color=TEXT_MUTED, fg_color="transparent",
                     justify="left").pack(anchor="w", padx=SPACE_SM, pady=(0, SPACE_SM))
    else:
        for fname in ref_files:
            row = ctk.CTkFrame(parent, fg_color=BG_SECONDARY, corner_radius=10,
                               border_width=1, border_color=ACCENT_GLOW)
            row.pack(fill="x", padx=SPACE_SM, pady=(0, SPACE_XS))

            ctk.CTkLabel(row, text=f"📖  {fname}", font=F(10),
                         text_color=TEXT_PRIMARY, fg_color="transparent",
                         anchor="w", wraplength=190).pack(
                side="left", fill="x", expand=True, padx=SPACE_SM, pady=SPACE_XS)

            ctk.CTkButton(row, text="✕",
                          command=lambda f=fname: _remove_ref_and_refresh(f, parent),
                          font=F(10), fg_color="transparent", hover_color=BORDER,
                          text_color=TEXT_MUTED, width=26, height=26, corner_radius=8
                          ).pack(side="right", padx=SPACE_XS)

        ctk.CTkButton(parent, text="Clear all references",
                      command=lambda: _clear_refs_and_refresh(parent),
                      font=F(10), fg_color="#2D1515", hover_color="#3D2020",
                      text_color="#FCA5A5", corner_radius=10, height=30
                      ).pack(fill="x", padx=SPACE_SM, pady=(SPACE_XS, SPACE_SM))

    # ── فاصل ──
    ctk.CTkFrame(parent, fg_color=BORDER, height=1, corner_radius=0).pack(
        fill="x", padx=SPACE_SM, pady=SPACE_SM)

    # ── الملفات المحفوظة ──
    ctk.CTkLabel(parent, text="🗂  Saved files", font=F(13, "bold"),
                 text_color=TEXT_PRIMARY, fg_color="transparent",
                 anchor="w").pack(fill="x", padx=SPACE_SM, pady=(0, SPACE_XS))

    items = load_archive()
    if not items:
        ctk.CTkLabel(parent, text="Nothing here yet.\n\nGenerate a report, Excel,\nor convert a file —\nit will appear here.",
                    font=F(11), text_color=TEXT_MUTED, fg_color="transparent",
                    justify="center").pack(expand=True, pady=SPACE_LG)
        return

    icons_map = {".docx": "📄", ".xlsx": "📊", ".xls": "📊", ".pdf": "🔄"}

    for item in items:
        ext = os.path.splitext(item["name"])[1].lower()
        ic = icons_map.get(ext, "📁")

        row = ctk.CTkFrame(parent, fg_color=BG_SECONDARY, corner_radius=10,
                           border_width=1, border_color=BORDER)
        row.pack(fill="x", padx=SPACE_SM, pady=(SPACE_XS, 0))

        accent_bar = ctk.CTkFrame(row, fg_color=ACCENT, width=3, corner_radius=0)
        accent_bar.pack(side="left", fill="y")

        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True, padx=SPACE_SM, pady=SPACE_XS)

        name_lbl = ctk.CTkLabel(info, text=f"{ic}  {item['name']}", font=F(11),
                                text_color=TEXT_PRIMARY, fg_color="transparent",
                                anchor="w", wraplength=200)
        name_lbl.pack(fill="x")
        time_lbl = ctk.CTkLabel(info, text=item["time"], font=F(8),
                                text_color=TEXT_MUTED, fg_color="transparent", anchor="w")
        time_lbl.pack(fill="x")

        open_btn = ctk.CTkButton(row, text="↗", command=lambda p=item["path"]: open_path(p),
                                 font=F(13, "bold"), fg_color="transparent", hover_color=BORDER,
                                 text_color=ACCENT, width=28, height=28, corner_radius=8)
        open_btn.pack(side="right", padx=SPACE_SM)


def _remove_ref_and_refresh(fname, parent):
    ragtools.remove_reference_file(fname)
    for w in parent.winfo_children():
        w.destroy()
    build_archive_panel(parent)


def _clear_refs_and_refresh(parent):
    ragtools.clear_references()
    for w in parent.winfo_children():
        w.destroy()
    build_archive_panel(parent)


# ═══════════════════════════════════════════════
#  THEMES PANEL
# ═══════════════════════════════════════════════
def open_theme_creator():
    dlg = ctk.CTkToplevel(root)
    dlg.title("Create theme")
    dlg.configure(fg_color=BG_SECONDARY)
    dlg.geometry("320x440")
    dlg.attributes("-topmost", True)
    dlg.resizable(False, False)

    picks = {"bg": BG_PRIMARY, "card": BG_CARD, "accent": ACCENT, "text": TEXT_PRIMARY}
    swatches = {}

    ctk.CTkLabel(dlg, text="Create your theme", font=F(16, "bold"),
                text_color=TEXT_PRIMARY, fg_color="transparent").pack(pady=(SPACE_MD, 4))
    ctk.CTkLabel(dlg, text="Pick 4 colors — the rest is generated", font=F(10),
                text_color=TEXT_MUTED, fg_color="transparent").pack()

    ctk.CTkLabel(dlg, text="Theme name", font=F(10), text_color=TEXT_MUTED,
                fg_color="transparent").pack(anchor="w", padx=SPACE_MD, pady=(SPACE_SM, 2))
    name_entry = ctk.CTkEntry(dlg, font=F(12), fg_color=INPUT_BG, text_color=TEXT_PRIMARY,
                              border_width=0, corner_radius=8)
    name_entry.insert(0, "My Theme")
    name_entry.pack(fill="x", padx=SPACE_MD, pady=(0, SPACE_SM))

    labels = {"bg": "Background", "card": "Cards / Panels", "accent": "Accent", "text": "Text"}

    def pick(key):
        def apply(hexcolor, k=key):
            picks[k] = hexcolor
            swatches[k].configure(fg_color=hexcolor)
        open_circle_color_picker(dlg, picks[key], labels[key], apply)

    for key in ("bg", "card", "accent", "text"):
        row = ctk.CTkFrame(dlg, fg_color="transparent")
        row.pack(fill="x", padx=SPACE_MD, pady=6)
        ctk.CTkLabel(row, text=labels[key], font=F(12), text_color=TEXT_PRIMARY,
                    fg_color="transparent").pack(side="left")
        sw = ctk.CTkButton(row, text="", command=lambda k=key: pick(k),
                           fg_color=picks[key], hover_color=picks[key],
                           width=32, height=32, corner_radius=16,
                           border_width=1, border_color=BORDER)
        sw.pack(side="right")
        swatches[key] = sw

    def save_and_apply():
        theme_dict = derive_theme(picks["bg"], picks["card"], picks["accent"], picks["text"])
        name = name_entry.get().strip() or "My Theme"
        apply_theme(name, is_custom=True, theme_dict=theme_dict)

    save_btn = ctk.CTkButton(dlg, text="Save & Apply (restarts app)", command=save_and_apply,
                             font=F(12, "bold"), fg_color=ACCENT, hover_color=ACCENT_GLOW,
                             text_color="#000000", corner_radius=10, height=38)
    save_btn.pack(fill="x", padx=SPACE_MD, pady=SPACE_MD)


# ═══════════════════════════════════════════════
#  ADVANCED THEME EDITOR — كل لون في الواجهة على حدة
# ═══════════════════════════════════════════════
ADVANCED_COLOR_LABELS = {
    "BG_PRIMARY":    "Main background",
    "BG_SECONDARY":  "Header / panels background",
    "BG_CARD":       "Card background",
    "ACCENT":        "Accent (buttons / highlights)",
    "ACCENT_LIGHT":  "Accent — light variant",
    "ACCENT_GLOW":   "Accent — hover / glow variant",
    "TEXT_PRIMARY":  "Primary text",
    "TEXT_SECONDARY":"Secondary text",
    "TEXT_MUTED":    "Muted / hint text",
    "BORDER":        "Borders",
    "INPUT_BG":      "Input field background",
    "BUBBLE_USER":   "Your message bubble",
    "BUBBLE_USER_B": "Your message bubble — border",
    "BUBBLE_AI":     "AI message bubble",
    "BUBBLE_AI_B":   "AI message bubble — border",
}

def open_advanced_theme_editor():
    dlg = ctk.CTkToplevel(root)
    dlg.title("Customize every color")
    dlg.configure(fg_color=BG_SECONDARY)
    dlg.geometry("380x620")
    dlg.attributes("-topmost", True)
    dlg.resizable(False, False)

    ctk.CTkLabel(dlg, text="Customize every color", font=F(16, "bold"),
                text_color=TEXT_PRIMARY, fg_color="transparent").pack(pady=(SPACE_MD, 2))
    ctk.CTkLabel(dlg, text="Tap any swatch to change it", font=F(10),
                text_color=TEXT_MUTED, fg_color="transparent").pack(pady=(0, SPACE_SM))

    name_row = ctk.CTkFrame(dlg, fg_color="transparent")
    name_row.pack(fill="x", padx=SPACE_MD, pady=(0, SPACE_SM))
    ctk.CTkLabel(name_row, text="Theme name", font=F(10), text_color=TEXT_MUTED,
                fg_color="transparent").pack(anchor="w")
    name_entry = ctk.CTkEntry(name_row, font=F(12), fg_color=INPUT_BG, text_color=TEXT_PRIMARY,
                              border_width=0, corner_radius=8)
    name_entry.insert(0, "My Custom Theme")
    name_entry.pack(fill="x", pady=(2, 0))

    picks = dict(THEME)  # تبدأ بكل قيم الثيم الحالي — كل لون قابل للتعديل
    swatches = {}

    scroll = ctk.CTkScrollableFrame(dlg, fg_color="transparent",
                                    scrollbar_button_color=BORDER,
                                    scrollbar_button_hover_color=ACCENT)
    scroll.pack(fill="both", expand=True, padx=SPACE_MD, pady=(0, SPACE_SM))

    def pick(key, lbl):
        def apply(hexcolor, k=key):
            picks[k] = hexcolor
            swatches[k].configure(fg_color=hexcolor)
        open_circle_color_picker(dlg, picks[key], lbl, apply)

    for key, lbl in ADVANCED_COLOR_LABELS.items():
        row = ctk.CTkFrame(scroll, fg_color="transparent")
        row.pack(fill="x", pady=4)
        ctk.CTkLabel(row, text=lbl, font=F(11), text_color=TEXT_PRIMARY,
                    fg_color="transparent", anchor="w", wraplength=220).pack(side="left", fill="x", expand=True)
        sw = ctk.CTkButton(row, text="", command=lambda k=key, l=lbl: pick(k, l),
                           fg_color=picks[key], hover_color=picks[key],
                           width=32, height=32, corner_radius=16,
                           border_width=1, border_color=BORDER)
        sw.pack(side="right")
        swatches[key] = sw

    def save_and_apply():
        name = name_entry.get().strip() or "My Custom Theme"
        apply_theme(name, is_custom=True, theme_dict=dict(picks))

    ctk.CTkButton(dlg, text="Save & Apply (restarts app)", command=save_and_apply,
                 font=F(12, "bold"), fg_color=ACCENT, hover_color=ACCENT_GLOW,
                 text_color="#000000", corner_radius=10, height=38
                 ).pack(fill="x", padx=SPACE_MD, pady=(0, SPACE_MD))


def build_themes_panel(parent):
    active = _current_theme_name()

    def add_row(name, th, is_custom=False):
        is_active = (name == active)
        row = ctk.CTkFrame(parent, fg_color=BORDER if is_active else BG_SECONDARY,
                           corner_radius=10, border_width=1,
                           border_color=ACCENT if is_active else BORDER)
        row.pack(fill="x", padx=SPACE_SM, pady=(SPACE_XS, 0))

        swatch_row = ctk.CTkFrame(row, fg_color="transparent")
        swatch_row.pack(side="left", padx=SPACE_SM, pady=SPACE_SM)
        for key in ("BG_PRIMARY", "ACCENT", "BUBBLE_USER_B", "TEXT_PRIMARY"):
            dot = ctk.CTkLabel(swatch_row, text="", fg_color=th.get(key, "#888"),
                               corner_radius=8, width=16, height=16)
            dot.pack(side="left", padx=1)

        label_text = name + ("  ✓" if is_active else "")
        lbl = ctk.CTkLabel(row, text=label_text, font=F(11),
                           text_color=TEXT_PRIMARY, fg_color="transparent")
        lbl.pack(side="left", padx=SPACE_XS)

        def on_click(e=None, n=name, c=is_custom):
            apply_theme(n, is_custom=c)

        for w in (row, swatch_row, lbl):
            w.bind("<Button-1>", on_click)

    for name, th in PRESET_THEMES.items():
        add_row(name, th)

    customs = _load_custom_themes_raw()
    if customs:
        ctk.CTkFrame(parent, fg_color=BORDER, height=1).pack(fill="x", padx=SPACE_SM, pady=SPACE_SM)
        ctk.CTkLabel(parent, text="Your themes", font=F(10), text_color=TEXT_MUTED,
                    fg_color="transparent").pack(anchor="w", padx=SPACE_SM)
        for name, th in customs.items():
            add_row(name, th, is_custom=True)

    ctk.CTkButton(parent, text="+ Create theme", command=open_theme_creator,
                 font=F(12, "bold"), fg_color=ACCENT, hover_color=ACCENT_GLOW,
                 text_color="#000000", corner_radius=10, height=36).pack(
        fill="x", padx=SPACE_SM, pady=(SPACE_SM, 4))

    ctk.CTkButton(parent, text="🎛  Customize every color", command=open_advanced_theme_editor,
                 font=F(12), fg_color=BG_SECONDARY, hover_color=BORDER,
                 text_color=TEXT_PRIMARY, corner_radius=10, height=36,
                 border_width=1, border_color=BORDER).pack(
        fill="x", padx=SPACE_SM, pady=(0, SPACE_SM))


# ═══════════════════════════════════════════════
#  ACCOUNT / SUBSCRIPTION DIALOG — مراجعة الاشتراك والتفعيل وتعديل المفتاح
# ═══════════════════════════════════════════════
def open_account_dialog():
    dlg = ctk.CTkToplevel(root)
    dlg.title("Account & Subscription")
    dlg.configure(fg_color=BG_SECONDARY)
    dlg.geometry("360x460")
    dlg.attributes("-topmost", True)
    dlg.resizable(False, False)

    ctk.CTkLabel(dlg, text="🔑  Account & Subscription", font=F(16, "bold"),
                text_color=TEXT_PRIMARY, fg_color="transparent").pack(pady=(SPACE_MD, 4))

    info_card = ctk.CTkFrame(dlg, fg_color=BG_CARD, corner_radius=12,
                             border_width=1, border_color=BORDER)
    info_card.pack(fill="x", padx=SPACE_MD, pady=(SPACE_SM, SPACE_SM))

    status_dot = ctk.CTkLabel(info_card, text="●  checking...", font=F(13, "bold"),
                              text_color=TEXT_MUTED, fg_color="transparent")
    status_dot.pack(anchor="w", padx=SPACE_MD, pady=(SPACE_MD, 2))

    name_val = ctk.CTkLabel(info_card, text="", font=F(11), text_color=TEXT_SECONDARY,
                            fg_color="transparent")
    name_val.pack(anchor="w", padx=SPACE_MD)

    expiry_val = ctk.CTkLabel(info_card, text="", font=F(11), text_color=TEXT_SECONDARY,
                              fg_color="transparent")
    expiry_val.pack(anchor="w", padx=SPACE_MD, pady=(0, 4))

    hwid_row = ctk.CTkFrame(info_card, fg_color="transparent")
    hwid_row.pack(fill="x", padx=SPACE_MD, pady=(0, SPACE_MD))
    hwid_short = get_raw_hwid()
    hwid_lbl = ctk.CTkLabel(hwid_row, text=f"Device ID: {hwid_short[:18]}...",
                            font=("Consolas", 9), text_color=TEXT_MUTED, fg_color="transparent")
    hwid_lbl.pack(side="left")

    def copy_hwid():
        dlg.clipboard_clear()
        dlg.clipboard_append(hwid_short)
        copy_btn.configure(text="✓ Copied")
        dlg.after(1500, lambda: copy_btn.configure(text="Copy"))

    copy_btn = ctk.CTkButton(hwid_row, text="Copy", command=copy_hwid,
                             font=F(9), fg_color=BG_SECONDARY, hover_color=BORDER,
                             text_color=TEXT_PRIMARY, corner_radius=6, width=50, height=22)
    copy_btn.pack(side="right")

    def refresh_info():
        status_dot.configure(text="●  checking...", text_color=TEXT_MUTED)
        name_val.configure(text="")
        expiry_val.configure(text="")

        def run():
            info = keyssystem.get_account_info(hwid_short)

            def apply_ui():
                if not info.get("found"):
                    status_dot.configure(text="●  No subscription found", text_color="#EF4444")
                    name_val.configure(text="No key is linked to this device yet.")
                    expiry_val.configure(text="")
                    return

                status = info.get("status", "Unknown")
                colors = {"Activated": "#34D399", "Expired": "#FCA5A5", "Unused": "#FCD34D"}
                status_dot.configure(text=f"●  {status}", text_color=colors.get(status, TEXT_MUTED))
                name_val.configure(text=f"Name: {info.get('name') or '—'}")

                if status == "Activated":
                    days = info.get("days_left")
                    expires = info.get("expires_at", "")[:10]
                    days_txt = f"{days} day(s) left" if days is not None else ""
                    expiry_val.configure(text=f"Expires: {expires}   ({days_txt})")
                elif status == "Expired":
                    expiry_val.configure(text="Your subscription has ended. Enter a new key below.")
                else:
                    expiry_val.configure(text="Activation pending.")

            root.after(0, apply_ui)

        threading.Thread(target=run, daemon=True).start()

    ctk.CTkLabel(dlg, text="Enter a new / renewal activation key", font=F(11),
                text_color=TEXT_MUTED, fg_color="transparent").pack(
        anchor="w", padx=SPACE_MD, pady=(SPACE_SM, 2))

    key_entry = ctk.CTkEntry(dlg, font=F(12), fg_color=INPUT_BG, text_color=TEXT_PRIMARY,
                             border_width=0, corner_radius=8, placeholder_text="XXXX-XXXX-XXXX")
    key_entry.pack(fill="x", padx=SPACE_MD)

    key_msg = ctk.CTkLabel(dlg, text="", font=F(10), text_color="#EF4444", fg_color="transparent")
    key_msg.pack(pady=(4, 0))

    def apply_new_key():
        code = key_entry.get().strip()
        if not code:
            key_msg.configure(text="Please enter a key.", text_color="#EF4444")
            return
        key_msg.configure(text="Verifying...", text_color=TEXT_MUTED)
        apply_btn.configure(state="disabled")

        def run():
            ok = keyssystem.verify_and_use_key(code)

            def apply_ui():
                apply_btn.configure(state="normal")
                if ok:
                    key_msg.configure(text="✓ Key applied successfully!", text_color="#34D399")
                    key_entry.delete(0, "end")
                    refresh_info()
                else:
                    key_msg.configure(text="❌ Invalid key, already used, or an error occurred.",
                                       text_color="#EF4444")

            root.after(0, apply_ui)

        threading.Thread(target=run, daemon=True).start()

    apply_btn = ctk.CTkButton(dlg, text="Apply key", command=apply_new_key,
                              font=F(12, "bold"), fg_color=ACCENT, hover_color=ACCENT_GLOW,
                              text_color="#000000", corner_radius=10, height=36)
    apply_btn.pack(fill="x", padx=SPACE_MD, pady=(SPACE_SM, SPACE_SM))

    ctk.CTkButton(dlg, text="↻  Refresh status", command=refresh_info,
                 font=F(11), fg_color="transparent", hover_color=BORDER,
                 text_color=TEXT_MUTED, corner_radius=8, height=30,
                 border_width=1, border_color=BORDER).pack(fill="x", padx=SPACE_MD)

    refresh_info()

    def add_row(name, th, is_custom=False):
        is_active = (name == active)
        row = ctk.CTkFrame(parent, fg_color=BORDER if is_active else BG_SECONDARY,
                           corner_radius=10, border_width=1,
                           border_color=ACCENT if is_active else BORDER)
        row.pack(fill="x", padx=SPACE_SM, pady=(SPACE_XS, 0))

        swatch_row = ctk.CTkFrame(row, fg_color="transparent")
        swatch_row.pack(side="left", padx=SPACE_SM, pady=SPACE_SM)
        for key in ("BG_PRIMARY", "ACCENT", "BUBBLE_USER_B", "TEXT_PRIMARY"):
            dot = ctk.CTkLabel(swatch_row, text="", fg_color=th.get(key, "#888"),
                               corner_radius=8, width=16, height=16)
            dot.pack(side="left", padx=1)

        label_text = name + ("  ✓" if is_active else "")
        lbl = ctk.CTkLabel(row, text=label_text, font=F(11),
                           text_color=TEXT_PRIMARY, fg_color="transparent")
        lbl.pack(side="left", padx=SPACE_XS)

        def on_click(e=None, n=name, c=is_custom):
            apply_theme(n, is_custom=c)

        for w in (row, swatch_row, lbl):
            w.bind("<Button-1>", on_click)

    for name, th in PRESET_THEMES.items():
        add_row(name, th)

    customs = _load_custom_themes_raw()
    if customs:
        ctk.CTkFrame(parent, fg_color=BORDER, height=1).pack(fill="x", padx=SPACE_SM, pady=SPACE_SM)
        ctk.CTkLabel(parent, text="Your themes", font=F(10), text_color=TEXT_MUTED,
                    fg_color="transparent").pack(anchor="w", padx=SPACE_SM)
        for name, th in customs.items():
            add_row(name, th, is_custom=True)

    ctk.CTkButton(parent, text="+ Create theme", command=open_theme_creator,
                 font=F(12, "bold"), fg_color=ACCENT, hover_color=ACCENT_GLOW,
                 text_color="#000000", corner_radius=10, height=36).pack(
        fill="x", padx=SPACE_SM, pady=(SPACE_SM, 4))

    ctk.CTkButton(parent, text="🎛  Customize every color", command=open_advanced_theme_editor,
                 font=F(12), fg_color=BG_SECONDARY, hover_color=BORDER,
                 text_color=TEXT_PRIMARY, corner_radius=10, height=36,
                 border_width=1, border_color=BORDER).pack(
        fill="x", padx=SPACE_SM, pady=(0, SPACE_SM))



def _auto_title_conversation(first_text):
    """يسمي المحادثة تلقائياً من أول رسالة فيها (مرة واحدة فقط، مثل Claude)."""
    try:
        with db_connect() as conn:
            row = conn.execute(
                "SELECT title, (SELECT COUNT(*) FROM messages WHERE conversation_id = conversations.id) AS cnt "
                "FROM conversations WHERE id = ?", (current_conversation_id,)
            ).fetchone()
        if row and (row[0] in (None, "", "New chat")) and row[1] <= 1:
            title = first_text.strip().replace("\n", " ")[:50]
            if title:
                db_rename_conversation(current_conversation_id, title)
                if panel_visible and current_panel_tab == "chats":
                    root.after(0, lambda: show_panel_tab("chats"))
    except Exception as e:
        print("auto title error:", e)


# ═══════════════════════════════════════════════
#  CHAT HISTORY HELPERS (UI)
# ═══════════════════════════════════════════════
def clear_chat_history():
    """يمسح المحادثة من الـ UI ومن قاعدة البيانات."""
    db_clear()
    for widget in chat_scroll.winfo_children():
        widget.destroy()
    add_message_bubble("system", "Chat cleared. Starting fresh!")


# ═══════════════════════════════════════════════
#  SETTINGS PANEL (personality / memory customization)
# ═══════════════════════════════════════════════
def build_settings_panel(parent):
    custom = load_customization()

    # ── صورة الـ AI الشخصية (pfp) ──
    ctk.CTkLabel(parent, text="AI picture", font=F(11), text_color=TEXT_MUTED,
                fg_color="transparent").pack(anchor="w", padx=SPACE_SM, pady=(SPACE_SM, 2))

    avatar_row = ctk.CTkFrame(parent, fg_color="transparent")
    avatar_row.pack(fill="x", padx=SPACE_SM)

    if _avatar_ctk_image is not None:
        preview = ctk.CTkLabel(avatar_row, text="", image=_avatar_ctk_image,
                               fg_color=BG_SECONDARY, corner_radius=20, width=40, height=40)
    else:
        preview = ctk.CTkLabel(avatar_row, text="AI", font=F(11, "bold"), text_color="#000000",
                               fg_color=ACCENT, corner_radius=20, width=40, height=40)
    preview.pack(side="left", padx=(0, SPACE_SM))

    def pick_avatar():
        path = filedialog.askopenfilename(
            title="Choose AI picture",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.webp *.gif"), ("All files", "*.*")]
        )
        if path and set_ai_avatar(path):
            add_message_bubble("system", "✓ AI picture updated — new messages will show it")
            show_panel_tab("settings")

    def clear_avatar():
        remove_ai_avatar()
        add_message_bubble("system", "AI picture removed")
        show_panel_tab("settings")

    ctk.CTkButton(avatar_row, text="Change picture", command=pick_avatar,
                 font=F(11), fg_color=BG_SECONDARY, hover_color=BORDER,
                 text_color=TEXT_PRIMARY, corner_radius=8, height=32
                 ).pack(side="left", padx=(0, SPACE_XS))
    ctk.CTkButton(avatar_row, text="Remove", command=clear_avatar,
                 font=F(11), fg_color="transparent", hover_color=BORDER,
                 text_color=TEXT_MUTED, corner_radius=8, height=32, width=64
                 ).pack(side="left")

    ctk.CTkLabel(parent, text="Assistant name", font=F(11), text_color=TEXT_MUTED,
                fg_color="transparent").pack(anchor="w", padx=SPACE_SM, pady=(SPACE_SM, 2))
    name_entry = ctk.CTkEntry(parent, font=F(12), fg_color=INPUT_BG, text_color=TEXT_PRIMARY,
                              border_width=0, corner_radius=8)
    name_entry.insert(0, ai_name)
    name_entry.pack(fill="x", padx=SPACE_SM)

    ctk.CTkLabel(parent, text="Personality (optional)", font=F(11), text_color=TEXT_MUTED,
                fg_color="transparent").pack(anchor="w", padx=SPACE_SM, pady=(SPACE_SM, 2))
    personality_box = ctk.CTkTextbox(parent, font=F(11), fg_color=INPUT_BG,
                                     text_color=TEXT_PRIMARY, corner_radius=8, height=70)
    personality_box.insert("1.0", custom["personality"])
    personality_box.pack(fill="x", padx=SPACE_SM)

    ctk.CTkLabel(parent, text="Memory — facts to always remember", font=F(11),
                text_color=TEXT_MUTED, fg_color="transparent").pack(anchor="w", padx=SPACE_SM, pady=(SPACE_SM, 2))
    memory_box = ctk.CTkTextbox(parent, font=F(11), fg_color=INPUT_BG,
                                text_color=TEXT_PRIMARY, corner_radius=8, height=100)
    memory_box.insert("1.0", custom["memory"])
    memory_box.pack(fill="x", padx=SPACE_SM)

    # ── Adaptive Personality Toggle ──
    adaptive_row = ctk.CTkFrame(parent, fg_color="transparent")
    adaptive_row.pack(fill="x", padx=SPACE_SM, pady=(SPACE_SM, 2))

    adaptive_var = ctk.BooleanVar(value=custom.get("adaptive_personality", True))

    ctk.CTkLabel(adaptive_row, text="🧠  Adaptive Personality", font=F(11, "bold"),
                text_color=TEXT_PRIMARY, fg_color="transparent").pack(side="left")

    adaptive_switch = ctk.CTkSwitch(
        adaptive_row, text="", variable=adaptive_var,
        onvalue=True, offvalue=False,
        fg_color=BORDER, progress_color=ACCENT,
        button_color=TEXT_PRIMARY, button_hover_color=ACCENT_LIGHT,
        width=40, height=20
    )
    adaptive_switch.pack(side="right")

    ctk.CTkLabel(parent,
                text="When ON, the AI learns your preferred style from the conversation and updates personality automatically.",
                font=F(9), text_color=TEXT_MUTED, fg_color="transparent", wraplength=220,
                justify="left").pack(anchor="w", padx=SPACE_SM, pady=(0, SPACE_SM))

    # ── Adaptive Memory Toggle ──
    memory_adaptive_row = ctk.CTkFrame(parent, fg_color="transparent")
    memory_adaptive_row.pack(fill="x", padx=SPACE_SM, pady=(SPACE_XS, 2))

    adaptive_memory_var = ctk.BooleanVar(value=custom.get("adaptive_memory", True))

    ctk.CTkLabel(memory_adaptive_row, text="💾  Adaptive Memory", font=F(11, "bold"),
                text_color=TEXT_PRIMARY, fg_color="transparent").pack(side="left")

    ctk.CTkSwitch(
        memory_adaptive_row, text="", variable=adaptive_memory_var,
        onvalue=True, offvalue=False,
        fg_color=BORDER, progress_color=ACCENT,
        button_color=TEXT_PRIMARY, button_hover_color=ACCENT_LIGHT,
        width=40, height=20
    ).pack(side="right")

    ctk.CTkLabel(parent,
                text="When ON, the AI automatically saves important facts from the conversation (name, preferences, etc.) into Memory.",
                font=F(9), text_color=TEXT_MUTED, fg_color="transparent", wraplength=220,
                justify="left").pack(anchor="w", padx=SPACE_SM, pady=(0, SPACE_SM))

    def save_settings():
        global ai_name, system_instruction
        new_name = name_entry.get().strip() or ai_name
        ai_name = new_name
        with open("ainame", "w", encoding="utf-8") as f:
            f.write(ai_name)
        save_customization(personality_box.get("1.0", "end").strip(),
                           memory_box.get("1.0", "end").strip(),
                           adaptive_personality=adaptive_var.get(),
                           adaptive_memory=adaptive_memory_var.get())
        system_instruction = build_system_instruction()
        root.title(ai_name)
        title_label.configure(text=ai_name)
        add_message_bubble("system", "✓ Settings saved")

    ctk.CTkButton(parent, text="Save settings", command=save_settings,
                 font=F(12, "bold"), fg_color=ACCENT, hover_color=ACCENT_GLOW,
                 text_color="#000000", corner_radius=10, height=36).pack(
        fill="x", padx=SPACE_SM, pady=SPACE_MD)

    # ── فاصل ──
    ctk.CTkFrame(parent, fg_color=BORDER, height=1, corner_radius=0).pack(
        fill="x", padx=SPACE_SM, pady=(0, SPACE_SM))

    ctk.CTkLabel(parent, text="🗑  Danger zone", font=F(11, "bold"),
                text_color="#FCA5A5", fg_color="transparent").pack(
        anchor="w", padx=SPACE_SM, pady=(0, 4))

    ctk.CTkLabel(parent, text="Clears all saved messages permanently.",
                font=F(9), text_color=TEXT_MUTED, fg_color="transparent").pack(
        anchor="w", padx=SPACE_SM, pady=(0, SPACE_XS))

    ctk.CTkButton(parent, text="🗑  Clear chat history", command=clear_chat_history,
                 font=F(11), fg_color="#2D1515", hover_color="#3D2020",
                 text_color="#FCA5A5", corner_radius=10, height=34).pack(
        fill="x", padx=SPACE_SM, pady=(0, SPACE_MD))

# ═══════════════════════════════════════════════
#  END OF PART 4
#  Simple mode + AI logic (process_message) in Part 5
# ═══════════════════════════════════════════════
# ═══════════════════════════════════════════════
#  PART 5 — SIMPLE MODE + AI LOGIC (final part)
#  (append after Part 4)
# ═══════════════════════════════════════════════

def make_draggable(handle, window):
    def start(e):
        handle._dx = e.x
        handle._dy = e.y
    def move(e):
        window.geometry(f"+{window.winfo_x()+e.x-handle._dx}+{window.winfo_y()+e.y-handle._dy}")
    handle.bind("<Button-1>", start)
    handle.bind("<B1-Motion>", move)


def enter_simple_mode():
    global simple_win, simple_entry
    root.withdraw()
    simple_win = ctk.CTkToplevel()
    simple_win.overrideredirect(True)
    simple_win.attributes("-topmost", True)

    # ── taskbar entry: نخلي simple_win تظهر في الـ taskbar ──
    import sys as _sys
    if _sys.platform == "win32":
        # Windows: نضيف النافذة للـ taskbar عبر ctypes
        import ctypes as _ct
        _GWL_EXSTYLE  = -20
        _WS_EX_APPWINDOW = 0x00040000
        _WS_EX_TOOLWINDOW = 0x00000080
        simple_win.update_idletasks()
        hwnd = _ct.windll.user32.GetParent(simple_win.winfo_id())
        style = _ct.windll.user32.GetWindowLongW(hwnd, _GWL_EXSTYLE)
        style = (style & ~_WS_EX_TOOLWINDOW) | _WS_EX_APPWINDOW
        _ct.windll.user32.SetWindowLongW(hwnd, _GWL_EXSTYLE, style)
        simple_win.withdraw()
        simple_win.deiconify()
    else:
        # Linux: نستخدم wm_attributes type=normal لإظهارها في الـ taskbar
        try:
            simple_win.wm_attributes("-type", "normal")
        except Exception:
            pass
    simple_win.configure(fg_color=ACCENT)
    sw, sh = simple_win.winfo_screenwidth(), simple_win.winfo_screenheight()
    simple_win.geometry(f"380x60+{sw-410}+{sh-90}")

    cont = ctk.CTkFrame(simple_win, fg_color=BG_SECONDARY, corner_radius=14)
    cont.pack(fill="both", expand=True, padx=1, pady=1)

    handle = ctk.CTkFrame(cont, fg_color=BG_SECONDARY, width=24, corner_radius=0)
    handle.pack(side="left", fill="y")
    grip_lbl = ctk.CTkLabel(handle, text="⠿", font=F(12), text_color=TEXT_MUTED, fg_color="transparent")
    grip_lbl.pack(expand=True)
    make_draggable(handle, simple_win)
    make_draggable(grip_lbl, simple_win)

    back_btn = ctk.CTkButton(cont, text="⤢", command=exit_simple_mode,
                             font=F(12), fg_color=BG_CARD, hover_color=BORDER,
                             text_color=TEXT_SECONDARY, width=32, height=36, corner_radius=10)
    back_btn.pack(side="left", padx=(2, 4), pady=8)

    # ← زر الإرسال يُبنى أولاً حتى pack يحجز مساحته قبل الـ entry
    send_icon = ctk.CTkButton(cont, text="➤", command=on_send_simple,
                              font=F(13, "bold"), fg_color=ACCENT, hover_color=ACCENT_GLOW,
                              text_color="#000000", width=40, height=36, corner_radius=10)
    send_icon.pack(side="right", padx=(0, 6), pady=8)

    global _simple_real_text
    _simple_real_text = ""   # تصفير عند كل دخول لـ simple mode

    simple_entry = ctk.CTkEntry(cont, font=F(12), fg_color=INPUT_BG, text_color=TEXT_PRIMARY,
                                border_width=0, corner_radius=10, height=36,
                                placeholder_text="Type a message...")
    simple_entry.pack(side="left", fill="both", expand=True, padx=(0, 4), pady=8)
    simple_entry.bind("<Return>", on_send_simple)
    simple_entry.bind("<Key>", _simple_on_char)
    simple_entry.bind("<BackSpace>", _simple_on_backspace)
    simple_entry.bind("<<Paste>>", _simple_on_paste)

    # ─── تركيز الكيبورد ───
    def _do_focus():
        if not simple_win or not simple_win.winfo_exists():
            return
        simple_win.lift()
        simple_win.focus_force()
        simple_entry.focus_force()
        try:
            simple_entry._entry.focus_force()   # الـ tk.Entry الداخلي في CTkEntry
        except Exception:
            pass

    def force_entry_focus(e=None):
        if simple_entry and simple_win.winfo_exists():
            _do_focus()

    for widget in (simple_win, cont, handle, grip_lbl, back_btn):
        widget.bind("<Button-1>", force_entry_focus)

    simple_win.update_idletasks()
    simple_win.after(200, _do_focus)

    simple_win.update_idletasks()
    simple_win.after(150, claim_focus_once)


def exit_simple_mode():
    global simple_mode, simple_win, simple_entry, _simple_real_text
    simple_mode = False
    _simple_real_text = ""
    if simple_win:
        simple_win.destroy()
        simple_win = None
    simple_entry = None
    root.deiconify()


def _simple_render():
    """يعيد رسم simple_entry من _simple_real_text مع bidi صحيح."""
    if not simple_entry:
        return
    rtl = is_rtl_text(_simple_real_text)
    display = _reshape_for_display(_simple_real_text) if rtl else _simple_real_text
    simple_entry.delete(0, "end")
    simple_entry.insert(0, display)
    try:
        simple_entry.configure(justify="right" if rtl else "left")
    except Exception:
        pass

def _simple_on_char(event=None):
    global _simple_real_text
    char = event.char
    if not char or not char.isprintable():
        return
    _simple_real_text += char
    _simple_render()
    return "break"

def _simple_on_backspace(event=None):
    global _simple_real_text
    if _simple_real_text:
        _simple_real_text = _simple_real_text[:-1]
    if _simple_real_text:
        _simple_render()
    else:
        simple_entry.delete(0, "end")
    return "break"

def _simple_on_paste(event=None):
    global _simple_real_text
    try:
        pasted = simple_entry.clipboard_get()
    except Exception:
        return "break"
    _simple_real_text += pasted
    _simple_render()
    return "break"

def on_send_simple(event=None):
    global _simple_real_text
    if not simple_entry:
        return
    txt = _simple_real_text.strip()
    if not txt:
        return
    _simple_real_text = ""
    simple_entry.delete(0, "end")
    root.after(0, lambda: add_message_bubble("user", txt))
    threading.Thread(target=process_message, args=(txt,), daemon=True).start()


def show_flying_message(text, kind="ai"):
    if not simple_win or not simple_win.winfo_exists():
        return
    colors = {
        "ai":      (BUBBLE_AI, BUBBLE_AI_B, TEXT_PRIMARY),
        "success": ("#0D2D1A", "#14532D", "#86EFAC"),
        "error":   ("#2D1515", "#7F1D1D", "#FCA5A5"),
        "system":  (BG_CARD, BORDER, TEXT_MUTED),
    }
    bg, border, fg = colors.get(kind, colors["ai"])

    popup = ctk.CTkToplevel(simple_win)
    popup.overrideredirect(True)
    popup.attributes("-topmost", True)
    try:
        popup.attributes("-alpha", 0.0)
    except Exception:
        pass
    popup.configure(fg_color=border)

    bubble = ctk.CTkFrame(popup, fg_color=bg, corner_radius=12)
    bubble.pack(padx=1, pady=1)

    hdr = ctk.CTkFrame(bubble, fg_color="transparent")
    hdr.pack(fill="x", padx=SPACE_SM, pady=(SPACE_XS, 0))
    ctk.CTkLabel(hdr, text=ai_name, font=F(10), text_color=ACCENT_LIGHT,
                fg_color="transparent").pack(side="left")
    ctk.CTkLabel(hdr, text="✕", font=F(10), text_color=TEXT_MUTED,
                fg_color="transparent").pack(side="right")

    content = render_rich_text(bubble, text, fg, bg)
    content.pack(padx=SPACE_MD, pady=SPACE_SM)

    popup.update_idletasks()
    pw, ph = popup.winfo_reqwidth(), popup.winfo_reqheight()
    sx, sy, sw2 = simple_win.winfo_x(), simple_win.winfo_y(), simple_win.winfo_width()
    popup.geometry(f"+{sx+sw2-pw}+{sy-ph-14}")

    def close(e=None):
        if popup.winfo_exists():
            popup.destroy()

    for w in (popup, bubble, hdr, *hdr.winfo_children()):
        w.bind("<Button-1>", close)

    def fade(step=0.0, growing=True):
        if not popup.winfo_exists():
            return
        try:
            if growing:
                step += 0.12
                popup.attributes("-alpha", min(step, 1.0))
                if step < 1.0:
                    popup.after(15, lambda: fade(step, True))
                else:
                    popup.after(5000, lambda: fade(1.0, False))
            else:
                step -= 0.08
                if step > 0:
                    popup.attributes("-alpha", step)
                    popup.after(30, lambda: fade(step, False))
                else:
                    close()
        except Exception:
            pass

    fade()


# ═══════════════════════════════════════════════
#  APPEND MESSAGE (terminal + UI)
# ═══════════════════════════════════════════════
def append_message(role, text):
    icons = {"user": "You", "ai": ai_name, "system": "System", "error": "Error", "success": "Done"}
    print(f"[{icons.get(role, role)}]: {text}")

    # ← الرسالة تُسجَّل دايماً بالمحادثة الرئيسية (حتى لو نحن بـ simple mode)
    #   هذا يضمن إنها تظهر لما نرجع للوضع العادي
    root.after(0, lambda: add_message_bubble(role, text))

    # ← بالإضافة لذلك، لو نحن بـ simple mode نعرضها كفقاعة طائرة فوق النافذة الصغيرة
    if simple_mode and role in ("ai", "success", "error", "system"):
        root.after(0, lambda: show_flying_message(text, role))


# ═══════════════════════════════════════════════
#  MAIN AI LOGIC
# ═══════════════════════════════════════════════
def process_message(user_input):
    global system_instruction, ai_name

    # ── حماية من الإرسال المتزامن ──
    if not _send_lock.acquire(blocking=False):
        append_message("system", "Please wait for the previous response...")
        return

    try:
        # ── أوامر خاصة ──
        egg_reply = check_easter_egg(user_input)
        if egg_reply:
            append_message("system", egg_reply)
            return

        if user_input.strip().lower().startswith("change name"):
            parts = user_input.strip().split(" ", 2)
            if len(parts) >= 3:
                ai_name = parts[2].strip()
                with open("ainame", "w", encoding="utf-8") as f:
                    f.write(ai_name)
                system_instruction = build_system_instruction()
                root.title(ai_name)
                root.after(0, lambda: title_label.configure(text=ai_name))
                append_message("system", f"Name changed to {ai_name}")
            else:
                append_message("system", "Usage: change name <new name>")
            return

        # ── حفظ رسالة المستخدم في SQLite ──
        db_save_message("user", user_input)
        _auto_title_conversation(user_input)

        # ── بناء الـ context من آخر 20 رسالة ──
        history_rows = db_get_context()
        full_context = "\n".join(
            f"{'User' if r == 'user' else 'Assistant'}: {c}"
            for r, c in history_rows
        )

        # ── RAG: بحث في المراجع المرفوعة إن وجدت ──
        ref_context, ref_sources = None, []
        if ragtools.has_references():
            try:
                ref_context, ref_sources = ragtools.search_reference(client, user_input)
            except Exception as e:
                print("reference search error:", e)

        contents_prefix = ""
        if ref_context:
            contents_prefix = (
                "The user has uploaded reference material. If it answers the question, "
                "base your answer on it and mention the source file and page number. "
                "If not relevant, answer from your own knowledge.\n\n"
                f"=== REFERENCE MATERIAL ===\n{ref_context}\n=== END ===\n\n"
            )

        # ── تعليمات تنسيق المعادلات الرياضية ──
        math_instruction = (
            "\n\nIMPORTANT — Math formatting rules (always follow these):\n"
            "- Wrap ALL math expressions in LaTeX delimiters. No exceptions.\n"
            "- Inline math (inside text): $x^2$, $\\frac{1}{2}$, $\\sqrt{x}$\n"
            "- Display math (on its own line): $$\\int_0^\\infty e^{-x} dx = 1$$\n"
            "- NEVER write math as plain text like x^2, (x^3)/3+C, or sqrt(x).\n"
            "- ALWAYS use LaTeX: $x^3/3 + C$ not (x^3)/3+C\n"
            "- Examples: integral result → $\\frac{x^3}{3} + C$, "
            "quadratic formula → $x = \\frac{-b \\pm \\sqrt{b^2-4ac}}{2a}$"
        )

        root.after(0, lambda: status_label.configure(text="● thinking...", text_color=TEXT_MUTED))

        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=f"{contents_prefix}Here is our recent conversation history:\n{full_context}\nAssistant:",
            config=types.GenerateContentConfig(
                system_instruction=system_instruction + math_instruction,
                response_mime_type="application/json"
            )
        )

        try:
            data = json.loads(response.text)
        except json.JSONDecodeError as e:
            append_message("error", f"Failed to parse response: {e}")
            return

        intent = data.get("intent")
        ai_reply = None  # نحفظ رد الـ AI لنخزّنه في قاعدة البيانات

        # ── الشخصية التكيفية: تحديث customization.json لو وجد personality_update ──
        personality_update = data.get("personality_update")
        memory_update = data.get("memory_update")
        if (personality_update and isinstance(personality_update, str) and personality_update.strip()) or            (memory_update and isinstance(memory_update, str) and memory_update.strip()):
            try:
                cur_custom = load_customization()
                new_personality = personality_update.strip() if (personality_update and isinstance(personality_update, str) and personality_update.strip()) else cur_custom["personality"]
                new_memory = memory_update.strip() if (memory_update and isinstance(memory_update, str) and memory_update.strip()) else cur_custom["memory"]
                save_customization(
                    new_personality,
                    new_memory,
                    adaptive_personality=cur_custom["adaptive_personality"],
                    adaptive_memory=cur_custom["adaptive_memory"]
                )
                system_instruction = build_system_instruction()
            except Exception as _pe:
                print("adaptive update error:", _pe)

        if intent in ("chat", "question"):
            ai_reply = fix_latex(data.get("answer", "..."))
            append_message("ai", ai_reply)
            if ref_sources:
                append_message("system", "📚 Possibly relevant: " + " | ".join(ref_sources))

        else:
            target = data.get("target")
            action = data.get("action")
            query  = data.get("query")

            if action in ("reading file", "uploading file"):
                append_message("system", "Opening file...")

                def get_prompt():
                    import tkinter.simpledialog as sd
                    return sd.askstring("File Request", "What do you want to do with this file?",
                                        parent=root) or "explain and summarize this file"

                result = controltools.file_uploading(target, prompt_callback=get_prompt)
                if result:
                    ai_reply = result
                    append_message("ai", result)
                if target and os.path.exists(target):
                    add_to_archive(target)

            elif action == "converting file":
                append_message("system", "Converting to PDF...")
                aitools.convert_word_to_pdf_cross_platform(target)
                ai_reply = "File converted successfully!"
                append_message("success", ai_reply)
                target_dir = os.path.dirname(target) if target else DOWNLOADS_DIR
                archive_latest_file(target_dir or DOWNLOADS_DIR, (".pdf",))

            elif action == "open":
                thelink = locallinks.get(target) if target in locallinks else data.get("link")
                controltools.open_browser(thelink)
                ai_reply = f"Opened: {thelink}"
                append_message("success", ai_reply)

            elif action == "making excel":
                append_message("system", "Generating Excel file, please wait...")
                er = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=f"{excel_prompt}\n\nUSER REQUEST: Create a professional Excel sheet about: '{query}'."
                )
                aitools.create_excel_report_from_json(er.text)
                ai_reply = "Excel file saved to Downloads!"
                append_message("success", ai_reply)
                archive_latest_file(DOWNLOADS_DIR, (".xlsx", ".xls"))

            elif action == "making excel from file":
                append_message("system", "Reading file and generating Excel...")
                aitools.make_excel_from_file(target, query)
                ai_reply = "Excel file ready!"
                append_message("success", ai_reply)
                archive_latest_file(DOWNLOADS_DIR, (".xlsx", ".xls"))

            elif action == "making report":
                append_message("system", "Generating report, please wait...")
                rr = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=f"{report_prompt}\n\nUSER REQUEST: Create a professional and detailed academic report about: '{query}'."
                )
                safe_query = "".join(c for c in query if c.isalnum() or c in " _-").strip()
                aitools.compile_report_from_ai_json(rr.text, output_filename=f"{safe_query}.docx")
                ai_reply = f"Report saved: {safe_query}.docx"
                append_message("success", ai_reply)
                archive_latest_file(DOWNLOADS_DIR, (".docx",))

        # ── حفظ رد الـ AI في SQLite ──
        if ai_reply:
            db_save_message("assistant", ai_reply)

        root.after(0, lambda: status_label.configure(text="● online", text_color="#34D399"))

    except ClientError as e:
        if e.code == 429:
            append_message("error", "Rate limit reached. Waiting 35 seconds...")
            root.after(0, lambda: status_label.configure(text="● waiting...", text_color="#FCD34D"))
            time.sleep(35)
            root.after(0, lambda: status_label.configure(text="● online", text_color="#34D399"))
            append_message("system", "Back online!")
        else:
            append_message("error", str(e))
            root.after(0, lambda: status_label.configure(text="● online", text_color="#34D399"))

    except Exception as e:
        append_message("error", str(e))
        root.after(0, lambda: status_label.configure(text="● online", text_color="#34D399"))

    finally:
        _send_lock.release()


# ═══════════════════════════════════════════════
#  ATTACHED FILE LOGIC ("+" button flow)
# ═══════════════════════════════════════════════
def process_attached_file(file_path, prompt):
    """يرسل ملف/صورة مرفقة عبر زر + مباشرة لـ Gemini مع طلب المستخدم"""

    if not _send_lock.acquire(blocking=False):
        append_message("system", "Please wait for the previous response...")
        return

    try:
        root.after(0, lambda: status_label.configure(text="● reading file...", text_color=TEXT_MUTED))

        full_prompt = prompt or "Describe and summarize this file. If it contains Arabic text, reply in Arabic."
        uploaded_file = client.files.upload(file=file_path)

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[uploaded_file, full_prompt],
            config=types.GenerateContentConfig(system_instruction=system_instruction)
        )

        try:
            client.files.delete(name=uploaded_file.name)
        except Exception:
            pass

        ai_reply = response.text
        append_message("ai", ai_reply)

        # ── حفظ في SQLite ──
        db_save_message("user", f"{prompt} [attached: {os.path.basename(file_path)}]")
        db_save_message("assistant", ai_reply)

        root.after(0, lambda: status_label.configure(text="● online", text_color="#34D399"))

    except ClientError as e:
        if e.code == 429:
            append_message("error", "Rate limit reached. Waiting 35 seconds...")
            root.after(0, lambda: status_label.configure(text="● waiting...", text_color="#FCD34D"))
            time.sleep(35)
            root.after(0, lambda: status_label.configure(text="● online", text_color="#34D399"))
            append_message("system", "Back online!")
        else:
            append_message("error", str(e))
            root.after(0, lambda: status_label.configure(text="● online", text_color="#34D399"))

    except Exception as e:
        append_message("error", str(e))
        root.after(0, lambda: status_label.configure(text="● online", text_color="#34D399"))

    finally:
        _send_lock.release()


# ═══════════════════════════════════════════════
#  STARTUP — تحميل المحادثة من SQLite
# ═══════════════════════════════════════════════
def load_history_to_ui():
    """يحمّل كل المحادثة المحفوظة ويعرضها في الـ UI عند بدء التشغيل."""
    rows = db_load_all()
    if not rows:
        add_message_bubble("system", f"Welcome! I am {ai_name}. How can I help you today? ")
        add_message_bubble("system", "Type 'change name <name>' to rename me.")
    else:
        add_message_bubble("system", f"── Previous conversation loaded ({len(rows)} messages) ──")
        for role, content in rows:
            add_message_bubble(role if role != "assistant" else "ai", content)
        add_message_bubble("system", "── End of history ──")

load_history_to_ui()
entry_box.focus()
root.mainloop()