"""
Scanly — License Generator
============================
هذا البرنامج خاص بالبائع فقط. لا تشاركه مع أحد.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sys, os

# ─── Add parent dir so we can import license_system ──────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from license_system import generate_license, get_hwid, PLANS

# ─── Palette ─────────────────────────────────────────────────────────────
BG       = "#0F172A"
SURFACE  = "#1E293B"
BORDER   = "#334155"
PRIMARY  = "#3B82F6"
PRIMARY_D= "#2563EB"
SUCCESS  = "#10B981"
DANGER   = "#EF4444"
TEXT     = "#F1F5F9"
TEXT2    = "#94A3B8"
FONT     = "Dubai"

def hc(c, f=0.85):
    r,g,b = int(c[1:3],16), int(c[3:5],16), int(c[5:7],16)
    return "#{:02x}{:02x}{:02x}".format(int(r*f),int(g*f),int(b*f))


class GeneratorApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Scanly ─ License Generator  🔑")
        self.root.geometry("680x560")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        self._build()

    # ─────────────────────────────────────────────────────────────────────
    def _build(self):
        # ── Header ───────────────────────────────────────────────────────
        hdr = tk.Frame(self.root, bg=PRIMARY, height=60)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="🔑  Scanly License Generator",
                 font=(FONT, 16, "bold"), bg=PRIMARY, fg="white"
                 ).pack(side="right", padx=20, pady=12)
        tk.Label(hdr, text="أداة البائع — سرية",
                 font=(FONT, 10), bg=PRIMARY, fg="#BFDBFE"
                 ).pack(side="left", padx=20)

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=30, pady=20)

        # ── HWID input ───────────────────────────────────────────────────
        self._section(body, "رقم جهاز العميل  (HWID)")

        hwid_row = tk.Frame(body, bg=BG)
        hwid_row.pack(fill="x", pady=(0, 16))

        self.hwid_var = tk.StringVar()
        hwid_entry = tk.Entry(hwid_row, textvariable=self.hwid_var,
                              font=(FONT, 13, "bold"),
                              bg=SURFACE, fg=TEXT,
                              insertbackground=TEXT,
                              relief="flat", bd=0,
                              justify="center")
        hwid_entry.pack(side="right", fill="x", expand=True, ipady=8, padx=(0,8))

        # Auto-fill my own HWID button
        self._btn(hwid_row, "جهازي أنا", self._fill_my_hwid,
                  color="#7C3AED", side="left")

        # Paste button
        self._btn(hwid_row, "📋 لصق", self._paste_hwid,
                  color=BORDER, side="left")

        # ── Plan selector ─────────────────────────────────────────────────
        self._section(body, "نوع الاشتراك")

        plan_frame = tk.Frame(body, bg=BG)
        plan_frame.pack(fill="x", pady=(0, 20))

        self.plan_var = tk.StringVar(value="سنة")
        plans = list(PLANS.keys())
        colors = ["#6366F1", "#3B82F6", "#06B6D4", "#10B981", "#F59E0B"]

        for i, plan in enumerate(plans):
            color = colors[i % len(colors)]
            rb = tk.Radiobutton(
                plan_frame, text=plan,
                variable=self.plan_var, value=plan,
                font=(FONT, 11, "bold"),
                bg=BG, fg=TEXT,
                activebackground=BG, activeforeground=TEXT,
                selectcolor=SURFACE,
                indicatoron=0,
                relief="flat",
                padx=14, pady=8,
                cursor="hand2",
                command=lambda c=color, rb_=None: None
            )
            rb.pack(side="right", padx=4)
            # Hover
            rb.bind("<Enter>", lambda e, w=rb, c=color: w.config(bg=c, fg="white"))
            rb.bind("<Leave>", lambda e, w=rb: w.config(bg=BG, fg=TEXT))

        # ── Generate button ───────────────────────────────────────────────
        gen_btn = tk.Button(body, text="⚡  توليد كود التفعيل",
                            font=(FONT, 13, "bold"),
                            bg=PRIMARY, fg="white",
                            activebackground=PRIMARY_D, activeforeground="white",
                            relief="flat", cursor="hand2",
                            padx=20, pady=12,
                            command=self._generate)
        gen_btn.pack(fill="x", pady=(0, 20))
        gen_btn.bind("<Enter>", lambda e: gen_btn.config(bg=PRIMARY_D))
        gen_btn.bind("<Leave>", lambda e: gen_btn.config(bg=PRIMARY))

        # ── Result ────────────────────────────────────────────────────────
        self._section(body, "كود التفعيل الناتج")

        result_frame = tk.Frame(body, bg=SURFACE,
                                highlightthickness=1,
                                highlightbackground=BORDER)
        result_frame.pack(fill="x", pady=(0, 12))

        self.result_var = tk.StringVar(value="─────  في انتظار التوليد  ─────")
        result_lbl = tk.Label(result_frame, textvariable=self.result_var,
                              font=(FONT, 15, "bold"),
                              bg=SURFACE, fg=SUCCESS,
                              pady=14, padx=10, justify="center")
        result_lbl.pack(fill="x")

        # Expiry info
        self.expiry_var = tk.StringVar(value="")
        tk.Label(result_frame, textvariable=self.expiry_var,
                 font=(FONT, 9), bg=SURFACE, fg=TEXT2,
                 pady=(0), padx=10).pack(fill="x")

        copy_btn = tk.Button(result_frame, text="📋  نسخ الكود",
                             font=(FONT, 10, "bold"),
                             bg=BG, fg=TEXT2,
                             activebackground=BORDER,
                             relief="flat", cursor="hand2",
                             padx=10, pady=6,
                             command=self._copy_result)
        copy_btn.pack(fill="x")

    # ─────────────────────────────────────────────────────────────────────
    def _section(self, parent, title):
        tk.Label(parent, text=title,
                 font=(FONT, 10, "bold"),
                 bg=BG, fg=TEXT2,
                 anchor="e").pack(fill="x", pady=(0, 6))

    def _btn(self, parent, text, cmd, color=PRIMARY, side="right"):
        b = tk.Button(parent, text=text,
                      font=(FONT, 10),
                      bg=color, fg="white",
                      activebackground=hc(color),
                      relief="flat", cursor="hand2",
                      padx=10, pady=8,
                      command=cmd)
        b.pack(side=side, padx=(0, 6))
        b.bind("<Enter>", lambda e: b.config(bg=hc(color)))
        b.bind("<Leave>", lambda e: b.config(bg=color))

    def _fill_my_hwid(self):
        try:
            hwid = get_hwid()
            self.hwid_var.set(hwid)
        except Exception as ex:
            messagebox.showerror("خطأ", str(ex))

    def _paste_hwid(self):
        try:
            text = self.root.clipboard_get().strip()
            self.hwid_var.set(text)
        except Exception:
            pass

    def _generate(self):
        hwid = self.hwid_var.get().strip().upper()
        if not hwid or len(hwid) < 10:
            messagebox.showwarning("تنبيه", "أدخل رقم جهاز العميل (HWID) أولاً")
            return
        plan = self.plan_var.get()
        try:
            key, start, expiry = generate_license(hwid, plan)
            self.result_var.set(key)
            if expiry == "9999-12-31":
                self.expiry_var.set(f"النوع: {plan}  |  صالح مدى الحياة")
            else:
                self.expiry_var.set(f"النوع: {plan}  |  يبدأ من: {start}  |  ينتهي في: {expiry}")
        except Exception as ex:
            messagebox.showerror("خطأ في التوليد", str(ex))

    def _copy_result(self):
        key = self.result_var.get()
        if "انتظار" in key:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(key)
        messagebox.showinfo("✅", "تم نسخ الكود!")


def main():
    root = tk.Tk()
    try:
        root.tk.call('tk', 'scaling', 1.2)
    except Exception:
        pass
    GeneratorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
