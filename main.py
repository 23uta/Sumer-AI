# --------------------------------------------------------
# Project: [Sumer-AI]
# Author: [Mohammed Ahmed Abd-Ali]
# License: GNU General Public License v3.0 (GPLv3)
# Copyright (C) 2026
# --------------------------------------------------------

import tkinter as tk
from tkinter import font
import threading

# ═══════════════════════════════════════════════
#  KEYS / SUBSCRIPTION LOGIC
#  (موحّد مع keyssystem.py بدل تكرار منطق منفصل ومتعارض)
# ═══════════════════════════════════════════════
import keyssystem
from keyssystem import get_raw_hwid, supabase

# ═══════════════════════════════════════════════
#  COLORS — Same Theme
# ═══════════════════════════════════════════════
BG_PRIMARY   = "#0A0A0A"
BG_SECONDARY = "#111111"
BG_CARD      = "#1A1A1A"

ACCENT_BLUE  = "#D4AF37"
ACCENT_GOLD  = "#F5D060"
ACCENT_GLOW  = "#B8960C"

TEXT_PRIMARY   = "#F5F5F5"
TEXT_SECONDARY = "#A89060"
TEXT_MUTED     = "#3D3D3D"

BORDER_COLOR = "#2A2A2A"
INPUT_BG     = "#080808"

FONT_MAIN  = ("Segoe UI", 11)
FONT_BOLD  = ("Segoe UI", 11, "bold")
FONT_SMALL = ("Segoe UI", 9)
FONT_TITLE = ("Segoe UI", 20, "bold")
FONT_MONO  = ("Consolas", 10)

SPACE_XS = 6
SPACE_SM = 12
SPACE_MD = 20

# (get_raw_hwid مستوردة من keyssystem.py في الأعلى)

# ═══════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════
def rounded_rect(canvas, x1, y1, x2, y2, r, **kwargs):
    points = [
        x1+r, y1, x2-r, y1, x2, y1, x2, y1+r,
        x2, y2-r, x2, y2, x2-r, y2, x1+r, y2,
        x1, y2, x1, y2-r, x1, y1+r, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


def make_rounded_button(parent, text, command, bg=ACCENT_BLUE, fg="#000000",
                         font_cfg=FONT_BOLD, padx=SPACE_MD, pady=10, w=None):
    f = font.Font(family=font_cfg[0], size=font_cfg[1],
                  weight=font_cfg[2] if len(font_cfg) > 2 else "normal")
    text_w = f.measure(text) + padx * 2
    btn_w  = w if w else text_w
    btn_h  = f.metrics("linespace") + pady * 2

    cnv = tk.Canvas(parent, width=btn_w, height=btn_h,
                    bg=parent["bg"], highlightthickness=0, cursor="hand2")

    rect_id = rounded_rect(cnv, 2, 2, btn_w-2, btn_h-2, 10, fill=bg, outline="")
    text_id = cnv.create_text(btn_w//2, btn_h//2, text=text,
                               fill=fg, font=font_cfg, anchor="center")

    def on_enter(e): cnv.itemconfig(rect_id, fill=ACCENT_GLOW)
    def on_leave(e): cnv.itemconfig(rect_id, fill=bg)
    def on_click(e): command()

    for widget in [cnv, text_id]:
        if isinstance(widget, int):
            cnv.tag_bind(widget, "<Button-1>", on_click)
            cnv.tag_bind(widget, "<Enter>",    on_enter)
            cnv.tag_bind(widget, "<Leave>",    on_leave)
        else:
            widget.bind("<Button-1>", on_click)
            widget.bind("<Enter>",    on_enter)
            widget.bind("<Leave>",    on_leave)

    cnv.bind("<Button-1>", on_click)
    cnv.bind("<Enter>",    on_enter)
    cnv.bind("<Leave>",    on_leave)
    return cnv


def make_input(parent, placeholder="", show=None):
    frame = tk.Frame(parent, bg=INPUT_BG,
                     highlightbackground=BORDER_COLOR, highlightthickness=1)

    var = tk.StringVar()
    entry = tk.Entry(frame, textvariable=var, font=FONT_MAIN,
                     fg=TEXT_MUTED, bg=INPUT_BG,
                     insertbackground=ACCENT_BLUE,
                     relief="flat", bd=0, show=show)
    entry.pack(fill="x", ipady=10, padx=SPACE_SM, pady=2)

    # Placeholder
    entry.insert(0, placeholder)

    def on_focus_in(e):
        if entry.get() == placeholder:
            entry.delete(0, "end")
            entry.config(fg=TEXT_PRIMARY)
            if show:
                entry.config(show=show)

    def on_focus_out(e):
        if not entry.get():
            entry.insert(0, placeholder)
            entry.config(fg=TEXT_MUTED, show="")

    entry.bind("<FocusIn>",  on_focus_in)
    entry.bind("<FocusOut>", on_focus_out)

    return frame, entry, var


# ═══════════════════════════════════════════════
#  MAIN WINDOW
# ═══════════════════════════════════════════════
root = tk.Tk()
root.title("Sumer AI — Login")
root.geometry("460x600")
root.configure(bg=BG_PRIMARY)
root.resizable(False, False)

# ── أيقونة النافذة ──
try:
    import os
    from PIL import Image, ImageTk
    _icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "AN.png")
    _pil_icon = Image.open(_icon_path).resize((32, 32))
    _icon = ImageTk.PhotoImage(_pil_icon)
    root.iconphoto(True, _icon)
except Exception:
    pass

# Center window
root.update_idletasks()
x = (root.winfo_screenwidth()  - 460) // 2
y = (root.winfo_screenheight() - 600) // 2
root.geometry(f"460x600+{x}+{y}")

hwid = get_raw_hwid()

# ═══════════════════════════════════════════════
#  PAGES CONTAINER
# ═══════════════════════════════════════════════
container = tk.Frame(root, bg=BG_PRIMARY)
container.pack(fill="both", expand=True)

pages = {}

def show_page(name):
    for p in pages.values():
        p.pack_forget()
    pages[name].pack(fill="both", expand=True)

# ═══════════════════════════════════════════════
#  STATUS BAR (shared)
# ═══════════════════════════════════════════════
status_bar = tk.Frame(root, bg=BG_SECONDARY, height=32)
status_bar.pack(fill="x", side="bottom")
status_bar.pack_propagate(False)

status_msg = tk.Label(status_bar, text="", font=FONT_SMALL,
                       fg=TEXT_MUTED, bg=BG_SECONDARY)
status_msg.pack(side="left", padx=SPACE_SM, pady=6)

hwid_label = tk.Label(status_bar, text=f"ID: {hwid[:20]}...",
                       font=("Consolas", 8), fg=TEXT_MUTED, bg=BG_SECONDARY)
hwid_label.bind("<Button-1>", lambda e: [
    root.clipboard_clear(),
    root.clipboard_append(hwid),
    set_status("✓ ID copied to clipboard!", ACCENT_GOLD)
])
hwid_label.config(cursor="hand2")
hwid_label.pack(side="right", padx=SPACE_SM, pady=6)

manage_label = tk.Label(status_bar, text="🔑 Manage subscription",
                         font=FONT_SMALL, fg=TEXT_SECONDARY, bg=BG_SECONDARY, cursor="hand2")
manage_label.pack(side="right", padx=SPACE_SM, pady=6)
manage_label.bind("<Button-1>", lambda e: open_account_dialog())
manage_label.bind("<Enter>", lambda e: manage_label.config(fg=ACCENT_GOLD))
manage_label.bind("<Leave>", lambda e: manage_label.config(fg=TEXT_SECONDARY))

def set_status(msg, color=TEXT_MUTED):
    status_msg.config(text=msg, fg=color)


# ═══════════════════════════════════════════════
#  ACCOUNT DIALOG — مراجعة الاشتراك والتفعيل + تغيير المفتاح
# ═══════════════════════════════════════════════
def open_account_dialog():
    dlg = tk.Toplevel(root)
    dlg.title("Account & Subscription")
    dlg.configure(bg=BG_PRIMARY)
    dlg.geometry("380x440")
    dlg.resizable(False, False)
    dlg.transient(root)
    dlg.grab_set()

    x = root.winfo_x() + (460 - 380) // 2
    y = root.winfo_y() + (600 - 440) // 2
    dlg.geometry(f"380x440+{x}+{y}")

    tk.Label(dlg, text="🔑  Account & Subscription", font=FONT_TITLE,
             fg=TEXT_PRIMARY, bg=BG_PRIMARY).pack(pady=(SPACE_MD, SPACE_SM))

    info_card = tk.Frame(dlg, bg=BG_CARD, highlightbackground=BORDER_COLOR, highlightthickness=1)
    info_card.pack(fill="x", padx=SPACE_MD)

    status_lbl = tk.Label(info_card, text="●  checking...", font=FONT_BOLD,
                           fg=TEXT_MUTED, bg=BG_CARD, anchor="w")
    status_lbl.pack(fill="x", padx=SPACE_SM, pady=(SPACE_SM, 2))

    name_lbl = tk.Label(info_card, text="", font=FONT_SMALL, fg=TEXT_SECONDARY,
                         bg=BG_CARD, anchor="w")
    name_lbl.pack(fill="x", padx=SPACE_SM)

    expiry_lbl = tk.Label(info_card, text="", font=FONT_SMALL, fg=TEXT_SECONDARY,
                           bg=BG_CARD, anchor="w", justify="left", wraplength=320)
    expiry_lbl.pack(fill="x", padx=SPACE_SM, pady=(0, SPACE_SM))

    def refresh_info():
        status_lbl.config(text="●  checking...", fg=TEXT_MUTED)
        name_lbl.config(text="")
        expiry_lbl.config(text="")

        def run():
            info = keyssystem.get_account_info(hwid)

            def apply_ui():
                if not info.get("found"):
                    status_lbl.config(text="●  No subscription found", fg="#EF4444")
                    name_lbl.config(text="No key is linked to this device yet.")
                    return

                status = info.get("status", "Unknown")
                colors = {"Activated": "#34D399", "Expired": "#FCA5A5", "Unused": "#FCD34D"}
                status_lbl.config(text=f"●  {status}", fg=colors.get(status, TEXT_MUTED))
                name_lbl.config(text=f"Name: {info.get('name') or '—'}")

                if status == "Activated":
                    days = info.get("days_left")
                    expires = (info.get("expires_at") or "")[:10]
                    days_txt = f"{days} day(s) left" if days is not None else ""
                    expiry_lbl.config(text=f"Expires: {expires}   ({days_txt})")
                elif status == "Expired":
                    expiry_lbl.config(text="Your subscription has ended. Enter a new key below to renew.")
                else:
                    expiry_lbl.config(text="Activation pending.")

            root.after(0, apply_ui)

        threading.Thread(target=run, daemon=True).start()

    tk.Label(dlg, text="Device ID", font=FONT_SMALL, fg=TEXT_MUTED, bg=BG_PRIMARY).pack(
        anchor="w", padx=SPACE_MD, pady=(SPACE_SM, 0))
    id_row = tk.Frame(dlg, bg=BG_PRIMARY)
    id_row.pack(fill="x", padx=SPACE_MD)
    tk.Label(id_row, text=hwid[:26] + "...", font=FONT_MONO, fg=TEXT_SECONDARY,
             bg=BG_PRIMARY).pack(side="left")

    def copy_id():
        dlg.clipboard_clear()
        dlg.clipboard_append(hwid)
        copy_id_btn.config(text="✓ Copied")
        dlg.after(1500, lambda: copy_id_btn.config(text="Copy"))

    copy_id_btn = tk.Label(id_row, text="Copy", font=FONT_SMALL, fg=ACCENT_BLUE,
                            bg=BG_PRIMARY, cursor="hand2")
    copy_id_btn.pack(side="right")
    copy_id_btn.bind("<Button-1>", lambda e: copy_id())

    tk.Label(dlg, text="New / renewal activation key", font=FONT_SMALL,
             fg=TEXT_MUTED, bg=BG_PRIMARY).pack(anchor="w", padx=SPACE_MD, pady=(SPACE_MD, 2))

    new_key_frame, new_key_entry, new_key_var = make_input(dlg, placeholder="Enter your key here")
    new_key_frame.pack(fill="x", padx=SPACE_MD)

    dlg_msg = tk.Label(dlg, text="", font=FONT_SMALL, fg="#EF4444", bg=BG_PRIMARY)
    dlg_msg.pack(pady=(SPACE_XS, 0))

    def apply_new_key():
        code = new_key_var.get().strip()
        if not code or code == "Enter your key here":
            dlg_msg.config(text="Please enter a key.", fg="#EF4444")
            return
        dlg_msg.config(text="Verifying...", fg=TEXT_MUTED)

        def run():
            ok = keyssystem.verify_and_use_key(code)

            def apply_ui():
                if ok:
                    dlg_msg.config(text="✓ Key applied successfully!", fg="#34D399")
                    refresh_info()
                else:
                    dlg_msg.config(text="❌ Invalid key, already used, or an error occurred.",
                                    fg="#EF4444")

            root.after(0, apply_ui)

        threading.Thread(target=run, daemon=True).start()

    apply_btn = make_rounded_button(dlg, "Apply key  ➤", apply_new_key,
                                     bg=ACCENT_BLUE, fg="#000000",
                                     font_cfg=FONT_BOLD, padx=SPACE_MD, pady=10, w=336)
    apply_btn.pack(padx=SPACE_MD, pady=SPACE_SM)

    refresh_info()

# ═══════════════════════════════════════════════
#  PAGE 1 — CHECKING (splash)
# ═══════════════════════════════════════════════
page_check = tk.Frame(container, bg=BG_PRIMARY)
pages["check"] = page_check

tk.Label(page_check, text="", bg=BG_PRIMARY).pack(expand=True)

logo_cnv = tk.Canvas(page_check, width=80, height=80,
                      bg=BG_PRIMARY, highlightthickness=0)
logo_cnv.pack()
logo_cnv.create_oval(5, 5, 75, 75, fill=BG_CARD, outline=ACCENT_BLUE, width=2)
logo_cnv.create_text(40, 40, text="AI", fill=ACCENT_BLUE,
                      font=("Segoe UI", 24, "bold"))

tk.Label(page_check, text="AI Assistant",
          font=FONT_TITLE, fg=TEXT_PRIMARY, bg=BG_PRIMARY).pack(pady=(SPACE_MD, 4))
tk.Label(page_check, text="Checking license...",
          font=FONT_SMALL, fg=TEXT_MUTED, bg=BG_PRIMARY).pack()

check_spinner = tk.Label(page_check, text="◐",
                          font=("Segoe UI", 20), fg=ACCENT_BLUE, bg=BG_PRIMARY)
check_spinner.pack(pady=SPACE_MD)

tk.Label(page_check, text="", bg=BG_PRIMARY).pack(expand=True)

spinner_chars = ["◐", "◓", "◑", "◒"]
spinner_idx   = [0]

def spin():
    spinner_idx[0] = (spinner_idx[0] + 1) % 4
    check_spinner.config(text=spinner_chars[spinner_idx[0]])
    root.after(150, spin)

spin()

# ═══════════════════════════════════════════════
#  PAGE 2 — ACTIVATE
# ═══════════════════════════════════════════════
page_activate = tk.Frame(container, bg=BG_PRIMARY)
pages["activate"] = page_activate

tk.Label(page_activate, text="", bg=BG_PRIMARY).pack(expand=True)

# Logo
logo2 = tk.Canvas(page_activate, width=64, height=64,
                   bg=BG_PRIMARY, highlightthickness=0)
logo2.pack()
logo2.create_oval(4, 4, 60, 60, fill=BG_CARD, outline=ACCENT_BLUE, width=2)
logo2.create_text(32, 32, text="AI", fill=ACCENT_BLUE, font=("Segoe UI", 18, "bold"))

tk.Label(page_activate, text="Activation Required",
          font=FONT_TITLE, fg=TEXT_PRIMARY, bg=BG_PRIMARY).pack(pady=(SPACE_MD, 4))
tk.Label(page_activate, text="Enter your activation key to continue",
          font=FONT_SMALL, fg=TEXT_MUTED, bg=BG_PRIMARY).pack(pady=(0, SPACE_MD))

# Card
card = tk.Frame(page_activate, bg=BG_CARD,
                 highlightbackground=BORDER_COLOR, highlightthickness=1)
card.pack(padx=SPACE_MD*2, fill="x")

tk.Label(card, text="Activation Key", font=FONT_SMALL,
          fg=TEXT_SECONDARY, bg=BG_CARD).pack(anchor="w", padx=SPACE_MD, pady=(SPACE_MD, 4))

code_frame, code_entry, code_var = make_input(card, placeholder="Enter your key here")
code_frame.pack(fill="x", padx=SPACE_MD, pady=(0, SPACE_MD))

activate_msg = tk.Label(card, text="", font=FONT_SMALL,
                          fg="#EF4444", bg=BG_CARD)
activate_msg.pack(pady=(0, SPACE_XS))

def do_activate():
    code = code_var.get().strip()
    if not code or code == "Enter your key here":
        activate_msg.config(text="Please enter your activation key", fg="#EF4444")
        return

    activate_msg.config(text="Verifying...", fg=TEXT_MUTED)
    set_status("Verifying key...", TEXT_MUTED)
    root.update()

    def run():
        try:
            ok = keyssystem.verify_and_use_key(code)

            if not ok:
                root.after(0, lambda: activate_msg.config(
                    text="❌ Invalid key, already used elsewhere, or expired.", fg="#EF4444"))
                root.after(0, lambda: set_status("Activation failed", "#EF4444"))
                return

            info = keyssystem.get_account_info(hwid)
            name = info.get("name") if info.get("found") else "User"
            root.after(0, lambda: on_success(name or "User"))

        except Exception as e:
            root.after(0, lambda: activate_msg.config(
                text=f"❌ Error: {e}", fg="#EF4444"))

    threading.Thread(target=run, daemon=True).start()

act_btn = make_rounded_button(card, "Activate  ➤", do_activate,
                               bg=ACCENT_BLUE, fg="#000000",
                               font_cfg=FONT_BOLD, padx=SPACE_MD, pady=10, w=380)
act_btn.pack(padx=SPACE_MD, pady=SPACE_MD)

tk.Label(page_activate, text="", bg=BG_PRIMARY).pack(expand=True)

# ═══════════════════════════════════════════════
#  PAGE 3 — WELCOME
# ═══════════════════════════════════════════════
page_welcome = tk.Frame(container, bg=BG_PRIMARY)
pages["welcome"] = page_welcome

tk.Label(page_welcome, text="", bg=BG_PRIMARY).pack(expand=True)

welcome_logo = tk.Canvas(page_welcome, width=90, height=90,
                          bg=BG_PRIMARY, highlightthickness=0)
welcome_logo.pack()
welcome_logo.create_oval(5, 5, 85, 85, fill=BG_CARD, outline=ACCENT_GOLD, width=2)
welcome_logo.create_text(45, 45, text="✓", fill=ACCENT_GOLD,
                          font=("Segoe UI", 32, "bold"))

welcome_title = tk.Label(page_welcome, text="Welcome back!",
                          font=FONT_TITLE, fg=TEXT_PRIMARY, bg=BG_PRIMARY)
welcome_title.pack(pady=(SPACE_MD, 4))

welcome_sub = tk.Label(page_welcome, text="",
                        font=FONT_SMALL, fg=TEXT_SECONDARY, bg=BG_PRIMARY)
welcome_sub.pack()

tk.Label(page_welcome, text="Launching assistant...",
          font=FONT_SMALL, fg=TEXT_MUTED, bg=BG_PRIMARY).pack(pady=SPACE_SM)

progress_frame = tk.Frame(page_welcome, bg=BORDER_COLOR, height=2)
progress_frame.pack(fill="x", padx=SPACE_MD*3, pady=SPACE_SM)

progress_bar = tk.Frame(progress_frame, bg=ACCENT_GOLD, height=2, width=0)
progress_bar.place(x=0, y=0, height=2)

tk.Label(page_welcome, text="", bg=BG_PRIMARY).pack(expand=True)

launch_result = [False]

def animate_progress(step=0):
    total = 300
    progress_frame.update_idletasks()
    w = progress_frame.winfo_width()
    new_w = int((step / total) * w)
    progress_bar.place(x=0, y=0, height=2, width=new_w)
    if step < total:
        root.after(5, lambda: animate_progress(step + 3))
    else:
        launch_result[0] = True
        root.destroy()

def on_success(name="User"):
    welcome_title.config(text=f"Welcome, {name}!")
    welcome_sub.config(text="License verified successfully")
    set_status("✓ License valid", "#34D399")
    show_page("welcome")
    root.after(300, lambda: animate_progress(0))

# ═══════════════════════════════════════════════
#  LICENSE CHECK ON START
# ═══════════════════════════════════════════════
def check_license():
    try:
        info = keyssystem.get_account_info(hwid)

        if not info.get("found"):
            root.after(0, lambda: [
                show_page("activate"),
                set_status("No license found", "#EF4444")
            ])
            return

        status = info.get("status")

        if status == "Activated":
            root.after(0, lambda: on_success(info.get("name") or "User"))

        elif status == "Expired":
            root.after(0, lambda: [
                show_page("activate"),
                set_status("⚠️ Subscription ended", "#FCD34D")
            ])

        else:
            root.after(0, lambda: [
                show_page("activate"),
                set_status("Activation required", TEXT_MUTED)
            ])

    except Exception as e:
        root.after(0, lambda: [
            show_page("activate"),
            set_status(f"Connection error: {e}", "#EF4444")
        ])

# ═══════════════════════════════════════════════
#  START
# ═══════════════════════════════════════════════
show_page("check")
root.after(800, lambda: threading.Thread(target=check_license, daemon=True).start())

root.mainloop()

# ← بعد ما تنغلق نافذة اللوغن، شغّل البرنامج الرئيسي
if launch_result[0]:
    import runpy
    import os
    _main_ui_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nologinmain.py")
    runpy.run_path(_main_ui_path, run_name="__main__")
