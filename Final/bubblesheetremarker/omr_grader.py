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



# ── UI Palette & Fonts (Scanly Design System) ──────────────────────────────
PALETTE = {
    "bg":         "#F8FAFC",
    "surface":    "#FFFFFF",
    "border":     "#E2E8F0",
    "primary":    "#4D4D4D",
    "primary_dk": "#333333",
    "primary_lt": "#4D4D4D",
    "success":    "#10B981",
    "success_lt": "#ECFDF5",
    "warning":    "#F59E0B",
    "warning_lt": "#FFFBEB",
    "danger":     "#EF4444",
    "danger_lt":  "#FEF2F2",
    "muted":      "#475569",
    "text":       "#0F172A",
    "text2":      "#475569",
}
FONT_MAIN = "Dubai"
FONT_MONO = "Consolas"

LANG = {"ar": True}  # mutable flag

TRANSLATIONS = {
    # Header & Titles
    "🎯  مصحح البابل شيت": "🎯  Bubble Sheet Grader",
    "Scanly": "Scanly",
    "Scanly OMR": "Scanly OMR",
    "Scanly — تفعيل البرنامج": "Scanly — Activate Program",
    "🔒  Scanly — تفعيل البرنامج": "🔒  Scanly — Activate Program",
    "🔒": "🔒",
    "البرنامج يحتاج إلى ترخيص لتشغيله": "The program requires a license to run",
    "رقم جهازك (أرسله للبائع للحصول على كود التفعيل)": "Your Device ID (send to seller to get activation code)",
    "📋 نسخ": "📋 Copy",
    "أدخل كود التفعيل:": "Enter Activation Code:",
    "⚡  تفعيل البرنامج": "⚡  Activate Program",
    "للحصول على كود التفعيل تواصل مع المطور": "To get the activation code, contact the developer",
    "❌  أدخل كود التفعيل": "❌  Enter Activation Code",
    "❌  كود التفعيل غير صحيح": "❌  Invalid Activation Code",
    "مدى الحياة": "Lifetime",
    "شهر": "Month",
    "٣ شهور": "3 Months",
    "٦ شهور": "6 Months",
    "سنة": "Year",
    "مخصص": "Custom",
    "فشل التفعيل. تحقق من الكود وأعد المحاولة.": "Activation failed. Verify the code and try again.",
    "❌ خطأ": "❌ Error",
    "  —  ✅ مدى الحياة": "  —  ✅ Lifetime",
    "  —  ⏳ {days_left} يوم متبقي": "  —  ⏳ {days_left} days remaining",

    # Settings Card
    "⚙️  إعدادات الاختبار": "⚙️  Test Settings",
    "نوع ورقة الإجابة:": "Answer Sheet Type:",
    "A5  (الحالية)": "A5  (Current)",
    "A6  (A4 ÷ 4)": "A6  (A4 ÷ 4)",
    "ورقة A5 — 54 سؤال + رقم الطالب": "A5 Sheet — 54 Questions + Student ID",
    "ورقة A6 (ربع A4) — 30 سؤال + رقم الطالب": "A6 Sheet (A4 / 4) — 30 Questions + Student ID",
    "عدد الأسئلة:": "Number of Questions:",

    # Answer Key Card
    "🔑  مفتاح الإجابة": "🔑  Answer Key",
    "📄  سكان ورقة الإجابة": "📄  Scan Answer Sheet",
    "🖼️  رفع صورة ورقة الإجابة": "🖼️  Upload Answer Sheet",
    "⚠️ لم يتم تحميل مفتاح بعد": "⚠️ No key loaded yet",
    "أو أدخل يدوياً:": "Or enter manually:",
    "💾 حفظ المفتاح": "💾 Save Key",
    "مسح الكل": "Clear All",
    "أو رفع صورة ورقة الإجابة من الجهاز": "Or upload answer sheet image from device",

    # Scanner Card
    "🖨️  السكانر": "🖨️  Scanner",
    "اختر السكانر:": "Select Scanner:",
    "دقة السكان (DPI):": "Scan DPI:",
    "📄  سكان وصحح": "📄  Scan & Grade",
    "🔁  سكان متواصل (دفعة)": "🔁  Continuous Scan",
    "🔧  معايرة الكشف": "🔧  Calibrate Detection",
    "📁  رفع مجلد كامل": "📁  Upload Folder",
    "📂  رفع صورة": "📂  Upload Image",
    "💾  تصدير CSV": "💾  Export CSV",
    "🗑️ مسح النتائج": "🗑️ Clear Results",
    "📊  نتائج التصحيح": "📊  Grading Results",

    # Treeview Columns
    "الرقم": "#",
    "اسم الملف / الورقة": "File / Sheet Name",
    "رقم الطالب": "Student ID",
    "الدرجة المستحقة": "Score",
    "الإجابات الصحيحة": "Correct Answers",
    "الإجابات الخاطئة": "Wrong Answers",
    "النسبة المئوية": "Percentage",

    # Table/Tree Results Headers
    "م": "#",
    "الملف / الورقة": "File / Sheet",
    "الدرجة": "Score",
    "صح": "Correct",
    "غلط": "Wrong",
    "النسبة": "Percentage",

    # Details Card
    "🔍  تفاصيل الورقة المختارة": "🔍  Selected Sheet Details",
    "السؤال": "Question",
    "الإجابة": "Answer",
    "الفجوة": "Gap",
    "الثقة": "Confidence",
    "عالية ✅": "High ✅",
    "متوسطة ⚠️": "Medium ⚠️",
    "منخفضة ⚠️": "Low ⚠️",
    "⬜ غير مكتشف:": "⬜ Undetected:",
    "🔴 ثقة منخفضة:": "🔴 Low Confidence:",
    "🟡 ثقة متوسطة:": "🟡 Medium Confidence:",
    "🟢 ثقة عالية:": "🟢 High Confidence:",

    # Key Review Window
    "مراجعة مفتاح الإجابة": "Review Answer Key",
    "راجع الإجابات — لو في غلطة عدّلها يدوياً من المفتاح": "Review answers — if there is a mistake, edit it manually from the key",
    "تأكيد": "Confirm",
    "تحذير": "Warning",
    "تنبيه": "Alert",
    "خطأ": "Error",
    "تم": "Done",
    "اكتمل": "Completed",
    "لا يوجد سكانر متصل": "No scanner connected",
    "اختر سكانر أولاً!": "Select scanner first!",
    "لم يتم استلام صورة!": "No image received!",
    "لم يتم استلام صورة من السكانر.": "No image received from scanner.",
    "سيُستخدم أول صفحة فقط كمفتاح إجابة.": "Only the first page will be used as the answer key.",
    "تم نسخ رقم الجهاز!": "Device ID copied!",
    "خطأ في القراءة": "Read Error",
    "تعذّر قراءة الورقة — تحقق من وضع الورقة والإضاءة.": "Could not read sheet — check sheet position and lighting.",
    "تعذّر قراءة الورقة — تحقق من الجودة": "Could not read sheet — check quality",
    "لا توجد نتائج للتصدير!": "No results to export!",
    "هل يريد مسح جميع النتائج؟": "Do you want to clear all results?",
    "سكان متواصل": "Continuous Scan",
    "وضع السكان المتواصل": "Continuous Scan Mode",
    "ضع الورق في الفيدر أو على الزجاج ثم اضغط 'سكان التالي'.": "Place paper in feeder or on glass and press 'Scan Next'.",
    "تصحيح مباشر بدون معاينة": "Direct grading without preview",
    "تم سكان: 0 ورقة": "Scanned: 0 sheets",
    "📄 سكان التالي": "📄 Scan Next",
    "✅ انتهيت": "✅ Done",
    "جارٍ تصحيح الأوراق...": "Grading sheets...",
    "خطأ في السكانر": "Scanner Error",
    "أ": "A", "ب": "B", "ج": "C", "د": "D", "؟": "?",
    "م": "#", "الملف / الورقة": "File / Sheet", "الدرجة": "Score", "صح": "Correct", "غلط": "Wrong", "النسبة": "Percentage",
    "أداة معايرة محسّنة — تعرض تقرير تفصيلي بدرجات الثقة لكل سؤال": "Enhanced calibration tool — displays a detailed confidence report for each question",
    "اختر صورة ورقة إجابة لمعايرة الكشف": "Select an answer sheet image to calibrate detection",
    "استخرج الإجابات من الصورة واحفظها كمفتاح": "Extract answers from image and save as key",
    "إغلاق": "Close",
    "أو رفع صورة": "Or Upload Image",
    "أو رفع صورة ورقة الإجابة": "Or Upload Answer Sheet Image",
    "أو رفع صورة ورقة الإجابة من الجهاز": "Or Upload Answer Sheet from Device",
    "حفظ مفتاح الإجابة": "Save Key",
    "نتائج التصحيح الضوئي": "Grading Results",
    "تفاصيل الورقة المحددة": "Selected Sheet Detail",
    "الرقم جهازك (أرسله للبائع للحصول على كود التفعيل)": "Your Device ID (send to seller to get activation code)",
    "نسخ رقم الجهاز": "Copy Device ID",
    "تفعيل": "Activate",
    "تم تفعيل البرنامج بنجاح!": "Program activated successfully!",
    "تأكيد مسح النتائج": "Confirm clearing results",
    "تصدير النتائج": "Export Results",
    "تم حفظ النتائج بنجاح!": "Results saved successfully!",
    "سكان ورقة الإجابة": "Scan Answer Sheet",
    "رفع صورة ورقة الإجابة": "Upload Answer Image",
    "سكان وصحح": "Scan & Grade",
    "سكان متواصل": "Continuous Scan",
    "معايرة الكشف": "Calibrate Detection",
    "رفع صورة": "Upload Image",
    "رفع مجلد كامل": "Upload Folder",
    "تصدير CSV": "Export CSV",
    "مسح النتائج": "Clear Results",
    "تفاصيل الورقة المختارة": "Selected Sheet Details",
    "معاينة الصورة المسحوبة": "Preview Scanned Image",
    "سكان التالي": "Scan Next",
    "انتهيت": "Done",
    "جارٍ التصحيح...": "Grading...",
    "تم التصحيح": "Grading Complete",
    "ثقة عالية:": "High Confidence:",
    "ثقة متوسطة:": "Medium Confidence:",
    "ثقة منخفضة:": "Low Confidence:",
    "غير مكتشف:": "Undetected:",
    "🔒  Scanly — تفعيل": "🔒  Scanly — Activation",
    "فشل التفعيل. تحقق من الكود وأعد المحاولة.": "Activation failed. Verify the code and try again.",
    "إجمالي: {total} ورقة  |  متوسط: {avg:.1f}/{n}  |  ": "Total: {total} sheets  |  Average: {avg:.1f}/{n}  |  ",

    # Complex templates
    "تم سحب {pages} ورقة من الفيدر.\nسيُستخدم أول صفحة فقط كمفتاح إجابة.": "Pulled {pages} sheets from feeder.\nOnly the first page will be used as the answer key.",
    "إجمالي: {total} ورقة  |  متوسط: {avg:.1f}/{n}  |  أعلى: {max_score}  |  أدنى: {min_score}": "Total: {total} sheets  |  Average: {avg:.1f}/{n}  |  Max: {max_score}  |  Min: {min_score}",
}

def T(key):
    if not LANG["ar"]:
        return TRANSLATIONS.get(key, key)
    return key
# ===================== OMR CORE =====================

QUESTION_YS = [int(round(161 + i * 53.115)) for i in range(27)]

COL_SECTIONS = [
    {"qs": list(range(1, 28)),  "xs": {T("د"): 422, T("ج"): 476, T("ب"): 529, T("أ"): 582}},  # اليمين/الوسط
    {"qs": list(range(28, 55)), "xs": {T("د"): 78, T("ج"): 132, T("ب"): 185, T("أ"): 238}},   # اليسار
]

TARGET_H, TARGET_W = 1600, 1131

# نصف حجم منطقة القراءة لكل فقاعة (بكسل)
BUBBLE_RADIUS = 16

# إحداثيات X لأعمدة رقم الطالب (4 خانات)
A5_ID_XS = [780, 832, 885, 938]

# إحداثيات Y لصفوف أرقام رقم الطالب (0-9)
A5_ID_YS = [int(round(235 + i * 52.888)) for i in range(10)]



# --- عتبات الكشف (يمكن تعديلها لضبط الدقة) ---
# فرق الظلام المطلوب بين الفقاعة المملوءة وبقية الفقاعات في نفس الصف
ADAPTIVE_GAP_THRESHOLD = 20   # مرفوع لتفادي الـ مزدوج الكاذبة بسبب حواف الدوائر
# أي فقاعة أفتح من هذه القيمة تُعدّ فارغة حتى لو كان الفرق كافياً
ABSOLUTE_MAX_FILLED    = 200   # مرفوع لتشميل التظليل بالقلم الرصاص

# لو True: يحفظ صورة debug تبين أين بيقرأ الكود بالضبط (شغلها لمعرفة سبب المشكلة)
DEBUG_SAVE_OVERLAY = True
DEBUG_OVERLAY_PATH = r"debug_overlay.png"

# لو True: يطبق تصحيح المنظور (عطّلها مؤقتاً لحين نتأكد من صحة الإحداثيات)
PERSPECTIVE_CORRECTION_ENABLED = False


# ===================== إعدادات ورقة A6 (ربع A4 — 30 سؤال) =====================
# أبعاد الورقة بعد الـ resize
A6_TARGET_H, A6_TARGET_W = 1052, 748

# إحداثيات Y لصفوف رقم الطالب (4 خانات: آلاف، مئات، عشرات، آحاد)
# كل صف فيه 10 فقاعات للأرقام 0-9
A6_ID_YS = [80, 135, 190, 245]

# إحداثيات X للأرقام 0-9 في صفوف رقم الطالب (من اليمين لليسار)
A6_ID_XS = [660, 595, 530, 465, 400, 335, 270, 205, 140, 75]

# إحداثيات Y للأسئلة الـ 30 (15 صف، خطوة ~48 بكسل)
A6_QUESTION_YS = [320 + i * 48 for i in range(15)]

# أعمدة الأسئلة (2 عمود: يمين أسئلة 1-15، يسار أسئلة 16-30)
A6_COL_SECTIONS = [
    {"qs": list(range(1, 16)),  "xs": {T("د"): 400, T("ج"): 460, T("ب"): 520, T("أ"): 580}},  # يمين
    {"qs": list(range(16, 31)), "xs": {T("د"): 100, T("ج"): 160, T("ب"): 220, T("أ"): 280}},  # يسار
]

# نصف حجم منطقة القراءة للفقاعات في ورقة A6 (أصغر من A5)
A6_BUBBLE_RADIUS = 13
A6_ADAPTIVE_GAP_THRESHOLD = 15



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


def _detect_bubble_centers(gray_raw):
    """اكتشاف مراكز الفقاعات المطبوعة من قناع ثنائي."""
    _, thresh = cv2.threshold(gray_raw, 127, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    centers = []
    for c in contours:
        area = cv2.contourArea(c)
        perimeter = cv2.arcLength(c, True)
        if perimeter == 0:
            continue
        circularity = 4 * np.pi * area / (perimeter * perimeter)
        if 180 < area < 1000 and circularity > 0.4:
            m = cv2.moments(c)
            if m["m00"] != 0:
                centers.append((int(m["m10"] / m["m00"]), int(m["m01"] / m["m00"])))
    return centers


def _fit_a5_id_grid(gray_raw):
    """
    ضبط شبكة الكود (4 خانات × 10 أرقام) من الفقاعات المكتشفة في منطقة الكود.
    يرجع (xs[4], ys[10]) أو None.
    """
    id_pts = [
        p for p in _detect_bubble_centers(gray_raw)
        if 700 < p[0] < 1000 and 200 < p[1] < 730
    ]
    if len(id_pts) < 20:
        return None

    col_buckets = [[] for _ in range(4)]
    for x, y in id_pts:
        col_i = min(range(4), key=lambda i: abs(x - A5_ID_XS[i]))
        if abs(x - A5_ID_XS[col_i]) < 45:
            col_buckets[col_i].append((x, y))

    fitted_xs = []
    for i, bucket in enumerate(col_buckets):
        if len(bucket) < 5:
            return None
        fitted_xs.append(int(round(np.mean([p[0] for p in bucket]))))

    row_buckets = [[] for _ in range(10)]
    for x, y in id_pts:
        row_i = min(range(10), key=lambda i: abs(y - A5_ID_YS[i]))
        if abs(y - A5_ID_YS[row_i]) < 28:
            row_buckets[row_i].append(y)

    fitted_ys = []
    for i, bucket in enumerate(row_buckets):
        if len(bucket) < 2:
            return None
        fitted_ys.append(int(round(np.mean(bucket))))

    print(
        f"[OMR] ID grid fitted from {len(id_pts)} bubbles: "
        f"X={fitted_xs}, Y0={fitted_ys[0]}, step~{(fitted_ys[-1]-fitted_ys[0])/9:.1f}"
    )
    return fitted_xs, fitted_ys


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


def _save_debug_overlay(img_bgr, num_questions, fitted_coords=None, id_xs=None, id_ys=None):
    """
    يحفظ صورة debug:
    - أخضر (رفيع): القالب الثابت
    - برتقالي: نقاط قراءة الكود الفعلية
    - أحمر: نقاط قراءة الأسئلة الفعلية
    """
    if id_xs is None:
        id_xs = A5_ID_XS
    if id_ys is None:
        id_ys = A5_ID_YS
    overlay = img_bgr.copy()

    # قالب ثابت (للمقارنة)
    for cy in A5_ID_YS:
        for cx in A5_ID_XS:
            cv2.circle(overlay, (cx, cy), BUBBLE_RADIUS, (0, 180, 0), 1)
    for sec in COL_SECTIONS:
        for row_idx, q_num in enumerate(sec["qs"]):
            if q_num > num_questions:
                continue
            cy = QUESTION_YS[row_idx]
            for cx in sec["xs"].values():
                cv2.circle(overlay, (cx, cy), BUBBLE_RADIUS, (0, 180, 0), 1)

    # نقاط القراءة الفعلية
    for cy in id_ys:
        for cx in id_xs:
            cv2.circle(overlay, (cx, cy), BUBBLE_RADIUS, (255, 128, 0), 2)

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
            cv2.putText(
                overlay, str(q_num), (xs[T("أ")] + 5, cy - 2),
                cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 0, 0), 1,
            )

    cv2.putText(
        overlay,
        "Green=template  Orange=ID read  Red=answers read",
        (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (40, 40, 40), 1,
    )
    cv2.imwrite(DEBUG_OVERLAY_PATH, overlay)
    print(f"[DEBUG] overlay saved: {DEBUG_OVERLAY_PATH}")



def _read_student_id_a5(gray, xs=None, ys=None):
    """
    يقرأ رقم الطالب من شبكة فقاعات الكود لورقة A5.
    4 خانات (أعمدة) × 10 أرقام (صفوف 0-9)
    """
    if xs is None: xs = A5_ID_XS
    if ys is None: ys = A5_ID_YS
    digits = []
    for cx in xs:
        bubble_vals = {}
        for digit, cy in enumerate(ys):
            bubble_vals[digit] = _sample_bubble(gray, cx, cy, radius=BUBBLE_RADIUS)

        row_mean = float(np.mean(list(bubble_vals.values())))
        filled = []
        for digit, val in bubble_vals.items():
            gap = row_mean - val
            if gap >= ADAPTIVE_GAP_THRESHOLD and val <= ABSOLUTE_MAX_FILLED:
                filled.append(digit)

        if len(filled) == 1:
            digits.append(str(filled[0]))
        else:
            digits.append("?")

    if "?" in digits:
        return None
    return int("".join(digits))




def read_bubble_sheet(image_path_or_array, num_questions=54):
    """
    يقرأ ورقة إجابة الفقاعات باستخدام:
    1) محاذاة ديناميكية للشبكة (dynamic grid alignment) تتكيف مع الميلان، التمدد، والإزاحة
    2) عتبة تكيفية لكل صف (adaptive per-row threshold)
    3) درجة ثقة لكل إجابة

    يرجع: (dict سؤال→إجابة, student_id أو None, رسالة_خطأ_أو_None)
    """
    if isinstance(image_path_or_array, str):
        img = cv2.imread(image_path_or_array)
        if img is None:
            return None, None, "تعذر فتح الصورة"
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
    detected_bubbles = _detect_bubble_centers(gray_raw)

    answers = {}
    answer_confidence = {}
    fitted_coords = {}

    for sec_idx, sec in enumerate(COL_SECTIONS):
        col_xs = sec["xs"]
        questions_in_sec = sec["qs"]
        # حدود الـ X التقريبية لكل عمود
        x_min, x_max = [(350, 700), (50, 350)][sec_idx]
        
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
            
            # تقدير خطوة التباعد الرأسي (step_y) ديناميكياً من التجمعات المكتشفة
            # هذا يحمي الكود من الفشل في حالة وجود هوامش سحب أو تغيير في الأبعاد
            y_coords = sorted([sum(x[1] for x in r) / len(r) for r in rows])
            diffs = [y_coords[i+1] - y_coords[i] for i in range(len(y_coords)-1)]
            # نفلتر الفروقات لتكون قريبة من الخطوة المتوقعة (بين 45 و 60 بكسل)
            valid_diffs = [d for d in diffs if 45 < d < 60]
            if len(valid_diffs) > 0:
                estimated_step = np.median(valid_diffs)
            else:
                estimated_step = 53.115  # الخطوة الافتراضية
            
            # ب) تعيين رقم الصف الفعلي لكل تجمع وحساب الانحدار الخطي Y = a * row_idx + b
            if len(rows) >= 5:
                min_row_y = y_coords[0]
                valid_rows = []
                for r in rows:
                    avg_y = sum(x[1] for x in r) / len(r)
                    row_idx = int(round((avg_y - min_row_y) / estimated_step))
                    if 0 <= row_idx < 27:
                        valid_rows.append((row_idx, avg_y))
                
                if len(valid_rows) >= 5:
                    X_mat = np.array([[r[0], 1] for r in valid_rows])
                    Y_mat = np.array([r[1] for r in valid_rows])
                    a, b = np.linalg.lstsq(X_mat, Y_mat, rcond=None)[0]
                    # التأكد أن خطوة التباعد والبداية معقولين (الخطوة الافتراضية ~53.1)
                    # قمنا بتوسيع الحدود لتقبل الإزاحات الناتجة عن هوامش السحب من السكانر
                    b_min = 90 if sec_idx == 0 else 60
                    b_max = 250 if sec_idx == 0 else 220
                    if 45 < a < 60 and b_min < b < b_max:
                        ys = [int(round(a * i + b)) for i in range(27)]
                    else:
                        print(f"[OMR] Section {sec_idx+1} fit params out of range (step={a:.1f}, start={b:.1f}), using fallback Ys")
            
            # ج) ضبط إحداثيات الـ X ديناميكياً باستخدام الانحدار الخطي لمنع انكماش الصفحة أفقياً
            # أولاً: تقدير الإزاحة الأفقية الكلية للعمود (X shift) لتفادي الانزلاق لعمود مجاور
            best_dx = 0
            max_align_score = -1
            for dx in range(-100, 101):
                score = 0
                for p in sec_pts:
                    min_dist = min(abs(p[0] - (col_xs[ch] + dx)) for ch in col_xs)
                    if min_dist < 15:
                        score += 1
                if score > max_align_score or (score == max_align_score and abs(dx) < abs(best_dx)):
                    max_align_score = score
                    best_dx = dx
            
            col_xs_shifted = {ch: col_xs[ch] + best_dx for ch in col_xs}
            col_map = {T("د"): 0, T("ج"): 1, T("ب"): 2, T("أ"): 3}
            col_points = []
            for p in sec_pts:
                closest_ch = min(col_xs_shifted, key=lambda ch: abs(p[0] - col_xs_shifted[ch]))
                if abs(p[0] - col_xs_shifted[closest_ch]) < 20:
                    col_points.append((col_map[closest_ch], p[0]))
            
            x_fit_success = False
            if len(col_points) >= 5:
                try:
                    X_mat_x = np.array([[cp[0], 1] for cp in col_points])
                    Y_mat_x = np.array([cp[1] for cp in col_points])
                    a_x, b_x = np.linalg.lstsq(X_mat_x, Y_mat_x, rcond=None)[0]
                    
                    expected_b = [422, 78][sec_idx]
                    # التحقق من أن البداية قريبة من المتوقع بعد تطبيق الإزاحة الكلية
                    if 45 < a_x < 60 and (expected_b + best_dx - 30) < b_x < (expected_b + best_dx + 30):
                        xs = {ch: int(round(a_x * col_map[ch] + b_x)) for ch in col_xs}
                        print(f"[OMR] Section {sec_idx+1} fitted X: step={a_x:.1f}, start={b_x:.1f} (dx={best_dx})")
                        x_fit_success = True
                except Exception as e:
                    print(f"[OMR] Section {sec_idx+1} X fit failed: {e}")
            
            # في حالة عدم ملاءمة الخط، نلجأ للمتوسط البسيط كبديل احتياطي ثانٍ
            if not x_fit_success:
                x_groups = {ch: [] for ch in col_xs}
                for p in sec_pts:
                    closest_ch = min(col_xs_shifted, key=lambda ch: abs(p[0] - col_xs_shifted[ch]))
                    if abs(p[0] - col_xs_shifted[closest_ch]) < 20:
                        x_groups[closest_ch].append(p[0])
                for ch in col_xs:
                    if len(x_groups[ch]) >= 3:
                        xs[ch] = int(round(np.mean(x_groups[ch])))
                    
        fitted_coords[sec_idx] = (ys, xs)

    # محاذاة رأسية موحّدة: العمود الأيسر يستخدم نفس ميل/بداية العمود الأيمن إن أمكن
    if 0 in fitted_coords and 1 in fitted_coords:
        ys0, _ = fitted_coords[0]
        ys1, xs1 = fitted_coords[1]
        global_step = (ys0[-1] - ys0[0]) / 26.0
        global_start = ys0[0]
        ys1_mapped = [int(round(global_start + i * global_step)) for i in range(27)]
        # إن كان فرق الصف الأوسط كبيراً، نعتمد الخريطة الموحّدة
        mid_drift = abs(ys1[13] - ys1_mapped[13])
        if mid_drift > 8:
            print(f"[OMR] Section 2 Y unified with section 1 (drift was {mid_drift}px)")
            fitted_coords[1] = (ys1_mapped, xs1)

    for sec_idx, sec in enumerate(COL_SECTIONS):
        ys, xs = fitted_coords[sec_idx]
        questions_in_sec = sec["qs"]

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

    # تعديل إحداثيات الكود: أولوية لملاءمة منطقة الكود نفسها
    adjusted_id_ys = list(A5_ID_YS)
    adjusted_id_xs = list(A5_ID_XS)
    id_fit = _fit_a5_id_grid(gray_raw)
    if id_fit:
        adjusted_id_xs, adjusted_id_ys = id_fit
    elif 0 in fitted_coords:
        ys_sec0, xs_sec0 = fitted_coords[0]
        fitted_step = (ys_sec0[-1] - ys_sec0[0]) / 26.0
        # ربط صفوف الكود بصف السؤال 1 (وليس y=161 الثابت)
        adjusted_id_ys = [
            int(round(ys_sec0[0] + (cy - QUESTION_YS[0]) * (fitted_step / 53.115)))
            for cy in A5_ID_YS
        ]
        sec0_template_xs = COL_SECTIONS[0]["xs"]
        x_offsets = [
            xs_sec0[ch] - sec0_template_xs[ch]
            for ch in sec0_template_xs if ch in xs_sec0
        ]
        if x_offsets:
            avg_x_offset = int(round(np.mean(x_offsets)))
            adjusted_id_xs = [cx + avg_x_offset for cx in A5_ID_XS]
            print(f"[OMR] Adjusted Student ID X coords by offset: {avg_x_offset}")

    # --- حفظ overlay debug لمعرفة فين يقرأ الكود ---
    if DEBUG_SAVE_OVERLAY:
        _save_debug_overlay(img, num_questions, fitted_coords, id_xs=adjusted_id_xs, id_ys=adjusted_id_ys)

    student_id = _read_student_id_a5(gray, xs=adjusted_id_xs, ys=adjusted_id_ys)
    result = {q: answers.get(q, T("؟")) for q in range(1, num_questions + 1)}
    return result, student_id, None


# ===================== دوال ورقة A6 =====================

def _read_student_id_a6(gray):
    """
    يقرأ رقم الطالب من صفوف الفقاعات في أعلى ورقة A6.
    الترتيب: صف 1 = آلاف، صف 2 = مئات، صف 3 = عشرات، صف 4 = آحاد
    كل صف فيه 10 فقاعات للأرقام 0-9 (من اليمين لليسار)
    """
    digits = []
    for cy in A6_ID_YS:
        bubble_vals = {}
        for digit, cx in enumerate(A6_ID_XS):
            bubble_vals[digit] = _sample_bubble(gray, cx, cy, radius=A6_BUBBLE_RADIUS)

        row_mean = float(np.mean(list(bubble_vals.values())))
        filled = []
        for digit, val in bubble_vals.items():
            gap = row_mean - val
            if gap >= A6_ADAPTIVE_GAP_THRESHOLD and val <= ABSOLUTE_MAX_FILLED:
                filled.append(digit)

        if len(filled) == 1:
            digits.append(str(filled[0]))
        else:
            digits.append("?")

    if "?" in digits:
        return None  # لم يُقرأ الرقم بشكل كامل
    return int("".join(digits))


def _save_debug_overlay_a6(img_bgr, num_questions):
    """
    يحفظ صورة debug لورقة A6 تبيّن مواضع القراءة:
    - دوائر زرقاء = خانات رقم الطالب
    - دوائر حمراء = فقاعات الإجابات
    """
    overlay = img_bgr.copy()
    # --- رقم الطالب ---
    place_names = ["آلاف", "مئات", "عشرات", "آحاد"]
    for row_idx, cy in enumerate(A6_ID_YS):
        for digit, cx in enumerate(A6_ID_XS):
            cv2.circle(overlay, (cx, cy), A6_BUBBLE_RADIUS, (255, 128, 0), 2)
            cv2.putText(overlay, str(digit), (cx - 5, cy + 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.28, (0, 0, 200), 1)
        cv2.putText(overlay, place_names[row_idx], (A6_ID_XS[0] + 5, cy - 3),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (180, 0, 180), 1)
    # --- الأسئلة ---
    for sec in A6_COL_SECTIONS:
        col_xs = sec["xs"]
        for row_idx, q_num in enumerate(sec["qs"]):
            if q_num > num_questions:
                continue
            cy = A6_QUESTION_YS[row_idx]
            for choice, cx in col_xs.items():
                cv2.circle(overlay, (cx, cy), A6_BUBBLE_RADIUS, (0, 0, 255), 2)
            cv2.putText(overlay, str(q_num), (col_xs[T("أ")] + 5, cy - 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 0, 0), 1)
    path = "debug_overlay_a6.png"
    cv2.imwrite(path, overlay)
    print(f"[DEBUG A6] overlay saved: {path}")


def read_bubble_sheet_a6(image_path_or_array, num_questions=30):
    """
    يقرأ ورقة إجابة A6 (ربع A4) بها:
    - رقم الطالب في الأعلى (4 خانات × 10 فقاعات 0-9)
    - 30 سؤال في عمودين (15 يمين + 15 يسار)

    يرجع: (dict سؤال→إجابة, student_id أو None, رسالة_خطأ_أو_None)
    """
    if isinstance(image_path_or_array, str):
        img = cv2.imread(image_path_or_array)
        if img is None:
            return None, None, "تعذر فتح الصورة"
    else:
        img = image_path_or_array.copy()

    target_h, target_w = A6_TARGET_H, A6_TARGET_W

    # --- الخطوة 1: resize ---
    orig_h, orig_w = img.shape[:2]
    if orig_h != target_h or orig_w != target_w:
        img = cv2.resize(img, (target_w, target_h), interpolation=cv2.INTER_AREA)

    # --- الخطوة 2: كشف وتصحيح الدوران 180 درجة ---
    gray_temp = img[:, :, 1] if img.ndim == 3 else img.copy()
    _, thresh_temp = cv2.threshold(gray_temp, 127, 255, cv2.THRESH_BINARY_INV)
    contours_temp, _ = cv2.findContours(thresh_temp, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    bubbles_at_top = 0
    for c in contours_temp:
        area = cv2.contourArea(c)
        perimeter = cv2.arcLength(c, True)
        if perimeter == 0:
            continue
        circularity = 4 * np.pi * area / (perimeter * perimeter)
        if 60 < area < 1000 and circularity > 0.4:
            M = cv2.moments(c)
            if M["m00"] != 0:
                cY = int(M["m01"] / M["m00"])
                if cY < 100:
                    bubbles_at_top += 1
    if bubbles_at_top < 3:
        print("[OMR A6] ورقة مقلوبة — تدوير 180...")
        img = cv2.rotate(img, cv2.ROTATE_180)

    # --- الخطوة 3: تحويل لرمادي + CLAHE ---
    gray_raw = img[:, :, 1] if img.ndim == 3 else img.copy()
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray_raw)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    # --- الخطوة 4: قراءة رقم الطالب ---
    student_id = _read_student_id_a6(gray)

    # --- الخطوة 5: قراءة إجابات الأسئلة ---
    answers = {}
    for sec in A6_COL_SECTIONS:
        col_xs = sec["xs"]
        for row_idx, q_num in enumerate(sec["qs"]):
            if q_num > num_questions:
                continue
            cy = A6_QUESTION_YS[row_idx]
            bubble_vals = {ch: _sample_bubble(gray, cx, cy, radius=A6_BUBBLE_RADIUS)
                           for ch, cx in col_xs.items()}

            row_mean = float(np.mean(list(bubble_vals.values())))
            filled_choices = [ch for ch, val in bubble_vals.items()
                              if (row_mean - val) >= A6_ADAPTIVE_GAP_THRESHOLD
                              and val <= ABSOLUTE_MAX_FILLED]

            if len(filled_choices) > 1:
                answers[q_num] = "مزدوج"
            elif len(filled_choices) == 1:
                answers[q_num] = filled_choices[0]

    # --- حفظ debug overlay ---
    if DEBUG_SAVE_OVERLAY:
        _save_debug_overlay_a6(img, num_questions)

    result = {q: answers.get(q, T("؟")) for q in range(1, num_questions + 1)}
    return result, student_id, None


def grade(student_answers, answer_key, num_questions):

    score = 0
    details = []
    for q in range(1, num_questions+1):
        student = student_answers.get(q, T("؟"))
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


def _scan_naps2(scanner_name, driver_type, dpi, sheet_type="A5"):
    """مسح عبر NAPS2 — يرجع قائمة بكل الصفحات (مهم للفيدر)."""
    import subprocess, tempfile, os, glob, shutil
    naps2_path = r"C:\Program Files\NAPS2\NAPS2.Console.exe"
    if not os.path.exists(naps2_path):
        naps2_path = r"C:\Program Files (x86)\NAPS2\NAPS2.Console.exe"
        if not os.path.exists(naps2_path):
            raise Exception("NAPS2 not found")

    pagesize = "a5" if sheet_type == "A5" else "a6"
    drivers = ["twain", "wia"]

    def _read_pages_from_dir(tmpdir):
        files = sorted(glob.glob(os.path.join(tmpdir, "page_*.jpg")))
        if not files:
            files = sorted(glob.glob(os.path.join(tmpdir, "*.jpg")))
        images = []
        for f in files:
            im = cv2.imread(f)
            if im is not None:
                images.append(im)
        return images

    def _try_source(source):
        for drv in drivers:
            tmpdir = tempfile.mkdtemp(prefix="omr_naps2_")
            out_pattern = os.path.join(tmpdir, "page_$(n).jpg")
            cmd = [
                naps2_path,
                "--driver", drv,
                "--device", scanner_name,
                "--source", source,
                "--pagesize", pagesize,
                "--dpi", str(dpi),
                "--bitdepth", "gray",
                "-o", out_pattern,
                "-f",
            ]
            print(f"[NAPS2] Trying {source} with driver ({drv})...")
            result = subprocess.run(cmd, capture_output=True, text=True)
            images = _read_pages_from_dir(tmpdir)
            shutil.rmtree(tmpdir, ignore_errors=True)
            if images:
                print(f"[NAPS2] {source} ({drv}): {len(images)} page(s)")
                return images
            err = (result.stderr or result.stdout or "").strip()
            print(f"[NAPS2] {source} ({drv}) failed: {err}")

        return []

    pages = _try_source("feeder")
    if pages:
        return pages
    pages = _try_source("glass")
    if pages:
        return pages
    raise Exception("فشل المسح الضوئي تماماً باستخدام NAPS2 من الدرج والزجاج.")


def scan_pages(scanner_info, dpi=300, window=None, sheet_type="A5"):
    """سكان وارجع قائمة صور BGR (صفحة أو أكثر من الفيدر)."""
    if isinstance(scanner_info, str):
        scanner_info = {"name": scanner_info, "type": "TWAIN", "id": scanner_info}

    import os
    naps2_installed = (
        os.path.exists(r"C:\Program Files\NAPS2\NAPS2.Console.exe")
        or os.path.exists(r"C:\Program Files (x86)\NAPS2\NAPS2.Console.exe")
    )

    if naps2_installed:
        try:
            print("[SCAN] NAPS2 is installed. Using NAPS2 engine...")
            return _scan_naps2(scanner_info["name"], scanner_info["type"], dpi, sheet_type=sheet_type)
        except Exception as naps_err:
            print(f"[SCAN] NAPS2 engine failed, falling back to native drivers: {naps_err}")

    if scanner_info["type"] == "TWAIN":
        return _scan_twain(scanner_info["name"], dpi, window, sheet_type=sheet_type)
    img = _scan_wia(scanner_info["id"], dpi, sheet_type=sheet_type)
    return [img] if img is not None else []


def scan_image(scanner_info, dpi=300, window=None, sheet_type="A5"):
    """سكان صفحة واحدة (للتوافق) — يرجع آخر صفحة إن وُجدت أكثر من واحدة."""
    pages = scan_pages(scanner_info, dpi=dpi, window=window, sheet_type=sheet_type)
    if not pages:
        return None
    return pages[-1]



def _scan_twain(scanner_name, dpi, window, sheet_type="A5"):
    import twain
    sm = twain.SourceManager(window)
    ss = sm.open_source(scanner_name)
    try:
        # محاولة تفعيل درج سحب الورق الآلي (Feeder/ADF)
        ss.set_capability(twain.CAP_FEEDERENABLED, twain.TWTY_BOOL, True)
        ss.set_capability(twain.CAP_AUTOFEED, twain.TWTY_BOOL, True)
    except Exception as e:
        print(f"[TWAIN] Feeder not supported or failed: {e}")
    ss.set_capability(twain.ICAP_PIXELTYPE, twain.TWTY_UINT16, twain.TWPT_GRAY)
    ss.set_capability(twain.ICAP_XRESOLUTION, twain.TWTY_FIX32, dpi)
    ss.set_capability(twain.ICAP_YRESOLUTION, twain.TWTY_FIX32, dpi)
    if sheet_type == "A6":
        # A6 = 105×148 ملم = 4.13×5.83 بوصة
        try:
            ss.set_capability(twain.ICAP_SUPPORTEDSIZES, twain.TWTY_UINT16, twain.TWSS_A6)
        except Exception:
            ss.set_image_layout((0, 0, 4.13, 5.83))
    else:
        # A5 = 148×210 ملم = 5.83×8.27 بوصة
        try:
            ss.set_capability(twain.ICAP_SUPPORTEDSIZES, twain.TWTY_UINT16, twain.TWSS_A5)
        except Exception:
            ss.set_image_layout((0, 0, 5.83, 8.27))
    ss.request_acquire(show_ui=False, modal_ui=False)
    images = []
    while True:
        try:
            rv = ss.xfer_image_natively()
            if rv is None:
                break
            handle, count = rv
            pil_img = twain.dib_to_pil(handle)
            images.append(cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR))
        except twain.excDSTransferCancelled:
            break
    ss.destroy()
    sm.destroy()
    print(f"[TWAIN] transferred {len(images)} page(s) from feeder/flatbed")
    return images


def _scan_wia(device_id, dpi, sheet_type="A5"):
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

    # مساعد لتعيين الخصائص بالـ ID لتفادي مشاكل اللغة (Name Not Found)
    def set_prop_by_id(properties, prop_id, value):
        for prop in properties:
            if prop.PropertyID == prop_id:
                try:
                    prop.Value = value
                    return True
                except Exception as e:
                    print(f"[WIA] Failed to set prop {prop_id} to {value}: {e}")
                    return False
        return False

    def configure_item(item):
        set_prop_by_id(item.Properties, 6147, dpi)  # Horizontal Resolution
        set_prop_by_id(item.Properties, 6148, dpi)  # Vertical Resolution
        set_prop_by_id(item.Properties, 6146, 4)    # Current Intent (Grayscale = 4)
        
        # WIA يستخدم وحدة 1/1000 بوصة
        if sheet_type == "A6":
            w_thou = 4130
            h_thou = 5830
        else:
            w_thou = 5830
            h_thou = 8270
        
        set_prop_by_id(item.Properties, 6151, int(w_thou * dpi / 1000))  # Horizontal Extent
        set_prop_by_id(item.Properties, 6152, int(h_thou * dpi / 1000))  # Vertical Extent
        set_prop_by_id(item.Properties, 6149, 0)  # Horizontal Start
        set_prop_by_id(item.Properties, 6150, 0)  # Vertical Start

    # محاولة تهيئة الجهاز لاستخدام درج سحب الورق الآلي (ADF/Feeder)
    # 1 = FEEDER, 2 = FLATBED
    try:
        print("[WIA] Attempting to select ADF Feeder (property 3088 = 1)...")
        set_prop_by_id(device.Properties, 3088, 1)  # WIA_DPS_DOCUMENT_HANDLING_SELECT = 1 (FEEDER)
        set_prop_by_id(device.Properties, 3096, 1)  # WIA_DPS_PAGES = 1

        configure_item(scanner_item)
        image = scanner_item.Transfer("{B96B3CAB-0728-11D3-9D7B-0000F81EF32E}")
        print("[WIA] Scan from ADF Feeder succeeded!")
        return _save_wia_image(image)
    except Exception as adf_err:
        print(f"[WIA] ADF scan failed (might be empty or unsupported): {adf_err}")
        
        # إذا فشل، نتراجع إلى الزجاج (Flatbed)
        print("[WIA] Falling back to Flatbed (Glass) (property 3088 = 2)...")
        try:
            set_prop_by_id(device.Properties, 3088, 2)  # WIA_DPS_DOCUMENT_HANDLING_SELECT = 2 (FLATBED)
        except Exception as dev_err:
            print(f"[WIA] Failed to set device to flatbed: {dev_err}")

        configure_item(scanner_item)
        image = scanner_item.Transfer("{B96B3CAB-0728-11D3-9D7B-0000F81EF32E}")
        print("[WIA] Scan from Flatbed succeeded!")
        return _save_wia_image(image)

def _save_wia_image(image):
    import tempfile, os
    tmp = tempfile.mktemp(suffix=".bmp")
    image.SaveFile(tmp)
    img = cv2.imread(tmp)
    os.remove(tmp)
    return img




# ===================== GUI =====================

class OMRApp:

    def side_right(self):
        return "right" if LANG["ar"] else "left"

    def side_left(self):
        return "left" if LANG["ar"] else "right"

    def _toggle_language(self):
        LANG["ar"] = not LANG["ar"]
        self._lang_btn.config(text="AR" if not LANG["ar"] else "EN")
        self._rebuild_ui()

    def _rebuild_ui(self):
        geom = self.root.geometry()
        for w in self.root.winfo_children():
            w.destroy()
        self._build_ui()
        self.root.geometry(geom)
        self._apply_state_to_ui()

    def _apply_state_to_ui(self):
        self._refresh_key_grid()
        for idx, r in enumerate(self.students_results, 1):
            sid_display = str(r["student_id"]) if r.get("student_id") is not None else "-"
            pct = r["pct"]
            tag = "pass" if pct >= 50 else "fail"
            self.tree.insert("", "end",
                values=(r["idx"], r["file"], sid_display, f"{r['score']}/{r['n']}", r["score"], r["wrong"], f"{pct}%"),
                tags=(tag,))
        self.tree.tag_configure("pass", foreground="#10B981")
        self.tree.tag_configure("fail", foreground="#EF4444")
        
        if self.students_results:
            total = len(self.students_results)
            avg = sum(r["score"] for r in self.students_results) / total
            n = self.num_questions.get()
            lbl_text = T("إجمالي: {total} ورقة  |  متوسط: {avg:.1f}/{n}  |  أعلى: {max_score}  |  أدنى: {min_score}").format(
                total=total,
                avg=avg,
                n=n,
                max_score=max(r['score'] for r in self.students_results),
                min_score=min(r['score'] for r in self.students_results)
            )
            self.summary_var.set(lbl_text)
        else:
            self.summary_var.set("")
            
        self._update_key_status()

    def __init__(self, root):
        self.root = root
        self.root.title(T("Scanly OMR"))
        self.root.geometry("1200x740")
        self.root.configure(bg="#F8FAFC")
        self.root.minsize(900, 600)
        # Set window icon
        try:
            from PIL import Image as _Img, ImageTk as _ITk
            _icon_img = _Img.open(os.path.join(ASSET_DIR, "Scanly.png"))
            self._icon_photo = _ITk.PhotoImage(_icon_img)
            self.root.iconphoto(True, self._icon_photo)
        except Exception:
            pass

        self.answer_key = {}
        self.num_questions = tk.IntVar(value=54)
        self.students_results = []
        self.key_file = "answer_key.json"
        self.scanner_var = tk.StringVar(value="")
        self.scan_counter = 0
        # نوع ورقة الإجابة: "A5" = الديزاين الحالي (81 س) | "A6" = الجديد (A4 ÷ 4، 30 س)
        self.sheet_type = tk.StringVar(value="A5")

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
        header = tk.Frame(self.root, bg="#4D4D4D", height=60)
        header.pack(fill="x")
        header.pack_propagate(False)

        # Language Toggle Button (Left side of header)
        self._lang_btn = tk.Button(
            header,
            text="EN" if LANG["ar"] else "AR",
            font=("Dubai", 10, "bold"),
            bg="#333333",
            fg="white",
            activebackground="#333333",
            activeforeground="white",
            relief="flat",
            cursor="hand2",
            padx=12, pady=4,
            command=self._toggle_language
        )
        self._lang_btn.pack(side="left", padx=20, pady=12)

        # Logo icon
        try:
            from PIL import Image as _Img, ImageTk as _ITk
            _logo = _Img.open(os.path.join(ASSET_DIR, "Scanly.png")).resize((30, 30), _Img.LANCZOS)
            self._logo_img = _ITk.PhotoImage(_logo)
            tk.Label(header, image=self._logo_img, bg="#4D4D4D").pack(side=self.side_right(), padx=(20, 6), pady=10)
        except Exception:
            pass
        tk.Label(header, text=T("Scanly"),
                 font=("Dubai", 16, "bold"), bg="#4D4D4D", fg="white").pack(side=self.side_right(), padx=(0, 4), pady=10)

        main = tk.Frame(self.root, bg="#F8FAFC")
        main.pack(fill="both", expand=True, padx=12, pady=10)

        left = tk.Frame(main, bg="#F8FAFC", width=330)
        left.pack(side=self.side_right(), fill="y")
        left.pack_propagate(False)

        right = tk.Frame(main, bg="#F8FAFC")
        right.pack(side=self.side_right(), fill="both", expand=True, padx=(0,10))

        self._build_left(left)
        self._build_right(right)

    def _build_left(self, parent):
        # Scanner card
        scan_card = self._card(parent, T("🖨️  السكانر"))

        tk.Label(scan_card, text=T("اختر السكانر:"), font=("Dubai", 10),
                 bg="#FFFFFF", anchor="e").pack(fill="x", padx=10, pady=(6,2))

        scan_row = tk.Frame(scan_card, bg="#FFFFFF")
        scan_row.pack(fill="x", padx=10, pady=(0,4))

        self.scanner_combo = ttk.Combobox(scan_row, textvariable=self.scanner_var,
                                           font=("Dubai", 10), state="readonly")
        self.scanner_combo.pack(side="right", fill="x", expand=True)

        tk.Button(scan_row, text="🔄", font=("Dubai", 11), bg="#FFFFFF",
                  relief="flat", command=self._refresh_scanners).pack(side="left", padx=(4,0))

        # DPI
        dpi_row = tk.Frame(scan_card, bg="#FFFFFF")
        dpi_row.pack(fill="x", padx=10, pady=(0,8))
        tk.Label(dpi_row, text=T("دقة السكان (DPI):"), font=("Dubai", 10),
                 bg="#FFFFFF").pack(side="right")
        self.dpi_var = tk.IntVar(value=300)
        ttk.Combobox(dpi_row, textvariable=self.dpi_var,
                     values=[150, 200, 300, 400, 600],
                     width=6, state="readonly").pack(side="left")

        # Big scan button
        self.scan_btn = tk.Button(scan_card,
                  text=T("سكان وصحح"),
                  font=("Dubai", 14, "bold"),
                  bg="#4D4D4D", fg="#FFFFFF",
                  relief="flat", padx=10, pady=10,
                  command=self._scan_and_grade)
        self.scan_btn.pack(fill="x", padx=10, pady=(0,6))

        # Continuous scan button
        self.cont_btn = tk.Button(scan_card,
                  text=T("سكان متواصل (دفعة)"),
                  font=("Dubai", 11, "bold"),
                  bg="#4D4D4D", fg="#FFFFFF",
                  relief="flat", padx=10, pady=6,
                  command=self._scan_continuous)
        self.cont_btn.pack(fill="x", padx=10, pady=(0,8))

        # Calibration button
        tk.Button(scan_card,
                  text=T("معايرة الكشف"),
                  font=("Dubai", 10),
                  bg="#4D4D4D", fg="#FFFFFF",
                  relief="flat", padx=10, pady=5,
                  command=self._calibrate_detection).pack(fill="x", padx=10, pady=(0,8))

        # Settings card
        card = self._card(parent, T("⚙️  إعدادات الاختبار"))

        # --- اختيار نوع الورقة ---
        tk.Label(card, text=T("نوع ورقة الإجابة:"), font=("Dubai", 10, "bold"),
                 bg="#FFFFFF", anchor="e").pack(fill="x", padx=10, pady=(8, 2))

        type_frame = tk.Frame(card, bg="#FFFFFF")
        type_frame.pack(fill="x", padx=10, pady=(0, 2))

        self._type_lbl_var = tk.StringVar(value=T("ورقة A5 — 54 سؤال + رقم الطالب"))

        def _on_sheet_type_change(*_):
            if self.sheet_type.get() == "A5":
                self._num_spinbox.config(to=54)
                self.num_questions.set(54)
                self._type_lbl_var.set(T("ورقة A5 — 54 سؤال + رقم الطالب"))
                self._type_lbl.config(fg="#2563EB")
            else:
                self._num_spinbox.config(to=30)
                self.num_questions.set(30)
                self._type_lbl_var.set(T("ورقة A6 (ربع A4) — 30 سؤال + رقم الطالب"))
                self._type_lbl.config(fg="#7C3AED")
            self._refresh_key_grid()

        tk.Radiobutton(type_frame, text=T("A5  (الحالية)"),
                       variable=self.sheet_type, value="A5",
                       font=("Dubai", 10), bg="#FFFFFF",
                       selectcolor="#2563EB", fg="#0F172A",
                       activebackground="#FFFFFF",
                       command=_on_sheet_type_change).pack(side="right", padx=(0, 8))

        tk.Radiobutton(type_frame, text=T("A6  (A4 ÷ 4)"),
                       variable=self.sheet_type, value="A6",
                       font=("Dubai", 10), bg="#FFFFFF",
                       selectcolor="#7C3AED", fg="#0F172A",
                       activebackground="#FFFFFF",
                       command=_on_sheet_type_change).pack(side="right", padx=(0, 4))

        self._type_lbl = tk.Label(card, textvariable=self._type_lbl_var,
                                  font=("Dubai", 9), bg="#FFFFFF", fg="#2563EB", anchor="e")
        self._type_lbl.pack(fill="x", padx=10, pady=(0, 6))

        # --- عدد الأسئلة ---
        tk.Label(card, text=T("عدد الأسئلة:"), font=("Dubai", 11),
                 bg="#FFFFFF", anchor="e").pack(fill="x", padx=10, pady=(2, 2))
        num_frame = tk.Frame(card, bg="#FFFFFF")
        num_frame.pack(fill="x", padx=10, pady=(0, 8))
        self._num_spinbox = tk.Spinbox(num_frame, from_=1, to=54, width=6,
                                       textvariable=self.num_questions,
                                       font=("Dubai", 13, "bold"),
                                       command=self._refresh_key_grid)
        self._num_spinbox.pack(side="right")

        # Answer key card
        card2 = self._card(parent, T("🔑  مفتاح الإجابة"))

        # زر سكان ورقة الإجابة
        self.scan_key_btn = tk.Button(card2,
                  text=T("📄  سكان ورقة الإجابة"),
                  font=("Dubai", 12, "bold"),
                  bg="#10B981", fg="#FFFFFF",
                  relief="flat", padx=10, pady=10,
                  command=self._scan_answer_key)
        self.scan_key_btn.pack(fill="x", padx=10, pady=(8,4))

        # أو رفع صورة
        tk.Button(card2, text=T("🖼️  رفع صورة ورقة الإجابة"),
                  font=("Dubai", 10),
                  bg="#2563EB", fg="#FFFFFF",
                  relief="flat", padx=8, pady=6,
                  command=self._load_key_from_image).pack(fill="x", padx=10, pady=(0,6))

        # حالة المفتاح
        self.key_status_var = tk.StringVar(value=T("⚠️ لم يتم تحميل مفتاح بعد"))
        self.key_status_lbl = tk.Label(card2, textvariable=self.key_status_var,
                 font=("Dubai", 10, "bold"), bg="#FFFFFF", fg="#EF4444", anchor="e")
        self.key_status_lbl.pack(fill="x", padx=10, pady=(0,4))

        # separator
        tk.Frame(card2, bg="#F8FAFC", height=1).pack(fill="x", padx=8)
        tk.Label(card2, text=T("أو أدخل يدوياً:"), font=("Dubai", 9),
                 bg="#FFFFFF", fg="#475569", anchor="e").pack(fill="x", padx=10, pady=(4,0))

        self.key_frame_scroll = tk.Frame(card2, bg="#FFFFFF")
        self.key_frame_scroll.pack(fill="both", expand=True, padx=5, pady=5)

        canvas = tk.Canvas(self.key_frame_scroll, bg="#FFFFFF", highlightthickness=0, height=160)
        scrollbar = ttk.Scrollbar(self.key_frame_scroll, orient="vertical", command=canvas.yview)
        self.key_inner = tk.Frame(canvas, bg="#FFFFFF")
        self.key_inner.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0,0), window=self.key_inner, anchor="ne")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="right", fill="both", expand=True)
        scrollbar.pack(side="left", fill="y")

        self.key_vars = {}
        self._build_key_grid()
        self._update_key_status()

        btn_frame = tk.Frame(card2, bg="#FFFFFF")
        btn_frame.pack(fill="x", padx=8, pady=(0,8))
        tk.Button(btn_frame, text=T("💾 حفظ المفتاح"), font=("Dubai", 10),
                  bg="#10B981", fg="#FFFFFF", relief="flat", padx=8, pady=4,
                  command=self._save_key).pack(side="right", padx=2)
        tk.Button(btn_frame, text=T("مسح الكل"), font=("Dubai", 10),
                  bg="#EF4444", fg="#FFFFFF", relief="flat", padx=8, pady=4,
                  command=self._clear_key).pack(side="right", padx=2)

    def _update_key_status(self):
        n = self.num_questions.get()
        filled = sum(1 for q in range(1, n+1) if self.answer_key.get(q))
        if filled == n:
            self.key_status_var.set(T("✅ المفتاح جاهز ({n} سؤال)").format(n=n))
            self.key_status_lbl.config(fg="#10B981")
        elif filled > 0:
            self.key_status_var.set(T("⚠️ مكتمل {filled} من {n} سؤال").format(filled=filled, n=n))
            self.key_status_lbl.config(fg="#F59E0B")
        else:
            self.key_status_var.set(T("⚠️ لم يتم تحميل مفتاح بعد"))
            self.key_status_lbl.config(fg="#EF4444")

    def _scan_answer_key(self):
        """سكان ورقة الإجابة الصح واحفظها كمفتاح"""
        scanner = self._get_selected_scanner()
        if not scanner:
            messagebox.showerror(T("خطأ"), T("اختر سكانر أولاً!"))
            return
        self.scan_key_btn.config(text="⏳ جارٍ السكان...", state="disabled")
        self.root.update()
        try:
            pages = scan_pages(scanner, dpi=self.dpi_var.get(), window=self.root,
                               sheet_type=self.sheet_type.get())
            if not pages:
                messagebox.showerror(T("خطأ"), T("لم يتم استلام صورة!"))
                return
            if len(pages) > 1:
                msg = T("تم سحب {pages} ورقة من الفيدر.\nسيُستخدم أول صفحة فقط كمفتاح إجابة.").format(pages=len(pages))
                messagebox.showinfo(T(T("تنبيه")), msg)
            self._extract_key_from_image(pages[0])
        except Exception as e:
            messagebox.showerror(T("خطأ في السكانر"), str(e))
        finally:
            self.scan_key_btn.config(text=T("📄  سكان ورقة الإجابة"), state="normal")

    def _load_key_from_image(self):
        """رفع صورة ورقة الإجابة من الجهاز"""
        path = filedialog.askopenfilename(
            title="اختر صورة ورقة الإجابة",
            filetypes=[("صور", "*.png *.jpg *.jpeg *.bmp")])
        if not path:
            return
        img = cv2.imread(path)
        if img is None:
            messagebox.showerror(T("خطأ"), "تعذر فتح الصورة!")
            return
        self._extract_key_from_image(img)

    def _extract_key_from_image(self, img):
        """استخرج الإجابات من الصورة واحفظها كمفتاح"""
        n = self.num_questions.get()
        if self.sheet_type.get() == "A6":
            answers, _, err = read_bubble_sheet_a6(img, n)
        else:
            answers, _, err = read_bubble_sheet(img, n)
        if err:
            messagebox.showerror(T("خطأ في القراءة"), err)
            return
        # تحقق إن فيه إجابات اتقرأت
        found = sum(1 for v in answers.values() if v != T("؟"))
        if found < n // 2:
            if not messagebox.askyesno(T("تحذير"),
                T("تم قراءة {found} إجابة فقط من {n}.\nهل تريد المتابعة؟").format(found=found, n=n)):
                return
        # احفظ كمفتاح
        self.answer_key = {q: v for q, v in answers.items() if v != T("؟")}
        self._save_key_to_file()
        # حدّث الـ grid اليدوي
        for q, var in self.key_vars.items():
            var.set(self.answer_key.get(q, ""))
        self._update_key_status()
        self._show_key_preview(answers, n)

    def _show_key_preview(self, answers, n):
        win = tk.Toplevel(self.root)
        win.title(T("مراجعة مفتاح الإجابة"))
        win.geometry("520x580")
        win.configure(bg="#FFFFFF")
        win.grab_set()

        found = sum(1 for v in answers.values() if v != T("؟"))
        hdr = tk.Frame(win, bg="#10B981", height=50)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text=T("✅ تم قراءة {found} من {n} إجابة").format(found=found, n=n),
                 font=("Dubai", 13, "bold"), bg="#10B981", fg="#FFFFFF").pack(pady=12)

        tk.Label(win, text=T("راجع الإجابات — لو في غلطة عدّلها يدوياً من المفتاح"),
                 font=("Dubai", 10), bg="#FFFFFF", fg="#475569").pack(pady=(8,4))

        frame = tk.Frame(win, bg="#FFFFFF")
        frame.pack(fill="both", expand=True, padx=10, pady=5)
        canvas = tk.Canvas(frame, bg="#FFFFFF", highlightthickness=0)
        sb = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg="#FFFFFF")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0,0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        for ci, lbl in enumerate([T("السؤال"), T("الإجابة"), T("السؤال"), T("الإجابة"), T("السؤال"), T("الإجابة")]):
            tk.Label(inner, text=lbl, font=("Dubai", 9, "bold"),
                     bg="#F8FAFC", width=9, relief="flat", padx=4, pady=4).grid(
                row=0, column=ci, padx=1, pady=1)

        cols = 3
        for i, q in enumerate(range(1, n+1)):
            row = (i // cols) + 1
            col_base = (i % cols) * 2
            ans = answers.get(q, T("؟"))
            bg = "#ECFDF5" if ans != T("؟") else "#FEF2F2"
            tk.Label(inner, text=T("س {q}").format(q=q), font=("Dubai", 10),
                     bg=bg, width=9, padx=4, pady=5).grid(
                row=row, column=col_base, padx=1, pady=1, sticky="nsew")
            tk.Label(inner, text=ans, font=("Dubai", 12, "bold"),
                     bg=bg, fg="#10B981" if ans != T("؟") else "#EF4444",
                     width=9, padx=4, pady=5).grid(
                row=row, column=col_base+1, padx=1, pady=1, sticky="nsew")

        tk.Button(win, text="✅ تمام، ابدأ تصحيح الطلاب",
                  font=("Dubai", 12, "bold"), bg="#10B981", fg="#FFFFFF",
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
            self.scanner_combo["values"] = [T("لا يوجد سكانر متصل")]
            self.scanner_var.set(T("لا يوجد سكانر متصل"))
            self.scan_btn.config(state="disabled")
            self.cont_btn.config(state="disabled")
            messagebox.showwarning(T("تنبيه"),
                "مش لاقي سكانر.\n\nتأكد من:\n1- السكانر متوصل ومشغول\n2- درايفر الشركة مثبت (HP/Canon/Epson...)\n3- pywin32 مثبت: pip install pywin32")

    def _build_key_grid(self):
        for w in self.key_inner.winfo_children():
            w.destroy()
        self.key_vars = {}
        n = self.num_questions.get()

        for col, label in enumerate(["س", T("أ"), T("ب"), T("ج"), T("د")]):
            tk.Label(self.key_inner, text=label, font=("Dubai", 9, "bold"),
                     bg="#F8FAFC", width=4, relief="flat").grid(row=0, column=col, padx=1, pady=1)

        choices = [T("أ"), T("ب"), T("ج"), T("د")]
        for q in range(1, n+1):
            var = tk.StringVar(value=self.answer_key.get(q, ""))
            self.key_vars[q] = var
            bg = "#FFFFFF" if q % 2 == 0 else "#F8FAFC"
            tk.Label(self.key_inner, text=str(q), font=("Dubai", 9),
                     bg=bg, width=4).grid(row=q, column=0, padx=1, pady=1)
            for ci, ch in enumerate(choices):
                tk.Radiobutton(self.key_inner, text=ch, variable=var, value=ch,
                               font=("Dubai", 9), bg=bg,
                               selectcolor="#4D4D4D", fg="#0F172A",
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
        messagebox.showinfo(T("تم"), "✅ تم حفظ مفتاح الإجابة!")

    def _clear_key(self):
        for var in self.key_vars.values():
            var.set("")
        self.answer_key = {}

    def _build_right(self, parent):
        btn_row = tk.Frame(parent, bg="#F8FAFC")
        btn_row.pack(fill="x", pady=(0,8))

        tk.Button(btn_row, text=T("📂  رفع صورة"),
                  font=("Dubai", 11, "bold"), bg="#2563EB", fg="#FFFFFF",
                  relief="flat", padx=12, pady=7,
                  command=self._grade_single).pack(side="right", padx=4)

        tk.Button(btn_row, text=T("📁  رفع مجلد كامل"),
                  font=("Dubai", 11, "bold"), bg="#10B981", fg="#FFFFFF",
                  relief="flat", padx=12, pady=7,
                  command=self._grade_batch).pack(side="right", padx=4)

        tk.Button(btn_row, text=T("💾  تصدير CSV"),
                  font=("Dubai", 11, "bold"), bg="#10B981", fg="#FFFFFF",
                  relief="flat", padx=12, pady=7,
                  command=self._export).pack(side="left", padx=4)

        tk.Button(btn_row, text=T("🗑️ مسح النتائج"),
                  font=("Dubai", 11), bg="#475569", fg="#FFFFFF",
                  relief="flat", padx=12, pady=7,
                  command=self._clear_results).pack(side="left", padx=4)

        # Results table
        card = self._card(parent, T("📊  نتائج التصحيح"))
        self.summary_var = tk.StringVar(value="")
        tk.Label(card, textvariable=self.summary_var, font=("Dubai", 11),
                 bg="#FFFFFF", fg="#4D4D4D", anchor="e").pack(fill="x", padx=10, pady=4)

        cols = (T("م"), T("الملف / الورقة"), T("رقم الطالب"), T("الدرجة"), T("صح"), T("غلط"), T("النسبة"))
        self.tree = ttk.Treeview(card, columns=cols, show="headings", height=9)
        style = ttk.Style()
        style.configure("Treeview", font=("Dubai", 11), rowheight=26)
        style.configure("Treeview.Heading", font=("Dubai", 11, "bold"))

        widths = [35, 170, 80, 65, 55, 55, 65]
        for c, w in zip(cols, widths):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w, anchor="center")

        sb = ttk.Scrollbar(card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="right", fill="both", expand=True, padx=(8,0), pady=(0,8))
        sb.pack(side="left", fill="y", pady=(0,8))
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # Detail
        detail_card = self._card(parent, T("🔍  تفاصيل الورقة المختارة"))
        self.detail_text = tk.Text(detail_card, height=7, font=("Consolas", 10),
                                    bg="#F8FAFC", relief="flat", wrap="word",
                                    state="disabled")
        self.detail_text.pack(fill="both", expand=True, padx=8, pady=(0,8))
        self.detail_text.tag_configure("ok", foreground="#10B981")
        self.detail_text.tag_configure("err", foreground="#EF4444")
        self.detail_text.tag_configure("bold", font=("Consolas", 10, "bold"))

    def _card(self, parent, title):
        frame = tk.Frame(parent, bg="#FFFFFF", bd=0,
                         highlightthickness=1, highlightbackground="#E2E8F0")
        frame.pack(fill="both", expand=True, pady=(0,8))
        tk.Label(frame, text=title, font=("Dubai", 11, "bold"),
                 bg="#F8FAFC", fg="#0F172A", anchor="e", padx=10, pady=5).pack(fill="x")
        return frame

    def _validate_key(self):
        n = self.num_questions.get()
        missing = [q for q in range(1, n+1) if not self.answer_key.get(q)]
        if missing:
            return messagebox.askyesno(T("تحذير"),
                T("مفتاح الإجابة ناقص في {missing} سؤال.\nهل تريد المتابعة؟").format(missing=len(missing)))
        return True

    def _process_scanned_pages(self, pages, parent=None, on_progress=None, skip_preview=False):
        """تصحيح الصفحات — مع أو بدون معاينة. يرجع (نجح، فشل القراءة)."""
        accepted = 0
        failed = 0
        total = len(pages)
        silent_errors = skip_preview and total > 1
        for i, img in enumerate(pages, 1):
            if img is None:
                continue
            pending_num = self.scan_counter + 1
            if total > 1:
                name = T("سكان #{pending_num} (ورقة {i} من {total})").format(pending_num=pending_num, i=i, total=total)
            else:
                name = T("سكان #{pending_num}").format(pending_num=pending_num)
            if on_progress:
                on_progress(i, total, name, skip_preview)
            if skip_preview:
                self.scan_counter = pending_num
                if self._process_image_array(
                    img, name, parent=parent, silent=silent_errors,
                ):
                    accepted += 1
                else:
                    failed += 1
            else:
                ok, final_img = self._show_and_confirm_scan(img, name)
                if ok:
                    self.scan_counter = pending_num
                    if self._process_image_array(final_img, name, parent=parent):
                        accepted += 1
                    else:
                        failed += 1
        return accepted, failed

    def _show_and_confirm_scan(self, img, name, parent=None):
        """عرض الصورة المسحوبة واطلب تأكيد المستخدم ودعم تدويرها"""
        # سنحفظ الصورة في قائمة لتمكين تعديلها داخل الدوال الفرعية
        current_img = [img]
        
        # النافذة الرئيسية دائماً — حتى تظهر فوق نافذة السكان المتواصل
        preview_win = tk.Toplevel(self.root)
        preview_win.title(T("معاينة المسح - {name}").format(name=name))
        preview_win.configure(bg="#FFFFFF")
        preview_win.transient(self.root)
        preview_win.attributes("-topmost", True)
        preview_win.grab_set()
        
        # عنوان
        hdr = tk.Frame(preview_win, bg="#2563EB", height=50)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text=T("📸 معاينة الصورة المسحوبة"), 
                 font=("Dubai", 13, "bold"), bg="#2563EB", fg="#FFFFFF").pack(pady=10)
        
        # عرض الصورة
        img_label = tk.Label(preview_win, bg="#FFFFFF")
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
        msg_frame = tk.Frame(preview_win, bg="#FFFFFF")
        msg_frame.pack(fill="x", padx=10, pady=(0, 5))
        tk.Label(msg_frame, text="هل الصورة واضحة ومستقيمة؟ يمكنك شقلبتها إذا كانت مقلوبة.",
                 font=("Dubai", 10), bg="#FFFFFF", fg="#475569").pack()
        
        # أزرار
        btn_frame = tk.Frame(preview_win, bg="#FFFFFF")
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        result = [False]  # لحفظ إجابة المستخدم
        
        def _close_preview(accepted):
            result[0] = accepted
            try:
                preview_win.attributes("-topmost", False)
            except tk.TclError:
                pass
            preview_win.destroy()

        def on_accept():
            _close_preview(True)
        
        def on_reject():
            _close_preview(False)
            
        def on_rotate():
            # تدوير الصورة 180 درجة
            current_img[0] = cv2.rotate(current_img[0], cv2.ROTATE_180)
            update_preview()
        
        # زر القبول
        tk.Button(btn_frame, text="✅ الصورة ممتازة - تابع التصحيح",
                  font=("Dubai", 11, "bold"), bg="#10B981", fg="#FFFFFF",
                  relief="flat", padx=15, pady=8,
                  command=on_accept).pack(side="right", padx=5)
                  
        # زر التدوير التفاعلي
        tk.Button(btn_frame, text="🔁 شقلب الورقة 180°",
                  font=("Dubai", 11, "bold"), bg="#F59E0B", fg="#FFFFFF",
                  relief="flat", padx=15, pady=8,
                  command=on_rotate).pack(side="right", padx=5)
        
        # زر الرفض
        tk.Button(btn_frame, text="❌ أعد المسح",
                  font=("Dubai", 11), bg="#EF4444", fg="#FFFFFF",
                  relief="flat", padx=15, pady=8,
                  command=on_reject).pack(side="right", padx=5)
        
        preview_win.resizable(False, False)
        
        # انتظر حتى يغلق المستخدم النافذة
        self.root.wait_window(preview_win)
        
        return result[0], current_img[0]

    def _calibrate_detection(self):
        """أداة معايرة محسّنة — تعرض تقرير تفصيلي بدرجات الثقة لكل سؤال"""
        path = filedialog.askopenfilename(
            title=T("اختر صورة ورقة إجابة لمعايرة الكشف"),
            filetypes=[("صور", "*.png *.jpg *.jpeg *.bmp")])
        if not path:
            return

        img = cv2.imread(path)
        if img is None:
            messagebox.showerror(T("خطأ"), "تعذر فتح الصورة!")
            return

        # --- اجري القراءة مع الحصول على بيانات الثقة التفصيلية ---
        n = self.num_questions.get()
        # نُعيد تشغيل الكشف ونجمع بيانات أكثر تفصيلاً
        img_proc = img.copy()
        if self.sheet_type.get() == "A6":
            target_h, target_w = A6_TARGET_H, A6_TARGET_W
        else:
            target_h, target_w = TARGET_H, TARGET_W

        orig_h, orig_w = img_proc.shape[:2]
        if orig_h != target_h or orig_w != target_w:
            img_proc = cv2.resize(img_proc, (target_w, target_h), interpolation=cv2.INTER_AREA)
        img_proc = _correct_perspective(img_proc, target_w, target_h)
        gray = cv2.cvtColor(img_proc, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)

        # اختيار الإحداثيات والبارامترات بناءً على نوع الورقة
        if self.sheet_type.get() == "A6":
            sections = A6_COL_SECTIONS
            question_ys = A6_QUESTION_YS
            radius = A6_BUBBLE_RADIUS
        else:
            sections = COL_SECTIONS
            question_ys = QUESTION_YS
            radius = BUBBLE_RADIUS

        ADAPTIVE_GAP_THRESHOLD = 15
        ABSOLUTE_MAX_FILLED    = 185

        cal_data = {}  # q_num -> {"answer": x, "gap": y, "confidence": z, "vals": {...}}
        for sec in sections:
            col_xs = sec["xs"]
            for row_idx, q_num in enumerate(sec["qs"]):
                if q_num > n:
                    continue
                cy = question_ys[row_idx]
                bubble_vals = {ch: _sample_bubble(gray, cx, cy, radius=radius) for ch, cx in col_xs.items()}
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
                    cal_data[q_num] = {"answer": T("؟"), "gap": gap, "confidence": "none", "vals": bubble_vals}

        detected  = sum(1 for d in cal_data.values() if d["answer"] != T("؟"))
        high_conf = sum(1 for d in cal_data.values() if d["confidence"] == "high")
        med_conf  = sum(1 for d in cal_data.values() if d["confidence"] == "medium")
        low_conf  = sum(1 for d in cal_data.values() if d["confidence"] == "low")
        unanswered = [q for q, d in cal_data.items() if d["answer"] == T("؟")]

        # --- نافذة النتائج ---
        win = tk.Toplevel(self.root)
        win.title("تقرير معايرة الكشف")
        win.geometry("620x620")
        win.configure(bg="#FFFFFF")

        # رأس
        hdr_color = "#10B981" if detected >= 70 else ("#F59E0B" if detected >= 50 else "#EF4444")
        hdr = tk.Frame(win, bg=hdr_color, height=60)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        icon = "✅" if detected >= 70 else ("⚠️" if detected >= 50 else "❌")
        tk.Label(hdr, text=T("{icon}  تم كشف {detected} من {n} إجابة").format(icon=icon, detected=detected, n=n),
                 font=("Dubai", 14, "bold"), bg=hdr_color, fg="#FFFFFF").pack(pady=16)

        # إحصائيات الثقة
        stat_frame = tk.Frame(win, bg="#FFFFFF")
        stat_frame.pack(fill="x", padx=15, pady=10)
        for txt, val, color in [
            (T("🟢 ثقة عالية:"), high_conf, "#10B981"),
            (T("🟡 ثقة متوسطة:"), med_conf, "#F59E0B"),
            (T("🔴 ثقة منخفضة:"), low_conf, "#EF4444"),
            (T("⬜ غير مكتشف:"), len(unanswered), "#475569"),
        ]:
            row = tk.Frame(stat_frame, bg="#FFFFFF")
            row.pack(fill="x", pady=1)
            tk.Label(row, text=txt, font=("Dubai", 11), bg="#FFFFFF", fg="#0F172A",
                     anchor="e", width=18).pack(side="right")
            tk.Label(row, text=str(val), font=("Dubai", 11, "bold"), bg="#FFFFFF",
                     fg=color).pack(side="right", padx=6)

        # أسئلة غير مكتشفة
        if unanswered:
            tk.Frame(win, bg="#F8FAFC", height=1).pack(fill="x", padx=10)
            tk.Label(win, text=T("أسئلة لم تُكتشف ({unanswered}):").format(unanswered=len(unanswered)),
                     font=("Dubai", 10, "bold"), bg="#FFFFFF", fg="#EF4444", anchor="e").pack(
                fill="x", padx=15, pady=(8, 2))
            q_list = ", ".join(T("س{q}").format(q=q) for q in sorted(unanswered))
            tk.Label(win, text=q_list, font=("Dubai", 10), bg="#FFFFFF",
                     fg="#475569", wraplength=560, justify="right").pack(
                fill="x", padx=15, pady=(0, 6))

        # جدول تفصيلي قابل للتمرير
        tk.Frame(win, bg="#F8FAFC", height=1).pack(fill="x", padx=10)
        tk.Label(win, text="تفاصيل كل سؤال (الفجوة = فرق الظلام، كلما زاد كان الكشف أوثق):",
                 font=("Dubai", 9), bg="#FFFFFF", fg="#475569", anchor="e").pack(
            fill="x", padx=15, pady=(4, 2))

        table_frame = tk.Frame(win, bg="#FFFFFF")
        table_frame.pack(fill="both", expand=True, padx=10, pady=(0, 5))
        canvas = tk.Canvas(table_frame, bg="#FFFFFF", highlightthickness=0)
        sb = ttk.Scrollbar(table_frame, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg="#FFFFFF")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        conf_colors = {"high": "#ECFDF5", "medium": "#FFFBEB",
                       "low": "#FEF2F2", "none": "#F8FAFC"}
        conf_labels = {"high": T("عالية ✅"), "medium": T("متوسطة ⚠️"),
                       "low": T("منخفضة ⚠️"), "none": "—"}

        for ci, lbl in enumerate([T("السؤال"), T("الإجابة"), T("الفجوة"), T("الثقة")]):
            tk.Label(inner, text=lbl, font=("Dubai", 9, "bold"),
                     bg="#F8FAFC", width=10, relief="flat", padx=4, pady=4).grid(
                row=0, column=ci, padx=1, pady=1)

        cols = 2  # نعرض عمودين من البيانات جنباً لجنب
        for i, q in enumerate(range(1, n + 1)):
            d = cal_data.get(q, {"answer": T("؟"), "gap": 0, "confidence": "none"})
            bg = conf_colors[d["confidence"]]
            col_offset = (i % cols) * 4
            base_row   = (i // cols) + 1
            tk.Label(inner, text=T("س{q}").format(q=q), font=("Dubai", 9),
                     bg=bg, width=6, padx=3, pady=4).grid(
                row=base_row, column=col_offset, padx=1, pady=1, sticky="nsew")
            tk.Label(inner, text=d["answer"], font=("Dubai", 9, "bold"),
                     bg=bg, width=5, fg="#0F172A").grid(
                row=base_row, column=col_offset + 1, padx=1, pady=1, sticky="nsew")
            tk.Label(inner, text=f"{d['gap']:.1f}", font=("Dubai", 9),
                     bg=bg, width=6).grid(
                row=base_row, column=col_offset + 2, padx=1, pady=1, sticky="nsew")
            tk.Label(inner, text=conf_labels[d["confidence"]], font=("Dubai", 9),
                     bg=bg, width=10).grid(
                row=base_row, column=col_offset + 3, padx=1, pady=1, sticky="nsew")

        # نصيحة
        tip_frame = tk.Frame(win, bg="#EEF2FF")
        tip_frame.pack(fill="x", padx=10, pady=5)
        if detected >= 75:
            tip = "💡 الكشف ممتاز! يمكنك المتابعة بثقة."
        elif detected >= 55:
            tip = "💡 نصيحة: جرب رفع DPI إلى 300 أو أكثر لتحسين الكشف."
        else:
            tip = "💡 نصيحة: تأكد من إضاءة جيدة، ورقة مسطّحة، و DPI ≥ 300. قد تحتاج لإعادة معايرة الإحداثيات."
        tk.Label(tip_frame, text=tip, font=("Dubai", 10), bg="#EEF2FF",
                 fg="#1D4ED8", wraplength=560, justify="right", anchor="e").pack(
            fill="x", padx=10, pady=8)

        tk.Button(win, text=T("إغلاق"), font=("Dubai", 11), bg="#94A3B8", fg="#FFFFFF",
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
            messagebox.showerror(T("خطأ"), T("اختر سكانر أولاً!"))
            return

        self.scan_btn.config(text="⏳  جارٍ السكان...", state="disabled")
        self.root.update()

        try:
            pages = scan_pages(scanner, dpi=self.dpi_var.get(), window=self.root,
                               sheet_type=self.sheet_type.get())
            if not pages:
                messagebox.showerror(T("خطأ"), T("لم يتم استلام صورة من السكانر."))
                return
            self._process_scanned_pages(pages)
        except Exception as e:
            messagebox.showerror(T("خطأ في السكانر"), str(e))
        finally:
            self.scan_btn.config(text=T("📄  سكان وصحح"), state="normal")

    def _scan_continuous(self):
        """Keep scanning until user says stop."""
        if not self._validate_key():
            return
        scanner = self._get_selected_scanner()
        if not scanner:
            messagebox.showerror(T("خطأ"), T("اختر سكانر أولاً!"))
            return

        scanner_info = scanner
        win = tk.Toplevel(self.root)
        win.title(T(T("سكان متواصل")))
        win.geometry("400x250")
        win.configure(bg="#FFFFFF")
        win.transient(self.root)
        win.grab_set()

        tk.Label(win, text="🔁 وضع السكان المتواصل",
                 font=("Dubai", 13, "bold"), bg="#FFFFFF").pack(pady=(15, 5))
        tk.Label(
            win,
            text=T("ضع الورق في الفيدر أو على الزجاج ثم اضغط T('سكان التالي')."),
            font=("Dubai", 9), bg="#FFFFFF", fg="#475569", justify="center",
        ).pack()

        auto_grade_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            win,
            text=T("تصحيح مباشر بدون معاينة"),
            variable=auto_grade_var,
            bg="#FFFFFF",
            font=("Dubai", 10),
            anchor="e",
        ).pack(fill="x", padx=16, pady=(4, 0))

        count_var = tk.StringVar(value=T("تم سكان: 0 ورقة"))
        status_var = tk.StringVar(value="")
        tk.Label(win, textvariable=count_var, font=("Dubai", 11, "bold"),
                 bg="#FFFFFF", fg="#4D4D4D").pack(pady=4)
        tk.Label(win, textvariable=status_var, font=("Dubai", 9),
                 bg="#FFFFFF", fg="#475569").pack(pady=(0, 4))

        scanned = [0]
        scanning = [False]

        btn_frame = tk.Frame(win, bg="#FFFFFF")
        btn_frame.pack(pady=5)

        def _set_scanning(active):
            scanning[0] = active
            state = "disabled" if active else "normal"
            next_btn.config(state=state)
            done_btn.config(state=state)

        def do_scan():
            if scanning[0]:
                return
            _set_scanning(True)
            status_var.set("⏳ جارٍ السكان...")
            try:
                try:
                    win.grab_release()
                except tk.TclError:
                    pass
                self.root.update()

                pages = scan_pages(
                    scanner_info,
                    dpi=self.dpi_var.get(),
                    window=self.root,
                    sheet_type=self.sheet_type.get(),
                )
                if not pages:
                    messagebox.showerror(T("خطأ"), T("لم يتم استلام صورة!"), parent=win)
                    status_var.set("")
                    return

                def on_progress(i, total, name, skip_preview):
                    if skip_preview:
                        if total > 1:
                            status_var.set(T("جارٍ تصحيح ورقة {i} من {total}...").format(i=i, total=total))
                        else:
                            status_var.set(T("جارٍ التصحيح..."))
                    elif total > 1:
                        status_var.set(T("معاينة ورقة {i} من {total}...").format(i=i, total=total))
                    else:
                        status_var.set("معاينة الصورة...")
                    if win.winfo_exists():
                        win.update()

                batch, failed = self._process_scanned_pages(
                    pages,
                    parent=win,
                    on_progress=on_progress,
                    skip_preview=auto_grade_var.get(),
                )
                scanned[0] += batch
                count_var.set(T("تم سكان: {scanned} ورقة").format(scanned=scanned[0]))
                if batch > 0 and failed > 0:
                    status_var.set(T("✅ {batch} ورقة — تعذّر قراءة {failed}").format(batch=batch, failed=failed))
                elif batch > 0:
                    if len(pages) > 1:
                        status_var.set(T("✅ تم تصحيح {batch} ورقة").format(batch=batch))
                    else:
                        status_var.set("✅ تم التصحيح")
                elif failed > 0:
                    status_var.set(T("تعذّر قراءة الورقة — تحقق من الجودة"))
                elif len(pages) > 0 and not auto_grade_var.get():
                    status_var.set("لم تُقبل أي ورقة — راجع المعاينة")
                else:
                    status_var.set("")
                if failed > 0 and batch > 0:
                    messagebox.showwarning(
                        T("تنبيه"),
                        T("تم تصحيح {batch} ورقة.\nتعذّر قراءة {failed} ورقة — راجع الجودة أو المعايرة.").format(batch=batch, failed=failed),
                        parent=win,
                    )
                elif failed > 0:
                    messagebox.showerror(
                        T("خطأ"),
                        T("تعذّر قراءة الورقة — تحقق من وضع الورقة والإضاءة."),
                        parent=win,
                    )
            except Exception as e:
                messagebox.showerror(T("خطأ"), str(e), parent=win)
                status_var.set("")
            finally:
                try:
                    if win.winfo_exists():
                        win.grab_set()
                except tk.TclError:
                    pass
                _set_scanning(False)

        next_btn = tk.Button(btn_frame, text=T("📄 سكان التالي"),
                             font=("Dubai", 12, "bold"), bg="#4D4D4D", fg="#FFFFFF",
                             relief="flat", padx=14, pady=8,
                             command=do_scan)
        next_btn.pack(side="right", padx=8)
        done_btn = tk.Button(btn_frame, text=T("✅ انتهيت"),
                             font=("Dubai", 12), bg="#10B981", fg="#FFFFFF",
                             relief="flat", padx=14, pady=8,
                             command=win.destroy)
        done_btn.pack(side="right", padx=8)

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
            messagebox.showerror(T("خطأ"), "لا توجد صور!")
            return

        prog_win = tk.Toplevel(self.root)
        prog_win.title(T("جارٍ التصحيح..."))
        prog_win.geometry("360x120")
        prog_win.grab_set()
        tk.Label(prog_win, text=T("جارٍ تصحيح الأوراق..."), font=("Dubai", 12)).pack(pady=10)
        prog = ttk.Progressbar(prog_win, maximum=len(images), length=300)
        prog.pack(pady=5)
        status_lbl = tk.Label(prog_win, text="", font=("Dubai", 10))
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
        messagebox.showinfo(T("اكتمل"),
            T("✅ تم تصحيح {n_done} ورقة\nالمتوسط: {avg:.1f} / {questions}").format(n_done=n_done, avg=avg, questions=self.num_questions.get()))

    def _process_image(self, path, silent=False):
        n = self.num_questions.get()
        if self.sheet_type.get() == "A6":
            answers, student_id, err = read_bubble_sheet_a6(path, n)
        else:
            answers, student_id, err = read_bubble_sheet(path, n)
        if err:
            if not silent:
                messagebox.showerror(T("خطأ"), err)
            return
        display_name = os.path.basename(path)
        if student_id is not None:
            display_name = T("طالب {student_id:04d}").format(student_id=student_id)
        self._add_result(display_name, answers, student_id=student_id)

    def _process_image_array(self, img, name, parent=None, silent=False):
        n = self.num_questions.get()
        if self.sheet_type.get() == "A6":
            answers, student_id, err = read_bubble_sheet_a6(img, n)
        else:
            answers, student_id, err = read_bubble_sheet(img, n)
        if err:
            if not silent:
                kw = {"parent": parent} if parent is not None else {}
                messagebox.showerror(T("خطأ في القراءة"), err, **kw)
            return False
        display_name = name
        if student_id is not None:
            display_name = T("طالب {student_id:04d}").format(student_id=student_id)
        self._add_result(display_name, answers, student_id=student_id)
        return True

    def _add_result(self, name, answers, student_id=None):
        n = self.num_questions.get()
        score, details = grade(answers, self.answer_key, n)
        wrong = sum(1 for d in details if not d["ok"] and d["correct"])
        pct = round(score / n * 100) if n > 0 else 0
        idx = len(self.students_results) + 1

        result = {"idx": idx, "file": name, "score": score,
                  "wrong": wrong, "pct": pct, "details": details, "n": n,
                  "student_id": student_id}
        self.students_results.append(result)

        tag = "pass" if pct >= 50 else "fail"
        # في وضع A6 يظهر رقم الطالب في العمود الثاني
        sid_display = str(student_id) if student_id is not None else "-"
        iid = self.tree.insert("", "end",
            values=(idx, name, sid_display, f"{score}/{n}", score, wrong, f"{pct}%"),
            tags=(tag,))
        self.tree.tag_configure("pass", foreground="#10B981")
        self.tree.tag_configure("fail", foreground="#EF4444")

        total = len(self.students_results)
        avg = sum(r["score"] for r in self.students_results) / total
        lbl_text = T("إجمالي: {total} ورقة  |  متوسط: {avg:.1f}/{n}  |  أعلى: {max_score}  |  أدنى: {min_score}").format(
            total=total,
            avg=avg,
            n=n,
            max_score=max(r['score'] for r in self.students_results),
            min_score=min(r['score'] for r in self.students_results)
        )
        self.summary_var.set(lbl_text)

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
            self.detail_text.insert("end", T("\n❌ أسئلة خاطئة ({count}):\n").format(count=len(wrongs)), "err")
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
        if messagebox.askyesno(T("تأكيد"), "هل تريد مسح جميع النتائج؟"):
            self.students_results = []
            for item in self.tree.get_children():
                self.tree.delete(item)
            self.summary_var.set("")
            self.scan_counter = 0

    def _export(self):
        if not self.students_results:
            messagebox.showinfo(T("تنبيه"), T("لا توجد نتائج للتصدير!"))
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            title="حفظ النتائج")
        if not path:
            return
        n = self.num_questions.get()
        with open(path, "w", encoding="utf-8-sig") as f:
            q_headers = ",".join([T("س{q}").format(q=q) for q in range(1, n+1)])
            f.write(f"م,الملف,رقم الطالب,الدرجة,النسبة,{q_headers}\n")
            for r in self.students_results:
                student_id = r.get("student_id")
                student_id_str = f"{student_id:04d}" if student_id is not None else "-"
                answers_str = ",".join([d["student"] for d in r["details"]])
                f.write(f"{r['idx']},{r['file']},{student_id_str},{r['score']},{r['pct']}%,{answers_str}\n")
        messagebox.showinfo(T("تم"), T("✅ تم حفظ النتائج:\n{path}").format(path=path))




# ===================== LICENSE ACTIVATION WINDOW =====================

class ActivationWindow:
    def __init__(self, root: tk.Tk):
        self.root   = root
        self.passed = False
        self._hwid  = get_hwid()

        root.title(T("Scanly — تفعيل البرنامج"))
        root.geometry("620x560")
        root.configure(bg="#F8FAFC")
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        
        try:
            from PIL import Image as _Img, ImageTk as _ITk
            _icon_img = _Img.open(os.path.join(ASSET_DIR, "Scanly.png"))
            self._icon_photo = _ITk.PhotoImage(_icon_img)
            root.iconphoto(True, self._icon_photo)
        except Exception:
            pass

        self._build()

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
            r, g, b = int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)
            return "#{:02x}{:02x}{:02x}".format(int(r*f), int(g*f), int(b*f))

        hdr = tk.Frame(self.root, bg=PRIMARY, height=64)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text=T("🔒  Scanly — تفعيل البرنامج"),
                 font=(FONT, 16, "bold"), bg=PRIMARY, fg="#FFFFFF"
                 ).pack(side="right", padx=20, pady=14)

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=30, pady=20)

        tk.Label(body, text=T("🔒"),
                 font=("Segoe UI Emoji", 36),
                 bg=BG, fg=TEXT).pack(pady=(0, 6))
        tk.Label(body,
                 text=T("البرنامج يحتاج إلى ترخيص لتشغيله"),
                 font=(FONT, 12), bg=BG, fg=TEXT2).pack(pady=(0, 20))

        hwid_card = tk.Frame(body, bg=SURFACE,
                             highlightthickness=1,
                             highlightbackground=BORDER)
        hwid_card.pack(fill="x", pady=(0, 16))

        tk.Label(hwid_card,
                 text=T("رقم جهازك (أرسله للبائع للحصول على كود التفعيل)"),
                 font=(FONT, 9), bg=SURFACE, fg=TEXT2,
                 anchor="e", padx=12, pady=8
                 ).pack(fill="x")

        hwid_row = tk.Frame(hwid_card, bg=SURFACE)
        hwid_row.pack(fill="x", padx=12, pady=(4, 10))

        tk.Label(hwid_row, text=self._hwid,
                 font=(FONT, 14, "bold"),
                 bg=SURFACE, fg=SUCCESS,
                 anchor="e").pack(side="right", expand=True)

        copy_btn = tk.Button(hwid_row, text=T("📋 نسخ"),
                             font=(FONT, 9),
                             bg="#E2E8F0", fg=TEXT2,
                             activebackground="#CBD5E1",
                             relief="flat", cursor="hand2",
                             padx=10, pady=4,
                             command=self._copy_hwid)
        copy_btn.pack(side="left")

        tk.Label(body, text=T("أدخل كود التفعيل:"),
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

        self.status_var = tk.StringVar(value="")
        self.status_lbl = tk.Label(body, textvariable=self.status_var,
                                   font=(FONT, 10, "bold"),
                                   bg=BG, fg=DANGER,
                                   anchor="center")
        self.status_lbl.pack(fill="x", pady=(0, 10))

        act_btn = tk.Button(body,
                            text=T("⚡  تفعيل البرنامج"),
                            font=(FONT, 13, "bold"),
                            bg=PRIMARY, fg="#FFFFFF",
                            activebackground=hc(PRIMARY),
                            relief="flat", cursor="hand2",
                            padx=20, pady=12,
                            command=self._activate)
        act_btn.pack(fill="x")
        act_btn.bind("<Enter>", lambda e: act_btn.config(bg=hc(PRIMARY)))
        act_btn.bind("<Leave>", lambda e: act_btn.config(bg=PRIMARY))

        tk.Label(body, text=T("للحصول على كود التفعيل تواصل مع المطور"),
                 font=(FONT, 8), bg=BG, fg=TEXT2,
                 anchor="center").pack(fill="x", pady=(14, 0))

    def _copy_hwid(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self._hwid)
        messagebox.showinfo(T("✅"), T("تم نسخ رقم الجهاز!"))

    def _activate(self):
        key = self.key_var.get().strip().upper()

        if not key:
            self.status_var.set(T("❌  أدخل كود التفعيل"))
            return

        is_ok, start, expiry = verify_license_key(self._hwid, key)
        if not is_ok:
            self.status_var.set(T("❌  كود التفعيل غير صحيح"))
            return

        if expiry == LIFETIME_EXPIRY:
            plan = T("مدى الحياة")
        else:
            try:
                exp_date = datetime.strptime(expiry, "%Y-%m-%d").date()
                days = (exp_date - date.today()).days
                if days <= 32:    plan = T("شهر")
                elif days <= 95:  plan = T("٣ شهور")
                elif days <= 185: plan = T("٦ شهور")
                else:             plan = T("سنة")
            except Exception:
                plan = T("مخصص")

        save_license(self._hwid, key, start, expiry, plan)
        self.passed = True
        self.root.destroy()

    def _on_close(self):
        if not self.passed:
            self.root.destroy()
            import sys; sys.exit(0)


# ===================== MAIN =====================

def main():
    is_valid, msg, days_left = check_license()

    if not is_valid:
        act_root = tk.Tk()
        try:
            act_root.tk.call('tk', 'scaling', 1.2)
        except Exception:
            pass
        act_win = ActivationWindow(act_root)
        act_root.mainloop()

        if not act_win.passed:
            return

        is_valid, msg, days_left = check_license()
        if not is_valid:
            messagebox.showerror(T("❌ خطأ"), T("فشل التفعيل. تحقق من الكود وأعد المحاولة."))
            return

    root = tk.Tk()
    root.resizable(True, True)
    try:
        root.tk.call('tk', 'scaling', 1.2)
    except:
        pass

    app = OMRApp(root)

    if days_left == -1:
        root.title(root.title() + T("  —  ✅ مدى الحياة"))
    elif days_left > 0:
        root.title(root.title() + T("  —  ⏳ {days_left} يوم متبقي").format(days_left=days_left))

    root.mainloop()


if __name__ == "__main__":
    main()

