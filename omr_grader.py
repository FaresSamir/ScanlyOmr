import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import cv2
import numpy as np
from PIL import Image, ImageTk
import os
import sys
import json
import tempfile
from datetime import datetime, date
from license_system import (
    check_license, save_license, load_license,
    get_hwid, verify_license_key, PLANS, LIFETIME_EXPIRY
)

# ── Base directory (works for both .py and .exe) ────────────────────────────
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
    ASSET_DIR = getattr(sys, '_MEIPASS', BASE_DIR)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    ASSET_DIR = BASE_DIR

# ===================== OMR CORE =====================

QUESTION_YS = [150,198,249,297,349,399,448,498,549,597,647,697,748,795,846,
               895,944,993,1041,1090,1141,1191,1240,1288,1340,1388,1439]

COL_SECTIONS = [
    {"qs": list(range(1,28)),  "xs": {"د":724, "ج":773, "ب":822, "أ":872}},
    {"qs": list(range(28,55)), "xs": {"د":411, "ج":461, "ب":510, "أ":559}},
    {"qs": list(range(55,82)), "xs": {"د":106, "ج":154, "ب":202, "أ":250}},
]

TARGET_H, TARGET_W = 1491, 1055
BUBBLE_RADIUS = 18
ADAPTIVE_GAP_THRESHOLD = 8
ABSOLUTE_MAX_FILLED    = 200
DEBUG_SAVE_OVERLAY = True
DEBUG_OVERLAY_PATH = r"debug_overlay.png"
PERSPECTIVE_CORRECTION_ENABLED = False


def _order_points(pts):
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def _correct_perspective(img, target_w, target_h):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    blurred = cv2.GaussianBlur(gray, (7, 7), 0)
    edged = cv2.Canny(blurred, 30, 100)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    edged = cv2.dilate(edged, kernel, iterations=2)
    contours, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    sheet_contour = None
    for c in contours[:8]:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        area = cv2.contourArea(c)
        if len(approx) == 4 and area > (target_w * target_h * 0.3):
            sheet_contour = approx
            break
    if sheet_contour is None:
        return img
    pts = sheet_contour.reshape(4, 2).astype("float32")
    rect = _order_points(pts)
    dst = np.array([
        [0, 0],
        [target_w - 1, 0],
        [target_w - 1, target_h - 1],
        [0, target_h - 1]
    ], dtype="float32")
    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(img, M, (target_w, target_h))
    return warped


def _sample_bubble(gray, cx, cy, radius=BUBBLE_RADIUS):
    h, w = gray.shape
    if cx < 0 or cy < 0 or cx >= w or cy >= h:
        return 255.0
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(mask, (cx, cy), max(1, radius - 2), 255, -1)
    mean_val = cv2.mean(gray, mask=mask)[0]
    return mean_val


def _save_debug_overlay(img_bgr, num_questions, fitted_coords=None):
    overlay = img_bgr.copy()
    for sec_idx, sec in enumerate(COL_SECTIONS):
        if fitted_coords and sec_idx in fitted_coords:
            ys, xs = fitted_coords[sec_idx]
        else:
            ys = QUESTION_YS
            xs = sec["xs"]
        for row_idx, q_num in enumerate(sec["qs"]):
            if q_num > num_questions:
                continue
            cy = ys[row_idx]
            for choice, cx in xs.items():
                cv2.circle(overlay, (cx, cy), BUBBLE_RADIUS, (0, 0, 255), 2)
            cv2.putText(overlay, str(q_num), (xs["أ"] + 5, cy - 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 0, 0), 1)
    cv2.imwrite(DEBUG_OVERLAY_PATH, overlay)
    print(f"[DEBUG] overlay saved: {DEBUG_OVERLAY_PATH}")


def read_bubble_sheet(image_path_or_array, num_questions=81):
    if isinstance(image_path_or_array, str):
        img = cv2.imread(image_path_or_array)
        if img is None:
            return None, "تعذر فتح الصورة"
    else:
        img = image_path_or_array.copy()

    target_h, target_w = TARGET_H, TARGET_W
    orig_h, orig_w = img.shape[:2]
    if orig_h != target_h or orig_w != target_w:
        img = cv2.resize(img, (target_w, target_h), interpolation=cv2.INTER_AREA)

    if img.ndim == 3:
        gray_temp = img[:, :, 1]
    else:
        gray_temp = img.copy()
    _, thresh_temp = cv2.threshold(gray_temp, 127, 255, cv2.THRESH_BINARY_INV)
    contours_temp, _ = cv2.findContours(thresh_temp, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    bubbles_at_top = 0
    for c in contours_temp:
        area = cv2.contourArea(c)
        perimeter = cv2.arcLength(c, True)
        if perimeter == 0:
            continue
        circularity = 4 * np.pi * area / (perimeter * perimeter)
        if 180 < area < 1000 and circularity > 0.4:
            M = cv2.moments(c)
            if M["m00"] != 0:
                cY = int(M["m01"] / M["m00"])
                if cY < 120:
                    bubbles_at_top += 1
    if bubbles_at_top >= 3:
        print("[OMR] Detected upside-down sheet! Rotating 180 degrees automatically...")
        img = cv2.rotate(img, cv2.ROTATE_180)

    if img.ndim == 3:
        gray_raw = img[:, :, 1]
    else:
        gray_raw = img.copy()

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray_raw)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    _, thresh = cv2.threshold(gray_raw, 127, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    detected_bubbles = []
    for c in contours:
        area = cv2.contourArea(c)
        perimeter = cv2.arcLength(c, True)
        if perimeter == 0:
            continue
        circularity = 4 * np.pi * area / (perimeter * perimeter)
        if 180 < area < 1000 and circularity > 0.4:
            M = cv2.moments(c)
            if M["m00"] != 0:
                cX = int(M["m10"] / M["m00"])
                cY = int(M["m01"] / M["m00"])
                detected_bubbles.append((cX, cY))

    answers = {}
    answer_confidence = {}
    fitted_coords = {}

    for sec_idx, sec in enumerate(COL_SECTIONS):
        col_xs = sec["xs"]
        questions_in_sec = sec["qs"]
        x_min, x_max = [(680, 920), (370, 600), (50, 270)][sec_idx]
        sec_pts = [p for p in detected_bubbles if x_min < p[0] < x_max]
        ys = list(QUESTION_YS)
        xs = dict(col_xs)

        if len(sec_pts) >= 5:
            rows = []
            for p in sec_pts:
                placed = False
                for r in rows:
                    avg_y = sum(x[1] for x in r) / len(r)
                    if abs(p[1] - avg_y) < 15:
                        r.append(p)
                        placed = True
                        break
                if not placed:
                    rows.append([p])
            rows.sort(key=lambda r: sum(x[1] for x in r) / len(r))

            if len(rows) >= 5:
                min_row_y = sum(x[1] for x in rows[0]) / len(rows[0])
                valid_rows = []
                for r in rows:
                    avg_y = sum(x[1] for x in r) / len(r)
                    row_idx = int(round((avg_y - min_row_y) / 48.0))
                    if 0 <= row_idx < 27:
                        valid_rows.append((row_idx, avg_y))

                if len(valid_rows) >= 5:
                    X_mat = np.array([[r[0], 1] for r in valid_rows])
                    Y_mat = np.array([r[1] for r in valid_rows])
                    a, b = np.linalg.lstsq(X_mat, Y_mat, rcond=None)[0]
                    if 44 < a < 52 and 120 < b < 190:
                        ys = [int(round(a * i + b)) for i in range(27)]
                    else:
                        print(f"[OMR] Section {sec_idx+1} fit params out of range (step={a:.1f}, start={b:.1f}), using fallback Ys")

            x_groups = {ch: [] for ch in col_xs}
            for p in sec_pts:
                closest_ch = min(col_xs, key=lambda ch: abs(p[0] - col_xs[ch]))
                if abs(p[0] - col_xs[closest_ch]) < 25:
                    x_groups[closest_ch].append(p[0])
            for ch in col_xs:
                if len(x_groups[ch]) >= 3:
                    xs[ch] = int(round(np.mean(x_groups[ch])))

        fitted_coords[sec_idx] = (ys, xs)

        for row_idx, q_num in enumerate(questions_in_sec):
            if q_num > num_questions:
                continue
            cy = ys[row_idx]
            bubble_vals = {}
            for choice, cx in xs.items():
                bubble_vals[choice] = _sample_bubble(gray, cx, cy)

            row_mean = np.mean(list(bubble_vals.values()))
            filled_choices = []
            for choice, val in bubble_vals.items():
                gap = row_mean - val
                if gap >= ADAPTIVE_GAP_THRESHOLD and val <= ABSOLUTE_MAX_FILLED:
                    filled_choices.append(choice)

            if len(filled_choices) > 1:
                answers[q_num] = "مزدوج"
                answer_confidence[q_num] = "low"
            elif len(filled_choices) == 1:
                choice = filled_choices[0]
                answers[q_num] = choice
                gap = row_mean - bubble_vals[choice]
                if gap >= 40:
                    answer_confidence[q_num] = "high"
                elif gap >= 22:
                    answer_confidence[q_num] = "medium"
                else:
                    answer_confidence[q_num] = "low"

    if DEBUG_SAVE_OVERLAY:
        _save_debug_overlay(img, num_questions, fitted_coords)

    result = {q: answers.get(q, "؟") for q in range(1, num_questions + 1)}
    return result, None


def grade(student_answers, answer_key, num_questions):
    score = 0
    details = []
    for q in range(1, num_questions+1):
        student = student_answers.get(q, "؟")
        correct = answer_key.get(q, "")
        is_correct = (student == correct) and correct != ""
        if is_correct:
            score += 1
        details.append({"q": q, "student": student, "correct": correct, "ok": is_correct})
    return score, details


# ===================== SCANNER =====================

def get_scanners(window=None):
    scanners = []
    try:
        import twain
        sm = twain.SourceManager(window)
        sources = sm.source_list
        sm.destroy()
        for s in (sources or []):
            scanners.append({"name": s, "type": "TWAIN", "id": s})
        print(f"[TWAIN] found: {sources}")
    except Exception as e:
        print(f"[TWAIN] not available: {e}")

    try:
        import win32com.client
        wia = win32com.client.Dispatch("WIA.DeviceManager")
        for dev in wia.DeviceInfos:
            if dev.Type == 1:
                name = dev.Properties("Name").Value
                scanners.append({"name": name, "type": "WIA", "id": dev.DeviceID})
                print(f"[WIA] found: {name}")
    except Exception as e:
        print(f"[WIA] not available: {e}")

    return scanners


def scan_image(scanner_info, dpi=300, window=None):
    if isinstance(scanner_info, str):
        scanner_info = {"name": scanner_info, "type": "TWAIN", "id": scanner_info}
    if scanner_info["type"] == "TWAIN":
        return _scan_twain(scanner_info["name"], dpi, window)
    else:
        return _scan_wia(scanner_info["id"], dpi)


def _scan_twain(scanner_name, dpi, window):
    import twain
    sm = twain.SourceManager(window)
    ss = sm.open_source(scanner_name)
    ss.set_capability(twain.ICAP_PIXELTYPE, twain.TWTY_UINT16, twain.TWPT_GRAY)
    ss.set_capability(twain.ICAP_XRESOLUTION, twain.TWTY_FIX32, dpi)
    ss.set_capability(twain.ICAP_YRESOLUTION, twain.TWTY_FIX32, dpi)
    try:
        ss.set_capability(twain.ICAP_SUPPORTEDSIZES, twain.TWTY_UINT16, twain.TWSS_A5)
    except Exception:
        ss.set_image_layout((0, 0, 5.83, 8.27))
    ss.request_acquire(show_ui=False, modal_ui=False)
    img = None
    while True:
        try:
            rv = ss.xfer_image_natively()
            if rv is None:
                break
            handle, count = rv
            pil_img = twain.dib_to_pil(handle)
            img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        except twain.excDSTransferCancelled:
            break
    ss.destroy()
    sm.destroy()
    return img


def _scan_wia(device_id, dpi):
    import win32com.client, tempfile, os
    wia = win32com.client.Dispatch("WIA.DeviceManager")
    device = None
    for dev_info in wia.DeviceInfos:
        if dev_info.DeviceID == device_id:
            device = dev_info.Connect()
            break
    if device is None:
        raise Exception("الماسح الضوئي غير متصل أو غير متوفر!")
    scanner_item = device.Items[1]
    try:
        scanner_item.Properties("Horizontal Resolution").Value = dpi
        scanner_item.Properties("Vertical Resolution").Value = dpi
        scanner_item.Properties("Current Intent").Value = 4
        a5_w_thou = 5830
        a5_h_thou = 8270
        scanner_item.Properties("Horizontal Extent").Value = int(a5_w_thou * dpi / 1000)
        scanner_item.Properties("Vertical Extent").Value   = int(a5_h_thou * dpi / 1000)
        scanner_item.Properties("Horizontal Start").Value  = 0
        scanner_item.Properties("Vertical Start").Value    = 0
    except Exception:
        pass
    image = scanner_item.Transfer("{B96B3CAB-0728-11D3-9D7B-0000F81EF32E}")
    tmp = tempfile.mktemp(suffix=".bmp")
    image.SaveFile(tmp)
    img = cv2.imread(tmp)
    os.remove(tmp)
    return img


# ===================== THEME & LANGUAGE =====================

LANG = {"ar": True}  # mutable flag

STRINGS = {
    "app_title":        {"ar": "Scanly",  "en": "Scanly"},
    "scanner_card":     {"ar": "الماسح الضوئي",                  "en": "Scanner"},
    "choose_scanner":   {"ar": "اختر الماسح الضوئي:",             "en": "Select scanner:"},
    "scan_dpi":         {"ar": "دقة المسح الضوئي (DPI):",          "en": "Scan DPI:"},
    "scan_grade":       {"ar": "مسح وتصحيح ضوئي",                "en": "Scan & Grade"},
    "scan_batch":       {"ar": "مسح متواصل (دفعة)",              "en": "Continuous Scan"},
    "calibrate":        {"ar": "معايرة دقة الكشف",                 "en": "Calibrate Detection"},
    "settings_card":    {"ar": "إعدادات الاختبار",                "en": "Exam Settings"},
    "num_questions":    {"ar": "عدد الأسئلة الإجمالي:",            "en": "Number of questions:"},
    "key_card":         {"ar": "مفتاح الإجابة النموذجية",          "en": "Answer Key"},
    "scan_key":         {"ar": "مسح ورقة الإجابة",                 "en": "Scan Answer Sheet"},
    "upload_key":       {"ar": "تحميل صورة ورقة الإجابة",          "en": "Upload Answer Image"},
    "key_not_loaded":   {"ar": "لم يتم تحميل مفتاح الإجابة بعد",    "en": "No key loaded yet"},
    "or_manual":        {"ar": "أو الإدخال يدوياً:",               "en": "Or enter manually:"},
    "save_key":         {"ar": "حفظ مفتاح الإجابة",                "en": "Save Key"},
    "clear_all":        {"ar": "مَسح كافة الحقول",                 "en": "Clear All"},
    "upload_img":       {"ar": "تحميل صورة ورقة",                  "en": "Upload Image"},
    "upload_folder":    {"ar": "تحميل مجلد كامل",                 "en": "Upload Folder"},
    "export_csv":       {"ar": "تصدير إلى ملف CSV",                "en": "Export CSV"},
    "clear_results":    {"ar": "مسح النتائج الحالية",               "en": "Clear Results"},
    "results_card":     {"ar": "نتائج التصحيح الضوئي",             "en": "Grading Results"},
    "detail_card":      {"ar": "تفاصيل الورقة المحددة",            "en": "Selected Sheet Detail"},
    "no_scanner":       {"ar": "لا يوجد ماسح ضوئي متصل",            "en": "No scanner found"},
    "scanning":         {"ar": "جارٍ المسح الضوئي...",             "en": "Scanning..."},
    "col_num":          {"ar": "الرقم",                           "en": "#"},
    "col_file":         {"ar": "اسم الملف / الورقة",               "en": "File / Sheet"},
    "col_score":        {"ar": "الدرجة المستحقة",                   "en": "Score"},
    "col_correct":      {"ar": "الإجابات الصحيحة",                 "en": "Correct"},
    "col_wrong":        {"ar": "الإجابات الخاطئة",                 "en": "Wrong"},
    "col_pct":          {"ar": "النسبة المئوية",                    "en": "%"},
}

PALETTE = {
    "bg":         "#F8FAFC",      # slate 50 (very light grayish blue)
    "surface":    "#FFFFFF",      # pure white
    "border":     "#E2E8F0",      # slate 200 (modern clean border)
    "primary":    "#4d4d4d",      # indigo 600 (rich modern primary brand color)
    "primary_dk": "#4d4d4d",      # indigo 800 (hover/dark state)
    "primary_lt": "#EEF2F6",      # slate 100/indigo light blend (background for selections/badges)
    "accent":     "#4d4d4d",      # sky 500 (vibrant blue)
    "success":    "#10B981",      # emerald 500
    "success_lt": "#ECFDF5",      # emerald 50
    "warning":    "#F59E0B",      # amber 500
    "warning_lt": "#FFFBEB",      # amber 50
    "danger":     "#EF4444",      # red 500
    "danger_lt":  "#FEF2F2",      # red 50
    "muted":      "#4d4d4d",      # slate 500 (cool gray text)
    "text":       "#0F172A",      # slate 900 (almost black, very soft contrast)
    "text2":      "#475569",      # slate 600 (secondary text)
    "purple":     "#3c83f6",      # violet 500
    "purple_lt":  "#eef3f7",      # violet 50
}

FONT_AR = "Dubai"      # Modern, professional Arabic font
FONT_EN = "Segoe UI"

def T(key):
    lang = "ar" if LANG["ar"] else "en"
    return STRINGS.get(key, {}).get(lang, key)

def get_font(size=10, bold=False, mono=False):
    base = FONT_AR if LANG["ar"] else FONT_EN
    if mono:
        base = "Consolas" if not LANG["ar"] else "Courier New"
    weight = "bold" if bold else "normal"
    return (base, size, weight)

def dir_flag():
    return "rtl" if LANG["ar"] else "ltr"


# ===================== GUI =====================

class OMRApp:
    def __init__(self, root):
        self.root = root
        self.root.title(T("app_title"))
        self.root.geometry("1200x740")
        self.root.configure(bg=PALETTE["bg"])
        self.root.minsize(900, 600)

        self.answer_key = {}
        self.num_questions = tk.IntVar(value=40)
        self.students_results = []
        self.key_file = "answer_key.json"
        self.scanner_var = tk.StringVar(value="")
        self.scan_counter = 0
        self._scanners_list = []

        # ttk style
        self._setup_styles()
        self._load_key_from_file()
        self._build_ui()
        self.root.after(500, self._refresh_scanners)

    # ------------------------------------------------------------------
    def _setup_styles(self):
        s = ttk.Style()
        s.theme_use("clam")

        s.configure("TFrame", background=PALETTE["bg"])
        s.configure("Card.TFrame", background=PALETTE["surface"],
                    relief="flat", borderwidth=1)

        s.configure("TCombobox",
                    fieldbackground=PALETTE["surface"],
                    background=PALETTE["surface"],
                    foreground=PALETTE["text"],
                    bordercolor=PALETTE["border"],
                    arrowcolor=PALETTE["muted"],
                    selectbackground=PALETTE["primary_lt"],
                    selectforeground=PALETTE["text"],
                    font=get_font(10))
        s.map("TCombobox", fieldbackground=[("readonly", PALETTE["surface"])])

        s.configure("Treeview",
                    background=PALETTE["surface"],
                    fieldbackground=PALETTE["surface"],
                    foreground=PALETTE["text"],
                    bordercolor=PALETTE["border"],
                    rowheight=30,
                    font=get_font(10))
        s.configure("Treeview.Heading",
                    background=PALETTE["bg"],
                    foreground=PALETTE["text2"],
                    font=get_font(10, bold=True),
                    relief="flat",
                    borderwidth=0)
        s.map("Treeview",
              background=[("selected", PALETTE["primary_lt"])],
              foreground=[("selected", PALETTE["primary"])])
        s.map("Treeview.Heading",
              background=[("active", PALETTE["border"])])

        s.configure("Vertical.TScrollbar",
                    background=PALETTE["bg"],
                    troughcolor=PALETTE["bg"],
                    bordercolor=PALETTE["bg"],
                    arrowcolor=PALETTE["muted"],
                    relief="flat")

        s.configure("TSpinbox",
                    fieldbackground=PALETTE["surface"],
                    background=PALETTE["surface"],
                    foreground=PALETTE["text"],
                    bordercolor=PALETTE["border"],
                    font=get_font(13, bold=True))

        s.configure("TProgressbar",
                    troughcolor=PALETTE["bg"],
                    background=PALETTE["primary"])

    # ------------------------------------------------------------------
    def _load_key_from_file(self):
        if os.path.exists(self.key_file):
            try:
                with open(self.key_file) as f:
                    data = json.load(f)
                self.answer_key = {int(k): v for k, v in data.get("key", {}).items()}
                self.num_questions.set(data.get("num", 40))
            except:
                pass

    def _save_key_to_file(self):
        with open(self.key_file, "w") as f:
            json.dump({"key": self.answer_key, "num": self.num_questions.get()}, f)

    # ------------------------------------------------------------------
    def _build_ui(self):
        # ── Top header bar ──────────────────────────────────────────────
        header = tk.Frame(self.root, bg=PALETTE["primary"], height=58)
        header.pack(fill="x")
        header.pack_propagate(False)

        # Lang toggle button (opposite to title)
        self._lang_btn = tk.Button(
            header,
            text="EN" if LANG["ar"] else "AR",
            font=get_font(10, bold=True),
            bg=PALETTE["primary_dk"],
            fg="white",
            activebackground=PALETTE["primary_dk"],
            activeforeground="white",
            relief="flat",
            cursor="hand2",
            padx=12, pady=4,
            command=self._toggle_language
        )
        self._lang_btn.pack(side=self.side_left(), padx=14, pady=12)

        # App title
        try:
            logo_pil = Image.open(os.path.join(ASSET_DIR, "Scanly.png"))
            logo_pil = logo_pil.resize((28, 28), Image.LANCZOS)
            self._logo_img = ImageTk.PhotoImage(logo_pil)
            self._title_lbl = tk.Label(
                header,
                image=self._logo_img,
                text=" " + T("app_title") + " ",
                compound=self.side_right(),
                font=get_font(18, bold=True),
                bg=PALETTE["primary"],
                fg="white"
            )
        except Exception as e:
            print(f"[UI] Logo load error: {e}")
            self._title_lbl = tk.Label(
                header,
                text="  ●  " + T("app_title"),
                font=get_font(18, bold=True),
                bg=PALETTE["primary"],
                fg="white"
            )
        self._title_lbl.pack(side=self.side_right(), padx=20, pady=10)

        # ── Body ────────────────────────────────────────────────────────
        body = tk.Frame(self.root, bg=PALETTE["bg"])
        body.pack(fill="both", expand=True, padx=14, pady=12)

        # Sidebar panel (fixed width)
        self._left_panel = tk.Frame(body, bg=PALETTE["bg"], width=310)
        self._left_panel.pack(side=self.side_right(), fill="y")
        self._left_panel.pack_propagate(False)

        # Separator line
        sep = tk.Frame(body, bg=PALETTE["border"], width=1)
        sep.pack(side=self.side_right(), fill="y", padx=6)

        # Main panel (expanding)
        self._right_panel = tk.Frame(body, bg=PALETTE["bg"])
        self._right_panel.pack(side=self.side_right(), fill="both", expand=True)

        self._build_left(self._left_panel)
        self._build_right(self._right_panel)

    # ------------------------------------------------------------------
    def side_right(self):
        return "right" if LANG["ar"] else "left"

    def side_left(self):
        return "left" if LANG["ar"] else "right"

    def _btn(self, parent, text_key=None, text=None, color=None, fg="white",
             command=None, size=10, bold=True, pady=8, padx=10, icon=""):
        bg = color or PALETTE["primary"]
        label = (icon + "  " if icon else "") + (text or T(text_key) if text_key else "")
        b = tk.Button(
            parent,
            text=label,
            font=get_font(size, bold=bold),
            bg=bg, fg=fg,
            activebackground=self._darken(bg),
            activeforeground=fg,
            relief="flat",
            cursor="hand2",
            padx=padx, pady=pady,
            command=command
        )
        # Hover effect
        def on_enter(e):
            if b['state'] == 'normal':
                b.config(bg=self._darken(bg))
        def on_leave(e):
            if b['state'] == 'normal':
                b.config(bg=bg)
        b.bind("<Enter>", on_enter)
        b.bind("<Leave>", on_leave)
        return b

    def _darken(self, hex_color):
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        factor = 0.85
        return "#{:02x}{:02x}{:02x}".format(
            int(r*factor), int(g*factor), int(b*factor))

    def _card(self, parent, title_key=None, title=None, expand=True, pack=True):
        """Returns (outer_frame, inner_frame)"""
        outer = tk.Frame(parent, bg=PALETTE["surface"],
                         highlightthickness=1,
                         highlightbackground=PALETTE["border"])
        if pack:
            outer.pack(fill="both", expand=expand, pady=(0, 10))

        # Modern card header (white background, elegant title)
        lbl_text = title or T(title_key) if title_key else ""
        if lbl_text:
            hdr = tk.Frame(outer, bg=PALETTE["surface"], height=36)
            hdr.pack(fill="x", padx=12, pady=(8, 0))
            hdr.pack_propagate(False)
            
            lbl = tk.Label(hdr, text=lbl_text,
                           font=get_font(11, bold=True),
                           bg=PALETTE["surface"],
                           fg=PALETTE["text"],
                           anchor="e" if LANG["ar"] else "w")
            lbl.pack(fill="both", expand=True)
            
            sep = tk.Frame(outer, bg=PALETTE["border"], height=1)
            sep.pack(fill="x", padx=12, pady=(4, 6))

        inner = tk.Frame(outer, bg=PALETTE["surface"])
        inner.pack(fill="both", expand=True, padx=12, pady=(4, 12))
        return outer, inner

    def _label(self, parent, text_key=None, text=None, size=10, bold=False,
               color=None, anchor=None):
        if anchor is None:
            anchor = "e" if LANG["ar"] else "w"
        lbl = tk.Label(
            parent,
            text=text or T(text_key) if text_key else "",
            font=get_font(size, bold=bold),
            bg=PALETTE["surface"],
            fg=color or PALETTE["text"],
            anchor=anchor
        )
        return lbl

    # ------------------------------------------------------------------
    def _build_left(self, parent):
        # ── Scanner card ─────────────────────────────────────────────
        _, sc = self._card(parent, "scanner_card", expand=False)
        self._scanner_card_inner = sc

        row_lbl = self._label(sc, "choose_scanner", size=9, color=PALETTE["muted"])
        row_lbl.pack(fill="x", pady=(0, 3))

        combo_row = tk.Frame(sc, bg=PALETTE["surface"])
        combo_row.pack(fill="x", pady=(0, 6))

        self._refresh_icon_btn = tk.Button(
            combo_row, text="↺",
            font=get_font(13, bold=True),
            bg=PALETTE["surface"], fg=PALETTE["muted"],
            activebackground=PALETTE["bg"],
            relief="flat", cursor="hand2",
            padx=4, pady=2,
            command=self._refresh_scanners
        )
        self._refresh_icon_btn.pack(side=self.side_left(), padx=4)

        self.scanner_combo = ttk.Combobox(
            combo_row, textvariable=self.scanner_var,
            font=get_font(9), state="readonly"
        )
        self.scanner_combo.pack(side=self.side_right(), fill="x", expand=True)

        # DPI row
        dpi_row = tk.Frame(sc, bg=PALETTE["surface"])
        dpi_row.pack(fill="x", pady=(0, 10))
        self._label(dpi_row, "scan_dpi", size=9, color=PALETTE["muted"]).pack(side=self.side_right())
        self.dpi_var = tk.IntVar(value=300)
        ttk.Combobox(dpi_row, textvariable=self.dpi_var,
                     values=[150, 200, 300, 400, 600],
                     width=6, state="readonly",
                     font=get_font(9)).pack(side=self.side_left())

        # Scan buttons
        self.scan_btn = self._btn(sc, "scan_grade", icon="⬤",
                                   color=PALETTE["primary"],
                                   size=11, pady=9,
                                   command=self._scan_and_grade)
        self.scan_btn.pack(fill="x", pady=(0, 4))

        self.cont_btn = self._btn(sc, "scan_batch", icon="⟳",
                                   color=PALETTE["accent"],
                                   size=10, pady=6,
                                   command=self._scan_continuous)
        self.cont_btn.pack(fill="x", pady=(0, 4))

        self.cal_btn = self._btn(sc, "calibrate",
                                  color=PALETTE["muted"],
                                  size=9, bold=False, pady=5,
                                  command=self._calibrate_detection)
        self.cal_btn.pack(fill="x")

        # ── Settings card ────────────────────────────────────────────
        _, stc = self._card(parent, "settings_card", expand=False)
        self._settings_card_inner = stc

        nq_lbl = self._label(stc, "num_questions", size=10)
        nq_lbl.pack(fill="x", pady=(0, 4))

        nq_row = tk.Frame(stc, bg=PALETTE["surface"])
        nq_row.pack(fill="x")

        # styled spinbox-like frame
        spin_border = tk.Frame(nq_row, bg=PALETTE["border"],
                               highlightthickness=0)
        spin_border.pack(side=self.side_right())
        self._spinbox = tk.Spinbox(
            spin_border, from_=1, to=81, width=5,
            textvariable=self.num_questions,
            font=get_font(14, bold=True),
            bg=PALETTE["surface"],
            fg=PALETTE["text"],
            relief="flat",
            buttonbackground=PALETTE["bg"],
            command=self._refresh_key_grid
        )
        self._spinbox.pack(padx=1, pady=1)

        # ── Answer Key card ──────────────────────────────────────────
        _, kc = self._card(parent, "key_card", expand=True)
        self._key_card_inner = kc

        self.scan_key_btn = self._btn(kc, "scan_key",
                                       color=PALETTE["success"],
                                       size=11, pady=8,
                                       command=self._scan_answer_key)
        self.scan_key_btn.pack(fill="x", pady=(0, 4))

        self._btn(kc, "upload_key",
                  color=PALETTE["accent"],
                  size=9, bold=False, pady=5,
                  command=self._load_key_from_image).pack(fill="x", pady=(0, 6))

        # Key status badge
        self.key_status_var = tk.StringVar(value="⚠  " + T("key_not_loaded"))
        self.key_status_lbl = tk.Label(
            kc, textvariable=self.key_status_var,
            font=get_font(9, bold=True),
            bg=PALETTE["danger_lt"],
            fg=PALETTE["danger"],
            anchor="e" if LANG["ar"] else "w", padx=8, pady=4
        )
        self.key_status_lbl.pack(fill="x", pady=(0, 6))

        # Divider
        tk.Frame(kc, bg=PALETTE["border"], height=1).pack(fill="x")
        self._label(kc, "or_manual", size=8, color=PALETTE["muted"]).pack(
            fill="x", pady=(4, 0))

        # Scrollable key grid
        scroll_wrap = tk.Frame(kc, bg=PALETTE["surface"])
        scroll_wrap.pack(fill="both", expand=True, pady=(4, 0))

        self._key_canvas = tk.Canvas(scroll_wrap, bg=PALETTE["surface"],
                                     highlightthickness=0, height=150)
        ksb = ttk.Scrollbar(scroll_wrap, orient="vertical",
                             command=self._key_canvas.yview)
        self.key_inner = tk.Frame(self._key_canvas, bg=PALETTE["surface"])
        self.key_inner.bind("<Configure>",
            lambda e: self._key_canvas.configure(
                scrollregion=self._key_canvas.bbox("all")))
        self._key_canvas.create_window((0, 0), window=self.key_inner, anchor="ne" if LANG["ar"] else "nw")
        self._key_canvas.configure(yscrollcommand=ksb.set)
        self._key_canvas.pack(side=self.side_right(), fill="both", expand=True)
        ksb.pack(side=self.side_left(), fill="y")

        self.key_vars = {}
        self._build_key_grid()
        self._update_key_status()

        btn_row = tk.Frame(kc, bg=PALETTE["surface"])
        btn_row.pack(fill="x", pady=(6, 0))

        self._btn(btn_row, "save_key",
                  color=PALETTE["success"],
                  size=9, pady=5,
                  command=self._save_key).pack(side=self.side_right(), padx=3)
        self._btn(btn_row, "clear_all",
                  color=PALETTE["danger"],
                  size=9, pady=5,
                  command=self._clear_key).pack(side=self.side_right(), padx=3)

    # ------------------------------------------------------------------
    def _build_right(self, parent):
        # ── Action buttons row ────────────────────────────────────────
        btn_bar = tk.Frame(parent, bg=PALETTE["bg"])
        btn_bar.pack(fill="x", pady=(0, 10))

        self._btn(btn_bar, "upload_img", icon="",
                  color=PALETTE["accent"],
                  size=10, pady=7, padx=14,
                  command=self._grade_single).pack(side=self.side_right(), padx=4)

        self._btn(btn_bar, "upload_folder", icon="",
                  color="#117A65",
                  size=10, pady=7, padx=14,
                  command=self._grade_batch).pack(side=self.side_right(), padx=4)

        self._btn(btn_bar, "export_csv", icon="↓",
                  color=PALETTE["success"],
                  size=10, pady=7, padx=14,
                  command=self._export).pack(side=self.side_left(), padx=4)

        self._btn(btn_bar, "clear_results",
                  color=PALETTE["muted"],
                  size=9, bold=False, pady=7, padx=14,
                  command=self._clear_results).pack(side=self.side_left(), padx=4)

        # Create PanedWindow below the action buttons
        paned = tk.PanedWindow(parent, orient="vertical", bg=PALETTE["bg"], bd=0, sashwidth=4, sashcursor="sb_v_double_arrow")
        paned.pack(fill="both", expand=True)

        # ── Results table card ────────────────────────────────────────
        rc_outer, rc = self._card(paned, "results_card", pack=False)
        self._results_card_inner = rc
        paned.add(rc_outer, minsize=180)

        # Summary strip
        self.summary_var = tk.StringVar(value="")
        self._summary_lbl = tk.Label(
            rc, textvariable=self.summary_var,
            font=get_font(10, bold=True),
            bg=PALETTE["primary_lt"],
            fg=PALETTE["primary"],
            anchor="e" if LANG["ar"] else "w", padx=10, pady=5
        )
        self._summary_lbl.pack(fill="x", pady=(0, 6))

        # Table
        cols = ("num", "file", "score", "correct", "wrong", "pct")
        self.tree = ttk.Treeview(rc, columns=cols, show="headings", height=9)
        widths = [50, 210, 85, 75, 75, 75]
        
        # Configure headings and columns
        col_titles = {
            "num": T("col_num"),
            "file": T("col_file"),
            "score": T("col_score"),
            "correct": T("col_correct"),
            "wrong": T("col_wrong"),
            "pct": T("col_pct")
        }
        for c, w in zip(cols, widths):
            self.tree.heading(c, text=col_titles[c])
            self.tree.column(c, width=w, anchor="center", minwidth=30)

        # Reorder displayed columns in RTL
        display_cols = list(reversed(cols)) if LANG["ar"] else cols
        self.tree["displaycolumns"] = display_cols

        tree_sb = ttk.Scrollbar(rc, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_sb.set)
        self.tree.pack(side=self.side_right(), fill="both", expand=True, padx=(6, 0) if LANG["ar"] else (0, 6))
        tree_sb.pack(side=self.side_left(), fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # Alternating row colors
        self.tree.tag_configure("pass", foreground=PALETTE["success"])
        self.tree.tag_configure("fail", foreground=PALETTE["danger"])
        self.tree.tag_configure("odd_pass",  background="#F0FBF4", foreground=PALETTE["success"])
        self.tree.tag_configure("odd_fail",  background="#FDF2F2", foreground=PALETTE["danger"])

        # ── Detail card ───────────────────────────────────────────────
        dc_outer, dc = self._card(paned, "detail_card", pack=False)
        self._detail_card_inner = dc
        paned.add(dc_outer, minsize=140)

        self.detail_text = tk.Text(
            dc, height=7,
            font=get_font(10, mono=True),
            bg=PALETTE["bg"],
            fg=PALETTE["text"],
            relief="flat",
            wrap="word",
            state="disabled",
            padx=8, pady=6,
            insertbackground=PALETTE["text"]
        )
        self.detail_text.pack(fill="both", expand=True)
        self.detail_text.tag_configure("ok",   foreground=PALETTE["success"])
        self.detail_text.tag_configure("err",  foreground=PALETTE["danger"])
        self.detail_text.tag_configure("bold", font=get_font(10, bold=True, mono=True))
        self.detail_text.tag_configure("head", foreground=PALETTE["accent"],
                                       font=get_font(10, bold=True, mono=True))
        self.detail_text.tag_configure("align", justify="right" if LANG["ar"] else "left")

    # ------------------------------------------------------------------
    #  LANGUAGE TOGGLE
    # ------------------------------------------------------------------
    def _toggle_language(self):
        LANG["ar"] = not LANG["ar"]
        self._lang_btn.config(text="AR" if not LANG["ar"] else "EN")
        self._rebuild_ui()

    def _rebuild_ui(self):
        """Destroy and rebuild all UI widgets after language switch."""
        # Remember window size
        geom = self.root.geometry()
        # destroy all children
        for w in self.root.winfo_children():
            w.destroy()
        # re-setup styles (fonts may change)
        self._setup_styles()
        # rebuild
        self._build_ui()
        self.root.geometry(geom)
        # restore state
        self._apply_state_to_ui()

    def _apply_state_to_ui(self):
        """Re-apply runtime state (key, results) after a rebuild."""
        # key grid
        self._refresh_key_grid()
        self._update_key_status()
        # scanners
        if self._scanners_list:
            names = [f"[{s['type']}] {s['name']}" for s in self._scanners_list]
            self.scanner_combo["values"] = names
            if names:
                self.scanner_var.set(names[0])
        # results table
        for r in self.students_results:
            self._insert_result_row(r)
        if self.students_results:
            n = self.num_questions.get()
            avg = sum(r["score"] for r in self.students_results) / len(self.students_results)
            avg_lbl = "المتوسط" if LANG["ar"] else "Avg"
            max_lbl = "أعلى درجة" if LANG["ar"] else "Max"
            min_lbl = "أدنى درجة" if LANG["ar"] else "Min"
            total_lbl = "إجمالي الأوراق" if LANG["ar"] else "Total"
            self.summary_var.set(
                f"  {total_lbl}: {len(self.students_results)}  |  "
                f"{avg_lbl}: {avg:.1f}/{n}  |  "
                f"{max_lbl}: {max(r['score'] for r in self.students_results)}  |  "
                f"{min_lbl}: {min(r['score'] for r in self.students_results)}")

    def _insert_result_row(self, result):
        n = result["n"]
        pct = result["pct"]
        idx = result["idx"]
        tag = "pass" if pct >= 50 else "fail"
        self.tree.insert("", "end",
            values=(idx, result["file"], f"{result['score']}/{n}",
                    result["score"], result["wrong"], f"{pct}%"),
            tags=(tag,))

    # ------------------------------------------------------------------
    #  KEY HELPERS (same logic, just re-styled widgets)
    # ------------------------------------------------------------------
    def _update_key_status(self):
        n = self.num_questions.get()
        filled = sum(1 for q in range(1, n+1) if self.answer_key.get(q))
        if filled == n:
            self.key_status_var.set(f"✔  {T('save_key')} — {n} {'سؤال' if LANG['ar'] else 'Qs'}")
            self.key_status_lbl.config(bg=PALETTE["success_lt"], fg=PALETTE["success"])
        elif filled > 0:
            self.key_status_var.set(f"◑  {filled} / {n}")
            self.key_status_lbl.config(bg=PALETTE["warning_lt"], fg=PALETTE["warning"])
        else:
            self.key_status_var.set("⚠  " + T("key_not_loaded"))
            self.key_status_lbl.config(bg=PALETTE["danger_lt"], fg=PALETTE["danger"])

    def _scan_answer_key(self):
        scanner = self._get_selected_scanner()
        if not scanner:
            messagebox.showerror("خطأ" if LANG["ar"] else "Error",
                                 "اختر سكانر أولاً!" if LANG["ar"] else "Select a scanner first!")
            return
        self.scan_key_btn.config(
            text=("⏳ " + T("scanning")), state="disabled")
        self.root.update()
        try:
            img = scan_image(scanner, dpi=self.dpi_var.get(), window=self.root)
            if img is None:
                messagebox.showerror("خطأ" if LANG["ar"] else "Error",
                                     "لم يتم استلام صورة!" if LANG["ar"] else "No image received!")
                return
            self._extract_key_from_image(img)
        except Exception as e:
            messagebox.showerror("Scanner Error", str(e))
        finally:
            self.scan_key_btn.config(text=T("scan_key"), state="normal")

    def _load_key_from_image(self):
        path = filedialog.askopenfilename(
            title="اختر صورة ورقة الإجابة" if LANG["ar"] else "Select answer sheet image",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp")])
        if not path:
            return
        img = cv2.imread(path)
        if img is None:
            messagebox.showerror("Error", "Cannot open image")
            return
        self._extract_key_from_image(img)

    def _extract_key_from_image(self, img):
        n = self.num_questions.get()
        answers, err = read_bubble_sheet(img, n)
        if err:
            messagebox.showerror("Error", err)
            return
        found = sum(1 for v in answers.values() if v != "؟")
        if found < n // 2:
            q = messagebox.askyesno(
                "تحذير" if LANG["ar"] else "Warning",
                f"{'تم قراءة' if LANG['ar'] else 'Only'} {found} {'إجابة فقط من' if LANG['ar'] else 'answers of'} {n}.\n"
                f"{'هل تريد المتابعة؟' if LANG['ar'] else 'Continue anyway?'}")
            if not q:
                return
        self.answer_key = {q: v for q, v in answers.items() if v != "؟"}
        self._save_key_to_file()
        for q, var in self.key_vars.items():
            var.set(self.answer_key.get(q, ""))
        self._update_key_status()
        self._show_key_preview(answers, n)

    def _show_key_preview(self, answers, n):
        win = tk.Toplevel(self.root)
        win.title(T("key_card") + " — " + ("مراجعة مفتاح الإجابة" if LANG["ar"] else "Review Answer Key"))
        win.geometry("520x580")
        win.configure(bg=PALETTE["surface"])
        win.grab_set()

        found = sum(1 for v in answers.values() if v != "؟")
        hdr = tk.Frame(win, bg=PALETTE["success"], height=52)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text=f"✔  {found} / {n}",
                 font=get_font(14, bold=True),
                 bg=PALETTE["success"], fg="white").pack(pady=12)

        tk.Label(win,
                 text=("يرجى مراجعة الإجابات وتعديلها يدوياً عند الحاجة"
                       if LANG["ar"] else "Please review the answers and edit manually if needed"),
                 font=get_font(10), bg=PALETTE["surface"],
                 fg=PALETTE["muted"]).pack(pady=(8, 4))

        frame = tk.Frame(win, bg=PALETTE["surface"])
        frame.pack(fill="both", expand=True, padx=10, pady=5)
        canvas = tk.Canvas(frame, bg=PALETTE["surface"], highlightthickness=0)
        sb = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=PALETTE["surface"])
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="ne" if LANG["ar"] else "nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side=self.side_right(), fill="both", expand=True)
        sb.pack(side=self.side_left(), fill="y")

        hdr_labels = (["Q", "Ans", "Q", "Ans", "Q", "Ans"]
                      if not LANG["ar"] else
                      ["السؤال", "الإجابة", "السؤال", "الإجابة", "السؤال", "الإجابة"])
        for ci, lbl in enumerate(hdr_labels):
            grid_col = (5 - ci) if LANG["ar"] else ci
            tk.Label(inner, text=lbl, font=get_font(9, bold=True),
                     bg=PALETTE["bg"], width=9,
                     relief="flat", padx=4, pady=4).grid(
                row=0, column=grid_col, padx=1, pady=1)

        cols = 3
        for i, q in enumerate(range(1, n+1)):
            row = (i // cols) + 1
            col_base = (i % cols) * 2
            ans = answers.get(q, "؟")
            bg = PALETTE["success_lt"] if ans != "؟" else PALETTE["danger_lt"]
            qtext = f"Q{q}" if not LANG["ar"] else f"س {q}"
            
            if LANG["ar"]:
                col_q = 5 - col_base
                col_ans = 5 - (col_base + 1)
            else:
                col_q = col_base
                col_ans = col_base + 1

            tk.Label(inner, text=qtext, font=get_font(10),
                     bg=bg, width=9, padx=4, pady=5).grid(
                row=row, column=col_q, padx=1, pady=1, sticky="nsew")
            tk.Label(inner, text=ans,
                     font=get_font(12, bold=True), bg=bg,
                     fg=PALETTE["success"] if ans != "؟" else PALETTE["danger"],
                     width=9, padx=4, pady=5).grid(
                row=row, column=col_ans, padx=1, pady=1, sticky="nsew")

        self._btn(win, text=("✔  " + ("تأكيد ومتابعة" if LANG["ar"] else "Confirm & Continue")),
                  color=PALETTE["success"], size=12, pady=10,
                  command=win.destroy).pack(pady=10, padx=20, fill="x")

    def _refresh_scanners(self):
        self.root.update_idletasks()
        self.root.update()
        self._scanners_list = get_scanners(window=self.root)
        print(f"[DEBUG] scanners: {self._scanners_list}")

        if self._scanners_list:
            names = [f"[{s['type']}] {s['name']}" for s in self._scanners_list]
            self.scanner_combo["values"] = names
            self.scanner_var.set(names[0])
            self.scan_btn.config(state="normal")
            self.cont_btn.config(state="normal")
        else:
            self.scanner_combo["values"] = [T("no_scanner")]
            self.scanner_var.set(T("no_scanner"))
            self.scan_btn.config(state="disabled")
            self.cont_btn.config(state="disabled")
            messagebox.showwarning(
                "تنبيه" if LANG["ar"] else "Warning",
                ("مش لاقي سكانر.\n\nتأكد من:\n1- السكانر متوصل ومشغول\n"
                 "2- درايفر الشركة مثبت\n3- pywin32 مثبت: pip install pywin32")
                if LANG["ar"] else
                ("No scanner found.\n\nMake sure:\n1- Scanner is connected and on\n"
                 "2- Manufacturer driver is installed\n3- pywin32 installed: pip install pywin32"))

    def _build_key_grid(self):
        for w in self.key_inner.winfo_children():
            w.destroy()
        self.key_vars = {}
        n = self.num_questions.get()

        choices = ["أ", "ب", "ج", "د"]
        headers = ["س"] + choices if LANG["ar"] else ["Q"] + choices
        for col, label in enumerate(headers):
            grid_col = (4 - col) if LANG["ar"] else col
            tk.Label(self.key_inner, text=label,
                     font=get_font(9, bold=True),
                     bg=PALETTE["bg"],
                     fg=PALETTE["text2"],
                     width=4, relief="flat").grid(
                row=0, column=grid_col, padx=1, pady=1)

        for q in range(1, n+1):
            var = tk.StringVar(value=self.answer_key.get(q, ""))
            self.key_vars[q] = var
            bg = PALETTE["surface"] if q % 2 == 0 else PALETTE["bg"]
            qtext = str(q)
            grid_col_lbl = 4 if LANG["ar"] else 0
            tk.Label(self.key_inner, text=qtext,
                     font=get_font(9), bg=bg,
                     fg=PALETTE["text2"], width=4).grid(
                row=q, column=grid_col_lbl, padx=1, pady=1)
            for ci, ch in enumerate(choices):
                grid_col_choice = (3 - ci) if LANG["ar"] else (ci + 1)
                tk.Radiobutton(
                    self.key_inner, text=ch, variable=var, value=ch,
                    font=get_font(9), bg=bg,
                    selectcolor=PALETTE["primary"],
                    fg=PALETTE["text"],
                    activebackground=bg,
                    relief="flat"
                ).grid(row=q, column=grid_col_choice, padx=1, pady=1)

    def _refresh_key_grid(self):
        self._build_key_grid()

    def _save_key(self):
        n = self.num_questions.get()
        for q in range(1, n+1):
            val = self.key_vars[q].get()
            if val:
                self.answer_key[q] = val
        self._save_key_to_file()
        self._update_key_status()
        messagebox.showinfo(
            "تم" if LANG["ar"] else "Saved",
            "✔  " + ("تم حفظ مفتاح الإجابة!" if LANG["ar"] else "Answer key saved!"))

    def _clear_key(self):
        for var in self.key_vars.values():
            var.set("")
        self.answer_key = {}
        self._update_key_status()

    # ------------------------------------------------------------------
    def _validate_key(self):
        n = self.num_questions.get()
        missing = [q for q in range(1, n+1) if not self.answer_key.get(q)]
        if missing:
            return messagebox.askyesno(
                "تحذير" if LANG["ar"] else "Warning",
                (f"مفتاح الإجابة ناقص في {len(missing)} سؤال.\nهل تريد المتابعة؟"
                 if LANG["ar"] else
                 f"Answer key missing {len(missing)} questions.\nContinue anyway?"))
        return True

    def _show_and_confirm_scan(self, img, name):
        current_img = [img]
        preview_win = tk.Toplevel(self.root)
        preview_win.title(f"{'معاينة المسح' if LANG['ar'] else 'Scan Preview'} — {name}")
        preview_win.configure(bg=PALETTE["surface"])
        preview_win.grab_set()

        hdr = tk.Frame(preview_win, bg=PALETTE["accent"], height=50)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr,
                 text=("📸  معاينة الصورة المسحوبة"
                       if LANG["ar"] else "📸  Scanned image preview"),
                 font=get_font(13, bold=True),
                 bg=PALETTE["accent"], fg="white").pack(pady=12)

        img_label = tk.Label(preview_win, bg=PALETTE["surface"])
        img_label.pack(padx=10, pady=10)
        photo_ref = [None]

        def update_preview():
            img_display = cv2.cvtColor(current_img[0], cv2.COLOR_BGR2RGB)
            max_w, max_h = 700, 600
            h, w = img_display.shape[:2]
            scale = min(max_w / w, max_h / h, 1.0)
            nw, nh = int(w*scale), int(h*scale)
            img_display = cv2.resize(img_display, (nw, nh))
            pil_img = Image.fromarray(img_display)
            photo = ImageTk.PhotoImage(pil_img)
            img_label.config(image=photo)
            photo_ref[0] = photo
            preview_win.geometry(f"{nw + 40}x{nh + 220}")
            preview_win.update()

        update_preview()

        tk.Label(preview_win,
                 text=("هل الصورة واضحة؟ يمكنك شقلبتها إذا كانت مقلوبة."
                       if LANG["ar"] else
                       "Is the image clear? Rotate if it appears upside down."),
                 font=get_font(10), bg=PALETTE["surface"],
                 fg=PALETTE["muted"]).pack(padx=10, pady=(0, 6))

        btn_frame = tk.Frame(preview_win, bg=PALETTE["surface"])
        btn_frame.pack(fill="x", padx=10, pady=(0, 12))
        result = [False]

        def on_accept():
            result[0] = True
            preview_win.destroy()

        def on_reject():
            result[0] = False
            preview_win.destroy()

        def on_rotate():
            current_img[0] = cv2.rotate(current_img[0], cv2.ROTATE_180)
            update_preview()

        self._btn(btn_frame,
                  text=("✔  " + ("الصورة ممتازة" if LANG["ar"] else "Looks good")),
                  color=PALETTE["success"], size=11, pady=8,
                  command=on_accept).pack(side="right", padx=5)

        self._btn(btn_frame,
                  text=("⟳  " + ("شقلب 180°" if LANG["ar"] else "Rotate 180°")),
                  color=PALETTE["warning"], size=11, pady=8,
                  command=on_rotate).pack(side="right", padx=5)

        self._btn(btn_frame,
                  text=("✕  " + ("أعد المسح" if LANG["ar"] else "Rescan")),
                  color=PALETTE["danger"], size=11, pady=8,
                  command=on_reject).pack(side="right", padx=5)

        preview_win.resizable(False, False)
        self.root.wait_window(preview_win)
        return result[0], current_img[0]

    def _calibrate_detection(self):
        path = filedialog.askopenfilename(
            title=("تحميل صورة ورقة الإجابة للمعايرة" if LANG["ar"] else "Select answer sheet image"),
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp")])
        if not path:
            return

        img = cv2.imread(path)
        if img is None:
            messagebox.showerror("Error", "Cannot open image")
            return

        n = 81
        img_proc = img.copy()
        target_h2, target_w2 = TARGET_H, TARGET_W
        orig_h, orig_w = img_proc.shape[:2]
        if orig_h != target_h2 or orig_w != target_w2:
            img_proc = cv2.resize(img_proc, (target_w2, target_h2), interpolation=cv2.INTER_AREA)
        img_proc = _correct_perspective(img_proc, target_w2, target_h2)
        gray = cv2.cvtColor(img_proc, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)

        _AGAP = 15
        _AMAX = 185

        cal_data = {}
        for sec in COL_SECTIONS:
            col_xs = sec["xs"]
            for row_idx, q_num in enumerate(sec["qs"]):
                if q_num > n:
                    continue
                cy = QUESTION_YS[row_idx]
                bubble_vals = {ch: _sample_bubble(gray, cx, cy) for ch, cx in col_xs.items()}
                row_vals = list(bubble_vals.values())
                row_mean = float(np.mean(row_vals))
                darkest_choice = min(bubble_vals, key=bubble_vals.get)
                darkest_val    = bubble_vals[darkest_choice]
                gap = row_mean - darkest_val
                is_filled = gap >= _AGAP and darkest_val <= _AMAX
                if is_filled:
                    conf = "high" if gap >= 40 else ("medium" if gap >= 22 else "low")
                    cal_data[q_num] = {"answer": darkest_choice, "gap": gap,
                                       "confidence": conf, "vals": bubble_vals}
                else:
                    cal_data[q_num] = {"answer": "؟", "gap": gap,
                                       "confidence": "none", "vals": bubble_vals}

        detected  = sum(1 for d in cal_data.values() if d["answer"] != "؟")
        high_conf = sum(1 for d in cal_data.values() if d["confidence"] == "high")
        med_conf  = sum(1 for d in cal_data.values() if d["confidence"] == "medium")
        low_conf  = sum(1 for d in cal_data.values() if d["confidence"] == "low")
        unanswered = [q for q, d in cal_data.items() if d["answer"] == "؟"]

        # Results window
        win = tk.Toplevel(self.root)
        win.title("تقرير معايرة الكشف والتعرف ضوئياً" if LANG["ar"] else "Calibration Report")
        win.geometry("660x640")
        win.configure(bg=PALETTE["surface"])
        win.grab_set()

        hdr_color = (PALETTE["success"] if detected >= 70
                     else (PALETTE["warning"] if detected >= 50 else PALETTE["danger"]))
        hdr = tk.Frame(win, bg=hdr_color, height=58)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        icon2 = "✔" if detected >= 70 else ("◑" if detected >= 50 else "✕")
        tk.Label(hdr, text=f"{icon2}   {detected} / {n}",
                 font=get_font(15, bold=True),
                 bg=hdr_color, fg="white").pack(pady=16)

        stat_frame = tk.Frame(win, bg=PALETTE["surface"])
        stat_frame.pack(fill="x", padx=16, pady=12)

        labels_ar = ["درجة مطابقة عالية:", "درجة مطابقة متوسطة:", "درجة مطابقة منخفضة:", "غير مكتشف (لم يتم التعرف عليه):"]
        labels_en = ["High confidence:", "Med confidence:", "Low confidence:", "Undetected:"]
        labels = labels_ar if LANG["ar"] else labels_en
        vals   = [high_conf, med_conf, low_conf, len(unanswered)]
        colors = [PALETTE["success"], PALETTE["warning"], PALETTE["danger"], PALETTE["muted"]]

        for txt, val, color in zip(labels, vals, colors):
            row = tk.Frame(stat_frame, bg=PALETTE["surface"])
            row.pack(fill="x", pady=2)
            tk.Label(row, text=txt, font=get_font(10), bg=PALETTE["surface"],
                     fg=PALETTE["text2"], anchor="e" if LANG["ar"] else "w", width=30).pack(side=self.side_right(), padx=6)
            # pill badge
            badge = tk.Frame(row, bg=color)
            badge.pack(side=self.side_right(), padx=6)
            tk.Label(badge, text=f" {val} ",
                     font=get_font(10, bold=True),
                     bg=color, fg="white", padx=4, pady=2).pack()

        if unanswered:
            tk.Frame(win, bg=PALETTE["border"], height=1).pack(fill="x", padx=10)
            q_list = ", ".join(f"س{q}" if LANG["ar"] else f"Q{q}"
                               for q in sorted(unanswered))
            tk.Label(win, text=q_list,
                     font=get_font(9), bg=PALETTE["surface"],
                     fg=PALETTE["muted"],
                     wraplength=600, justify="right" if LANG["ar"] else "left").pack(fill="x", padx=16, pady=6)

        # Detail scrollable table
        tk.Frame(win, bg=PALETTE["border"], height=1).pack(fill="x", padx=10)

        table_frame = tk.Frame(win, bg=PALETTE["surface"])
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)
        canvas2 = tk.Canvas(table_frame, bg=PALETTE["surface"], highlightthickness=0)
        sb2 = ttk.Scrollbar(table_frame, orient="vertical", command=canvas2.yview)
        inner2 = tk.Frame(canvas2, bg=PALETTE["surface"])
        inner2.bind("<Configure>",
                    lambda e: canvas2.configure(scrollregion=canvas2.bbox("all")))
        canvas2.create_window((0, 0), window=inner2, anchor="ne" if LANG["ar"] else "nw")
        canvas2.configure(yscrollcommand=sb2.set)
        canvas2.pack(side=self.side_right(), fill="both", expand=True)
        sb2.pack(side=self.side_left(), fill="y")

        conf_bgs = {"high": PALETTE["success_lt"], "medium": PALETTE["warning_lt"],
                    "low": PALETTE["danger_lt"],  "none": PALETTE["bg"]}
        conf_fg  = {"high": PALETTE["success"],    "medium": PALETTE["warning"],
                    "low": PALETTE["danger"],       "none": PALETTE["muted"]}
        conf_labels_ar = {"high": "ثقة عالية ✔", "medium": "ثقة متوسطة",
                          "low": "ثقة منخفضة", "none": "—"}
        conf_labels_en = {"high": "high ✔", "medium": "medium",
                          "low": "low", "none": "—"}
        clabels = conf_labels_ar if LANG["ar"] else conf_labels_en

        hdrs = (["رقم السؤال","الإجابة المكتشفة","مستوى التباين","مستوى الثقة"] if LANG["ar"]
                else ["Q","Answer","Gap","Confidence"])

        def get_cal_grid_col(sec_idx, field_idx):
            if LANG["ar"]:
                actual_sec = 1 - sec_idx
                actual_field = 3 - field_idx
            else:
                actual_sec = sec_idx
                actual_field = field_idx
            return actual_sec * 4 + actual_field

        COLS2 = 2
        for sec_idx in range(COLS2):
            for field_idx, lbl in enumerate(hdrs):
                grid_col = get_cal_grid_col(sec_idx, field_idx)
                tk.Label(inner2, text=lbl, font=get_font(9, bold=True),
                         bg=PALETTE["bg"], width=11 if LANG["ar"] else 10,
                         relief="flat", padx=4, pady=4).grid(
                    row=0, column=grid_col, padx=1, pady=1)

        for i, q in enumerate(range(1, n+1)):
            d = cal_data.get(q, {"answer": "؟", "gap": 0, "confidence": "none"})
            bg2 = conf_bgs[d["confidence"]]
            fg2 = conf_fg[d["confidence"]]
            sec_idx = i % COLS2
            base_row = (i // COLS2) + 1
            qtext = f"س{q}" if LANG["ar"] else f"Q{q}"
            
            fields = [
                (qtext, 6),
                (d["answer"], 5),
                (f"{d['gap']:.1f}", 6),
                (clabels[d["confidence"]], 11 if LANG["ar"] else 10)
            ]
            for field_idx, (txt2, w2) in enumerate(fields):
                fg_cell = fg2 if field_idx == 3 else PALETTE["text"]
                grid_col = get_cal_grid_col(sec_idx, field_idx)
                tk.Label(inner2, text=txt2, font=get_font(9),
                         bg=bg2, fg=fg_cell, width=w2,
                         padx=3, pady=4).grid(
                    row=base_row, column=grid_col,
                    padx=1, pady=1, sticky="nsew")

        # Tip
        tip_frame = tk.Frame(win, bg=PALETTE["primary_lt"])
        tip_frame.pack(fill="x", padx=10, pady=6)
        tip = (("💡 عملية الكشف والتعرف ممتازة جداً!" if detected >= 75
                else ("💡 يوصى برفع دقة المسح (DPI) إلى 300 أو أكثر لتحسين النتائج" if detected >= 55
                      else "💡 يرجى التأكد من جودة الإضاءة، ووضع الورقة بشكل مستوٍ تماماً، ودقة مسح DPI لا تقل عن 300"))
               if LANG["ar"] else
               ("💡 Detection is excellent!" if detected >= 75
                else ("💡 Try increasing DPI to 300+" if detected >= 55
                      else "💡 Ensure good lighting, flat paper, DPI ≥ 300")))
        tk.Label(tip_frame, text=tip, font=get_font(10),
                 bg=PALETTE["primary_lt"], fg=PALETTE["primary"],
                 wraplength=600, justify="right" if LANG["ar"] else "left",
                 anchor="e" if LANG["ar"] else "w",
                 padx=10, pady=8).pack(fill="x")

        self._btn(win, text=("إغلاق" if LANG["ar"] else "Close"),
                  color=PALETTE["muted"], size=10, bold=False,
                  pady=6, padx=20, command=win.destroy).pack(pady=(0, 10))

    def _get_selected_scanner(self):
        if not self._scanners_list:
            return None
        idx = self.scanner_combo.current()
        if idx < 0 or idx >= len(self._scanners_list):
            return None
        return self._scanners_list[idx]

    # ---- SCANNER METHODS ----

    def _scan_and_grade(self):
        if not self._validate_key():
            return
        scanner = self._get_selected_scanner()
        if not scanner:
            messagebox.showerror("Error", T("no_scanner"))
            return
        self.scan_btn.config(text="⏳  " + T("scanning"), state="disabled")
        self.root.update()
        try:
            img = scan_image(scanner, dpi=self.dpi_var.get(), window=self.root)
            if img is None:
                messagebox.showerror("Error",
                    "لم يتم استلام صورة" if LANG["ar"] else "No image received")
                return
            self.scan_counter += 1
            name = f"{'سكان' if LANG['ar'] else 'Scan'} #{self.scan_counter}"
            ok, final_img = self._show_and_confirm_scan(img, name)
            if ok:
                self._process_image_array(final_img, name)
        except Exception as e:
            messagebox.showerror("Scanner Error", str(e))
        finally:
            self.scan_btn.config(text=T("scan_grade"), state="normal")

    def _scan_continuous(self):
        if not self._validate_key():
            return
        scanner = self._get_selected_scanner()
        if not scanner:
            messagebox.showerror("Error", T("no_scanner"))
            return

        win = tk.Toplevel(self.root)
        win.title(T("scan_batch"))
        win.geometry("340x190")
        win.grab_set()
        win.configure(bg=PALETTE["surface"])

        hdr2 = tk.Frame(win, bg=PALETTE["accent"], height=48)
        hdr2.pack(fill="x")
        hdr2.pack_propagate(False)
        tk.Label(hdr2, text=T("scan_batch"),
                 font=get_font(13, bold=True),
                 bg=PALETTE["accent"], fg="white").pack(pady=12)

        count_var = tk.StringVar(
            value=("تم سكان: 0 ورقة" if LANG["ar"] else "Scanned: 0 sheets"))
        tk.Label(win, textvariable=count_var,
                 font=get_font(12, bold=True),
                 bg=PALETTE["surface"],
                 fg=PALETTE["primary"]).pack(pady=12)

        scanned = [0]

        def do_scan():
            try:
                img = scan_image(scanner, dpi=self.dpi_var.get(), window=self.root)
                if img is None:
                    messagebox.showerror("Error",
                        "لم يتم استلام صورة" if LANG["ar"] else "No image received",
                        parent=win)
                    return
                self.scan_counter += 1
                name = f"{'سكان' if LANG['ar'] else 'Scan'} #{self.scan_counter}"
                ok, final_img = self._show_and_confirm_scan(img, name)
                if ok:
                    self._process_image_array(final_img, name)
                    scanned[0] += 1
                count_var.set(
                    f"{'تم سكان:' if LANG['ar'] else 'Scanned:'} {scanned[0]} "
                    f"{'ورقة' if LANG['ar'] else 'sheets'}")
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=win)

        btn2 = tk.Frame(win, bg=PALETTE["surface"])
        btn2.pack(pady=6)

        self._btn(btn2,
                  text=("📄  " + ("سكان التالي" if LANG["ar"] else "Scan Next")),
                  color=PALETTE["primary"], size=12, pady=8,
                  command=do_scan).pack(side="right", padx=8)

        self._btn(btn2,
                  text=("✔  " + ("انتهيت" if LANG["ar"] else "Done")),
                  color=PALETTE["success"], size=12, pady=8,
                  command=win.destroy).pack(side="right", padx=8)

    # ---- FILE METHODS ----

    def _grade_single(self):
        if not self._validate_key():
            return
        path = filedialog.askopenfilename(
            title=("اختر صورة" if LANG["ar"] else "Select image"),
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp")])
        if not path:
            return
        self._process_image(path)

    def _grade_batch(self):
        if not self._validate_key():
            return
        folder = filedialog.askdirectory(
            title=("اختر المجلد" if LANG["ar"] else "Select folder"))
        if not folder:
            return
        images = [os.path.join(folder, f) for f in os.listdir(folder)
                  if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp"))]
        if not images:
            messagebox.showerror("Error",
                "لا توجد صور!" if LANG["ar"] else "No images found!")
            return

        prog_win = tk.Toplevel(self.root)
        prog_win.title("Processing..." if not LANG["ar"] else "جارٍ التصحيح...")
        prog_win.geometry("380x130")
        prog_win.configure(bg=PALETTE["surface"])
        prog_win.grab_set()
        tk.Label(prog_win,
                 text=("جارٍ تصحيح الأوراق..." if LANG["ar"] else "Grading sheets..."),
                 font=get_font(12), bg=PALETTE["surface"]).pack(pady=12)
        prog = ttk.Progressbar(prog_win, maximum=len(images), length=320)
        prog.pack(pady=4)
        status_lbl = tk.Label(prog_win, text="",
                               font=get_font(9), bg=PALETTE["surface"],
                               fg=PALETTE["muted"])
        status_lbl.pack()

        for i, path in enumerate(images):
            status_lbl.config(text=os.path.basename(path))
            prog["value"] = i + 1
            prog_win.update()
            self._process_image(path, silent=True)

        prog_win.destroy()
        n_done = len(images)
        recent = self.students_results[-n_done:]
        avg = sum(r["score"] for r in recent) / n_done
        messagebox.showinfo(
            "✔  " + ("تم" if LANG["ar"] else "Done"),
            (f"تم تصحيح {n_done} ورقة بنجاح.\nمتوسط الدرجات: {avg:.1f} / {self.num_questions.get()}"
             if LANG["ar"] else
             f"Graded {n_done} sheets\nAverage: {avg:.1f} / {self.num_questions.get()}"))

    def _process_image(self, path, silent=False):
        n = self.num_questions.get()
        answers, err = read_bubble_sheet(path, n)
        if err:
            if not silent:
                messagebox.showerror("Error", err)
            return
        self._add_result(os.path.basename(path), answers)

    def _process_image_array(self, img, name):
        n = self.num_questions.get()
        answers, err = read_bubble_sheet(img, n)
        if err:
            messagebox.showerror("Error", err)
            return
        self._add_result(name, answers)

    def _add_result(self, name, answers):
        n = self.num_questions.get()
        score, details = grade(answers, self.answer_key, n)
        wrong = sum(1 for d in details if not d["ok"] and d["correct"])
        pct = round(score / n * 100) if n > 0 else 0
        idx = len(self.students_results) + 1

        result = {"idx": idx, "file": name, "score": score,
                  "wrong": wrong, "pct": pct, "details": details, "n": n}
        self.students_results.append(result)

        tag = "pass" if pct >= 50 else "fail"
        iid = self.tree.insert("", "end",
            values=(idx, name, f"{score}/{n}", score, wrong, f"{pct}%"),
            tags=(tag,))

        total = len(self.students_results)
        avg = sum(r["score"] for r in self.students_results) / total
        self.summary_var.set(
            f"  {'إجمالي الأوراق' if LANG['ar'] else 'Total'}: {total}  |  "
            f"{'متوسط الدرجات' if LANG['ar'] else 'Avg'}: {avg:.1f}/{n}  |  "
            f"{'أعلى درجة' if LANG['ar'] else 'Max'}: {max(r['score'] for r in self.students_results)}  |  "
            f"{'أدنى درجة' if LANG['ar'] else 'Min'}: {min(r['score'] for r in self.students_results)}")

        self.tree.see(iid)
        self.tree.selection_set(iid)

    def _on_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        idx = self.tree.index(sel[0])
        if idx >= len(self.students_results):
            return
        result = self.students_results[idx]

        self.detail_text.config(state="normal")
        self.detail_text.delete("1.0", "end")

        sep_line = "─" * 52 + "\n"
        file_lbl = "اسم الملف / الورقة" if LANG["ar"] else "Sheet"
        score_lbl = "الدرجة المستحقة" if LANG["ar"] else "Score"
        header = f"{file_lbl}: {result['file']}    {score_lbl}: {result['score']}/{result['n']}  ({result['pct']}%)\n"
        self.detail_text.insert("end", header, "head")
        self.detail_text.insert("end", sep_line)

        wrongs = [d for d in result["details"] if not d["ok"] and d["correct"]]
        wrong_lbl = "الإجابات الخاطئة" if LANG["ar"] else "Wrong answers"
        answered_lbl = "إجابة الطالب" if LANG["ar"] else "student"
        correct_lbl  = "الإجابة الصحيحة" if LANG["ar"] else "key"

        if wrongs:
            self.detail_text.insert("end",
                f"\n✕  {wrong_lbl} ({len(wrongs)}):\n", "err")
            for d in wrongs:
                self.detail_text.insert("end",
                    f"  {'س' if LANG["ar"] else 'Q'}{d['q']:3d}:  "
                    f"{answered_lbl}=({d['student']})  {correct_lbl}=({d['correct']})\n",
                    "err")
        else:
            all_ok = "✔  عمل رائع! جميع الإجابات صحيحة تماماً." if LANG["ar"] else "✔  All answers correct!"
            self.detail_text.insert("end", f"\n{all_ok}\n", "ok")

        all_lbl = "تفاصيل جميع الأسئلة" if LANG["ar"] else "All answers"
        self.detail_text.insert("end", "\n" + sep_line + f"{all_lbl}:\n")
        line = ""
        for d in result["details"]:
            mark = "✓" if d["ok"] else "✗"
            q_prefix = "س" if LANG["ar"] else "Q"
            line += f"  {q_prefix}{d['q']:2d}:{d['student']}{mark}"
            if d["q"] % 8 == 0:
                self.detail_text.insert("end", line + "\n")
                line = ""
        if line:
            self.detail_text.insert("end", line + "\n")

        self.detail_text.tag_configure("align", justify="right" if LANG["ar"] else "left")
        self.detail_text.tag_add("align", "1.0", "end")
        self.detail_text.config(state="disabled")

    def _clear_results(self):
        confirm_msg = ("هل تريد مسح جميع النتائج؟"
                       if LANG["ar"] else "Clear all results?")
        if messagebox.askyesno("تأكيد" if LANG["ar"] else "Confirm", confirm_msg):
            self.students_results = []
            for item in self.tree.get_children():
                self.tree.delete(item)
            self.summary_var.set("")
            self.scan_counter = 0

    def _export(self):
        if not self.students_results:
            messagebox.showinfo("",
                "لا توجد نتائج للتصدير!" if LANG["ar"] else "No results to export!")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            title=("حفظ النتائج" if LANG["ar"] else "Save results"))
        if not path:
            return
        n = self.num_questions.get()
        with open(path, "w", encoding="utf-8-sig") as f:
            q_headers = ",".join(
                [f"{'س' if LANG['ar'] else 'Q'}{q}" for q in range(1, n+1)])
            f.write(f"#,{'الملف' if LANG['ar'] else 'File'},"
                    f"{'الدرجة' if LANG['ar'] else 'Score'},"
                    f"{'النسبة' if LANG['ar'] else 'Pct'},"
                    f"{q_headers}\n")
            for r in self.students_results:
                ans_str = ",".join([d["student"] for d in r["details"]])
                f.write(f"{r['idx']},{r['file']},{r['score']},{r['pct']}%,{ans_str}\n")
        messagebox.showinfo(
            "✔  " + ("تم" if LANG["ar"] else "Saved"),
            (f"تم حفظ النتائج:\n{path}" if LANG["ar"]
             else f"Results saved:\n{path}"))


# ===================== ACTIVATION WINDOW =====================

class ActivationWindow:
    """
    Shown at startup when no valid license is found.
    Blocks the main app until activation succeeds.
    """

    def __init__(self, root: tk.Tk):
        self.root   = root
        self.passed = False
        self._hwid  = get_hwid()

        root.title("Scanly — تفعيل البرنامج")
        root.geometry("620x560")
        root.configure(bg="#F8FAFC")
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build()

    # ------------------------------------------------------------------ build
    def _build(self):
        BG      = "#F8FAFC"
        SURFACE = "#FFFFFF"
        BORDER  = "#E2E8F0"
        PRIMARY = "#4D4D4D"
        SUCCESS = "#10B981"
        DANGER  = "#EF4444"
        TEXT    = "#0F172A"
        TEXT2   = "#475569"
        FONT    = "Dubai"

        def hc(c, f=0.82):
            r,g,b = int(c[1:3],16), int(c[3:5],16), int(c[5:7],16)
            return "#{:02x}{:02x}{:02x}".format(int(r*f),int(g*f),int(b*f))

        # Header
        hdr = tk.Frame(self.root, bg=PRIMARY, height=64)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="🔒  Scanly — تفعيل البرنامج",
                 font=(FONT, 16, "bold"), bg=PRIMARY, fg="white"
                 ).pack(side="right", padx=20, pady=14)

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=30, pady=20)

        # ── Lock icon / subtitle ──────────────────────────────────────────
        tk.Label(body, text="🔒",
                 font=("Segoe UI Emoji", 36),
                 bg=BG, fg=TEXT).pack(pady=(0, 6))
        tk.Label(body,
                 text="البرنامج يحتاج إلى ترخيص لتشغيله",
                 font=(FONT, 12), bg=BG, fg=TEXT2).pack(pady=(0, 20))

        # ── HWID card ────────────────────────────────────────────────────
        hwid_card = tk.Frame(body, bg=SURFACE,
                             highlightthickness=1,
                             highlightbackground=BORDER)
        hwid_card.pack(fill="x", pady=(0, 16))

        tk.Label(hwid_card,
                 text="رقم جهازك (أرسله للبائع للحصول على كود التفعيل)",
                 font=(FONT, 9), bg=SURFACE, fg=TEXT2,
                 anchor="e", padx=12, pady=8
                 ).pack(fill="x")

        hwid_row = tk.Frame(hwid_card, bg=SURFACE)
        hwid_row.pack(fill="x", padx=12, pady=(4, 10))

        tk.Label(hwid_row, text=self._hwid,
                 font=(FONT, 14, "bold"),
                 bg=SURFACE, fg=SUCCESS,
                 anchor="e").pack(side="right", expand=True)

        copy_btn = tk.Button(hwid_row, text="📋 نسخ",
                             font=(FONT, 9),
                             bg="#E2E8F0", fg=TEXT2,
                             activebackground="#CBD5E1",
                             relief="flat", cursor="hand2",
                             padx=10, pady=4,
                             command=self._copy_hwid)
        copy_btn.pack(side="left", padx=(0, 0))

        # ── License key input ─────────────────────────────────────────────
        tk.Label(body, text="أدخل كود التفعيل:",
                 font=(FONT, 10, "bold"),
                 bg=BG, fg=TEXT2, anchor="e"
                 ).pack(fill="x", pady=(0, 6))

        self.key_var = tk.StringVar()
        key_frame = tk.Frame(body, bg=SURFACE,
                             highlightthickness=1,
                             highlightbackground=BORDER)
        key_frame.pack(fill="x", pady=(0, 6))
        key_entry = tk.Entry(key_frame, textvariable=self.key_var,
                             font=(FONT, 13, "bold"),
                             bg=SURFACE, fg=TEXT,
                             insertbackground=TEXT,
                             relief="flat", bd=0,
                             justify="center")
        key_entry.pack(fill="x", ipady=10, padx=10)
        key_entry.bind("<Return>", lambda e: self._activate())

        # ── Status ────────────────────────────────────────────────────────
        self.status_var = tk.StringVar(value="")
        self.status_lbl = tk.Label(body, textvariable=self.status_var,
                                   font=(FONT, 10, "bold"),
                                   bg=BG, fg=DANGER,
                                   anchor="center")
        self.status_lbl.pack(fill="x", pady=(0, 10))

        # ── Activate button ───────────────────────────────────────────────
        act_btn = tk.Button(body,
                            text="⚡  تفعيل البرنامج",
                            font=(FONT, 13, "bold"),
                            bg=PRIMARY, fg="white",
                            activebackground=hc(PRIMARY),
                            relief="flat", cursor="hand2",
                            padx=20, pady=12,
                            command=self._activate)
        act_btn.pack(fill="x")
        act_btn.bind("<Enter>", lambda e: act_btn.config(bg=hc(PRIMARY)))
        act_btn.bind("<Leave>", lambda e: act_btn.config(bg=PRIMARY))

        # ── Contact ───────────────────────────────────────────────────────
        tk.Label(body, text="للحصول على كود التفعيل تواصل مع المطور",
                 font=(FONT, 8), bg=BG, fg=TEXT2,
                 anchor="center").pack(fill="x", pady=(14, 0))

    # ---------------------------------------------------------------- actions
    def _copy_hwid(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self._hwid)
        messagebox.showinfo("✅", "تم نسخ رقم الجهاز!")

    def _activate(self):
        key = self.key_var.get().strip().upper()

        if not key:
            self.status_var.set("❌  أدخل كود التفعيل")
            return

        is_ok, start, expiry = verify_license_key(self._hwid, key)
        if not is_ok:
            self.status_var.set("❌  كود التفعيل غير صحيح")
            return

        # Determine plan name from embedded expiry
        if expiry == LIFETIME_EXPIRY:
            plan = "مدى الحياة"
        else:
            try:
                exp_date = datetime.strptime(expiry, "%Y-%m-%d").date()
                days = (exp_date - date.today()).days
                if days <= 32:    plan = "شهر"
                elif days <= 95:  plan = "٣ شهور"
                elif days <= 185: plan = "٦ شهور"
                else:             plan = "سنة"
            except Exception:
                plan = "مخصص"

        save_license(self._hwid, key, start, expiry, plan)
        self.passed = True
        self.root.destroy()

    def _on_close(self):
        if not self.passed:
            self.root.destroy()
            import sys; sys.exit(0)


# ===================== MAIN =====================

def main():
    # ── 1) Check existing license ─────────────────────────────────────────
    is_valid, msg, days_left = check_license()

    if not is_valid:
        # Show activation window
        act_root = tk.Tk()
        try:
            act_root.tk.call('tk', 'scaling', 1.2)
        except Exception:
            pass
        act_win = ActivationWindow(act_root)
        act_root.mainloop()

        if not act_win.passed:
            return   # User closed without activating

        # Re-check after activation
        is_valid, msg, days_left = check_license()
        if not is_valid:
            messagebox.showerror("❌ خطأ", "فشل التفعيل. تحقق من الكود وأعد المحاولة.")
            return

    # ── 2) Launch main app ────────────────────────────────────────────────
    root = tk.Tk()
    root.resizable(True, True)
    try:
        root.tk.call('tk', 'scaling', 1.2)
    except Exception:
        pass

    app = OMRApp(root)

    # Show license status in title bar
    if days_left == -1:
        root.title(T("app_title") + "  —  ✅ مدى الحياة")
    elif days_left > 0:
        root.title(T("app_title") + f"  —  ⏳ {days_left} يوم متبقي")

    root.mainloop()


if __name__ == "__main__":
    main()