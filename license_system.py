"""
Scanly License System - Core Module
====================================
Shared between omr_grader.py and license_generator.py
"""

import hashlib
import hmac
import uuid
import json
import os
import base64
import subprocess
from datetime import datetime, date

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
LICENSE_FILE    = "license.dat"


# ── Hardware ID ────────────────────────────────────────────────────────────
def get_hwid() -> str:
    """Return a stable hardware fingerprint for this machine."""
    parts = []

    # 1) MAC address (usually stable)
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

    raw   = "|".join(parts)
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16].upper()
    return '-'.join(digest[i:i+4] for i in range(0, 16, 4))


# ── License generation & verification ──────────────────────────────────────
def _sign(hwid: str, expiry: str) -> str:
    msg = f"{hwid}|{expiry}".encode()
    sig = hmac.new(_SECRET, msg, hashlib.sha256).hexdigest()[:20].upper()
    return '-'.join(sig[i:i+5] for i in range(0, 20, 5))


def generate_license(hwid: str, plan: str) -> tuple[str, str]:
    """
    Returns (license_key, expiry_date_str)
    plan: one of PLANS keys
    """
    days = PLANS.get(plan)
    if days is None:
        expiry = LIFETIME_EXPIRY
    else:
        from datetime import timedelta
        expiry = (date.today() + timedelta(days=days)).strftime("%Y-%m-%d")
    key = _sign(hwid, expiry)
    return key, expiry


def verify_license_key(hwid: str, key: str, expiry: str) -> bool:
    expected = _sign(hwid, expiry)
    return key.upper().replace('-', '') == expected.replace('-', '')


# ── Persistence ────────────────────────────────────────────────────────────
def _license_path() -> str:
    """Store license.dat next to the executable / script."""
    import sys
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, LICENSE_FILE)


def save_license(hwid: str, key: str, expiry: str, plan: str) -> None:
    data = {"h": hwid, "k": key, "e": expiry, "p": plan}
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

    hwid   = data["h"]
    key    = data["k"]
    expiry = data["e"]
    plan   = data.get("p", "")

    if not verify_license_key(hwid, key, expiry):
        return False, "كود التفعيل غير صحيح أو تالف", -1

    if expiry == LIFETIME_EXPIRY:
        return True, f"✅  ترخيص مدى الحياة  —  {plan}", -1

    try:
        expiry_date = datetime.strptime(expiry, "%Y-%m-%d").date()
    except ValueError:
        return False, "تنسيق التاريخ في الترخيص غير صحيح", -1

    today = date.today()
    if today > expiry_date:
        return False, f"❌  انتهى الترخيص في  {expiry}", 0

    days_left = (expiry_date - today).days
    return True, f"✅  صالح حتى  {expiry}  ({days_left} يوم متبقي)", days_left
