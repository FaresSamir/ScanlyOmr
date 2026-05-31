import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import cv2
import numpy as np
from PIL import Image, ImageTk
import os
import json
import tempfile

# ===================== OMR CORE =====================

QUESTION_YS = [150,198,249,297,349,399,448,498,549,597,647,697,748,795,846,
               895,944,993,1041,1090,1141,1191,1240,1288,1340,1388,1439]

COL_SECTIONS = [
    {"qs": list(range(1,28)),  "xs": {"د":724, "ج":773, "ب":822, "أ":872}},  # اليمين
    {"qs": list(range(28,55)), "xs": {"د":411, "ج":461, "ب":510, "أ":559}},  # الوسط
    {"qs": list(range(55,82)), "xs": {"د":106, "ج":154, "ب":202, "أ":250}},  # اليسار
]

TARGET_H, TARGET_W = 1491, 1055

# نصف حجم منطقة القراءة لكل فقاعة (بكسل)
BUBBLE_RADIUS = 18

# --- عتبات الكشف (يمكن تعديلها لضبط الدقة) ---
# فرق الظلام المطلوب بين الفقاعة المملوءة وبقية الفقاعات في نفس الصف
ADAPTIVE_GAP_THRESHOLD = 8    # مخفوض للتعامل مع الظلال الخفيف
# أي فقاعة أفتح من هذه القيمة تُعدّ فارغة حتى لو كان الفرق كافياً
ABSOLUTE_MAX_FILLED    = 200   # مرفوع لتشميل التظليل بالقلم الرصاص

# لو True: يحفظ صورة debug تبين أين بيقرأ الكود بالضبط (شغلها لمعرفة سبب المشكلة)
DEBUG_SAVE_OVERLAY = True
DEBUG_OVERLAY_PATH = r"debug_overlay.png"

# لو True: يطبق تصحيح المنظور (عطّلها مؤقتاً لحين نتأكد من صحة الإحداثيات)
PERSPECTIVE_CORRECTION_ENABLED = False



def _order_points(pts):
    """رتب 4 نقاط بالترتيب: أعلى-يسار، أعلى-يمين، أسفل-يمين، أسفل-يسار"""
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def _correct_perspective(img, target_w, target_h):
    """
    حاول اكتشاف حواف ورقة الإجابة وتصحيح الانحراف (perspective warp).
    لو ما قدر يكتشف الحواف، يرجع الصورة كما هي بعد الـ resize.

    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # تحسين التباين أولاً
    gray = cv2.equalizeHist(gray)
    blurred = cv2.GaussianBlur(gray, (7, 7), 0)
    edged = cv2.Canny(blurred, 30, 100)

    # نوسّع الحواف قليلاً لتوصيلها
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    edged = cv2.dilate(edged, kernel, iterations=2)

    contours, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)

    sheet_contour = None
    for c in contours[:8]:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        area = cv2.contourArea(c)
        # نبحث عن مستطيل كبير يغطي على الأقل 30% من مساحة الصورة
        if len(approx) == 4 and area > (target_w * target_h * 0.3):
            sheet_contour = approx
            break

    if sheet_contour is None:
        # ما لقينا حواف واضحة — نرجع الصورة كما هي
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
    """
    اقرأ متوسط درجة الظلام في منطقة الفقاعة.
    نستخدم قناع دائري للحصول على القراءة الأدق.
    """
    h, w = gray.shape
    # تأكد من أن النقطة داخل حدود الصورة
    if cx < 0 or cy < 0 or cx >= w or cy >= h:
        return 255.0  # خارج الحدود = فارغ دائماً
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(mask, (cx, cy), max(1, radius - 2), 255, -1)
    mean_val = cv2.mean(gray, mask=mask)[0]
    return mean_val


def _save_debug_overlay(img_bgr, num_questions, fitted_coords=None):
    """
    يحفظ صورة عليها دوائر حمراء على كل نقطة يجب أن يقرأ منها الكود.
    افتح الصورة بعدك لتعرف إذا النقاط على الفقاعات أم لا.
    """
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
    """
    يقرأ ورقة إجابة الفقاعات باستخدام:
    1) محاذاة ديناميكية للشبكة (dynamic grid alignment) تتكيف مع الميلان، التمدد، والإزاحة
    2) عتبة تكيفية لكل صف (adaptive per-row threshold)
    3) درجة ثقة لكل إجابة

    يرجع: (dict سؤال→إجابة, رسالة_خطأ_أو_None)
    """
    if isinstance(image_path_or_array, str):
        img = cv2.imread(image_path_or_array)
        if img is None:
            return None, "تعذر فتح الصورة"
    else:
        img = image_path_or_array.copy()

    target_h, target_w = TARGET_H, TARGET_W

    # --- الخطوة 1: resize ---
    orig_h, orig_w = img.shape[:2]
    if orig_h != target_h or orig_w != target_w:
        img = cv2.resize(img, (target_w, target_h), interpolation=cv2.INTER_AREA)

    # --- الخطوة 1.5: كشف وتصحيح الدوران التلقائي 180 درجة (للأوراق المقلوبة) ---
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

    # --- الخطوة 2: تحويل لرمادي + تحسين التباين ---
    # نستخدم القناة الخضراء لتجنب التأثر بأي علامات حمراء مرسومة للمعاينة
    if img.ndim == 3:
        gray_raw = img[:, :, 1]
    else:
        gray_raw = img.copy()

    # CLAHE يحسّن التباين المحلي (مفيد لو الإضاءة غير منتظمة)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray_raw)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    # --- الخطوة 3: كشف الفقاعات لضبط الإحداثيات ديناميكياً ---
    _, thresh = cv2.threshold(gray_raw, 127, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    detected_bubbles = []
    for c in contours:
        area = cv2.contourArea(c)
        perimeter = cv2.arcLength(c, True)
        if perimeter == 0:
            continue
        circularity = 4 * np.pi * area / (perimeter * perimeter)
        # فلترة مبدئية لشكل الفقاعات الدائري وحجمها
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
        # حدود الـ X التقريبية لكل عمود
        x_min, x_max = [(680, 920), (370, 600), (50, 270)][sec_idx]
        
        # فلترة النقاط المكتشفة التابعة لهذا العمود
        sec_pts = [p for p in detected_bubbles if x_min < p[0] < x_max]
        
        ys = list(QUESTION_YS)
        xs = dict(col_xs)
        
        # محاولة ملاءمة الشبكة لو فيه نقاط كافية
        if len(sec_pts) >= 5:
            # أ) تجميع النقاط في صفوف أفقية متقاربة
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
            
            # ب) تعيين رقم الصف الفعلي لكل تجمع وحساب الانحدار الخطي Y = a * row_idx + b
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
                    # التأكد أن خطوة التباعد والبداية معقولين (الخطوة الافتراضية ~48)
                    if 44 < a < 52 and 120 < b < 190:
                        ys = [int(round(a * i + b)) for i in range(27)]
                    else:
                        print(f"[OMR] Section {sec_idx+1} fit params out of range (step={a:.1f}, start={b:.1f}), using fallback Ys")
            
            # ج) ضبط إحداثيات الـ X ديناميكياً للخيارات الأربعة
            x_groups = {ch: [] for ch in col_xs}
            for p in sec_pts:
                closest_ch = min(col_xs, key=lambda ch: abs(p[0] - col_xs[ch]))
                if abs(p[0] - col_xs[closest_ch]) < 25:
                    x_groups[closest_ch].append(p[0])
            for ch in col_xs:
                if len(x_groups[ch]) >= 3:
                    xs[ch] = int(round(np.mean(x_groups[ch])))
                    
        fitted_coords[sec_idx] = (ys, xs)

        # د) قراءة قيم التظليل بناءً على الإحداثيات المعدلة
        for row_idx, q_num in enumerate(questions_in_sec):
            if q_num > num_questions:
                continue
            cy = ys[row_idx]
            bubble_vals = {}
            for choice, cx in xs.items():
                bubble_vals[choice] = _sample_bubble(gray, cx, cy)

            row_mean = np.mean(list(bubble_vals.values()))
            # التحقق من جميع الفقاعات المظللة في الصف
            filled_choices = []
            for choice, val in bubble_vals.items():
                gap = row_mean - val
                if gap >= ADAPTIVE_GAP_THRESHOLD and val <= ABSOLUTE_MAX_FILLED:
                    filled_choices.append(choice)

            if len(filled_choices) > 1:
                # تظليل متعدد -> إجابة خاطئة
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

    # --- حفظ overlay debug لمعرفة فين يقرأ الكود ---
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

# ===================== SCANNER (TWAIN + WIA) =====================

def get_scanners(window=None):
    """إرجع قائمة السكانرات - يجرب TWAIN الأول ثم WIA"""
    scanners = []

    # جرب TWAIN أولاً
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

    # جرب WIA تاني
    try:
        import win32com.client
        wia = win32com.client.Dispatch("WIA.DeviceManager")
        for dev in wia.DeviceInfos:
            if dev.Type == 1:  # Scanner
                name = dev.Properties("Name").Value
                scanners.append({"name": name, "type": "WIA", "id": dev.DeviceID})
                print(f"[WIA] found: {name}")
    except Exception as e:
        print(f"[WIA] not available: {e}")

    return scanners


def scan_image(scanner_info, dpi=300, window=None):
    """سكان صورة وارجعها كـ numpy BGR array"""
    
    if isinstance(scanner_info, str):
        # قديم - اسم TWAIN مباشر
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
    # الورقة A5 (148×210 ملم) — نحدد المنطقة بدقة لتجنب مسح مساحة A4 كاملة
    try:
        ss.set_capability(twain.ICAP_SUPPORTEDSIZES, twain.TWTY_UINT16, twain.TWSS_A5)
    except Exception:
        # بعض السكانرات لا تدعم TWSS_A5 — نحدد الإطار يدوياً بالبوصة
        # A5 = 5.83 × 8.27 بوصة
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
        raise Exception("السكانر مش موجود!")
    scanner_item = device.Items[1]
    try:
        scanner_item.Properties("Horizontal Resolution").Value = dpi
        scanner_item.Properties("Vertical Resolution").Value = dpi
        scanner_item.Properties("Current Intent").Value = 4  # Grayscale
        # تحديد منطقة المسح بحجم A5 (148×210 ملم) بالبكسل
        # WIA يستخدم وحدة 1/1000 بوصة (thousandths of an inch)
        # A5: عرض=5.83 بوصة، ارتفاع=8.27 بوصة
        a5_w_thou = 5830   # 5.83 بوصة × 1000
        a5_h_thou = 8270   # 8.27 بوصة × 1000
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


# ===================== GUI =====================

class OMRApp:
    def __init__(self, root):
        self.root = root
        self.root.title("مصحح البابل شيت - OMR")
        self.root.geometry("1150x720")
        self.root.configure(bg="#f5f5f0")

        self.answer_key = {}
        self.num_questions = tk.IntVar(value=40)
        self.students_results = []
        self.key_file = "answer_key.json"
        self.scanner_var = tk.StringVar(value="")
        self.scan_counter = 0

        self._load_key_from_file()
        self._build_ui()
        # نأخر البحث عن السكانر لحد ما الـ window يظهر فعلاً على الشاشة
        self.root.after(500, self._refresh_scanners)

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

    def _build_ui(self):
        header = tk.Frame(self.root, bg="#c0392b", height=55)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="🎯  مصحح البابل شيت", font=("Arial", 20, "bold"),
                 bg="#c0392b", fg="white").pack(side="right", padx=20, pady=10)

        main = tk.Frame(self.root, bg="#f5f5f0")
        main.pack(fill="both", expand=True, padx=12, pady=10)

        left = tk.Frame(main, bg="#f5f5f0", width=330)
        left.pack(side="right", fill="y")
        left.pack_propagate(False)

        right = tk.Frame(main, bg="#f5f5f0")
        right.pack(side="right", fill="both", expand=True, padx=(0,10))

        self._build_left(left)
        self._build_right(right)

    def _build_left(self, parent):
        # Scanner card
        scan_card = self._card(parent, "🖨️  السكانر")

        tk.Label(scan_card, text="اختر السكانر:", font=("Arial", 10),
                 bg="white", anchor="e").pack(fill="x", padx=10, pady=(6,2))

        scan_row = tk.Frame(scan_card, bg="white")
        scan_row.pack(fill="x", padx=10, pady=(0,4))

        self.scanner_combo = ttk.Combobox(scan_row, textvariable=self.scanner_var,
                                           font=("Arial", 10), state="readonly")
        self.scanner_combo.pack(side="right", fill="x", expand=True)

        tk.Button(scan_row, text="🔄", font=("Arial", 11), bg="white",
                  relief="flat", command=self._refresh_scanners).pack(side="left", padx=(4,0))

        # DPI
        dpi_row = tk.Frame(scan_card, bg="white")
        dpi_row.pack(fill="x", padx=10, pady=(0,8))
        tk.Label(dpi_row, text="دقة السكان (DPI):", font=("Arial", 10),
                 bg="white").pack(side="right")
        self.dpi_var = tk.IntVar(value=300)
        ttk.Combobox(dpi_row, textvariable=self.dpi_var,
                     values=[150, 200, 300, 400, 600],
                     width=6, state="readonly").pack(side="left")

        # Big scan button
        self.scan_btn = tk.Button(scan_card,
                  text="📄  سكان وصحح",
                  font=("Arial", 14, "bold"),
                  bg="#c0392b", fg="white",
                  relief="flat", padx=10, pady=10,
                  command=self._scan_and_grade)
        self.scan_btn.pack(fill="x", padx=10, pady=(0,6))

        # Continuous scan button
        self.cont_btn = tk.Button(scan_card,
                  text="🔁  سكان متواصل (دفعة)",
                  font=("Arial", 11, "bold"),
                  bg="#8e44ad", fg="white",
                  relief="flat", padx=10, pady=6,
                  command=self._scan_continuous)
        self.cont_btn.pack(fill="x", padx=10, pady=(0,8))

        # Calibration button
        tk.Button(scan_card,
                  text="🔧  معايرة الكشف",
                  font=("Arial", 10),
                  bg="#95a5a6", fg="white",
                  relief="flat", padx=10, pady=5,
                  command=self._calibrate_detection).pack(fill="x", padx=10, pady=(0,8))

        # Settings card
        card = self._card(parent, "⚙️  إعدادات الاختبار")
        tk.Label(card, text="عدد الأسئلة:", font=("Arial", 11),
                 bg="white", anchor="e").pack(fill="x", padx=10, pady=(8,2))
        num_frame = tk.Frame(card, bg="white")
        num_frame.pack(fill="x", padx=10, pady=(0,8))
        tk.Spinbox(num_frame, from_=1, to=81, width=6,
                   textvariable=self.num_questions,
                   font=("Arial", 13, "bold"),
                   command=self._refresh_key_grid).pack(side="right")

        # Answer key card
        card2 = self._card(parent, "🔑  مفتاح الإجابة")

        # زر سكان ورقة الإجابة
        self.scan_key_btn = tk.Button(card2,
                  text="📄  سكان ورقة الإجابة",
                  font=("Arial", 12, "bold"),
                  bg="#27ae60", fg="white",
                  relief="flat", padx=10, pady=10,
                  command=self._scan_answer_key)
        self.scan_key_btn.pack(fill="x", padx=10, pady=(8,4))

        # أو رفع صورة
        tk.Button(card2, text="🖼️  رفع صورة ورقة الإجابة",
                  font=("Arial", 10),
                  bg="#2980b9", fg="white",
                  relief="flat", padx=8, pady=6,
                  command=self._load_key_from_image).pack(fill="x", padx=10, pady=(0,6))

        # حالة المفتاح
        self.key_status_var = tk.StringVar(value="⚠️ لم يتم تحميل مفتاح بعد")
        self.key_status_lbl = tk.Label(card2, textvariable=self.key_status_var,
                 font=("Arial", 10, "bold"), bg="white", fg="#e74c3c", anchor="e")
        self.key_status_lbl.pack(fill="x", padx=10, pady=(0,4))

        # separator
        tk.Frame(card2, bg="#ecf0f1", height=1).pack(fill="x", padx=8)
        tk.Label(card2, text="أو أدخل يدوياً:", font=("Arial", 9),
                 bg="white", fg="#7f8c8d", anchor="e").pack(fill="x", padx=10, pady=(4,0))

        self.key_frame_scroll = tk.Frame(card2, bg="white")
        self.key_frame_scroll.pack(fill="both", expand=True, padx=5, pady=5)

        canvas = tk.Canvas(self.key_frame_scroll, bg="white", highlightthickness=0, height=160)
        scrollbar = ttk.Scrollbar(self.key_frame_scroll, orient="vertical", command=canvas.yview)
        self.key_inner = tk.Frame(canvas, bg="white")
        self.key_inner.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0,0), window=self.key_inner, anchor="ne")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="right", fill="both", expand=True)
        scrollbar.pack(side="left", fill="y")

        self.key_vars = {}
        self._build_key_grid()
        self._update_key_status()

        btn_frame = tk.Frame(card2, bg="white")
        btn_frame.pack(fill="x", padx=8, pady=(0,8))
        tk.Button(btn_frame, text="💾 حفظ المفتاح", font=("Arial", 10),
                  bg="#27ae60", fg="white", relief="flat", padx=8, pady=4,
                  command=self._save_key).pack(side="right", padx=2)
        tk.Button(btn_frame, text="مسح الكل", font=("Arial", 10),
                  bg="#e74c3c", fg="white", relief="flat", padx=8, pady=4,
                  command=self._clear_key).pack(side="right", padx=2)

    def _update_key_status(self):
        n = self.num_questions.get()
        filled = sum(1 for q in range(1, n+1) if self.answer_key.get(q))
        if filled == n:
            self.key_status_var.set(f"✅ المفتاح جاهز ({n} سؤال)")
            self.key_status_lbl.config(fg="#27ae60")
        elif filled > 0:
            self.key_status_var.set(f"⚠️ مكتمل {filled} من {n} سؤال")
            self.key_status_lbl.config(fg="#f39c12")
        else:
            self.key_status_var.set("⚠️ لم يتم تحميل مفتاح بعد")
            self.key_status_lbl.config(fg="#e74c3c")

    def _scan_answer_key(self):
        """سكان ورقة الإجابة الصح واحفظها كمفتاح"""
        scanner = self._get_selected_scanner()
        if not scanner:
            messagebox.showerror("خطأ", "اختر سكانر أولاً!")
            return
        self.scan_key_btn.config(text="⏳ جارٍ السكان...", state="disabled")
        self.root.update()
        try:
            img = scan_image(scanner, dpi=self.dpi_var.get(), window=self.root)
            if img is None:
                messagebox.showerror("خطأ", "لم يتم استلام صورة!")
                return
            self._extract_key_from_image(img)
        except Exception as e:
            messagebox.showerror("خطأ في السكانر", str(e))
        finally:
            self.scan_key_btn.config(text="📄  سكان ورقة الإجابة", state="normal")

    def _load_key_from_image(self):
        """رفع صورة ورقة الإجابة من الجهاز"""
        path = filedialog.askopenfilename(
            title="اختر صورة ورقة الإجابة",
            filetypes=[("صور", "*.png *.jpg *.jpeg *.bmp")])
        if not path:
            return
        img = cv2.imread(path)
        if img is None:
            messagebox.showerror("خطأ", "تعذر فتح الصورة!")
            return
        self._extract_key_from_image(img)

    def _extract_key_from_image(self, img):
        """استخرج الإجابات من الصورة واحفظها كمفتاح"""
        n = self.num_questions.get()
        answers, err = read_bubble_sheet(img, n)
        if err:
            messagebox.showerror("خطأ في القراءة", err)
            return
        # تحقق إن فيه إجابات اتقرأت
        found = sum(1 for v in answers.values() if v != "؟")
        if found < n // 2:
            if not messagebox.askyesno("تحذير",
                f"تم قراءة {found} إجابة فقط من {n}.\nهل تريد المتابعة؟"):
                return
        # احفظ كمفتاح
        self.answer_key = {q: v for q, v in answers.items() if v != "؟"}
        self._save_key_to_file()
        # حدّث الـ grid اليدوي
        for q, var in self.key_vars.items():
            var.set(self.answer_key.get(q, ""))
        self._update_key_status()
        self._show_key_preview(answers, n)

    def _show_key_preview(self, answers, n):
        win = tk.Toplevel(self.root)
        win.title("مراجعة مفتاح الإجابة")
        win.geometry("520x580")
        win.configure(bg="white")
        win.grab_set()

        found = sum(1 for v in answers.values() if v != "؟")
        hdr = tk.Frame(win, bg="#27ae60", height=50)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text=f"✅ تم قراءة {found} من {n} إجابة",
                 font=("Arial", 13, "bold"), bg="#27ae60", fg="white").pack(pady=12)

        tk.Label(win, text="راجع الإجابات — لو في غلطة عدّلها يدوياً من المفتاح",
                 font=("Arial", 10), bg="white", fg="#7f8c8d").pack(pady=(8,4))

        frame = tk.Frame(win, bg="white")
        frame.pack(fill="both", expand=True, padx=10, pady=5)
        canvas = tk.Canvas(frame, bg="white", highlightthickness=0)
        sb = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg="white")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0,0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        for ci, lbl in enumerate(["السؤال", "الإجابة", "السؤال", "الإجابة", "السؤال", "الإجابة"]):
            tk.Label(inner, text=lbl, font=("Arial", 9, "bold"),
                     bg="#ecf0f1", width=9, relief="flat", padx=4, pady=4).grid(
                row=0, column=ci, padx=1, pady=1)

        cols = 3
        for i, q in enumerate(range(1, n+1)):
            row = (i // cols) + 1
            col_base = (i % cols) * 2
            ans = answers.get(q, "؟")
            bg = "#d5f5e3" if ans != "؟" else "#fde8e8"
            tk.Label(inner, text=f"س {q}", font=("Arial", 10),
                     bg=bg, width=9, padx=4, pady=5).grid(
                row=row, column=col_base, padx=1, pady=1, sticky="nsew")
            tk.Label(inner, text=ans, font=("Arial", 12, "bold"),
                     bg=bg, fg="#27ae60" if ans != "؟" else "#e74c3c",
                     width=9, padx=4, pady=5).grid(
                row=row, column=col_base+1, padx=1, pady=1, sticky="nsew")

        tk.Button(win, text="✅ تمام، ابدأ تصحيح الطلاب",
                  font=("Arial", 12, "bold"), bg="#27ae60", fg="white",
                  relief="flat", padx=15, pady=10,
                  command=win.destroy).pack(pady=10)

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
            self.scanner_combo["values"] = ["لا يوجد سكانر متصل"]
            self.scanner_var.set("لا يوجد سكانر متصل")
            self.scan_btn.config(state="disabled")
            self.cont_btn.config(state="disabled")
            messagebox.showwarning("تنبيه",
                "مش لاقي سكانر.\n\nتأكد من:\n1- السكانر متوصل ومشغول\n2- درايفر الشركة مثبت (HP/Canon/Epson...)\n3- pywin32 مثبت: pip install pywin32")

    def _build_key_grid(self):
        for w in self.key_inner.winfo_children():
            w.destroy()
        self.key_vars = {}
        n = self.num_questions.get()

        for col, label in enumerate(["س", "أ", "ب", "ج", "د"]):
            tk.Label(self.key_inner, text=label, font=("Arial", 9, "bold"),
                     bg="#ecf0f1", width=4, relief="flat").grid(row=0, column=col, padx=1, pady=1)

        choices = ["أ", "ب", "ج", "د"]
        for q in range(1, n+1):
            var = tk.StringVar(value=self.answer_key.get(q, ""))
            self.key_vars[q] = var
            bg = "#ffffff" if q % 2 == 0 else "#fafafa"
            tk.Label(self.key_inner, text=str(q), font=("Arial", 9),
                     bg=bg, width=4).grid(row=q, column=0, padx=1, pady=1)
            for ci, ch in enumerate(choices):
                tk.Radiobutton(self.key_inner, text=ch, variable=var, value=ch,
                               font=("Arial", 9), bg=bg,
                               selectcolor="#c0392b", fg="#2c2c2a",
                               activebackground=bg).grid(row=q, column=ci+1, padx=1, pady=1)

    def _refresh_key_grid(self):
        self._build_key_grid()

    def _save_key(self):
        n = self.num_questions.get()
        for q in range(1, n+1):
            val = self.key_vars[q].get()
            if val:
                self.answer_key[q] = val
        self._save_key_to_file()
        messagebox.showinfo("تم", "✅ تم حفظ مفتاح الإجابة!")

    def _clear_key(self):
        for var in self.key_vars.values():
            var.set("")
        self.answer_key = {}

    def _build_right(self, parent):
        btn_row = tk.Frame(parent, bg="#f5f5f0")
        btn_row.pack(fill="x", pady=(0,8))

        tk.Button(btn_row, text="📂  رفع صورة",
                  font=("Arial", 11, "bold"), bg="#2980b9", fg="white",
                  relief="flat", padx=12, pady=7,
                  command=self._grade_single).pack(side="right", padx=4)

        tk.Button(btn_row, text="📁  رفع مجلد كامل",
                  font=("Arial", 11, "bold"), bg="#16a085", fg="white",
                  relief="flat", padx=12, pady=7,
                  command=self._grade_batch).pack(side="right", padx=4)

        tk.Button(btn_row, text="💾  تصدير CSV",
                  font=("Arial", 11, "bold"), bg="#27ae60", fg="white",
                  relief="flat", padx=12, pady=7,
                  command=self._export).pack(side="left", padx=4)

        tk.Button(btn_row, text="🗑️ مسح النتائج",
                  font=("Arial", 11), bg="#7f8c8d", fg="white",
                  relief="flat", padx=12, pady=7,
                  command=self._clear_results).pack(side="left", padx=4)

        # Results table
        card = self._card(parent, "📊  نتائج التصحيح")
        self.summary_var = tk.StringVar(value="")
        tk.Label(card, textvariable=self.summary_var, font=("Arial", 11),
                 bg="white", fg="#c0392b", anchor="e").pack(fill="x", padx=10, pady=4)

        cols = ("م", "الملف / الورقة", "الدرجة", "صح", "غلط", "النسبة")
        self.tree = ttk.Treeview(card, columns=cols, show="headings", height=9)
        style = ttk.Style()
        style.configure("Treeview", font=("Arial", 11), rowheight=26)
        style.configure("Treeview.Heading", font=("Arial", 11, "bold"))

        widths = [40, 200, 70, 60, 60, 70]
        for c, w in zip(cols, widths):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w, anchor="center")

        sb = ttk.Scrollbar(card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="right", fill="both", expand=True, padx=(8,0), pady=(0,8))
        sb.pack(side="left", fill="y", pady=(0,8))
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # Detail
        detail_card = self._card(parent, "🔍  تفاصيل الورقة المختارة")
        self.detail_text = tk.Text(detail_card, height=7, font=("Courier", 10),
                                    bg="#fafafa", relief="flat", wrap="word",
                                    state="disabled")
        self.detail_text.pack(fill="both", expand=True, padx=8, pady=(0,8))
        self.detail_text.tag_configure("ok", foreground="#27ae60")
        self.detail_text.tag_configure("err", foreground="#e74c3c")
        self.detail_text.tag_configure("bold", font=("Courier", 10, "bold"))

    def _card(self, parent, title):
        frame = tk.Frame(parent, bg="white", bd=0,
                         highlightthickness=1, highlightbackground="#d3d1c7")
        frame.pack(fill="both", expand=True, pady=(0,8))
        tk.Label(frame, text=title, font=("Arial", 11, "bold"),
                 bg="#ecf0f1", fg="#2c2c2a", anchor="e", padx=10, pady=5).pack(fill="x")
        return frame

    def _validate_key(self):
        n = self.num_questions.get()
        missing = [q for q in range(1, n+1) if not self.answer_key.get(q)]
        if missing:
            return messagebox.askyesno("تحذير",
                f"مفتاح الإجابة ناقص في {len(missing)} سؤال.\nهل تريد المتابعة؟")
        return True

    def _show_and_confirm_scan(self, img, name):
        """عرض الصورة المسحوبة واطلب تأكيد المستخدم ودعم تدويرها"""
        # سنحفظ الصورة في قائمة لتمكين تعديلها داخل الدوال الفرعية
        current_img = [img]
        
        # إنشاء نافذة لعرض الصورة
        preview_win = tk.Toplevel(self.root)
        preview_win.title(f"معاينة المسح - {name}")
        preview_win.configure(bg="white")
        preview_win.grab_set()
        
        # عنوان
        hdr = tk.Frame(preview_win, bg="#2980b9", height=50)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text=f"📸 معاينة الصورة المسحوبة", 
                 font=("Arial", 13, "bold"), bg="#2980b9", fg="white").pack(pady=10)
        
        # عرض الصورة
        img_label = tk.Label(preview_win, bg="white")
        img_label.pack(padx=10, pady=10)
        
        # دالة لتحديث الصورة في الواجهة
        photo_ref = [None]  # لحفظ مرجع الصورة لمنع جمع المهملات
        
        def update_preview():
            # تحويل الصورة من BGR إلى RGB وتصغيرها للعرض
            img_display = cv2.cvtColor(current_img[0], cv2.COLOR_BGR2RGB)
            
            # حساب النسبة للعرض في نافذة بحجم معين
            max_width, max_height = 700, 600
            h, w = img_display.shape[:2]
            scale = min(max_width / w, max_height / h, 1.0)
            new_w, new_h = int(w * scale), int(h * scale)
            img_display = cv2.resize(img_display, (new_w, new_h))
            
            # تحويل إلى صورة PIL و ImageTk
            pil_img = Image.fromarray(img_display)
            photo = ImageTk.PhotoImage(pil_img)
            img_label.config(image=photo)
            photo_ref[0] = photo  # حفظ المرجع
            
            # تحديث حجم النافذة بشكل متناسب وديناميكي
            preview_win.geometry(f"{new_w + 40}x{new_h + 230}")
            preview_win.update()

        update_preview()
        
        # رسالة توضيحية
        msg_frame = tk.Frame(preview_win, bg="white")
        msg_frame.pack(fill="x", padx=10, pady=(0, 5))
        tk.Label(msg_frame, text="هل الصورة واضحة ومستقيمة؟ يمكنك شقلبتها إذا كانت مقلوبة.",
                 font=("Arial", 10), bg="white", fg="#7f8c8d").pack()
        
        # أزرار
        btn_frame = tk.Frame(preview_win, bg="white")
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        result = [False]  # لحفظ إجابة المستخدم
        
        def on_accept():
            result[0] = True
            preview_win.destroy()
        
        def on_reject():
            result[0] = False
            preview_win.destroy()
            
        def on_rotate():
            # تدوير الصورة 180 درجة
            current_img[0] = cv2.rotate(current_img[0], cv2.ROTATE_180)
            update_preview()
        
        # زر القبول
        tk.Button(btn_frame, text="✅ الصورة ممتازة - تابع التصحيح",
                  font=("Arial", 11, "bold"), bg="#27ae60", fg="white",
                  relief="flat", padx=15, pady=8,
                  command=on_accept).pack(side="right", padx=5)
                  
        # زر التدوير التفاعلي
        tk.Button(btn_frame, text="🔁 شقلب الورقة 180°",
                  font=("Arial", 11, "bold"), bg="#f39c12", fg="white",
                  relief="flat", padx=15, pady=8,
                  command=on_rotate).pack(side="right", padx=5)
        
        # زر الرفض
        tk.Button(btn_frame, text="❌ أعد المسح",
                  font=("Arial", 11), bg="#e74c3c", fg="white",
                  relief="flat", padx=15, pady=8,
                  command=on_reject).pack(side="right", padx=5)
        
        preview_win.resizable(False, False)
        
        # انتظر حتى يغلق المستخدم النافذة
        self.root.wait_window(preview_win)
        
        return result[0], current_img[0]

    def _calibrate_detection(self):
        """أداة معايرة محسّنة — تعرض تقرير تفصيلي بدرجات الثقة لكل سؤال"""
        path = filedialog.askopenfilename(
            title="اختر صورة ورقة إجابة لمعايرة الكشف",
            filetypes=[("صور", "*.png *.jpg *.jpeg *.bmp")])
        if not path:
            return

        img = cv2.imread(path)
        if img is None:
            messagebox.showerror("خطأ", "تعذر فتح الصورة!")
            return

        # --- اجري القراءة مع الحصول على بيانات الثقة التفصيلية ---
        n = 81
        # نُعيد تشغيل الكشف ونجمع بيانات أكثر تفصيلاً
        img_proc = img.copy()
        target_h, target_w = TARGET_H, TARGET_W
        orig_h, orig_w = img_proc.shape[:2]
        if orig_h != target_h or orig_w != target_w:
            img_proc = cv2.resize(img_proc, (target_w, target_h), interpolation=cv2.INTER_AREA)
        img_proc = _correct_perspective(img_proc, target_w, target_h)
        gray = cv2.cvtColor(img_proc, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)

        ADAPTIVE_GAP_THRESHOLD = 15
        ABSOLUTE_MAX_FILLED    = 185

        cal_data = {}  # q_num -> {"answer": x, "gap": y, "confidence": z, "vals": {...}}
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
                is_filled = gap >= ADAPTIVE_GAP_THRESHOLD and darkest_val <= ABSOLUTE_MAX_FILLED
                if is_filled:
                    conf = "high" if gap >= 40 else ("medium" if gap >= 22 else "low")
                    cal_data[q_num] = {"answer": darkest_choice, "gap": gap, "confidence": conf, "vals": bubble_vals}
                else:
                    cal_data[q_num] = {"answer": "؟", "gap": gap, "confidence": "none", "vals": bubble_vals}

        detected  = sum(1 for d in cal_data.values() if d["answer"] != "؟")
        high_conf = sum(1 for d in cal_data.values() if d["confidence"] == "high")
        med_conf  = sum(1 for d in cal_data.values() if d["confidence"] == "medium")
        low_conf  = sum(1 for d in cal_data.values() if d["confidence"] == "low")
        unanswered = [q for q, d in cal_data.items() if d["answer"] == "؟"]

        # --- نافذة النتائج ---
        win = tk.Toplevel(self.root)
        win.title("تقرير معايرة الكشف")
        win.geometry("620x620")
        win.configure(bg="white")

        # رأس
        hdr_color = "#27ae60" if detected >= 70 else ("#f39c12" if detected >= 50 else "#e74c3c")
        hdr = tk.Frame(win, bg=hdr_color, height=60)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        icon = "✅" if detected >= 70 else ("⚠️" if detected >= 50 else "❌")
        tk.Label(hdr, text=f"{icon}  تم كشف {detected} من {n} إجابة",
                 font=("Arial", 14, "bold"), bg=hdr_color, fg="white").pack(pady=16)

        # إحصائيات الثقة
        stat_frame = tk.Frame(win, bg="white")
        stat_frame.pack(fill="x", padx=15, pady=10)
        for txt, val, color in [
            ("🟢 ثقة عالية:", high_conf, "#27ae60"),
            ("🟡 ثقة متوسطة:", med_conf, "#f39c12"),
            ("🔴 ثقة منخفضة:", low_conf, "#e74c3c"),
            ("⬜ غير مكتشف:", len(unanswered), "#7f8c8d"),
        ]:
            row = tk.Frame(stat_frame, bg="white")
            row.pack(fill="x", pady=1)
            tk.Label(row, text=txt, font=("Arial", 11), bg="white", fg="#2c3e50",
                     anchor="e", width=18).pack(side="right")
            tk.Label(row, text=str(val), font=("Arial", 11, "bold"), bg="white",
                     fg=color).pack(side="right", padx=6)

        # أسئلة غير مكتشفة
        if unanswered:
            tk.Frame(win, bg="#ecf0f1", height=1).pack(fill="x", padx=10)
            tk.Label(win, text=f"أسئلة لم تُكتشف ({len(unanswered)}):",
                     font=("Arial", 10, "bold"), bg="white", fg="#e74c3c", anchor="e").pack(
                fill="x", padx=15, pady=(8, 2))
            q_list = ", ".join(f"س{q}" for q in sorted(unanswered))
            tk.Label(win, text=q_list, font=("Arial", 10), bg="white",
                     fg="#7f8c8d", wraplength=560, justify="right").pack(
                fill="x", padx=15, pady=(0, 6))

        # جدول تفصيلي قابل للتمرير
        tk.Frame(win, bg="#ecf0f1", height=1).pack(fill="x", padx=10)
        tk.Label(win, text="تفاصيل كل سؤال (الفجوة = فرق الظلام، كلما زاد كان الكشف أوثق):",
                 font=("Arial", 9), bg="white", fg="#7f8c8d", anchor="e").pack(
            fill="x", padx=15, pady=(4, 2))

        table_frame = tk.Frame(win, bg="white")
        table_frame.pack(fill="both", expand=True, padx=10, pady=(0, 5))
        canvas = tk.Canvas(table_frame, bg="white", highlightthickness=0)
        sb = ttk.Scrollbar(table_frame, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg="white")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        conf_colors = {"high": "#d5f5e3", "medium": "#fef9e7",
                       "low": "#fde8e8", "none": "#f2f3f4"}
        conf_labels = {"high": "عالية ✅", "medium": "متوسطة ⚠️",
                       "low": "منخفضة ⚠️", "none": "—"}

        for ci, lbl in enumerate(["السؤال", "الإجابة", "الفجوة", "الثقة"]):
            tk.Label(inner, text=lbl, font=("Arial", 9, "bold"),
                     bg="#ecf0f1", width=10, relief="flat", padx=4, pady=4).grid(
                row=0, column=ci, padx=1, pady=1)

        cols = 2  # نعرض عمودين من البيانات جنباً لجنب
        for i, q in enumerate(range(1, n + 1)):
            d = cal_data.get(q, {"answer": "؟", "gap": 0, "confidence": "none"})
            bg = conf_colors[d["confidence"]]
            col_offset = (i % cols) * 4
            base_row   = (i // cols) + 1
            tk.Label(inner, text=f"س{q}", font=("Arial", 9),
                     bg=bg, width=6, padx=3, pady=4).grid(
                row=base_row, column=col_offset, padx=1, pady=1, sticky="nsew")
            tk.Label(inner, text=d["answer"], font=("Arial", 9, "bold"),
                     bg=bg, width=5, fg="#2c3e50").grid(
                row=base_row, column=col_offset + 1, padx=1, pady=1, sticky="nsew")
            tk.Label(inner, text=f"{d['gap']:.1f}", font=("Arial", 9),
                     bg=bg, width=6).grid(
                row=base_row, column=col_offset + 2, padx=1, pady=1, sticky="nsew")
            tk.Label(inner, text=conf_labels[d["confidence"]], font=("Arial", 9),
                     bg=bg, width=10).grid(
                row=base_row, column=col_offset + 3, padx=1, pady=1, sticky="nsew")

        # نصيحة
        tip_frame = tk.Frame(win, bg="#eaf4fb")
        tip_frame.pack(fill="x", padx=10, pady=5)
        if detected >= 75:
            tip = "💡 الكشف ممتاز! يمكنك المتابعة بثقة."
        elif detected >= 55:
            tip = "💡 نصيحة: جرب رفع DPI إلى 300 أو أكثر لتحسين الكشف."
        else:
            tip = "💡 نصيحة: تأكد من إضاءة جيدة، ورقة مسطّحة، و DPI ≥ 300. قد تحتاج لإعادة معايرة الإحداثيات."
        tk.Label(tip_frame, text=tip, font=("Arial", 10), bg="#eaf4fb",
                 fg="#1a5276", wraplength=560, justify="right", anchor="e").pack(
            fill="x", padx=10, pady=8)

        tk.Button(win, text="إغلاق", font=("Arial", 11), bg="#95a5a6", fg="white",
                  relief="flat", padx=20, pady=6, command=win.destroy).pack(pady=(0, 10))


    def _get_selected_scanner(self):
        """إرجع scanner dict المختار"""
        if not hasattr(self, '_scanners_list') or not self._scanners_list:
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
            messagebox.showerror("خطأ", "اختر سكانر أولاً!")
            return

        self.scan_btn.config(text="⏳  جارٍ السكان...", state="disabled")
        self.root.update()

        try:
            img = scan_image(scanner, dpi=self.dpi_var.get(), window=self.root)
            if img is None:
                messagebox.showerror("خطأ", "لم يتم استلام صورة من السكانر.")
                return
            self.scan_counter += 1
            name = f"سكان #{self.scan_counter}"
            # عرض الصورة واطلب تأكيد
            ok, final_img = self._show_and_confirm_scan(img, name)
            if ok:
                self._process_image_array(final_img, name)
        except Exception as e:
            messagebox.showerror("خطأ في السكانر", str(e))
        finally:
            self.scan_btn.config(text="📄  سكان وصحح", state="normal")

    def _scan_continuous(self):
        """Keep scanning until user says stop."""
        if not self._validate_key():
            return
        scanner = self._get_selected_scanner()
        if not scanner:
            messagebox.showerror("خطأ", "اختر سكانر أولاً!")
            return

        # Dialog to control continuous scan
        scanner_info = scanner
        win = tk.Toplevel(self.root)
        win.title("سكان متواصل")
        win.geometry("320x180")
        win.grab_set()
        win.configure(bg="white")

        tk.Label(win, text="🔁 وضع السكان المتواصل",
                 font=("Arial", 13, "bold"), bg="white").pack(pady=(15,5))
        tk.Label(win, text="اضغط 'سكان التالي' بعد كل ورقة",
                 font=("Arial", 10), bg="white", fg="#7f8c8d").pack()

        count_var = tk.StringVar(value="تم سكان: 0 ورقة")
        tk.Label(win, textvariable=count_var, font=("Arial", 11, "bold"),
                 bg="white", fg="#c0392b").pack(pady=8)

        scanned = [0]

        def do_scan():
            try:
                img = scan_image(scanner_info, dpi=self.dpi_var.get(), window=self.root)
                if img is None:
                    messagebox.showerror("خطأ", "لم يتم استلام صورة!", parent=win)
                    return
                self.scan_counter += 1
                name = f"سكان #{self.scan_counter}"
                # عرض الصورة واطلب تأكيد
                ok, final_img = self._show_and_confirm_scan(img, name)
                if ok:
                    self._process_image_array(final_img, name)
                    scanned[0] += 1
                count_var.set(f"تم سكان: {scanned[0]} ورقة")
            except Exception as e:
                messagebox.showerror("خطأ", str(e), parent=win)

        btn_frame = tk.Frame(win, bg="white")
        btn_frame.pack(pady=5)
        tk.Button(btn_frame, text="📄 سكان التالي",
                  font=("Arial", 12, "bold"), bg="#c0392b", fg="white",
                  relief="flat", padx=14, pady=8,
                  command=do_scan).pack(side="right", padx=8)
        tk.Button(btn_frame, text="✅ انتهيت",
                  font=("Arial", 12), bg="#27ae60", fg="white",
                  relief="flat", padx=14, pady=8,
                  command=win.destroy).pack(side="right", padx=8)

    # ---- FILE METHODS ----

    def _grade_single(self):
        if not self._validate_key():
            return
        path = filedialog.askopenfilename(
            title="اختر صورة",
            filetypes=[("صور", "*.png *.jpg *.jpeg *.bmp")])
        if not path:
            return
        self._process_image(path)

    def _grade_batch(self):
        if not self._validate_key():
            return
        folder = filedialog.askdirectory(title="اختر المجلد")
        if not folder:
            return
        images = [os.path.join(folder, f) for f in os.listdir(folder)
                  if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp"))]
        if not images:
            messagebox.showerror("خطأ", "لا توجد صور!")
            return

        prog_win = tk.Toplevel(self.root)
        prog_win.title("جارٍ التصحيح...")
        prog_win.geometry("360x120")
        prog_win.grab_set()
        tk.Label(prog_win, text="جارٍ تصحيح الأوراق...", font=("Arial", 12)).pack(pady=10)
        prog = ttk.Progressbar(prog_win, maximum=len(images), length=300)
        prog.pack(pady=5)
        status_lbl = tk.Label(prog_win, text="", font=("Arial", 10))
        status_lbl.pack()

        for i, path in enumerate(images):
            status_lbl.config(text=os.path.basename(path))
            prog["value"] = i+1
            prog_win.update()
            self._process_image(path, silent=True)

        prog_win.destroy()
        n_done = len(images)
        recent = self.students_results[-n_done:]
        avg = sum(r["score"] for r in recent) / n_done
        messagebox.showinfo("اكتمل",
            f"✅ تم تصحيح {n_done} ورقة\nالمتوسط: {avg:.1f} / {self.num_questions.get()}")

    def _process_image(self, path, silent=False):
        n = self.num_questions.get()
        answers, err = read_bubble_sheet(path, n)
        if err:
            if not silent:
                messagebox.showerror("خطأ", err)
            return
        self._add_result(os.path.basename(path), answers)

    def _process_image_array(self, img, name):
        n = self.num_questions.get()
        answers, err = read_bubble_sheet(img, n)
        if err:
            messagebox.showerror("خطأ في القراءة", err)
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
        self.tree.tag_configure("pass", foreground="#27ae60")
        self.tree.tag_configure("fail", foreground="#e74c3c")

        total = len(self.students_results)
        avg = sum(r["score"] for r in self.students_results) / total
        self.summary_var.set(
            f"إجمالي: {total} ورقة  |  متوسط: {avg:.1f}/{n}  |  "
            f"أعلى: {max(r['score'] for r in self.students_results)}  |  "
            f"أدنى: {min(r['score'] for r in self.students_results)}")

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

        header = f"الورقة: {result['file']}    الدرجة: {result['score']}/{result['n']}  ({result['pct']}%)\n"
        header += "─" * 55 + "\n"
        self.detail_text.insert("end", header, "bold")

        wrongs = [d for d in result["details"] if not d["ok"] and d["correct"]]
        if wrongs:
            self.detail_text.insert("end", f"\n❌ أسئلة خاطئة ({len(wrongs)}):\n", "err")
            for d in wrongs:
                self.detail_text.insert("end",
                    f"  س{d['q']:3d}: أجاب ({d['student']})  الصحيح ({d['correct']})\n", "err")
        else:
            self.detail_text.insert("end", "\n✅ جميع الإجابات صحيحة!\n", "ok")

        self.detail_text.insert("end", "\n" + "─"*55 + "\nكل الإجابات:\n")
        line = ""
        for d in result["details"]:
            mark = "✓" if d["ok"] else "✗"
            line += f"  س{d['q']:2d}:{d['student']}{mark}"
            if d["q"] % 8 == 0:
                self.detail_text.insert("end", line + "\n")
                line = ""
        if line:
            self.detail_text.insert("end", line + "\n")

        self.detail_text.config(state="disabled")

    def _clear_results(self):
        if messagebox.askyesno("تأكيد", "هل تريد مسح جميع النتائج؟"):
            self.students_results = []
            for item in self.tree.get_children():
                self.tree.delete(item)
            self.summary_var.set("")
            self.scan_counter = 0

    def _export(self):
        if not self.students_results:
            messagebox.showinfo("تنبيه", "لا توجد نتائج للتصدير!")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            title="حفظ النتائج")
        if not path:
            return
        n = self.num_questions.get()
        with open(path, "w", encoding="utf-8-sig") as f:
            q_headers = ",".join([f"س{q}" for q in range(1, n+1)])
            f.write(f"م,الملف,الدرجة,النسبة,{q_headers}\n")
            for r in self.students_results:
                answers_str = ",".join([d["student"] for d in r["details"]])
                f.write(f"{r['idx']},{r['file']},{r['score']},{r['pct']}%,{answers_str}\n")
        messagebox.showinfo("تم", f"✅ تم حفظ النتائج:\n{path}")


def main():
    root = tk.Tk()
    root.resizable(True, True)
    try:
        root.tk.call('tk', 'scaling', 1.2)
    except:
        pass
    app = OMRApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
