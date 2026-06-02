"""
Scanly License System - Core Module
====================================
Shared between omr_grader.py and license_generator.py

Key format:  XXXXX-XXXXX-SSSSSSSS-EEEEEEEE
             └─10char sig─┘ └─start─┘ └─expiry─┘

Both start and expiry are embedded and signed.
Rolling back the clock below start date = denied.
"""

import hashlib
import hmac
import uuid
import json
import os
import base64
import subprocess
from datetime import datetime, date, timedelta

# ── Secret Key (obfuscated as byte array) ──────────────────────────────────
# "Sc@nly#2025!P$r0Key&Secure_Omar"
_K = [83,99,64,110,108,121,35,50,48,50,53,33,80,36,114,48,75,101,121,38,
      83,101,99,117,114,101,95,79,109,97,114]
_SECRET = bytes(_K)


# ── Plans ──────────────────────────────────────────────────────────────────
PLANS = {
    "شهر":          30,
    "٣ شهور":       90,
    "٦ شهور":       180,
    "سنة":          365,
    "مدى الحياة":   None,   # None = lifetime
}

LIFETIME_EXPIRY = "9999-12-31"
LIFETIME_START  = "2000-01-01"   # lifetime licenses valid from year 2000
LICENSE_FILE    = "license.dat"


# ── Hardware ID ────────────────────────────────────────────────────────────
def get_hwid() -> str:
    """Return a stable hardware fingerprint for this machine."""
    parts = []

    # 1) MAC address
    mac = uuid.getnode()
    mac_str = ':'.join(f'{(mac >> i) & 0xff:02x}' for i in range(0, 48, 8))
    parts.append(mac_str)

    # 2) CPU Processor ID (Windows)
    try:
        out = subprocess.check_output(
            "wmic cpu get ProcessorId /value",
            shell=True, stderr=subprocess.DEVNULL, timeout=5
        ).decode(errors="ignore")
        for line in out.splitlines():
            if "ProcessorId=" in line:
                parts.append(line.split("=", 1)[1].strip())
                break
    except Exception:
        pass

    # 3) Disk serial (first fixed disk)
    try:
        out = subprocess.check_output(
            "wmic diskdrive where MediaType='Fixed hard disk media' get SerialNumber /value",
            shell=True, stderr=subprocess.DEVNULL, timeout=5
        ).decode(errors="ignore")
        for line in out.splitlines():
            if "SerialNumber=" in line:
                sn = line.split("=", 1)[1].strip()
                if sn:
                    parts.append(sn)
                    break
    except Exception:
        pass

    raw    = "|".join(parts)
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16].upper()
    return '-'.join(digest[i:i+4] for i in range(0, 16, 4))


# ── String sanitization ─────────────────────────────────────────────────────
def _clean_str(s: str) -> str:
    """Removes invisible unicode characters (like LTR/RTL marks) and normalizes dashes."""
    if not s: return ""
    import re
    # Replace common dash variants with standard hyphen
    s = s.replace("–", "-").replace("—", "-").replace("−", "-")
    # Remove everything except A-Z, 0-9, and hyphens
    return re.sub(r'[^A-Z0-9\-]', '', s.upper())


# ── Internal signing ────────────────────────────────────────────────────────
def _raw_sign(hwid: str, start: str, expiry: str) -> str:
    """Returns 10-char uppercase hex HMAC signature."""
    msg = f"{hwid}|{start}|{expiry}".encode()
    return hmac.new(_SECRET, msg, hashlib.sha256).hexdigest()[:10].upper()


# ── License generation ──────────────────────────────────────────────────────
def generate_license(hwid: str, plan: str) -> tuple[str, str, str]:
    """
    Returns (license_key, start_date_str, expiry_date_str).

    Key format: XXXXX-XXXXX-SSSSSSSS-EEEEEEEE
      - 10-char HMAC signature (over hwid + start + expiry)
      - 8-char start date  (YYYYMMDD) — NOT-BEFORE date
      - 8-char expiry date (YYYYMMDD)
    """
    hwid = _clean_str(hwid)
    days  = PLANS.get(plan)
    today = date.today()

    if days is None:
        start  = LIFETIME_START
        expiry = LIFETIME_EXPIRY
    else:
        start  = today.strftime("%Y-%m-%d")
        expiry = (today + timedelta(days=days)).strftime("%Y-%m-%d")

    sig       = _raw_sign(hwid, start, expiry)          # 10 chars
    start_enc = start.replace("-", "")                   # YYYYMMDD
    exp_enc   = expiry.replace("-", "")                  # YYYYMMDD

    key = f"{sig[:5]}-{sig[5:10]}-{start_enc}-{exp_enc}"
    return key, start, expiry


# ── License verification ────────────────────────────────────────────────────
def verify_license_key(hwid: str, key: str) -> tuple[bool, str, str]:
    """
    Verify a license key.
    Returns (is_valid, start_str, expiry_str).
    start_str and expiry_str are "" if invalid.
    """
    hwid = _clean_str(hwid)
    clean = _clean_str(key)
    parts = clean.split("-")

    # Expected 4 parts: 5-5-8-8
    if len(parts) != 4:
        return False, "", ""

    sig_provided = parts[0] + parts[1]   # 10 chars
    start_enc    = parts[2]               # 8 chars YYYYMMDD
    exp_enc      = parts[3]               # 8 chars YYYYMMDD

    if len(sig_provided) != 10 or len(start_enc) != 8 or len(exp_enc) != 8:
        return False, "", ""

    # Parse dates
    try:
        start  = f"{start_enc[:4]}-{start_enc[4:6]}-{start_enc[6:8]}"
        expiry = f"{exp_enc[:4]}-{exp_enc[4:6]}-{exp_enc[6:8]}"
        if start != LIFETIME_START:
            datetime.strptime(start, "%Y-%m-%d")
        if expiry != LIFETIME_EXPIRY:
            datetime.strptime(expiry, "%Y-%m-%d")
    except ValueError:
        return False, "", ""

    # Verify signature
    expected_sig = _raw_sign(hwid, start, expiry)
    if sig_provided != expected_sig:
        return False, "", ""

    return True, start, expiry


# ── Persistence ────────────────────────────────────────────────────────────
def _license_path() -> str:
    import sys
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, LICENSE_FILE)


def save_license(hwid: str, key: str, start: str, expiry: str, plan: str) -> None:
    data = {"h": hwid, "k": key, "st": start, "e": expiry, "p": plan}
    encoded = base64.b64encode(json.dumps(data).encode()).decode()
    with open(_license_path(), 'w') as f:
        f.write(encoded)


def load_license() -> dict | None:
    path = _license_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r') as f:
            encoded = f.read().strip()
        return json.loads(base64.b64decode(encoded).decode())
    except Exception:
        return None


# ── Main check (called at startup) ─────────────────────────────────────────
def check_license() -> tuple[bool, str, int]:
    """
    Returns: (is_valid, message, days_remaining)
      days_remaining = -1  → lifetime
      days_remaining =  0  → expired today
      days_remaining >  0  → days left
    """
    data = load_license()
    if not data:
        return False, "لا يوجد ترخيص مفعّل", -1

    current_hwid = get_hwid()
    if data.get("h") != current_hwid:
        return False, "الترخيص غير صالح لهذا الجهاز", -1

    hwid = data["h"]
    key  = data["k"]
    plan = data.get("p", "")

    is_ok, start, expiry = verify_license_key(hwid, key)
    if not is_ok:
        return False, "كود التفعيل غير صحيح أو تالف", -1

    # ── Lifetime license ────────────────────────────────────────────────────
    if expiry == LIFETIME_EXPIRY:
        return True, f"✅  ترخيص مدى الحياة  —  {plan}", -1

    # ── Date checks ─────────────────────────────────────────────────────────
    try:
        start_date  = datetime.strptime(start,  "%Y-%m-%d").date()
        expiry_date = datetime.strptime(expiry, "%Y-%m-%d").date()
    except ValueError:
        return False, "تنسيق التاريخ في الترخيص غير صحيح", -1

    today = date.today()

    # Clock rollback: current date is BEFORE the activation/start date
    if today < start_date:
        return (False,
                f"❌  تاريخ الجهاز ({today}) سابق لتاريخ تفعيل الترخيص ({start})"
                f"\n   تحقق من ضبط التاريخ على جهازك", -1)

    # Expired
    if today > expiry_date:
        return False, f"❌  انتهى الترخيص في  {expiry}", 0

    days_left = (expiry_date - today).days
    return True, f"✅  صالح حتى  {expiry}  ({days_left} يوم متبقي)", days_left
