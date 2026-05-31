"""
Scanly License System - Core Module
====================================
Shared between omr_grader.py and license_generator.py

Key format:  XXXXX-XXXXX-XXXXX-YYYYMMDD
             └─ 15-char HMAC sig ─┘ └─ date ─┘
The expiry date is embedded inside the key — no separate date input needed.
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

    raw    = "|".join(parts)
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16].upper()
    return '-'.join(digest[i:i+4] for i in range(0, 16, 4))


# ── Internal signing ────────────────────────────────────────────────────────
def _raw_sign(hwid: str, expiry: str) -> str:
    """Returns 15-char uppercase hex HMAC signature."""
    msg = f"{hwid}|{expiry}".encode()
    return hmac.new(_SECRET, msg, hashlib.sha256).hexdigest()[:15].upper()


# ── License generation ──────────────────────────────────────────────────────
def generate_license(hwid: str, plan: str) -> tuple[str, str]:
    """
    Returns (license_key, expiry_date_str).
    The expiry date is embedded inside the key — format:
        XXXXX-XXXXX-XXXXX-YYYYMMDD
    """
    days = PLANS.get(plan)
    if days is None:
        expiry = LIFETIME_EXPIRY
    else:
        expiry = (date.today() + timedelta(days=days)).strftime("%Y-%m-%d")

    sig      = _raw_sign(hwid, expiry)           # 15 chars
    date_enc = expiry.replace("-", "")            # "99991231" or "20251231"
    key = f"{sig[:5]}-{sig[5:10]}-{sig[10:15]}-{date_enc}"
    return key, expiry


# ── License verification ────────────────────────────────────────────────────
def verify_license_key(hwid: str, key: str) -> tuple[bool, str]:
    """
    Verify a license key.
    Returns (is_valid, expiry_str).
    expiry_str is "" if invalid.
    """
    clean = key.upper().replace(" ", "")
    parts = clean.split("-")

    # Expected: 4 parts → 5-5-5-8
    if len(parts) != 4:
        return False, ""

    sig_provided = "".join(parts[:3])   # 15 chars
    date_enc     = parts[3]             # 8 chars YYYYMMDD

    if len(sig_provided) != 15 or len(date_enc) != 8:
        return False, ""

    # Parse expiry
    try:
        expiry = f"{date_enc[:4]}-{date_enc[4:6]}-{date_enc[6:8]}"
        # Validate it's a real date (or lifetime)
        if expiry != LIFETIME_EXPIRY:
            datetime.strptime(expiry, "%Y-%m-%d")
    except ValueError:
        return False, ""

    expected_sig = _raw_sign(hwid, expiry)
    if sig_provided != expected_sig:
        return False, ""

    return True, expiry


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
    now_ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
    data = {
        "h": hwid,
        "k": key,
        "e": expiry,
        "p": plan,
        "a": now_ts,    # activation timestamp
        "s": now_ts,    # last-seen timestamp (updated each run)
    }
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


def update_last_seen() -> None:
    """Call this every time the app launches successfully. Anchors the clock."""
    data = load_license()
    if not data:
        return
    data["s"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
    encoded = base64.b64encode(json.dumps(data).encode()).decode()
    with open(_license_path(), 'w') as f:
        f.write(encoded)


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
        return False, "لا يوجد ترخيص مفعʼل", -1

    current_hwid = get_hwid()
    if data.get("h") != current_hwid:
        return False, "الترخيص غير صالح لهذا الجهاز", -1

    hwid = data["h"]
    key  = data["k"]
    plan = data.get("p", "")

    is_ok, expiry = verify_license_key(hwid, key)
    if not is_ok:
        return False, "كود التفعيل غير صحيح أو تالف", -1

    # ── Clock rollback protection ──────────────────────────────────────────
    last_seen_str = data.get("s", "")
    if last_seen_str:
        try:
            last_seen = datetime.strptime(last_seen_str, "%Y-%m-%dT%H:%M:%S")
            now       = datetime.utcnow()
            # Allow up to 48h tolerance for DST / timezone changes
            if (last_seen - now).total_seconds() > 48 * 3600:
                return False, "❌  تم اكتشاف تلاعب بالتاريخ — اتصل بالمطور", -1
        except ValueError:
            pass

    # ── Lifetime license ───────────────────────────────────────────────────
    if expiry == LIFETIME_EXPIRY:
        return True, f"✅  ترخيص مدى الحياة  —  {plan}", -1

    # ── Timed license ────────────────────────────────────────────────────
    try:
        expiry_date = datetime.strptime(expiry, "%Y-%m-%d").date()
    except ValueError:
        return False, "تنسيق التاريخ في الترخيص غير صحيح", -1

    today = date.today()
    if today > expiry_date:
        return False, f"❌  انتهى الترخيص في  {expiry}", 0

    days_left = (expiry_date - today).days
    return True, f"✅  صالح حتى  {expiry}  ({days_left} يوم متبقي)", days_left
