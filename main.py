"""
WhatsApp Multi-Linker — PREMIUM v48 (ARJUNTHAKUR + FIXED GROUP IMAGE + NO VERIFICATION)
"""

import sys, os, types, json, logging, random
try:
    import colorama
    colorama.just_fix_windows_console()
except Exception:
    pass

logging.getLogger('neonize').setLevel(logging.CRITICAL)
logging.getLogger('urllib3').setLevel(logging.CRITICAL)

class ColorFormatter(logging.Formatter):
    COLORS = {'DEBUG':'\033[96m','INFO':'\033[92m','WARNING':'\033[93m','ERROR':'\033[91m','CRITICAL':'\033[1;95m'}
    RESET = '\033[0m'; DIM = '\033[2m'; BOLD = '\033[1m'
    def format(self, record):
        color = self.COLORS.get(record.levelname, '')
        ts = self.formatTime(record, '%H:%M:%S')
        icon = {'DEBUG':'🔍','INFO':'💡','WARNING':'⚠️ ','ERROR':'❌','CRITICAL':'🔥'}.get(record.levelname,'•')
        return f"{self.DIM}{ts}{self.RESET} {color}{self.BOLD}{icon} {record.levelname:<8}{self.RESET} {record.getMessage()}"

_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(ColorFormatter())
logging.basicConfig(level=logging.INFO, handlers=[_handler], force=True)
logger = logging.getLogger(__name__)

try:
    import magic  # noqa
except Exception:
    fake_magic = types.ModuleType("magic")
    fake_magic.Magic = lambda *a, **k: None
    fake_magic.from_buffer = lambda *a, **k: "application/octet-stream"
    fake_magic.from_file = lambda *a, **k: "application/octet-stream"
    sys.modules["magic"] = fake_magic

try:
    import psutil
    PSUTIL_OK = True
except ImportError:
    PSUTIL_OK = False

import io, gc, uuid, time, base64, shutil, hashlib, secrets, tempfile, mimetypes, contextlib
import urllib.request
from datetime import timedelta
import threading, traceback
from urllib.parse import quote
from flask import Flask, render_template_string, request, jsonify, session

try:
    import qrcode
    QR_OK = True
except ImportError:
    QR_OK = False

NEONIZE_OK = False
NEONIZE_ERROR = ""
try:
    from neonize.client import NewClient
    from neonize.events import ConnectedEv, DisconnectedEv, QREv, PairStatusEv, MessageEv
    from neonize.utils import build_jid
    NEONIZE_OK = True
    logger.info("NEONIZE IMPORTED SUCCESSFULLY")
except Exception as e:
    NEONIZE_ERROR = str(e)
    logger.error(f"NEONIZE IMPORT FAILED: {e}")

WAMessage = None
ExtendedTextMessage = None
ContextInfo = None
ImageMessage = None
PROTO_MENTION_OK = False
PROTO_IMAGE_OK = False

for _path in ["neonize.proto.waE2E.WAWebProtobufsE2E_pb2", "neonize.proto.WAWebProtobufsE2E_pb2"]:
    try:
        _mod = __import__(_path, fromlist=['Message', 'ExtendedTextMessage', 'ContextInfo', 'ImageMessage'])
        WAMessage = getattr(_mod, 'Message', None)
        ExtendedTextMessage = getattr(_mod, 'ExtendedTextMessage', None)
        ContextInfo = getattr(_mod, 'ContextInfo', None)
        ImageMessage = getattr(_mod, 'ImageMessage', None)
        if WAMessage and ExtendedTextMessage and ContextInfo:
            PROTO_MENTION_OK = True
        if ImageMessage:
            PROTO_IMAGE_OK = True
        if PROTO_MENTION_OK:
            logger.info(f"✅ PROTO LOADED FROM: {_path}")
            break
    except Exception:
        continue

if not PROTO_MENTION_OK:
    try:
        from neonize.proto import Message as WAMessage
        from neonize.proto import ExtendedTextMessage
        from neonize.proto import ContextInfo
        PROTO_MENTION_OK = True
        logger.info("✅ MENTION PROTO LOADED FROM neonize.proto")
    except Exception as e:
        logger.warning(f"❌ MENTION PROTO UNAVAILABLE: {e}")

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.permanent_session_lifetime = timedelta(days=30)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('sessions', exist_ok=True)
IMAGETASKS_DIR = os.path.join(os.getcwd(), 'imagetasks')
os.makedirs(IMAGETASKS_DIR, exist_ok=True)
WA_IMG_SEND_DIR = os.path.join(tempfile.gettempdir(), 'wa_img_send')
os.makedirs(WA_IMG_SEND_DIR, exist_ok=True)

# ═══════════════════════════════════════════════════════════
# 🔥 ADMIN CREDENTIALS (CHANGED AS REQUESTED)
# ═══════════════════════════════════════════════════════════
ADMIN_USERNAME = "ARJUNTHAKUR"
ADMIN_DISPLAY_NAME = "🔥╭─✺ARJUN THAKUR✺─╮🔥"
ADMIN_PASSWORD = "ARJUNTHAKUR"
BANNER_URL = "https://i.ibb.co/m5mKsjG2/zk-NBtlym-M6z-X4-Dndr-U.gif"

PROCESS_START_TIME = time.time()
_process_peak_rss = 0
_prev_net = {'time': time.time(), 'bytes_sent': 0, 'bytes_recv': 0}
GLOBAL_STATS = {'total_msg_sent': 0, 'total_img_sent': 0}

_CPU_SAMPLER = {'proc_percent': 0.0, 'sys_percent': 0.0, 'proc_mem_mb': 0.0, 'peak_mem_mb': 0.0}

def _cpu_sampler_worker():
    global _process_peak_rss
    if not PSUTIL_OK:
        return
    try:
        proc = psutil.Process(os.getpid())
        proc.cpu_percent(interval=None)
        psutil.cpu_percent(interval=None)
        time.sleep(2)
        while True:
            try:
                _CPU_SAMPLER['proc_percent'] = round(proc.cpu_percent(interval=None), 1)
                _CPU_SAMPLER['sys_percent'] = round(psutil.cpu_percent(interval=None), 1)
                rss = proc.memory_info().rss
                if rss > _process_peak_rss:
                    _process_peak_rss = rss
                _CPU_SAMPLER['proc_mem_mb'] = round(rss / (1024 * 1024), 1)
                _CPU_SAMPLER['peak_mem_mb'] = round(_process_peak_rss / (1024 * 1024), 1)
            except Exception:
                pass
            time.sleep(5)
    except Exception as e:
        logger.warning(f"CPU sampler error: {e}")

sessions = {}
sessions_lock = threading.Lock()
active_tasks = {}
tasks_lock = threading.Lock()

TASKS_FILE = os.path.join(os.getcwd(), 'tasks_state.json')
TASKS_SAVE_LOCK = threading.Lock()
BLOCKED_FILE = os.path.join(os.getcwd(), 'blocked_users.json')
BLOCKED_LOCK = threading.Lock()

def display_name_for(username):
    if username == ADMIN_USERNAME:
        return ADMIN_DISPLAY_NAME
    return username or ''

def load_blocked():
    try:
        with open(BLOCKED_FILE) as f: return json.load(f)
    except Exception: return {}

def save_blocked(m):
    with BLOCKED_LOCK:
        try:
            with open(BLOCKED_FILE, 'w') as f: json.dump(m, f, indent=2)
        except Exception: pass

BLOCKED_USERS = load_blocked()

def task_mark_running(t):
    if not t.get('run_since'): t['run_since'] = time.time()
    t['stopped_at'] = 0

def task_mark_stopped(t):
    rs = t.get('run_since')
    if rs:
        t['uptime_acc'] = float(t.get('uptime_acc', 0) or 0) + max(0, time.time() - rs)
        t['run_since'] = 0
    if not t.get('stopped_at'): t['stopped_at'] = time.time()

def task_uptime(t):
    acc = float(t.get('uptime_acc', 0) or 0)
    rs = t.get('run_since')
    if rs: acc += max(0, time.time() - rs)
    return int(acc)

def format_uptime_long(sec):
    sec = int(max(0, sec)); d = sec // 86400; h = (sec % 86400) // 3600
    m = (sec % 3600) // 60; s = sec % 60; parts = []
    if d > 0: parts.append(f"{d} DAY'S")
    if h > 0: parts.append(f"{h} HOURS")
    if m > 0: parts.append(f"{m} MINUTES")
    parts.append(f"{s} SECONDS"); return " ".join(parts)

_last_save_ts = 0
_SAVE_THROTTLE = 3

def save_tasks_state(force=False):
    global _last_save_ts
    now = time.time()
    if not force and (now - _last_save_ts) < _SAVE_THROTTLE: return
    _last_save_ts = now
    try:
        with TASKS_SAVE_LOCK:
            with tasks_lock:
                data = {}; ts = time.time()
                for tid, t in active_tasks.items():
                    status = (t.get('status') or '').upper()
                    if status not in ('RUNNING', 'QUEUED'):
                        continue
                    data[tid] = {k: t.get(k) for k in (
                        'session','target','target_name','target_type','status','messages',
                        'file_name','hater_name','last_hater_name','interval','sent','total',
                        'resume_index','start_time','next_message_time','mention_option',
                        'custom_mentions','owner','stopped_at','show_mention_name',
                        'task_kind','image_paths','image_count')}
                    data[tid]['uptime_acc'] = float(t.get('uptime_acc', 0) or 0)
                    data[tid]['run_since'] = t.get('run_since', 0) or 0
                    data[tid]['saved_at'] = ts
            tmp = TASKS_FILE + '.tmp'
            with open(tmp, 'w') as f: json.dump(data, f, indent=2)
            os.replace(tmp, TASKS_FILE)
    except Exception as e:
        logger.error(f"SAVE TASKS ERROR: {e}")

def load_tasks_state():
    if not os.path.exists(TASKS_FILE): return
    try:
        with open(TASKS_FILE) as f: data = json.load(f)
        with tasks_lock:
            for tid, t in data.items():
                status = (t.get('status') or '').upper()
                if status not in ('RUNNING', 'QUEUED'):
                    continue
                if not t.get('owner'):
                    t['owner'] = SESSION_OWNERS.get(t.get('session', ''), None) or ADMIN_USERNAME
                if 'show_mention_name' not in t: t['show_mention_name'] = True
                if 'task_kind' not in t: t['task_kind'] = 'MESSAGE'
                acc = float(t.get('uptime_acc', 0) or 0); rs = t.get('run_since', 0) or 0
                if rs:
                    saved_at = t.get('saved_at') or rs
                    acc += max(0, saved_at - rs)
                t['run_since'] = 0; t['uptime_acc'] = acc
                active_tasks[tid] = t
        logger.info(f"LOADED {len(data)} ACTIVE TASKS FROM DISK")
    except Exception as e:
        logger.error(f"LOAD TASKS ERROR: {e}")

USERS_FILE = os.path.join(os.getcwd(), 'users.json')
USERS_LOCK = threading.Lock()

def load_users():
    if not os.path.exists(USERS_FILE):
        salt = secrets.token_hex(8)
        default = {"admin": {"salt": salt, "pass": hashlib.sha256((salt + "admin123").encode()).hexdigest(), "created": time.time()}}
        with open(USERS_FILE, 'w') as f: json.dump(default, f, indent=2)
        logger.info("DEFAULT LOGIN → admin / admin123")
    try:
        with open(USERS_FILE) as f: return json.load(f)
    except Exception: return {}

USERS = load_users()

def save_users():
    with USERS_LOCK:
        with open(USERS_FILE, 'w') as f: json.dump(USERS, f, indent=2)

def hash_pass(salt, password):
    return hashlib.sha256((salt + password).encode()).hexdigest()

def ensure_admin_user():
    # Force update admin credentials to ARJUNTHAKUR
    if ADMIN_USERNAME not in USERS or True:
        salt = secrets.token_hex(8)
        USERS[ADMIN_USERNAME] = {"salt": salt, "pass": hash_pass(salt, ADMIN_PASSWORD), "created": time.time()}
        save_users()
        logger.info(f"✅ ADMIN USER SET: {ADMIN_USERNAME} / {ADMIN_PASSWORD}")

ensure_admin_user()

OWNER_FILE = os.path.join(os.getcwd(), 'sessions_owner.json')

def load_owner_map():
    try:
        with open(OWNER_FILE) as f: return json.load(f)
    except Exception: return {}

def save_owner_map(m):
    try:
        with open(OWNER_FILE, 'w') as f: json.dump(m, f, indent=2)
    except Exception: pass

SESSION_OWNERS = load_owner_map()
META_FILE = os.path.join(os.getcwd(), 'sessions_meta.json')
META_LOCK = threading.Lock()

def _load_meta():
    try:
        with open(META_FILE) as f: return json.load(f)
    except Exception: return {}

SESSION_META = _load_meta()

def _save_meta():
    try:
        with META_LOCK:
            tmp = META_FILE + '.tmp'
            with open(tmp, 'w') as f: json.dump(SESSION_META, f)
            os.replace(tmp, META_FILE)
    except Exception as e:
        logger.warning(f"META SAVE ERROR: {e}")

def update_meta(name, **kw):
    with META_LOCK:
        SESSION_META.setdefault(name, {}).update(kw)
    _save_meta()

PHOTO_CACHE = {}
PHOTO_CACHE_TTL = 900
PHOTO_CACHE_LOCK = threading.Lock()

def _digits(s): return ''.join(ch for ch in str(s or '') if ch.isdigit())

def _jid_parts(j):
    if j is None: return '', ''
    if isinstance(j, str):
        if '@' in j:
            u, s = j.split('@', 1)
            return u.split(':')[0].replace('User:', '').strip(), s.strip()
        return j.strip(), ''
    return (getattr(j, 'User', '') or '').strip(), (getattr(j, 'Server', '') or '').strip()

def _name_from_obj(o):
    if o is None: return ''
    for a in ('FullName', 'PushName', 'BusinessName', 'FirstName', 'Name', 'DisplayName'):
        try: v = getattr(o, a, '')
        except Exception: v = ''
        if isinstance(v, str) and v.strip(): return v.strip()
    return ''

def contact_name(c):
    n = _name_from_obj(c)
    if n: return n
    return _name_from_obj(getattr(c, 'Info', None))

def contact_user(c):
    cj = getattr(c, 'JID', None)
    u = (getattr(cj, 'User', '') if cj is not None else '') or (getattr(c, 'User', '') or '')
    return str(u).strip()

def _participant_ids(p):
    user, server = _jid_parts(getattr(p, 'JID', None))
    if not user:
        user = (getattr(p, 'User', '') or '').strip()
        server = (getattr(p, 'Server', '') or '').strip()
    if not user:
        lu, ls = _jid_parts(getattr(p, 'LID', None))
        if lu: user, server = lu, (ls or 'lid')
    if not user: return '', '', '', ''
    if not server: server = 's.whatsapp.net'
    pu, _ = _jid_parts(getattr(p, 'PhoneNumber', None))
    phone = pu or (user if server == 's.whatsapp.net' else '')
    dname = (getattr(p, 'DisplayName', '') or '').strip()
    return user, server, phone, dname

def _parse_jid_str(s):
    s = str(s or '').replace('+', '').replace(' ', '').replace('User:', '').strip()
    if '@' in s: u, sv = s.split('@', 1)
    else: u, sv = s, 's.whatsapp.net'
    return u.split(':')[0], (sv or 's.whatsapp.net')

def _dl_image(url, timeout=6):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
            if data: return "data:image/jpeg;base64," + base64.b64encode(data).decode()
    except Exception: pass
    return ""

def _pic_to_data_url(res, download=True):
    if not res: return ""
    try:
        if isinstance(res, bytes):
            return "data:image/jpeg;base64," + base64.b64encode(res).decode()
        if isinstance(res, str):
            if res.startswith('http'):
                return (_dl_image(res) or res) if download else res
            return ""
        url = getattr(res, 'URL', '') or ''
        if url:
            if download: return _dl_image(url) or url
            return url
        data = getattr(res, 'Data', None)
        if isinstance(data, bytes) and data:
            return "data:image/jpeg;base64," + base64.b64encode(data).decode()
    except Exception: pass
    return ""

def get_profile_pic(client, jid_obj, download=True):
    for mname in ('get_profile_picture', 'get_profile_picture_preview'):
        if hasattr(client, mname):
            try:
                d = _pic_to_data_url(getattr(client, mname)(jid_obj), download)
                if d: return d
            except Exception: pass
    return ""

def qr_to_data_url(qr_string):
    if not QR_OK: return ""
    try:
        img = qrcode.make(qr_string)
        buf = io.BytesIO(); img.save(buf, format='PNG')
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception: return ""

def get_server_stats():
    global _process_peak_rss, _prev_net
    stats = {
        'address': '—',
        'uptime_sec': int(time.time() - PROCESS_START_TIME),
        'uptime_str': format_uptime_long(int(time.time() - PROCESS_START_TIME)),
        'cpu_percent': 0.0, 'sys_cpu_percent': 0.0, 'cpu_count': os.cpu_count() or 1,
        'proc_mem_used_mb': 0.0, 'proc_mem_total_mb': 0.0,
        'sys_mem_used_gb': 0.0, 'sys_mem_total_gb': 0.0, 'sys_mem_percent': 0.0,
        'disk_used_mb': 0, 'disk_total_mb': 0, 'disk_percent': 0.0,
        'net_in_kbps': 0.0, 'net_out_kbps': 0.0, 'platform': sys.platform,
    }

    stats['cpu_percent'] = _CPU_SAMPLER.get('proc_percent', 0.0)
    stats['sys_cpu_percent'] = _CPU_SAMPLER.get('sys_percent', 0.0)
    stats['proc_mem_used_mb'] = _CPU_SAMPLER.get('proc_mem_mb', 0.0)
    stats['proc_mem_total_mb'] = _CPU_SAMPLER.get('peak_mem_mb', 0.0)

    if PSUTIL_OK:
        try:
            vm = psutil.virtual_memory()
            stats['sys_mem_used_gb'] = round(vm.used / (1024**3), 2)
            stats['sys_mem_total_gb'] = round(vm.total / (1024**3), 2)
            stats['sys_mem_percent'] = round(vm.percent, 1)
        except Exception: pass
        try:
            io_c = psutil.net_io_counters(); now = time.time()
            dt = max(0.1, now - _prev_net['time'])
            stats['net_in_kbps'] = round((io_c.bytes_recv - _prev_net['bytes_recv']) / dt / 1024, 1)
            stats['net_out_kbps'] = round((io_c.bytes_sent - _prev_net['bytes_sent']) / dt / 1024, 1)
            _prev_net = {'time': now, 'bytes_sent': io_c.bytes_sent, 'bytes_recv': io_c.bytes_recv}
        except Exception: pass
    else:
        try:
            with open('/proc/loadavg') as f: la = f.read().split()
            stats['sys_cpu_percent'] = round(float(la[0]) * 100 / stats['cpu_count'], 1)
            stats['cpu_percent'] = stats['sys_cpu_percent']
        except Exception: pass
        try:
            with open('/proc/meminfo') as f:
                info = {}
                for line in f:
                    parts = line.split(':')
                    if len(parts) == 2: info[parts[0].strip()] = int(parts[1].split()[0]) * 1024
            total = info.get('MemTotal', 0); avail = info.get('MemAvailable', info.get('MemFree', 0))
            used = total - avail
            stats['sys_mem_used_gb'] = round(used / (1024**3), 2)
            stats['sys_mem_total_gb'] = round(total / (1024**3), 2)
            if total: stats['sys_mem_percent'] = round(used * 100 / total, 1)
        except Exception: pass
        try:
            with open('/proc/self/status') as f:
                for line in f:
                    if line.startswith('VmRSS:'):
                        rss = int(line.split()[1]) * 1024
                        if rss > _process_peak_rss: _process_peak_rss = rss
                        stats['proc_mem_used_mb'] = round(rss / (1024*1024), 1)
                        stats['proc_mem_total_mb'] = round(_process_peak_rss / (1024*1024), 1)
                        break
        except Exception: pass

    try:
        du = shutil.disk_usage(os.getcwd())
        stats['disk_used_mb'] = int(du.used / (1024*1024))
        stats['disk_total_mb'] = int(du.total / (1024*1024))
        stats['disk_percent'] = round(du.used * 100 / du.total, 1) if du.total else 0
    except Exception: pass
    return stats


# ═══════════════════════════════════════════════════════════
# HTML TEMPLATE (v48)
# ═══════════════════════════════════════════════════════════
HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>WhatsApp Server — ARJUN THAKUR</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
<style>
:root {
  --app-bg: #FFF8DC;
  --card-bg: rgba(255, 250, 230, 0.98);
  --card-border: #1a5c2e;
  --text-main: #0d2b14;
}
* { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
html, body { margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden; }
body {
  background: #FFF8DC;
  color: #0d2b14;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  -webkit-font-smoothing: antialiased;
  display: flex; flex-direction: column;
  text-transform: uppercase;
}
input, textarea, select, .form-control, .form-select { text-transform: uppercase; color: #0d2b14 !important; background: #FFFDF0 !important; border-color: #1a5c2e !important; }
input::placeholder, .form-control::placeholder { color: #5a7a5e !important; text-transform: uppercase; }
input[type="password"] { text-transform: none; color: #0d2b14 !important; }

#convoSessionDropdown, #menuImgSession {
  color: #0d2b14 !important;
  font-weight: 900 !important;
  background: #FFFDF0 !important;
}
#convoSessionDropdown option, #menuImgSession option {
  color: #0d2b14 !important;
  font-weight: 800 !important;
  background: #FFFDF0;
}
#convoSessionDropdown option[value=""], #menuImgSession option[value=""], #menuImgSession option[value="__addnew__"] {
  color: #5a7a5e !important;
}

.app-container {
  flex: 1; overflow-y: auto; overflow-x: hidden;
  padding: 16px 14px 90px 14px;
  -webkit-overflow-scrolling: touch;
  position: relative;
  scroll-behavior: smooth;
  background: #FFF8DC;
  border-top: 4px solid #8B0000;
  border-bottom: 4px solid #006400;
  border-left: 4px solid #00008B;
  border-right: 4px solid #8B0000;
}
.app-container::-webkit-scrollbar { display: none; }
.app-container { -ms-overflow-style: none; scrollbar-width: none; }

.bottom-nav {
  position: fixed; bottom: 0; left: 0; right: 0; height: 72px;
  background: #FFF8DC;
  backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  border-top: 4px solid #8B0000;
  border-bottom: 4px solid #006400;
  border-left: 4px solid #00008B;
  border-right: 4px solid #8B0000;
  display: flex; align-items: center; justify-content: space-around;
  padding: 0 10px; z-index: 1000;
  box-shadow: 0 -4px 20px rgba(0,0,0,0.15);
}
.nav-item {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 4px; color: #5a7a5e; font-size: 10px; font-weight: 800;
  letter-spacing: .5px; cursor: pointer; width: 60px;
  transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
}
.nav-item i { font-size: 20px; transition: all 0.35s ease; }
.nav-item.active { color: #8B0000; }
.nav-item.active i { transform: translateY(-4px) scale(1.15); color: #8B0000; }
.nav-item:active { transform: scale(0.9); }

.app-header {
  display: flex; align-items: center; justify-content: space-between;
  background: #FFF8DC; border: 3px solid #00008B;
  border-radius: 20px; padding: 12px 18px; margin-bottom: 16px;
  box-shadow: 0 4px 15px rgba(0,0,0,0.1);
  animation: slideDown 0.5s ease;
}
@keyframes slideDown { from { transform: translateY(-15px); opacity: 0; } to { transform: none; opacity: 1; } }
.header-left { display: flex; align-items: center; gap: 6px; }
.logout-icon { color: #8B0000; font-size: 20px; cursor: pointer; transition: transform 0.3s ease; }
.logout-icon:hover { transform: scale(1.15) rotate(-8deg); }
.header-slash { color: #5a7a5e; font-size: 18px; font-weight: 900; }
.arrow-icon { color: #006400; font-size: 18px; }
.header-title {
  font-size: 15px; font-weight: 900; letter-spacing: 1px;
  margin: 0; flex: 1; text-align: center;
  color: #006400;
}
.header-right-icon {
  width: 38px; height: 38px; border-radius: 50%;
  background: #00008B;
  color: #fff; display: flex; align-items: center; justify-content: center;
  font-size: 18px; border: 2px solid #006400;
  box-shadow: 0 0 15px rgba(0, 0, 139, 0.4);
  cursor: pointer; transition: all 0.3s ease;
}
.header-right-icon:hover { transform: scale(1.12) rotate(8deg); }
.header-right-icon.admin-icon {
  background: #8B0000;
  box-shadow: 0 0 15px rgba(139, 0, 0, 0.4);
}

.page-view { display: none; }
.page-view.active { display: block; animation: pageIn .4s cubic-bezier(0.4, 0, 0.2, 1); }
@keyframes pageIn { from { opacity: 0; transform: translateY(15px); } to { opacity: 1; transform: none; } }

#tab-session.active {
  display: flex !important; flex-direction: column;
  justify-content: center; align-items: center;
  min-height: calc(100vh - 160px); padding: 20px 0 60px;
}
#tab-session .card-clean { width: 100%; max-width: 480px; }

.card-clean {
  background: #FFFDF0; border: 3px solid #006400;
  border-radius: 20px; padding: 18px; margin-bottom: 14px;
  box-shadow: 0 4px 15px rgba(0,0,0,0.1);
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}
.card-clean:hover { transform: translateY(-2px); box-shadow: 0 8px 25px rgba(0,0,0,0.15); }
.card-title {
  font-size: 14px; font-weight: 900; letter-spacing: 1px;
  margin-bottom: 14px; color: #8B0000;
}

.banner-container {
  width: 100%; border-radius: 16px; overflow: hidden;
  border: 3px solid #00008B; margin-bottom: 16px;
  box-shadow: 0 8px 24px rgba(0,0,139,.2);
  position: relative; background: #FFF8DC;
  animation: fadeUp 0.6s ease;
  aspect-ratio: 16/9;
  max-height: 260px;
}
@keyframes fadeUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: none; } }
.banner-container img { width: 100%; height: 100%; object-fit: cover; display: block; }
.banner-text {
  position: absolute; bottom: 0; left: 0; right: 0;
  background: linear-gradient(to top, rgba(255,248,220,0.95), transparent);
  padding: 20px 16px 12px; text-align: center;
}
.banner-title { font-size: 13px; font-weight: 900; color: #8B0000; letter-spacing: 1px; }
.banner-subtitle { font-size: 11px; font-weight: 800; color: #006400; letter-spacing: 1px; margin-top: 4px; }

@media (max-width: 480px) {
  .banner-container { aspect-ratio: 4/3; max-height: 220px; }
  .banner-title { font-size: 11px; }
  .banner-subtitle { font-size: 9px; }
}

.stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.stat-card {
  background: #FFFDF0; border: 3px solid #00008B;
  border-radius: 16px; padding: 14px; display: flex; align-items: center; gap: 12px;
  transition: transform 0.3s ease;
}
.stat-card:hover { transform: translateY(-3px); }
.stat-icon {
  width: 40px; height: 40px; border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  font-size: 16px; flex-shrink: 0;
}
.stat-icon.cpu { background: rgba(0,0,139,.15); color: #00008B; }
.stat-icon.msg { background: rgba(0,100,0,.15); color: #006400; }
.stat-icon.ram { background: rgba(139,0,0,.15); color: #8B0000; }
.stat-icon.img { background: rgba(139,0,139,.15); color: #8B008B; }
.stat-info { overflow: hidden; }
.stat-label { font-size: 9px; font-weight: 800; color: #5a7a5e; }
.stat-value { font-size: 16px; font-weight: 900; color: #0d2b14; }

.high-perf-card {
  background: #FFFDF0;
  border: 4px solid #8B0000;
  border-radius: 20px;
  padding: 20px; margin-top: 14px; text-align: center;
  box-shadow: 0 10px 30px rgba(139,0,0,.15);
  position: relative; overflow: hidden;
  animation: fadeUp 0.7s ease;
}
.high-perf-title { font-size: 12px; font-weight: 900; color: #00008B; letter-spacing: 2px; margin-bottom: 8px; }
.high-perf-name {
  font-size: 20px; font-weight: 900; letter-spacing: 2px; margin-bottom: 16px;
  color: #8B0000;
  text-shadow: 0 0 20px rgba(139,0,0,.2);
}
.hp-bar-bg { width: 100%; height: 10px; background: #e0d8c0; border-radius: 999px; margin-bottom: 8px; overflow: hidden; border: 2px solid #006400; }
.hp-bar-fill { height: 100%; border-radius: 999px; background: #8B0000; animation: shimmer 3s linear infinite; }
.hp-bar-fill-2 { height: 100%; border-radius: 999px; background: #006400; width: 65%; animation: shimmer 4s linear infinite; }
@keyframes shimmer { 0% { filter: brightness(1); } 50% { filter: brightness(1.3); } 100% { filter: brightness(1); } }
.hp-stats-row { display: flex; justify-content: space-between; align-items: center; font-size: 10px; font-weight: 800; color: #5a7a5e; margin-bottom: 12px; gap: 6px; flex-wrap: wrap; }
.hp-stats-row span { color: #006400; }
.hp-stats-row .live-date-value {
  color: #8B0000 !important;
  font-weight: 900;
  letter-spacing: 0.5px;
  font-size: 10px;
  text-align: right;
}

.hp-gradient-bar {
  width: 100%;
  height: 10px;
  background: #e0d8c0;
  border-radius: 999px;
  overflow: hidden;
  border: 2px solid #00008B;
  margin: 6px 0 12px 0;
}
.hp-gradient-fill {
  height: 100%;
  width: 68%;
  border-radius: 999px;
  background: linear-gradient(90deg, #8B0000 0%, #006400 50%, #00008B 100%);
  background-size: 200% 100%;
  animation: gradientShift 4s ease-in-out infinite;
}
@keyframes gradientShift {
  0% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}

.social-icons-row {
  display: flex; justify-content: center; gap: 10px; margin-top: 16px;
  padding-top: 16px; border-top: 2px solid #00008B; flex-wrap: wrap;
}
.social-icon {
  width: 36px; height: 36px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 15px; color: #fff; text-decoration: none;
  transition: all 0.35s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}
.social-icon.youtube { background: #8B0000; }
.social-icon.telegram { background: #00008B; }
.social-icon.whatsapp { background: #006400; }
.social-icon.pinterest { background: #8B0000; }
.social-icon.instagram { background: #8B008B; }
.social-icon.call { background: #00008B; }
.social-icon.kimi { background: #006400; }
.social-icon.gemini { background: #8B0000; }
.social-icon:hover { transform: translateY(-5px) scale(1.15); box-shadow: 0 8px 20px rgba(0,0,0,0.3); }

.form-control, .form-select {
  background-color: #FFFDF0 !important; border: 3px solid #006400 !important;
  color: #0d2b14 !important; border-radius: 14px; padding: 12px 16px;
  font-size: 14px; font-weight: 500; transition: all .25s ease;
}
.form-control:focus, .form-select:focus {
  background-color: #FFFDF0 !important; border-color: #8B0000 !important;
  box-shadow: 0 0 0 3px rgba(139,0,0,0.1);
}

.btn-app {
  width: 100%; border: 3px solid #006400; border-radius: 12px;
  padding: 10px 16px; background: #006400;
  color: #fff; font-weight: 800; font-size: 13px;
  letter-spacing: 1px; transition: all .3s ease; box-shadow: 0 4px 15px rgba(0,100,0,.2);
}
.btn-app:hover { transform: translateY(-2px); background: #008000; box-shadow: 0 6px 20px rgba(0,100,0,.4); }
.btn-app:active { transform: scale(0.98); }

.btn-secondary-app {
  width: 100%; border: 3px solid #00008B; border-radius: 12px;
  padding: 10px 16px; background: #FFFDF0;
  color: #00008B; font-weight: 800; font-size: 13px;
  letter-spacing: 1px; transition: all .3s ease;
}
.btn-secondary-app:hover { background: #00008B; color: #fff; }

.task-card-new {
  background: #FFFDF0;
  border: 3px solid #00008B; border-radius: 18px;
  padding: 14px; margin-bottom: 12px;
  transition: transform 0.3s ease;
  animation: fadeUp 0.5s ease;
}
.task-card-new:hover { transform: translateY(-3px); }
.task-card-header { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
.task-card-avatar-new { width: 44px; height: 44px; border-radius: 50%; object-fit: cover; border: 3px solid #006400; flex-shrink: 0; }
.task-card-title-new { font-size: 14px; font-weight: 900; color: #8B0000 !important; }
.task-badge-new-row { display: flex; gap: 6px; margin-bottom: 10px; flex-wrap: wrap; }
.task-badge-new { padding: 3px 8px; border-radius: 999px; font-size: 9px; font-weight: 800; }
.task-badge-new.blue { background: #00008B; color: #fff; }
.task-badge-new.pink { background: #8B0000; color: #fff; }
.task-info-line { display: flex; gap: 8px; padding: 4px 0; font-size: 11px; font-weight: 800; border-bottom: 1px solid #c0b89a; }
.task-info-label-new { color: #00008B; white-space: nowrap; }
.task-info-value-new { color: #0d2b14; word-break: break-word; }
.task-status-new { display: flex; align-items: center; gap: 8px; padding: 6px 0; font-size: 12px; font-weight: 900; color: #006400; }
.task-status-dot-new { width: 8px; height: 8px; border-radius: 50%; background: #006400; animation: pulse-green 1.5s infinite; }
.task-uptime-new { font-size: 10px; font-weight: 800; color: #006400; margin-bottom: 6px; }
.task-next-msg-new { font-size: 10px; font-weight: 800; color: #00008B; margin-bottom: 10px; }
.task-btn-row-new { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.task-btn-new { padding: 7px; border-radius: 10px; border: 3px solid #00008B; font-weight: 800; font-size: 10px; cursor: pointer; background: transparent; color: #00008B; transition: all .25s ease; }
.task-btn-new.green { border-color: #006400; color: #006400; }
.task-btn-new.green:hover { background: #006400; color: #fff; }
.task-btn-new.purple { border-color: #8B0000; color: #8B0000; }
.task-btn-new.purple:hover { background: #8B0000; color: #fff; }
.task-btn-new.red { border-color: #8B0000; color: #8B0000; grid-column: span 2; }
.task-btn-new.red:hover { background: #8B0000; color: #fff; }

.modal-clean .modal-content {
  background: #FFF8DC; border: 0; border-radius: 24px 24px 0 0;
  color: #0d2b14; height: 90vh; margin-top: 10vh;
}
.modal-clean .modal-header { border-bottom: 3px solid #00008B; padding: 16px 20px; background: #FFFDF0; }
.modal-clean .modal-body { padding: 20px; overflow-y: auto; background: #FFF8DC; }
.modal-clean .modal-footer { border-top: 3px solid #00008B; padding: 16px 20px; background: #FFFDF0; }
.modal-fullscreen-custom .modal-content { border-radius: 0 !important; height: 100vh; max-height: 100vh; margin-top: 0; }
.modal-fullscreen-custom .modal-body { padding: 0 !important; padding-bottom: 0 !important; overflow-y: auto; }

@media (max-width: 360px) {
  .modal-clean .modal-header h5 { font-size: 13px; }
  .modal-clean .modal-body { padding: 14px; }
}

.toast-clean {
  position: fixed; top: 20px; right: -400px;
  z-index: 999999; background: #006400;
  color: #fff; padding: 16px 24px; border-radius: 16px;
  box-shadow: 0 10px 30px rgba(0,100,0,.6);
  display: block; font-size: 13px; font-weight: 800;
  text-transform: uppercase; letter-spacing: 0.5px; max-width: 90%;
  text-align: center; transition: right 0.45s cubic-bezier(0.175, 0.885, 0.32, 1.275);
  border: 3px solid #00a000;
}
.toast-clean.show { right: 20px; }
.toast-clean.error { background: #8B0000; box-shadow: 0 10px 30px rgba(139,0,0,.6); border-color: #ff4444; }

.selected-members-chips { display: flex; flex-wrap: wrap; gap: 6px; min-height: 40px; padding: 8px; background: #FFFDF0; border: 3px dashed #006400; border-radius: 12px; margin-bottom: 10px; }
.member-chip { display: inline-flex; align-items: center; gap: 6px; padding: 4px 8px; background: #006400; color: #fff; border-radius: 999px; font-size: 10px; font-weight: 800; }

.member-card { background: #FFFDF0; border: 3px solid #00008B; border-radius: 14px; padding: 10px; display: flex; align-items: center; cursor: pointer; transition: all 0.25s ease; height: 100%; }
.member-card:hover { border-color: #8B0000; transform: translateY(-2px); }
.member-card.selected { border-color: #006400; background: #E8F5E9; }
.member-avatar { width: 42px; height: 42px; border-radius: 50%; margin-right: 10px; object-fit: cover; flex-shrink: 0; border: 3px solid #00008B; }
.member-info { overflow: hidden; flex-grow: 1; }
.member-name { font-size: 12px; font-weight: 800; color: #0d2b14; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.member-number { font-size: 10px; color: #8B0000; font-weight: 700; }
.member-check { width: 22px; height: 22px; border-radius: 50%; flex-shrink: 0; margin-left: 6px; display: flex; align-items: center; justify-content: center; background: #e0d8c0; color: transparent; font-size: 10px; transition: all .25s ease; }
.member-check.on { background: #006400; color: #fff; }

.toggle-switch-row { display: flex; align-items: center; justify-content: space-between; background: #E8F5E9; border: 3px solid #006400; border-radius: 999px; padding: 6px 12px; margin-bottom: 10px; cursor: pointer; }
.toggle-switch-label { color: #006400; font-size: 10px; font-weight: 800; }
.toggle-switch-box { width: 40px; height: 22px; background: #c0b89a; border-radius: 999px; position: relative; transition: background .3s ease; flex-shrink: 0; }
.toggle-switch-box.on { background: #006400; }
.toggle-switch-box::after { content: ''; position: absolute; top: 2px; left: 2px; width: 18px; height: 18px; background: #fff; border-radius: 50%; transition: transform .3s ease; }
.toggle-switch-box.on::after { transform: translateX(18px); }

.target-toggle-row { display: flex; background: #FFFDF0; border-radius: 999px; padding: 4px; border: 3px solid #00008B; margin-bottom: 10px; }
.target-toggle-btn { flex: 1; text-align: center; padding: 8px; border-radius: 999px; font-size: 10px; font-weight: 800; cursor: pointer; color: #5a7a5e; transition: all .25s ease; }
.target-toggle-btn.active { background: #00008B; color: #fff; }

.image-send-center-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 80px 14px 140px 14px;
  width: 100%;
}

.imsend-wrap { background: #FFFDF0; border: 4px solid #00008B; border-radius: 20px; padding: 16px; width: 100%; max-width: 520px; margin: 0 auto; }
.imsend-header { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
.imsend-ico { width: 40px; height: 40px; border-radius: 12px; background: #8B0000; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 18px; }
.imsend-title { color: #0d2b14; font-weight: 900; font-size: 13px; flex: 1; }
.imsend-x { color: #8B0000; font-size: 22px; cursor: pointer; }
.imsend-label { color: #00008B; font-size: 10px; font-weight: 800; margin: 12px 0 6px; display: block; }
.imsend-input { width: 100%; padding: 10px 12px; border-radius: 12px; background: #FFFDF0; border: 3px solid #006400; color: #0d2b14 !important; font-size: 13px; font-weight: 700; outline: none; margin-bottom: 8px; }
.imsend-toggle-row { display: flex; background: #FFFDF0; border-radius: 999px; padding: 4px; border: 3px solid #00008B; margin-bottom: 8px; }
.imsend-toggle-btn { flex: 1; text-align: center; padding: 6px; border-radius: 999px; font-size: 10px; font-weight: 800; cursor: pointer; color: #5a7a5e; }
.imsend-toggle-btn.active { background: #00008B; color: #fff; }
.imsend-group-btn { width: 100%; padding: 8px; border-radius: 12px; background: #8B0000; color: #fff; font-weight: 800; font-size: 12px; border: none; cursor: pointer; margin-bottom: 8px; display: flex; align-items: center; justify-content: center; gap: 8px; }
.imsend-upload { width: 100%; padding: 10px; border-radius: 12px; background: #00008B; color: #fff; font-weight: 800; font-size: 12px; border: none; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 8px; }
.imsend-start { width: 100%; padding: 10px; border-radius: 12px; background: #006400; color: #fff; font-weight: 900; font-size: 14px; border: none; cursor: pointer; margin-top: 14px; display: flex; align-items: center; justify-content: center; gap: 8px; }
.imsend-chosen { padding: 10px; border-radius: 12px; background: #E8F5E9; border: 3px solid #006400; display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.imsend-chosen-name { color: #006400; font-weight: 800; font-size: 11px; flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.imsend-chosen-badge { background: #006400; color: #fff; font-size: 9px; font-weight: 800; padding: 4px 10px; border-radius: 999px; }

.about-img-wrap {
  background: #FFFDF0;
  border: 4px solid #00008B; border-radius: 20px;
  padding: 24px 18px; margin: 0 auto; max-width: 480px;
  box-shadow: 0 15px 45px rgba(0,0,139,.2);
  animation: fadeUp 0.6s ease;
}
.about-img-title {
  font-size: 22px; font-weight: 900; letter-spacing: 2px;
  color: #8B0000; text-align: center; margin-bottom: 20px;
  display: flex; align-items: center; justify-content: center; gap: 10px;
}
.about-img-title .bars { display: inline-flex; flex-direction: column; gap: 3px; }
.about-img-title .bars span { display: block; width: 14px; height: 4px; background: #8B0000; border-radius: 2px; }
.about-img-text { font-size: 12px; font-weight: 800; line-height: 2.1; color: #0d2b14; text-align: center; letter-spacing: 1px; }
.about-img-text .yellow { color: #8B0000; }
.about-img-text .green { color: #006400; }
.about-img-text .white { color: #00008B; }
.about-img-text .gray { color: #5a7a5e; }
.about-img-icons { display: flex; justify-content: center; gap: 10px; flex-wrap: wrap; margin-top: 22px; font-size: 10px; font-weight: 800; color: #5a7a5e; letter-spacing: 1px; }
.about-img-icons i { color: #00008B; margin-right: 4px; }
.about-img-footer { margin-top: 22px; padding-top: 16px; border-top: 3px solid #00008B; text-align: center; font-size: 11px; font-weight: 900; color: #8B0000; letter-spacing: 1.5px; line-height: 1.9; }
.about-img-footer i { color: #8B0000; }

.img-locked-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 60px 16px 120px 16px;
  width: 100%;
}

@keyframes pulse-green { 0%, 100% { box-shadow: 0 0 0 0 rgba(0,100,0,.7); } 50% { box-shadow: 0 0 0 6px rgba(0,100,0,0); } }
</style>
</head>
<body>

<div id="toastBox" class="toast-clean"></div>

<div class="app-container" id="appContainer">
  <div class="app-header">
    <div class="header-left">
      <i class="fas fa-door-open logout-icon" onclick="logoutUser()"></i>
      <span class="header-slash">/</span>
      <i class="fas fa-arrow-right arrow-icon"></i>
    </div>
    <h1 class="header-title" id="headerUserName">ARJUN THAKUR SERVER</h1>
    <div class="header-right-icon" id="headerRightIcon" onclick="handleHeaderRightClick()">
      <i class="fas fa-info-circle" id="headerRightIconInner"></i>
    </div>
  </div>

  <div class="page-view active" id="tab-dashboard">
    <div class="banner-container">
      <img src="__BANNER_URL__" alt="Banner">
      <div class="banner-text">
        <div class="banner-title">ARJUN THAKUR SERVER</div>
        <div class="banner-subtitle">INFINITE RUN MODE • ZERO DOWNTIME</div>
      </div>
    </div>

    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon cpu"><i class="fas fa-microchip"></i></div>
        <div class="stat-info"><div class="stat-label">CPU USAGE</div><div class="stat-value" id="dashCpu">0%</div></div>
      </div>
      <div class="stat-card">
        <div class="stat-icon msg"><i class="fas fa-envelope"></i></div>
        <div class="stat-info"><div class="stat-label">MSG SENT</div><div class="stat-value" id="dashMsgSent">0</div></div>
      </div>
      <div class="stat-card">
        <div class="stat-icon ram"><i class="fas fa-memory"></i></div>
        <div class="stat-info"><div class="stat-label">RAM USED</div><div class="stat-value" id="dashRam">0 MB</div></div>
      </div>
      <div class="stat-card">
        <div class="stat-icon img"><i class="fas fa-image"></i></div>
        <div class="stat-info"><div class="stat-label">IMG SENT</div><div class="stat-value" id="dashImgSent">0</div></div>
      </div>
    </div>

    <div class="high-perf-card">
      <div class="high-perf-title">✦ HIGH-PERFORMANCE ✦ ALWAYS ACTIVE ✦</div>
      <div class="high-perf-name">🔥╭─✺ARJUN THAKUR✺─╮🔥</div>

      <div class="hp-bar-bg"><div class="hp-bar-fill" style="width: 78%;"></div></div>
      <div class="hp-bar-bg" style="height: 14px; margin-bottom: 12px;">
        <div class="hp-bar-fill-2"></div>
      </div>
      <hr style="border-color: #00008B; margin: 10px 0; border-width: 2px;">

      <div class="hp-stats-row">
        <span>SYSTEM UPTIME:</span>
        <span id="hpUptime" style="color:#006400;">0 SECONDS</span>
      </div>
      <hr style="border-color: #8B0000; margin: 10px 0; border-width: 2px;">
      <div class="hp-stats-row">
        <span>SYSTEM: LOAD/STATUS:</span>
        <span>SYSTEM LOAD: <span style="color:#006400;">ARJUN THAKUR</span></span>
      </div>
      <hr style="border-color: #00008B; margin: 10px 0; border-width: 2px;">

      <div class="hp-stats-row">
        <span><i class="fas fa-calendar-day"></i> LIVE TO DATE:</span>
        <span class="live-date-value" id="hpLiveDate">LOADING...</span>
      </div>

      <div class="hp-gradient-bar">
        <div class="hp-gradient-fill"></div>
      </div>

      <hr style="border-color: #8B0000; margin: 10px 0; border-width: 2px;">

      <div class="social-icons-row">
        <a href="https://youtube.com" target="_blank" class="social-icon youtube"><i class="fab fa-youtube"></i></a>
        <a href="https://t.me" target="_blank" class="social-icon telegram"><i class="fab fa-telegram-plane"></i></a>
        <a href="https://wa.me" target="_blank" class="social-icon whatsapp"><i class="fab fa-whatsapp"></i></a>
        <a href="https://pinterest.com" target="_blank" class="social-icon pinterest"><i class="fab fa-pinterest"></i></a>
        <a href="https://instagram.com" target="_blank" class="social-icon instagram"><i class="fab fa-instagram"></i></a>
        <a href="tel:9536764960" class="social-icon call"><i class="fas fa-phone-alt"></i></a>
        <a href="https://kimi.moonshot.cn" target="_blank" class="social-icon kimi"><i class="fas fa-robot"></i></a>
        <a href="https://gemini.google.com" target="_blank" class="social-icon gemini"><i class="fas fa-atom"></i></a>
      </div>
    </div>
  </div>

  <div class="page-view" id="tab-session">
    <div class="card-clean">
      <div class="card-title" style="text-align: center;"><i class="fas fa-plus-circle"></i> CREATE NEW SESSION</div>
      <div class="mb-3"><label style="font-size:11px; font-weight:800; color:#00008B;">Session Name</label><input type="text" class="form-control" id="session_name" placeholder="e.g. MySession_1"></div>
      <div class="mb-3"><label style="font-size:11px; font-weight:800; color:#00008B;">WhatsApp Number</label><input type="text" class="form-control" id="whatsapp_number" placeholder="e.g. 919536764960"></div>
      <div class="mb-4">
        <label style="font-size:11px; font-weight:800; color:#00008B;">Login Method</label>
        <select class="form-select" id="login_method">
          <option value="PAIRING CODE">PAIRING CODE (RECOMMENDED)</option>
          <option value="QR CODE">QR CODE</option>
        </select>
      </div>
      <button type="button" class="btn-app" id="btnGrenade"><i class="fas fa-rocket me-2"></i>LAUNCH SESSION</button>
    </div>
    <div id="authOutputArea" class="mt-3 text-center d-none"></div>
    <div id="authDataContainer" class="mt-3 text-center"></div>
  </div>

  <div class="page-view" id="tab-broadcast">
    <div class="card-clean">
      <div class="card-title"><i class="fas fa-paper-plane"></i> BROADCAST MESSAGE</div>
      <label style="font-size:11px; font-weight:800; color:#00008B;">SELECT SESSION</label>
      <select class="form-control mb-3" id="convoSessionDropdown" name="convo_session" style="color: #006400; font-weight: 900;">
        <option value="">-- SELECT A SESSION --</option>
      </select>

      <label style="font-size:11px; font-weight:800; color:#00008B;">SELECT OPINION</label>
      <div class="target-toggle-row">
        <div class="target-toggle-btn active" id="toggleNumber" onclick="setTargetType('NUMBER')">NUMBER</div>
        <div class="target-toggle-btn" id="toggleGroup" onclick="setTargetType('GROUP')">GROUP</div>
      </div>
      <input type="hidden" name="target_type" id="targetType" value="NUMBER">

      <div id="numberInputArea" class="mb-3">
        <input type="text" class="form-control" name="target_number" id="targetNumberInput" placeholder="ENTER TARGET NUMBER">
      </div>

      <button type="button" class="btn-secondary-app mb-3" id="selectGroupBtn" onclick="openGroupModal('broadcast')" style="display:none;">
        <i class="fas fa-users me-2"></i> SELECT GROUP
      </button>
      <input type="hidden" id="selectedGroupId" name="selected_group_id">
      <input type="hidden" id="selectedGroupName" name="selected_group_name">
      <div id="selectedGroupBox" class="imsend-chosen d-none mb-3">
        <div id="selectedGroupText" class="imsend-chosen-name"></div>
        <span class="imsend-chosen-badge"><i class="fas fa-check-circle"></i> GROUP READY</span>
      </div>

      <div id="mentionSection" style="display:none;">
        <label style="font-size:11px; font-weight:800; color:#00008B;">MENTION OPTION</label>
        <div class="target-toggle-row">
          <div class="target-toggle-btn active" onclick="setMention('NONE', this)">NO MENTION</div>
          <div class="target-toggle-btn" onclick="setMention('ALL', this)">ALL MEMBERS</div>
          <div class="target-toggle-btn" onclick="setMention('CUSTOM', this)">CUSTOM</div>
        </div>
        <input type="hidden" name="mention_option" id="mentionOption" value="NONE">
        <input type="hidden" id="showMentionName" value="1">
        <div class="toggle-switch-row" id="mentionNameToggle" onclick="toggleMentionName('broadcast')">
          <span class="toggle-switch-label"><i class="fas fa-comment-dots"></i> SHOW MENTION NAMES</span>
          <div class="toggle-switch-box on" id="mentionNameToggleBox"></div>
        </div>
        <div id="customMentionArea" class="mb-3 d-none">
          <div class="imsend-chosen" onclick="openCustomMentionModal('broadcast')" style="cursor:pointer; border-color:#8B0000;">
            <div style="color:#8B0000; font-weight:800; font-size:11px;"><i class="fas fa-users me-2"></i><span id="customMentionCount">0</span> MEMBERS SELECTED</div>
          </div>
          <div class="selected-members-chips" id="bc_selectedChips" style="margin-top:8px;"></div>
          <input type="hidden" id="customMentions" name="custom_mentions" value="">
        </div>
      </div>

      <label style="font-size:11px; font-weight:800; color:#00008B;">UPLOAD FILE (.TXT)</label>
      <input type="file" name="message_file" id="messageFile" accept=".txt" class="d-none" onchange="updateFileName()">
      <label for="messageFile" class="btn-secondary-app mb-3" style="display:block; text-align:center;">
        <i class="fas fa-cloud-upload-alt me-2"></i> <span id="uploadZoneText">CHOOSE FILE</span>
      </label>

      <label style="font-size:11px; font-weight:800; color:#00008B;">HATER NAME (OPTIONAL)</label>
      <input type="text" class="form-control mb-3" name="hater_name" placeholder="HATER NAME">

      <label style="font-size:11px; font-weight:800; color:#00008B;">DELAY (SECONDS)</label>
      <input type="number" class="form-control mb-3" name="speed_seconds" value="10" min="1">

      <label style="font-size:11px; font-weight:800; color:#00008B;">LAST HATER NAME</label>
      <input type="text" class="form-control mb-4" name="last_hater_name" placeholder="LAST HATER NAME">

      <button type="button" class="btn-app" id="startSendingBtn" onclick="submitTask()">
        <i class="fas fa-play me-2"></i> START SENDING
      </button>
    </div>
  </div>

  <div class="page-view" id="tab-manage">
    <div class="card-clean">
      <div class="card-title"><i class="fas fa-cog"></i> SESSION MANAGE</div>
      <button class="btn-secondary-app mb-3" onclick="loadSessionManage()"><i class="fas fa-rotate me-2"></i> REFRESH</button>
      <div id="sessionManageContainer">
        <div class="text-center py-4"><div class="spinner-border" style="color:#006400;"></div></div>
      </div>
    </div>
  </div>

</div>

<div class="bottom-nav">
  <div class="nav-item active" id="nav-dashboard" onclick="showPage('dashboard')"><i class="fas fa-home"></i><span>Home</span></div>
  <div class="nav-item" id="nav-session" onclick="showPage('session')"><i class="fas fa-qrcode"></i><span>Pair</span></div>
  <div class="nav-item" id="nav-broadcast" onclick="showPage('broadcast')"><i class="fas fa-paper-plane"></i><span>Broadcast</span></div>
  <div class="nav-item" id="nav-images" onclick="openImageSendMenu()"><i class="fas fa-image"></i><span>Images</span></div>
  <div class="nav-item" id="nav-manage" onclick="showPage('manage')"><i class="fas fa-user-cog"></i><span>Manage</span></div>
</div>

<div class="modal fade modal-clean" id="adminPanelModal" tabindex="-1" data-bs-backdrop="static">
  <div class="modal-dialog modal-fullscreen-custom" style="max-width:100%;width:100%;margin:0;">
    <div class="modal-content">
      <div class="modal-header" style="background:#FFFDF0;">
        <h5 class="modal-title" style="font-weight:900;color:#8B0000;"><i class="fas fa-crown me-2"></i>ADMIN PANEL</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal" style="background-color:#8B0000;"></button>
      </div>
      <div class="modal-body" style="padding:20px !important;">
        <div class="target-toggle-row mb-3">
          <div class="target-toggle-btn active" id="adminTab-sessions" onclick="switchAdminTab('sessions')">ACTIVE TASKS</div>
          <div class="target-toggle-btn" id="adminTab-users" onclick="switchAdminTab('users')">USERS</div>
        </div>
        <div id="adminTabContent"><div class="text-center py-4"><div class="spinner-border" style="color:#006400;"></div></div></div>
      </div>
    </div>
  </div>
</div>

<div class="modal fade modal-clean" id="switchUserModal" tabindex="-1" data-bs-backdrop="static">
  <div class="modal-dialog modal-fullscreen-custom" style="max-width:100%;width:100%;margin:0;">
    <div class="modal-content">
      <div class="modal-header" style="background:#FFFDF0;">
        <h5 class="modal-title" style="font-weight:900;color:#8B0000;"><i class="fas fa-users-cog me-2"></i>SWITCH USER / AUTO LOGIN</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal" style="background-color:#8B0000;"></button>
      </div>
      <div class="modal-body" id="switchUserBody" style="padding:20px !important;">
        <div class="text-center py-4"><div class="spinner-border" style="color:#006400;"></div></div>
      </div>
    </div>
  </div>
</div>

<div class="modal fade modal-clean" id="pairingCodeModal" tabindex="-1" data-bs-backdrop="static">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content" style="height: auto; margin-top: 0; border-radius: 24px;">
      <div class="modal-header" style="background:#FFFDF0; border-radius: 24px 24px 0 0;">
        <h5 class="modal-title" style="font-weight:900;color:#8B0000;"><i class="fas fa-key me-2"></i>PAIRING CODE</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal" onclick="cancelPairing()" style="background-color:#8B0000;"></button>
      </div>
      <div class="modal-body text-center py-4">
        <div style="color: #5a7a5e; font-size: 13px; font-weight: 800; margin-bottom: 10px;">ENTER THIS CODE IN WHATSAPP</div>
        <div id="pairCodeDisplay" style="color:#006400; font-weight:700; font-size:2rem; letter-spacing: 5px; margin: 20px 0;"></div>
        <button class="btn-app w-100" id="copyPairBtn" onclick="copyPairCode()"><i class="fas fa-copy me-2"></i>COPY CODE</button>
      </div>
    </div>
  </div>
</div>

<div class="modal fade modal-clean" id="aboutModal" tabindex="-1" data-bs-backdrop="static">
  <div class="modal-dialog modal-fullscreen-custom" style="max-width:100%;width:100%;margin:0;">
    <div class="modal-content">
      <div class="modal-header" style="background:#FFFDF0;">
        <h5 class="modal-title" style="font-weight:900;color:#8B0000;"><i class="fas fa-info-circle me-2"></i>ABOUT</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal" style="background-color:#8B0000;"></button>
      </div>
      <div class="modal-body" style="display:flex; align-items:center; justify-content:center; padding: 30px 16px !important;">
        <div class="about-img-wrap">
          <div class="about-img-title"><span class="bars"><span></span><span></span></span> ABOUT THIS SERVER</div>
          <div class="about-img-text">
            THIS IS A <span class="yellow">ARJUN THAKUR</span> WHATSAPP SERVER<br>
            BUILT FOR <span class="green">INFINITE RUN MODE</span> WITH <span class="green">365 DAYS</span><br>
            <span class="green">NON-STOP</span> OPERATION. ALL ERRORS ARE<br>
            AUTO-SKIPPED AND SESSIONS AUTO-<br>
            RECONNECT. YOU CAN SEND <span class="green">BULK MESSAGES</span><br>
            AND <span class="green">IMAGES</span> TO NUMBERS OR GROUPS WITH<br>
            CUSTOM DELAYS AND MENTIONS.
          </div>
          <hr style="border-color: #00008B; margin: 15px 0; border-width: 2px;">
          <div class="about-img-icons">
            <span><i class="fas fa-shield-alt"></i> SESSION PROTECTED</span>
            <span>•</span>
            <span><i class="fas fa-sync-alt"></i> AUTO-RECONNECT</span>
            <span>•</span>
            <span><i class="fas fa-bolt"></i> ZERO DOWNTIME</span>
          </div>
          <hr style="border-color: #00008B; margin: 15px 0; border-width: 2px;">
          <div class="about-img-footer">
            <i class="fas fa-crown"></i>—<i class="fas fa-crown"></i> || ARJUN THAKUR || <i class="fas fa-bomb"></i>—<i class="fas fa-bomb"></i> || ALLAH IS<br>
            EVERYTHING || <i class="fas fa-mosque"></i> || ALHAMDULILLAH ||—<i class="fas fa-crown"></i>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>

<div class="modal fade modal-clean" id="imageSendMenuModal" tabindex="-1" data-bs-backdrop="static">
  <div class="modal-dialog modal-fullscreen-custom" style="max-width:100%;width:100%;margin:0;">
    <div class="modal-content"><div class="modal-body" id="imageSendMenuBody" style="padding: 0 !important;"></div></div>
  </div>
</div>

<div class="modal fade modal-clean" id="groupModal" tabindex="-1" data-bs-backdrop="static">
  <div class="modal-dialog modal-fullscreen-custom" style="max-width:100%;width:100%;margin:0;">
    <div class="modal-content">
      <div class="modal-header" style="background:#FFFDF0;">
        <h5 class="modal-title" style="font-weight:900;color:#006400;"><i class="fas fa-users me-2"></i>Select Group</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal" style="background-color:#8B0000;"></button>
      </div>
      <div class="modal-body" style="padding:20px !important;">
        <div class="mb-3"><input type="text" class="form-control" id="groupSearchInput" placeholder="Search groups..."></div>
        <div id="groupListContainer" class="row g-3"></div>
      </div>
    </div>
  </div>
</div>

<div class="modal fade modal-clean" id="customMentionModal" tabindex="-1" data-bs-backdrop="static">
  <div class="modal-dialog modal-fullscreen-custom" style="max-width:100%;width:100%;margin:0;">
    <div class="modal-content">
      <div class="modal-header" style="background:#FFFDF0;">
        <h5 class="modal-title" style="font-weight:900;color:#006400;"><i class="fas fa-user-check me-2"></i>Select Members</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal" style="background-color:#8B0000;"></button>
      </div>
      <div class="modal-body" style="padding:20px !important;">
        <div class="mb-3 d-flex gap-2">
          <input type="text" class="form-control" id="memberSearchInput" placeholder="Search members...">
          <button type="button" class="btn-secondary-app" style="width:auto; padding: 8px 16px;" onclick="toggleAllMembers()"><i class="fas fa-check-double"></i></button>
        </div>
        <div id="memberListContainer" class="row g-2">
          <div class="col-12 text-center py-4"><div class="spinner-border spinner-border-sm" style="color:#006400;"></div></div>
        </div>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn-app" onclick="saveCustomMentions(event)"><i class="fas fa-save me-2"></i>SAVE CHANGE</button>
      </div>
    </div>
  </div>
</div>

<div class="modal fade modal-clean" id="updateTaskManageModal" tabindex="-1" data-bs-backdrop="static">
  <div class="modal-dialog modal-fullscreen-custom" style="max-width:100%;width:100%;margin:0;">
    <div class="modal-content">
      <div class="modal-header" style="background:#FFFDF0;">
        <h5 class="modal-title" style="font-weight:900;color:#8B0000;"><i class="fas fa-pen-to-square me-2"></i>UPDATE TASK</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal" style="background-color:#8B0000;"></button>
      </div>
      <div class="modal-body" style="padding:20px !important;">
        <input type="hidden" id="utm_task_id">
        <input type="hidden" id="utm_session_name">
        <div class="card-clean" style="background:#FFFDF0; border-color:#8B0000;">
          <div style="display:flex; align-items:center; gap:14px;">
            <img id="utm_avatar" src="https://ui-avatars.com/api/?name=U&background=8B0000&color=fff&bold=true" style="width:54px; height:54px; border-radius:50%; border:3px solid #006400;">
            <div style="overflow:hidden;">
              <div id="utm_wa_name" style="font-size:15px; font-weight:900; color:#8B0000;">—</div>
              <div id="utm_wa_phone" style="font-size:12px; font-weight:800; color:#00008B;">—</div>
            </div>
          </div>
        </div>

        <div class="target-toggle-row">
          <div class="target-toggle-btn active" id="utm_toggleNumber" onclick="utmSetTargetType('NUMBER')">NUMBER</div>
          <div class="target-toggle-btn" id="utm_toggleGroup" onclick="utmSetTargetType('GROUP')">GROUP</div>
        </div>
        <input type="hidden" id="utm_target_type" value="NUMBER">
        <div id="utm_numberArea">
          <input type="text" class="form-control mb-3" id="utm_target_number" placeholder="ENTER TARGET NUMBER">
        </div>
        <div id="utm_groupArea" class="d-none">
          <div id="utm_groupBox" class="imsend-chosen d-none mb-3">
            <div id="utm_groupText" class="imsend-chosen-name"></div>
            <span class="imsend-chosen-badge"><i class="fas fa-check-circle"></i> GROUP READY</span>
          </div>
          <button type="button" class="btn-secondary-app mb-3" onclick="openGroupModal('update')"><i class="fas fa-users me-2"></i> SELECT GROUP</button>
          <input type="hidden" id="utm_target_group" value="">
          <input type="hidden" id="utm_target_group_name" value="">
        </div>

        <div id="utm_mentionSection" style="display:none;">
          <label style="font-size:11px; font-weight:800; color:#00008B;">MENTION OPTION</label>
          <div class="target-toggle-row">
            <div class="target-toggle-btn active" id="utm_mNone" onclick="utmSetMention('NONE', this)">NO MENTION</div>
            <div class="target-toggle-btn" id="utm_mAll" onclick="utmSetMention('ALL', this)">ALL MEMBERS</div>
            <div class="target-toggle-btn" id="utm_mCust" onclick="utmSetMention('CUSTOM', this)">CUSTOM</div>
          </div>
          <input type="hidden" id="utm_mention_option" value="NONE">
          <input type="hidden" id="utm_show_mention_name" value="1">
          <div class="toggle-switch-row" onclick="toggleMentionName('update')">
            <span class="toggle-switch-label"><i class="fas fa-comment-dots"></i> SHOW MENTION NAMES</span>
            <div class="toggle-switch-box on" id="utm_mentionNameBox"></div>
          </div>
          <input type="hidden" id="utm_custom_mentions" value="">
        </div>

        <label style="font-size:11px; font-weight:800; color:#00008B;">UPLOAD FILE (.TXT) — OPTIONAL</label>
        <input type="file" class="d-none" id="utm_file_input" accept=".txt" onchange="updateUtmFileName()">
        <label for="utm_file_input" class="btn-secondary-app mb-3" style="display:block; text-align:center;">
          <i class="fas fa-cloud-upload-alt me-2"></i> <span id="utm_uploadZoneText">CHOOSE FILE</span>
        </label>

        <label style="font-size:11px; font-weight:800; color:#00008B;">HATER NAME</label>
        <input type="text" class="form-control mb-3" id="utm_hater_name" placeholder="HATER NAME">

        <label style="font-size:11px; font-weight:800; color:#00008B;">DELAY (SECONDS)</label>
        <input type="number" class="form-control mb-3" id="utm_speed" min="1" value="5">

        <label style="font-size:11px; font-weight:800; color:#00008B;">LAST HATER NAME</label>
        <input type="text" class="form-control mb-4" id="utm_last_hater_name" placeholder="LAST HATER NAME">

        <button type="button" class="btn-app" onclick="submitUpdateTaskManage()"><i class="fas fa-save me-2"></i> SAVE CHANGES</button>
      </div>
    </div>
  </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script>
let broadcastSelectedMembers = [];
let updateSelectedMembers = [];
let updateMemberNames = {};
let allGroupMembers = [];
let loadedGroupsData = [];
let manageSessionsData = {};
let manageTasksData = {};
let adminTasksData = {};
let groupModalContext = 'broadcast';
let memberModalContext = 'broadcast';
let memberPhotoGen = 0;
let currentUser = null;
let currentAdminTab = 'sessions';
let adminImageFiles = [];
let menuImgMembers = [];
let pairingModalShown = false;
const IMAGE_SEND_PASSWORD = 'PHOTHO';
const ADMIN_RAW = 'ARJUNTHAKUR';
const ADMIN_FANCY = '🔥╭─✺ARJUN THAKUR✺─╮🔥';

function updateLiveDate() {
  try {
    let now = new Date();
    let days = ['SUNDAY','MONDAY','TUESDAY','WEDNESDAY','THURSDAY','FRIDAY','SATURDAY'];
    let months = ['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'];
    let dayName = days[now.getDay()];
    let dt = now.getDate();
    let mon = months[now.getMonth()];
    let yr = now.getFullYear();
    let hh = String(now.getHours()).padStart(2, '0');
    let mm = String(now.getMinutes()).padStart(2, '0');
    let ss = String(now.getSeconds()).padStart(2, '0');
    let el = document.getElementById('hpLiveDate');
    if (el) el.textContent = dayName + ' ' + dt + ' ' + mon + ' ' + yr + ' • ' + hh + ':' + mm + ':' + ss;
  } catch(e) {}
}

function escapeHtml(text) {
  if (!text) return '';
  return text.toString().replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}
function avatarFor(name, bg) {
  return 'https://ui-avatars.com/api/?name=' + encodeURIComponent(name || 'U') + '&background=' + (bg || '8B0000') + '&color=fff&bold=true';
}
function showToast(msg, isError = false) {
  let t = $('#toastBox');
  t.html('<i class="fas ' + (isError ? 'fa-exclamation-circle' : 'fa-check-circle') + '"></i> ' + String(msg).toUpperCase()).removeClass('error show');
  if (isError) t.addClass('error');
  void t[0].offsetWidth;
  t.addClass('show');
  setTimeout(function() { t.removeClass('show'); }, 3500);
}
function getSelectedList() {
  if (memberModalContext === 'update') return updateSelectedMembers;
  if (memberModalContext === 'images') return menuImgMembers;
  return broadcastSelectedMembers;
}
function setSelectedList(arr) {
  if (memberModalContext === 'update') updateSelectedMembers = arr;
  else if (memberModalContext === 'images') menuImgMembers = arr;
  else broadcastSelectedMembers = arr;
}
function fmtGroupDisplay(id, name) {
  if (!name) return id || '';
  if (name === id) return id;
  return name;
}
function showPage(page) {
  $('.page-view').removeClass('active');
  $('.nav-item').removeClass('active');
  $('#tab-' + page).addClass('active');
  $('#nav-' + page).addClass('active');
  $('#appContainer').scrollTop(0);
  if (page === 'dashboard') loadDashboardStats();
  if (page === 'broadcast') updateSessionDropdown();
  if (page === 'manage') loadSessionManage();
}
function loadDashboardStats() {
  $.get('/api/dashboard_stats', function(st) {
    if (!st) return;
    $('#dashCpu').text(st.cpu_percent + '%');
    $('#dashMsgSent').text(st.total_msg_sent);
    $('#dashRam').text(st.proc_mem_used_mb + ' MB');
    $('#dashImgSent').text(st.total_img_sent);
    if (st.user_display) $('#headerUserName').text(st.user_display);
    $('#hpUptime').text(st.uptime_str || '0 SECONDS');
  });
}
function handleHeaderRightClick() {
  if (currentUser === ADMIN_RAW) {
    openSwitchUserModal();
  } else {
    openAboutModal();
  }
}
function openAboutModal() {
  bootstrap.Modal.getOrCreateInstance(document.getElementById('aboutModal')).show();
}
function openSwitchUserModal() {
  $('#switchUserBody').html('<div class="text-center py-4"><div class="spinner-border" style="color:#006400;"></div></div>');
  bootstrap.Modal.getOrCreateInstance(document.getElementById('switchUserModal')).show();
  $.get('/api/admin/registered_users', function(list) {
    let html = '';
    list.forEach(u => {
      let dn = u.display_name || u.username;
      html += `<div class="card-clean" style="margin-bottom:10px; display:flex; justify-content:space-between; align-items:center;">
        <div>
          <div style="font-weight:900; color:#8B0000; font-size:13px;">${escapeHtml(dn)}</div>
          <div style="font-size:10px; color:#5a7a5e;">${u.is_admin ? 'ADMIN' : 'USER'} · ${u.session_count} SESSIONS · ${u.task_count} TASKS</div>
        </div>
        <button class="btn-app" style="width:auto; padding:6px 16px; font-size:11px;" onclick="doSwitchUser('${escapeHtml(u.username).replace(/'/g, "\\'")}')">
          <i class="fas fa-sign-in-alt"></i> LOGIN
        </button>
      </div>`;
    });
    $('#switchUserBody').html(html || '<div class="text-center py-4 fw-bold" style="color:#5a7a5e;">NO USERS FOUND</div>');
  });
}
function doSwitchUser(username) {
  if (!confirm('SWITCH TO USER ' + username + '?')) return;
  $.post('/api/admin/switch_user', { username: username }, function(r) {
    if (r.error) { showToast(r.error, true); return; }
    showToast('SWITCHED TO ' + username);
    setTimeout(() => location.reload(), 1200);
  });
}
function logoutUser() {
  if (!confirm('LOGOUT KARNA HAI?')) return;
  $.post('/api/logout', function() { location.reload(); });
}
function setTargetType(type) {
  $('#targetType').val(type);
  if (type === 'NUMBER') {
    $('#toggleNumber').addClass('active'); $('#toggleGroup').removeClass('active');
    $('#numberInputArea').removeClass('d-none');
    $('#selectGroupBtn').hide(); $('#selectedGroupBox').addClass('d-none');
    $('#mentionSection').hide(); $('#mentionOption').val('NONE');
    $('#customMentionArea').addClass('d-none');
  } else {
    $('#toggleGroup').addClass('active'); $('#toggleNumber').removeClass('active');
    $('#numberInputArea').addClass('d-none');
    $('#selectGroupBtn').show(); $('#selectedGroupBox').removeClass('d-none');
    $('#mentionSection').show();
  }
}
function setMention(mode, el) {
  $('.target-toggle-btn').removeClass('active'); $(el).addClass('active');
  $('#mentionOption').val(mode);
  if (mode === 'CUSTOM') {
    $('#customMentionArea').removeClass('d-none');
    if (!$('#selectedGroupId').val()) { showToast('Please Select A Group First', true); setTargetType('GROUP'); }
  } else { $('#customMentionArea').addClass('d-none'); }
}
function toggleMentionName(ctx) {
  if (ctx === 'update') {
    let cur = $('#utm_show_mention_name').val() === '1';
    $('#utm_show_mention_name').val(cur ? '0' : '1');
    $('#utm_mentionNameBox').toggleClass('on', !cur);
  } else {
    let cur = $('#showMentionName').val() === '1';
    $('#showMentionName').val(cur ? '0' : '1');
    $('#mentionNameToggleBox').toggleClass('on', !cur);
  }
  showToast((ctx === 'update' ? $('#utm_show_mention_name').val() : $('#showMentionName').val()) === '1' ? "MENTION NAMES WILL SHOW" : "SILENT MENTIONS ONLY");
}
function updateFileName() {
  let f = $('#messageFile')[0].files[0];
  $('#uploadZoneText').text(f ? f.name : 'CHOOSE FILE');
}
function updateUtmFileName() {
  let f = $('#utm_file_input')[0].files[0];
  $('#utm_uploadZoneText').text(f ? f.name : 'CHOOSE FILE');
}
$(document).ready(function() {
  document.getElementById('groupModal').addEventListener('shown.bs.modal', function() {
    if (groupModalContext === 'update') suspendUpdateModal();
  });
  document.getElementById('groupModal').addEventListener('hidden.bs.modal', function() {
    resumeUpdateModalIfNeeded();
  });
  document.getElementById('customMentionModal').addEventListener('shown.bs.modal', function() {
    if (memberModalContext === 'update') suspendUpdateModal();
  });
  document.getElementById('customMentionModal').addEventListener('hidden.bs.modal', function() {
    resumeUpdateModalIfNeeded();
  });
  $.get('/api/me', function(r) {
    currentUser = r.user;
    if (r.user_display) $('#headerUserName').text(r.user_display);
    if (r.user === ADMIN_RAW) {
      $('#headerRightIconInner').removeClass('fa-info-circle').addClass('fa-users-cog');
      $('#headerRightIcon').addClass('admin-icon');
    } else {
      $('#headerRightIconInner').removeClass('fa-users-cog').addClass('fa-info-circle');
      $('#headerRightIcon').removeClass('admin-icon');
    }
  });
  $(document).ajaxError(function(e, xhr) { if (xhr.status === 401) location.reload(); });
  loadDashboardStats();
  updateLiveDate();
  setInterval(updateLiveDate, 1000);
  setInterval(loadDashboardStats, 15000);
  updateSessionDropdown();
  $('#btnGrenade').click(function() {
    let name = $('#session_name').val().trim(); let phone = $('#whatsapp_number').val().trim(); let method = $('#login_method').val();
    if (!name || !phone) { showToast("Please fill all fields", true); return; }
    $('#authOutputArea').removeClass('d-none').html('<div class="spinner-border" style="color:#006400;"></div><p class="mt-2 fw-bold" style="color:#5a7a5e;">Connecting...</p>');
    $.post('/api/init_auth', { session_name: name, whatsapp_number: phone, login_method: method }, function(res) {
      if (res.error) { showToast(res.error, true); return; }
      pairingModalShown = false;
      let poll = setInterval(function() {
        $.get('/api/get_auth_status/' + encodeURIComponent(name), function(st) {
          if (st.status === "INITIALIZING") {
              $('#authDataContainer').html('<div class="spinner-border" style="color:#8B0000;"></div><p class="mt-2 fw-bold" style="color:#5a7a5e;">Generating Pair Key...</p>');
          } else if (st.status === "QR_READY") {
              $('#authDataContainer').html('<h6 style="color:#00008B;">Scan QR Code:</h6><img src="' + st.qr_img + '" style="max-width:220px;border-radius:12px;background:#FFFDF0;padding:10px;display:inline-block;border:3px solid #006400;">');
          } else if (st.status === "CODE_READY") {
              if (!pairingModalShown) {
                  showPairingCodeModal(st.code);
                  pairingModalShown = true;
                  $('#authDataContainer').html('<div class="spinner-border" style="color:#006400;"></div><p class="mt-2 fw-bold" style="color:#5a7a5e;">Waiting for connection...</p>');
              }
          } else if (st.status === "CONNECTED") {
              clearInterval(poll);
              bootstrap.Modal.getInstance(document.getElementById('pairingCodeModal'))?.hide();
              updateSessionDropdown();
              showToast("Session connected!");
          } else if (st.status.startsWith("ERROR")) {
              $('#authDataContainer').html('<h5 style="color:#8B0000;">❌ ' + escapeHtml(st.status) + '</h5>');
              clearInterval(poll);
          }
        });
      }, 2000);
    }).fail(function(xhr) { $('#authDataContainer').html('<h5 style="color:#8B0000;">❌ ' + escapeHtml(xhr.responseJSON?.error || "Server Error") + '</h5>'); });
  });
  $('#groupSearchInput').on('input', function() {
    let q = $(this).val().toLowerCase();
    $('#groupListContainer .group-item-wrapper').each(function() {
      $(this).toggle(($(this).data('gname') || '').toString().toLowerCase().indexOf(q) !== -1 || ($(this).data('gid') || '').toString().toLowerCase().indexOf(q) !== -1);
    });
  });
  $('#memberSearchInput').on('input', function() {
    let q = $(this).val().toLowerCase();
    $('#memberListContainer .member-card-wrapper').each(function() {
      $(this).toggle(($(this).attr('data-mname') || '').toLowerCase().indexOf(q) !== -1 || ($(this).attr('data-mnum') || '').toLowerCase().indexOf(q) !== -1);
    });
  });
});
function showPairingCodeModal(code) {
  $('#pairCodeDisplay').text(code);
  bootstrap.Modal.getOrCreateInstance(document.getElementById('pairingCodeModal')).show();
  autoCopyToClipboard(code, false);
}
function autoCopyToClipboard(text, showMsg) {
  if (!text) return;
  function done() { if (showMsg !== false) showToast("CODE COPIED SUCCESSFULLY!"); }
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(done).catch(() => { if (fallbackCopyTextToClipboard(text)) done(); });
  } else {
    if (fallbackCopyTextToClipboard(text)) done();
  }
}
function copyPairCode() {
  let code = $('#pairCodeDisplay').text();
  if (!code) return;
  function afterCopySuccess() {
    showToast("CODE COPIED SUCCESSFULLY!");
    let btn = $('#copyPairBtn');
    btn.prop('disabled', true).html('<i class="fas fa-check me-2"></i>COPIED!');
    setTimeout(function() {
      try { bootstrap.Modal.getInstance(document.getElementById('pairingCodeModal'))?.hide(); } catch(e) {}
      $('#pairCodeDisplay').text('');
      $('#authDataContainer').html('');
      $('#authOutputArea').addClass('d-none').html('');
      $('#session_name').val('');
      $('#whatsapp_number').val('');
      $('#login_method').val('PAIRING CODE');
      pairingModalShown = false;
      btn.prop('disabled', false).html('<i class="fas fa-copy me-2"></i>COPY CODE');
      showPage('session');
      showToast("READY FOR NEW SESSION");
    }, 2000);
  }
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(code).then(afterCopySuccess).catch(() => { if (fallbackCopyTextToClipboard(code)) afterCopySuccess(); });
  } else {
    if (fallbackCopyTextToClipboard(code)) afterCopySuccess();
  }
}
function fallbackCopyTextToClipboard(text) {
  let textArea = document.createElement("textarea");
  textArea.value = text; textArea.style.position = "fixed"; textArea.style.left = "-999999px"; textArea.style.top = "-999999px";
  document.body.appendChild(textArea); textArea.focus(); textArea.select();
  let ok = false;
  try { ok = document.execCommand('copy'); } catch (err) { ok = false; }
  document.body.removeChild(textArea);
  return ok;
}
function cancelPairing() {}
function submitTask() {
  let session = $('#convoSessionDropdown').val(); let targetType = $('#targetType').val();
  let targetNumber = $('#targetNumberInput').val(); let groupId = $('#selectedGroupId').val();
  let file = $('#messageFile')[0].files[0];
  if (!session) { showToast("Please select a session", true); return; }
  if (targetType === 'GROUP' && !groupId) { showToast("Please select a group", true); return; }
  if (targetType === 'NUMBER' && !targetNumber) { showToast("Please enter target number", true); return; }
  if (!file) { showToast("Please upload a .txt file", true); return; }
  let formData = new FormData();
  formData.append('convo_session', session); formData.append('target_type', targetType);
  formData.append('target_number', targetNumber); formData.append('selected_group_id', groupId);
  formData.append('selected_group_name', $('#selectedGroupName').val());
  formData.append('speed_seconds', $('input[name="speed_seconds"]').val());
  formData.append('hater_name', $('input[name="hater_name"]').val());
  formData.append('last_hater_name', $('input[name="last_hater_name"]').val());
  formData.append('mention_option', targetType === 'GROUP' ? $('#mentionOption').val() : 'NONE');
  formData.append('show_mention_name', $('#showMentionName').val());
  formData.append('custom_mentions', JSON.stringify(broadcastSelectedMembers.slice()));
  formData.append('message_file', file);
  let btn = $('#startSendingBtn'); btn.addClass('disabled').html('<i class="fas fa-spinner fa-spin"></i> STARTING...');
  $.ajax({
    url: '/api/start_task', type: 'POST', data: formData, processData: false, contentType: false,
    success: function(res) {
      if (res.error) { showToast(res.error, true); btn.removeClass('disabled').html('<i class="fas fa-play me-2"></i> START SENDING'); return; }
      showToast("Task started! ID: " + res.task_id);
      btn.removeClass('disabled').html('<i class="fas fa-play me-2"></i> START SENDING');
    },
    error: function(xhr) { showToast(xhr.responseJSON?.error || "Server Error", true); btn.removeClass('disabled').html('<i class="fas fa-play me-2"></i> START SENDING'); }
  });
}
function openGroupModal(context) {
  groupModalContext = context || 'broadcast';
  let sessionName;
  if (context === 'images') { sessionName = $('#menuImgSession').val(); if (!sessionName || sessionName === '__addnew__') { showToast("Select session first", true); return; } }
  else if (context === 'update') { sessionName = ($('#utm_session_name').val() || '').trim(); }
  else { sessionName = $('#convoSessionDropdown').val(); if (!sessionName) { showToast("Please select a session first", true); return; } }
  if (!sessionName) { showToast("Session missing", true); return; }
  $('#groupSearchInput').val(''); $('#groupListContainer').html('<div class="col-12 text-center py-4"><div class="spinner-border" style="color:#006400;"></div></div>');
  bootstrap.Modal.getOrCreateInstance(document.getElementById('groupModal')).show();
  $.get('/api/get_groups/' + encodeURIComponent(sessionName), function(groups) {
    if (!groups || !groups.length) { $('#groupListContainer').html('<div class="col-12 text-center py-4 fw-bold" style="color:#5a7a5e;">No groups found</div>'); return; }
    loadedGroupsData = groups; let html = '';
    groups.forEach((g, index) => {
      let safeName = escapeHtml(g.name); let safeId = escapeHtml(g.id);
      let fb = avatarFor(g.name, '006400'); let imgSrc = g.photo ? g.photo : fb;
      let dispName = (g.name && g.name !== g.id) ? g.name : g.id;
      html += `<div class="col-12 group-item-wrapper" data-gname="${safeName}" data-gid="${safeId}">
        <div class="member-card" onclick="selectGroupByIndex(${index})">
          <img src="${imgSrc}" class="member-avatar" onerror="this.onerror=null;this.src='${fb}'">
          <div class="member-info"><div class="member-name">${escapeHtml(dispName)}</div><div class="member-number"><i class="fas fa-user-friends me-1"></i>${g.members} Members</div></div>
          <span style="color:#00008B; font-size:14px;"><i class="fas fa-arrow-right"></i></span>
        </div></div>`;
    });
    $('#groupListContainer').html(html);
  });
}
function selectGroupByIndex(idx) {
  let g = loadedGroupsData[idx]; if (!g) return;
  let disp = fmtGroupDisplay(g.id, g.name);
  if (groupModalContext === 'images') {
    $('#menuImgSelectedGroupId').val(g.id); $('#menuImgSelectedGroupName').val(g.name || '');
    $('#menuImgGroupBox').removeClass('d-none'); $('#menuImgGroupText').text(disp);
  } else if (groupModalContext === 'update') {
    $('#utm_target_group').val(g.id); $('#utm_target_group_name').val(g.name || '');
    $('#utm_groupBox').removeClass('d-none'); $('#utm_groupText').text(disp);
    utmSetTargetType('GROUP', true);
  } else {
    $('#selectedGroupId').val(g.id); $('#selectedGroupName').val(g.name);
    $('#selectedGroupBox').removeClass('d-none'); $('#selectedGroupText').text(disp);
    $('#selectGroupBtn').hide();
  }
  bootstrap.Modal.getInstance(document.getElementById('groupModal'))?.hide();
  showToast("GROUP SELECTED: " + disp);
}
function openCustomMentionModal(context) {
  memberModalContext = context || 'broadcast';
  let sessionName, groupId;
  if (context === 'images') {
    sessionName = $('#menuImgSession').val(); groupId = $('#menuImgSelectedGroupId').val();
    if (!sessionName || sessionName === '__addnew__' || !groupId) { showToast("Select session and group first", true); return; }
    _doOpenCustomMentionModal(sessionName, groupId);
  } else if (context === 'update') {
    sessionName = ($('#utm_session_name').val() || '').trim(); groupId = ($('#utm_target_group').val() || '').trim();
    if (!groupId) { showToast("Select group first", true); utmSetTargetType('GROUP'); return; }
    _doOpenCustomMentionModal(sessionName, groupId);
  } else {
    sessionName = $('#convoSessionDropdown').val(); groupId = $('#selectedGroupId').val();
    if (!sessionName || !groupId) { showToast("Select session and group first", true); return; }
    _doOpenCustomMentionModal(sessionName, groupId);
  }
}
function _doOpenCustomMentionModal(sessionName, groupId) {
  $('#memberSearchInput').val(''); $('#memberListContainer').html('<div class="col-12 text-center py-4"><div class="spinner-border spinner-border-sm" style="color:#006400;"></div></div>');
  bootstrap.Modal.getOrCreateInstance(document.getElementById('customMentionModal')).show();
  let gen = ++memberPhotoGen;
  $.get('/api/get_group_members/' + encodeURIComponent(sessionName) + '/' + encodeURIComponent(groupId), function(members) {
    if (members && members.error) { $('#memberListContainer').html('<div class="col-12 text-center py-4 small fw-bold" style="color:#8B0000;">' + escapeHtml(members.error) + '</div>'); return; }
    if (!members || !members.length) { $('#memberListContainer').html('<div class="col-12 text-center py-4 fw-bold" style="color:#5a7a5e;">No members found</div>'); return; }
    allGroupMembers = members;
    members.forEach(m => { updateMemberNames[m.jid] = (m.name || '').trim() || ('+' + m.number); });
    let selected = getSelectedList(); let html = '';
    members.forEach((m, i) => {
      let isSelected = selected.includes(m.jid); let nameShown = (m.name || '').trim() || ('+' + m.number);
      let fb = avatarFor(m.name || m.number, '00008B'); let src = m.photo ? m.photo : fb;
      html += `<div class="col-12 member-card-wrapper" id="mw_${i}" data-mname="${escapeHtml(nameShown)}" data-mnum="${escapeHtml(m.number)}">
        <div class="member-card ${isSelected ? 'selected' : ''}" data-jid="${escapeHtml(m.jid)}" onclick="toggleMember(${i}, this)">
          <img src="${src}" class="member-avatar" onerror="this.onerror=null;this.src='${fb}'">
          <div class="member-info"><div class="member-name">${escapeHtml(nameShown)}</div><div class="member-number">+${escapeHtml(m.number)}</div></div>
          <span class="member-check ${isSelected ? 'on' : ''}"><i class="fas fa-check"></i></span>
        </div></div>`;
    });
    $('#memberListContainer').html(html);
    loadMemberPhotos(sessionName, members, gen);
  });
}
function loadMemberPhotos(sessionName, members, gen) {
  let queue = []; members.forEach((m, i) => { if (!m.checked) queue.push(i); });
  let active = 0, MAX = 3;
  function next() {
    while (active < MAX && queue.length) {
      if (gen !== memberPhotoGen) return;
      let i = queue.shift(); let m = members[i]; active++;
      $.get('/api/get_member_photo/' + encodeURIComponent(sessionName) + '/' + encodeURIComponent(m.number), { jid: m.jid }, function(res) {
        if (gen !== memberPhotoGen || !res) return;
        let w = $('#mw_' + i); if (!w.length) return;
        if (res.photo) w.find('img').attr('src', res.photo);
        if (res.name) { w.find('.member-name').text(res.name); w.attr('data-mname', res.name.toLowerCase()); m.name = res.name; updateMemberNames[m.jid] = res.name; }
      }).always(function() { active--; next(); });
    }
  }
  next();
}
function syncMentionFields() {
  let list = getSelectedList();
  if (memberModalContext === 'images') {
    $('#menuImgCustom').val(list.join(',')); $('#menuImgMemberCount').text(list.length);
    let mc = $('#menuImgChips'); if (mc.length) { let h = ''; list.forEach(function(jid) { let nm = updateMemberNames[jid] || jid.split('@')[0]; h += `<span class="member-chip"><span class="chip-label">${escapeHtml(nm)}</span></span>`; }); mc.html(h); }
  } else if (memberModalContext === 'update') {
    $('#utm_custom_mentions').val(list.join(','));
  } else {
    $('#customMentions').val(list.join(',')); $('#customMentionCount').text(list.length);
    let bc = $('#bc_selectedChips'); if (bc.length) { let h = ''; list.forEach(function(jid) { let nm = updateMemberNames[jid] || jid.split('@')[0]; h += `<span class="member-chip"><span class="chip-label">${escapeHtml(nm)}</span></span>`; }); bc.html(h); }
  }
}
function toggleMember(i, el) {
  let m = allGroupMembers[i]; if (!m) return;
  let jid = m.jid; let list = getSelectedList(); let idx = list.indexOf(jid);
  if (idx === -1) { list.push(jid); $(el).addClass('selected'); $(el).find('.member-check').addClass('on'); }
  else { list.splice(idx, 1); $(el).removeClass('selected'); $(el).find('.member-check').removeClass('on'); }
  setSelectedList(list); syncMentionFields();
}
function toggleAllMembers() {
  let list = getSelectedList();
  if (list.length === allGroupMembers.length) setSelectedList([]); else setSelectedList(allGroupMembers.map(m => m.jid));
  let newList = getSelectedList();
  $('#memberListContainer .member-card').each(function() {
    let jid = $(this).attr('data-jid');
    if (newList.includes(jid)) { $(this).addClass('selected'); $(this).find('.member-check').addClass('on'); }
    else { $(this).removeClass('selected'); $(this).find('.member-check').removeClass('on'); }
  });
  syncMentionFields();
}
function saveCustomMentions(e) {
  try {
    if (e) { if (e.preventDefault) e.preventDefault(); if (e.stopPropagation) e.stopPropagation(); }
    let ctx = memberModalContext; let list = getSelectedList();
    if (ctx === 'update') {
      $('#utm_custom_mentions').val(list.join(','));
      if (list.length > 0) { $('#utm_mCust').addClass('active'); $('#utm_mNone').removeClass('active'); $('#utm_mAll').removeClass('active'); $('#utm_mention_option').val('CUSTOM'); }
    } else if (ctx === 'images') {
      $('#menuImgCustom').val(list.join(',')); $('#menuImgMemberCount').text(list.length); syncMentionFields();
      if (list.length > 0) { $('#menuImgCustomArea').removeClass('d-none'); $('#menuImgMention').val('CUSTOM'); $('#menuImgMNone').removeClass('active'); $('#menuImgMAll').removeClass('active'); $('#menuImgMCust').addClass('active'); }
    } else {
      $('#customMentions').val(list.join(',')); $('#customMentionCount').text(list.length);
    }
    bootstrap.Modal.getInstance(document.getElementById('customMentionModal')).hide();
    showToast("Saved " + list.length + " members");
  } catch(err) { console.error(err); }
  return false;
}
function updateSessionDropdown() {
  $.get('/api/get_all_sessions', function(all) {
    let html = '<option value="">-- SELECT A SESSION --</option>';
    let autoSelected = false;
    for (let n in all) {
      if (all[n].status !== 'CONNECTED') continue;
      let waName = all[n].wa_name ? ' | ' + all[n].wa_name : '';
      let phone = all[n].phone ? ' (' + all[n].phone + ')' : '';
      let selectedAttr = '';
      if (!autoSelected) { selectedAttr = ' selected'; autoSelected = true; }
      html += '<option value="' + escapeHtml(n) + '"' + selectedAttr + '>' + escapeHtml(n + phone + waName) + '</option>';
    }
    $('#convoSessionDropdown').html(html);
    $('#convoSessionDropdown').css('color', autoSelected ? '#006400' : '#5a7a5e');
  });
}
function loadSessionManage() {
  $.get('/api/session_manage_stats', function(list) {
    let c = $('#sessionManageContainer');
    if (!list || !list.length) { c.html('<div class="text-center py-4 fw-bold" style="color:#5a7a5e;">NO ACTIVE TASKS FOUND</div>'); return; }
    manageSessionsData = {}; manageTasksData = {}; let html = '';
    list.forEach(s => { if (s.task_id) { manageTasksData[s.task_id] = s; manageSessionsData[s.name] = s; html += buildTaskCard(s); } });
    c.html(html);
  });
}
function buildTaskCard(s) {
  let waNameRaw = (s.wa_name || '').trim(); let phoneRaw = (s.phone || '').trim();
  let displayWaName = waNameRaw || phoneRaw || s.name; let displayPhone = phoneRaw || '—';
  let fb = avatarFor(displayWaName, '8B0000'); let avatar = s.wa_photo || fb;
  let hasTask = !!s.task_id; let taskRunning = hasTask && (s.task_status === 'RUNNING' || s.task_status === 'QUEUED');
  let isImageTask = s.task_kind === 'IMAGE';
  let mentionCount = 0; if (s.mention_option === 'CUSTOM' && s.custom_mentions) mentionCount = s.custom_mentions.length;
  let mentionBadge = ''; if (s.mention_option && s.mention_option !== 'NONE') { let mText = s.mention_option === 'ALL' ? 'ALL' : mentionCount + ' NUMBERS'; mentionBadge = `<span class="task-badge-new blue"><i class="fas fa-at"></i> MENTIONS: ${mText}</span>`; }
  let kindBadge = isImageTask ? `<span class="task-badge-new pink"><i class="fas fa-image"></i> IMAGE TASK</span>` : `<span class="task-badge-new blue"><i class="fas fa-comment-dots"></i> MESSAGE TASK</span>`;
  let targetDisplay = s.target || ''; if (s.target_type === 'GROUP' && s.target && !s.target.includes('@')) targetDisplay += '@g.us';
  let fileDisplay = isImageTask ? (s.image_count || 0) + ' IMAGES' : (s.file_name || 'NO FILE');
  let targetNameDisplay = s.target_name || s.target || '—'; let speedDisplay = s.interval || 5; let lastHaterDisplay = s.last_hater_name || 'NONE';
  let statusColor = taskRunning ? '#006400' : '#8B0000'; let statusText = taskRunning ? 'RUNNING' : 'STOPPED';
  let nextMsgSec = '—'; if (taskRunning && s.next_message_time) { let diff = Math.max(0, Math.floor(s.next_message_time - (Date.now() / 1000))); nextMsgSec = diff + ' SEC'; }
  return `<div class="task-card-new">
    <div class="task-card-header">
      <img src="${avatar}" class="task-card-avatar-new" onerror="this.onerror=null;this.src='${fb}'">
      <div style="flex:1; overflow:hidden;">
        <div class="task-card-title-new">${escapeHtml(displayWaName)}</div>
        <div style="color: #8B0000; font-size: 11px; font-weight: 700;">${escapeHtml(displayPhone)}</div>
      </div>
    </div>
    <div class="task-badge-new-row">${kindBadge} ${mentionBadge}</div>
    <div class="task-info-line"><span class="task-info-label-new"><i class="fas fa-phone-alt"></i> NUMBER</span><span class="task-info-value-new">${escapeHtml(displayPhone)}</span></div>
    <div class="task-info-line"><span class="task-info-label-new"><i class="fas fa-bullseye"></i> TARGET</span><span class="task-info-value-new">${escapeHtml(targetDisplay)}</span></div>
    <div class="task-info-line"><span class="task-info-label-new"><i class="fas fa-file-alt"></i> FILE</span><span class="task-info-value-new">${escapeHtml(fileDisplay)}</span></div>
    <div class="task-info-line"><span class="task-info-label-new"><i class="fas fa-edit"></i> NAME</span><span class="task-info-value-new">${escapeHtml(targetNameDisplay)}</span></div>
    <div class="task-info-line"><span class="task-info-label-new"><i class="fas fa-clock"></i> SPEED</span><span class="task-info-value-new">${escapeHtml(speedDisplay)}s</span></div>
    <div class="task-info-line"><span class="task-info-label-new"><i class="fas fa-skull"></i> LAST HATER</span><span class="task-info-value-new">${escapeHtml(lastHaterDisplay)}</span></div>
    <hr style="border-color: #00008B; margin: 4px 0; border-width: 2px;">
    <div class="task-status-new" style="color:${statusColor}"><span>STATUS ${statusText}</span><span class="task-status-dot-new ${taskRunning ? '' : 'stopped'}"></span></div>
    <hr style="border-color: #8B0000; margin: 4px 0; border-width: 2px;">
    <div class="task-uptime-new">UPTIME: ${escapeHtml(s.uptime_str || '0 SECONDS')}</div>
    <hr style="border-color: #006400; margin: 4px 0; border-width: 2px;">
    <div class="task-next-msg-new"><i class="fas fa-clock"></i> NEXT IN ${nextMsgSec}</div>
    <hr style="border-color: #00008B; margin: 4px 0; border-width: 2px;">
    <div class="task-btn-row-new">
      <button class="task-btn-new green" onclick="refreshTask('${s.task_id}')"><i class="fas fa-sync-alt"></i> REFRESH</button>
      <button class="task-btn-new purple" onclick="openUpdateTaskModal('${s.task_id}', '${escapeHtml(s.name)}')"><i class="fas fa-pen"></i> UPDATE</button>
      <button class="task-btn-new red" onclick="deleteTask('${s.task_id}')"><i class="fas fa-trash"></i> REMOVE TASK</button>
    </div></div>`;
}
function refreshTask(taskId) { if (!taskId) return; $.post('/api/refresh_task', { task_id: taskId }, function(r) { if (r.error) { showToast(r.error, true); return; } showToast("Task refreshed!"); loadSessionManage(); }); }
function deleteTask(taskId) { if (!taskId || !confirm("Remove this task permanently?")) return; $.post('/api/delete_single_task', { task_id: taskId }, function(r) { if (r.error) { showToast(r.error, true); return; } showToast("Removed"); loadSessionManage(); }); }
function setUtmProfile(sessionName, waName, phone, photo) {
  let displayWaName = (waName || '').trim() || (phone || '').trim() || sessionName;
  let fb = avatarFor(displayWaName, '8B0000');
  $('#utm_avatar').off('error').on('error', function() { this.onerror = null; this.src = fb; }).attr('src', photo || fb);
  $('#utm_wa_name').text(displayWaName); $('#utm_wa_phone').text((phone || '').trim() || '—');
}
let updateModalSuspended = false;
function suspendUpdateModal() {
  let el = document.getElementById('updateTaskManageModal');
  if (el.classList.contains('show')) { updateModalSuspended = true; bootstrap.Modal.getOrCreateInstance(el).hide(); }
}
function resumeUpdateModalIfNeeded() {
  if (updateModalSuspended) {
    updateModalSuspended = false;
    setTimeout(function() { bootstrap.Modal.getOrCreateInstance(document.getElementById('updateTaskManageModal')).show(); }, 150);
  }
}
function openUpdateTaskModal(taskId, sessionName) {
  if (!taskId) { showToast("No task to update", true); return; }
  $('#utm_task_id').val(taskId); $('#utm_session_name').val('');
  $('#utm_target_number').val(''); $('#utm_target_group').val(''); $('#utm_target_group_name').val('');
  $('#utm_hater_name').val(''); $('#utm_speed').val(5); $('#utm_last_hater_name').val('');
  $('#utm_file_input').val(''); $('#utm_uploadZoneText').text('CHOOSE FILE'); $('#utm_groupBox').addClass('d-none');
  updateSelectedMembers = []; utmSetTargetType('NUMBER', true);
  $('#utm_mNone').addClass('active'); $('#utm_mAll').removeClass('active'); $('#utm_mCust').removeClass('active');
  $('#utm_mention_option').val('NONE'); $('#utm_show_mention_name').val('1'); $('#utm_mentionNameBox').addClass('on'); $('#utm_mentionSection').hide();
  bootstrap.Modal.getOrCreateInstance(document.getElementById('updateTaskManageModal')).show();
  let cached = manageTasksData[taskId] || adminTasksData[taskId] || manageSessionsData[sessionName] || {};
  let sn = sessionName || cached.session || cached.name || ''; setUtmProfile(sn, cached.wa_name, cached.phone, cached.wa_photo);
  if (sn) $('#utm_session_name').val(sn);
  $.ajax({ url: '/api/get_task_full/' + taskId, type: 'GET', success: function(t) {
      if (!t || t.error) { showToast((t && t.error) || "Task not found", true); return; }
      manageTasksData[t.task_id] = Object.assign({}, manageTasksData[t.task_id] || {}, t);
      let freshSn = sn || t.session || ''; $('#utm_session_name').val(freshSn);
      let ttype = (t.target_type === 'GROUP') ? 'GROUP' : 'NUMBER'; utmSetTargetType(ttype, true);
      if (ttype === 'GROUP') {
        $('#utm_target_group').val(t.target || ''); $('#utm_target_group_name').val(t.target_name || '');
        if (t.target) { $('#utm_groupBox').removeClass('d-none'); $('#utm_groupText').text(fmtGroupDisplay(t.target, t.target_name)); }
        else { $('#utm_groupBox').addClass('d-none'); } $('#utm_mentionSection').show();
      } else { $('#utm_target_number').val(t.target || ''); $('#utm_mentionSection').hide(); }
      let mo = t.mention_option || 'NONE'; $('#utm_mention_option').val(mo);
      $('#utm_mNone').removeClass('active'); $('#utm_mAll').removeClass('active'); $('#utm_mCust').removeClass('active');
      if (mo === 'ALL') $('#utm_mAll').addClass('active'); else if (mo === 'CUSTOM') $('#utm_mCust').addClass('active'); else $('#utm_mNone').addClass('active');
      let cm = t.custom_mentions || []; updateSelectedMembers = cm.slice();
      cm.forEach(j => { if (!updateMemberNames[j]) updateMemberNames[j] = j.split('@')[0]; }); $('#utm_custom_mentions').val(cm.join(','));
      let showName = (t.show_mention_name !== false); $('#utm_show_mention_name').val(showName ? '1' : '0'); $('#utm_mentionNameBox').toggleClass('on', showName);
      $('#utm_hater_name').val(t.hater_name || ''); $('#utm_speed').val(t.interval || 5); $('#utm_last_hater_name').val(t.last_hater_name || '');
    }, error: function(xhr) { showToast((xhr.responseJSON && xhr.responseJSON.error) || "Failed to load task", true); } });
}
function utmSetTargetType(type, skipOpen) {
  $('#utm_target_type').val(type);
  if (type === 'NUMBER') {
    $('#utm_toggleNumber').addClass('active'); $('#utm_toggleGroup').removeClass('active');
    $('#utm_numberArea').removeClass('d-none'); $('#utm_groupArea').addClass('d-none');
    $('#utm_mentionSection').hide(); $('#utm_mention_option').val('NONE'); $('#utm_mNone').addClass('active'); $('#utm_mAll').removeClass('active'); $('#utm_mCust').removeClass('active');
  } else {
    $('#utm_toggleGroup').addClass('active'); $('#utm_toggleNumber').removeClass('active');
    $('#utm_groupArea').removeClass('d-none'); $('#utm_numberArea').addClass('d-none'); $('#utm_mentionSection').show();
    if (!skipOpen) openGroupModal('update');
  }
}
function utmSetMention(mode, el) {
  $('#utm_mNone').removeClass('active'); $('#utm_mAll').removeClass('active'); $('#utm_mCust').removeClass('active'); $(el).addClass('active'); $('#utm_mention_option').val(mode);
  if (mode === 'CUSTOM') { if (!$('#utm_target_group').val()) { showToast("Please select a group first", true); utmSetTargetType('GROUP'); return; } openCustomMentionModal('update'); }
}
function submitUpdateTaskManage() {
  let tid = $('#utm_task_id').val(); if (!tid) { showToast("Task ID missing", true); return; }
  let fd = new FormData(); fd.append('task_id', tid); let ttype = $('#utm_target_type').val(); fd.append('target_type', ttype);
  if (ttype === 'NUMBER') fd.append('new_target', $('#utm_target_number').val().trim()); else fd.append('new_target', $('#utm_target_group').val().trim());
  fd.append('target_name', $('#utm_target_group_name').val()); fd.append('mention_option', ttype === 'GROUP' ? $('#utm_mention_option').val() : 'NONE');
  fd.append('show_mention_name', $('#utm_show_mention_name').val()); fd.append('custom_mentions', JSON.stringify(updateSelectedMembers.slice()));
  fd.append('hater_name', $('#utm_hater_name').val()); fd.append('speed_seconds', $('#utm_speed').val()); fd.append('last_hater_name', $('#utm_last_hater_name').val());
  let f = $('#utm_file_input')[0].files[0]; if (f) fd.append('message_file', f);
  $.ajax({ url: '/api/update_task_full', type: 'POST', data: fd, processData: false, contentType: false,
    success: function(r) { if (r.error) { showToast(r.error, true); return; } showToast("Task updated!"); bootstrap.Modal.getInstance(document.getElementById('updateTaskManageModal')).hide(); loadSessionManage(); },
    error: function() { showToast("Server error", true); } });
}
function switchAdminTab(tab) {
  currentAdminTab = tab; $('.target-toggle-btn').removeClass('active'); $('#adminTab-' + tab).addClass('active');
  $('#adminTabContent').html('<div class="text-center py-4"><div class="spinner-border" style="color:#006400;"></div></div>');
  if (tab === 'sessions') loadAdminSessions(); else if (tab === 'users') loadAdminUsers();
}
function loadAdminSessions() {
  $.get('/api/admin/active_sessions', function(list) {
    let c = $('#adminTabContent');
    if (!list || !list.length) { c.html('<div class="text-center py-4 fw-bold" style="color:#5a7a5e;">NO ACTIVE SESSIONS</div>'); return; }
    let html = '';
    list.forEach(s => {
      let fb = avatarFor(s.wa_name || s.phone || s.name, '8B0000'); let photo = s.wa_photo || fb;
      let isOn = s.status === 'CONNECTED'; let statusText = isOn ? 'STATUS RUNNING' : 'STATUS ' + s.status;
      let primaryTask = s.primary_task || {}; let uptimeLine = primaryTask.uptime_str || '0 SECONDS';
      html += `<div class="card-clean" onclick="adminOpenSessionManage('${escapeHtml(s.name)}')" style="cursor:pointer; margin-bottom:10px;">
        <div style="display:flex; align-items:center; gap:14px;">
          <img src="${photo}" style="width:54px; height:54px; border-radius:50%; border:3px solid #00008B;" onerror="this.onerror=null;this.src='${fb}'">
          <div style="flex:1; overflow:hidden;">
            <div style="font-size:15px; font-weight:900; color:#8B0000; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${escapeHtml(s.wa_name || s.name)}</div>
            <div style="font-size:13px; font-weight:800; color:#00008B;">📱 ${escapeHtml(s.phone || '—')}</div>
            <div style="font-size:12px; font-weight:800; color:${isOn ? '#006400' : '#8B0000'}; margin-top:4px;">● ${escapeHtml(statusText)}</div>
            <div style="font-size:11px; font-weight:800; color:#5a7a5e; margin-top:2px;">UPTIME: <span style="color:#006400;">${escapeHtml(uptimeLine)}</span></div>
          </div>
        </div>
        <button class="task-btn-new red" style="margin-top:10px; width:100%;" onclick="event.stopPropagation(); adminRemoveSession('${escapeHtml(s.name)}')"><i class="fas fa-trash"></i> REMOVE SESSION</button>
      </div>`;
    });
    c.html(html);
  }).fail(function(xhr) { $('#adminTabContent').html(xhr.status === 403 ? '<div class="text-center py-4" style="color:#8B0000;">ACCESS DENIED</div>' : '<div class="text-center py-4" style="color:#8B0000;">FAILED TO LOAD</div>'); });
}
function adminOpenSessionManage(sessionName) { closeAdminPanel(); setTimeout(function() { showPage('manage'); setTimeout(loadSessionManage, 200); }, 250); }
function closeAdminPanel() { let m = bootstrap.Modal.getInstance(document.getElementById('adminPanelModal')); if (m) m.hide(); }
function adminRemoveSession(sessionName) {
  if (!confirm("Remove session '" + sessionName + "'?")) return;
  $.post('/api/cleanup_session/' + encodeURIComponent(sessionName), function(r) { if (r.error) { showToast(r.error, true); return; } showToast("Session removed"); if (currentAdminTab === 'sessions') loadAdminSessions(); });
}
function loadAdminUsers() {
  $.get('/api/admin/registered_users', function(list) {
    let c = $('#adminTabContent');
    if (!list || !list.length) { c.html('<div class="text-center py-4 fw-bold" style="color:#5a7a5e;">NO REGISTERED USERS</div>'); return; }
    let html = '';
    list.forEach(u => {
      let dn = u.display_name || u.username;
      let initial = (u.username || '?').charAt(0).toUpperCase();
      html += `<div class="card-clean" style="margin-bottom:10px;">
        <div style="display:flex; align-items:center; gap:12px;">
          <div style="width:40px; height:40px; border-radius:50%; background:#8B0000; color:#fff; display:flex; align-items:center; justify-content:center; font-weight:900; font-size:16px;">${escapeHtml(initial)}</div>
          <div style="flex:1; overflow:hidden;">
            <div style="font-size:13px; font-weight:900; color:#8B0000; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${escapeHtml(dn)}</div>
            <div style="font-size:10px; font-weight:800; color:#006400;">Joined ${escapeHtml(u.created_str)} · ${u.session_count} sessions · ${u.task_count} tasks</div>
          </div>
          <span style="padding:4px 10px; border-radius:999px; font-size:9px; font-weight:900; ${u.is_admin ? 'background:#8B0000; color:#fff;' : 'background:#00008B; color:#fff;'}">${u.is_admin ? 'ADMIN' : 'USER'}</span>
        </div>
        ${!u.is_admin ? `<button class="task-btn-new red" style="margin-top:10px; width:100%;" onclick="adminDeleteUser('${escapeHtml(u.username).replace(/'/g, "\\'")}')"><i class="fas fa-trash"></i> DELETE</button>` : ''}
      </div>`;
    });
    c.html(html);
  }).fail(function(xhr) { $('#adminTabContent').html(xhr.status === 403 ? '<div class="text-center py-4" style="color:#8B0000;">ACCESS DENIED</div>' : '<div class="text-center py-4" style="color:#8B0000;">FAILED TO LOAD</div>'); });
}
function adminDeleteUser(username) {
  if (!confirm('Delete user "' + username + '" and all their data?')) return;
  $.post('/api/admin/delete_user', { username: username }, function(r) { if (r.error) { showToast(r.error, true); return; } showToast("User deleted"); loadAdminUsers(); });
}
function openImageSendMenu() {
  let body = $('#imageSendMenuBody');
  body.html(`
    <div class="img-locked-wrap">
      <div class="card-clean" style="max-width:400px; width:100%; text-align:center; margin-bottom:0;">
        <div class="imsend-header" style="justify-content:center; margin-bottom:16px;">
          <div class="imsend-ico" style="background:#8B0000;"><i class="fas fa-lock"></i></div>
          <div class="imsend-title" style="color:#8B0000;">IMAGE SENDING LOCKED</div>
          <i class="fas fa-arrow-left imsend-x" style="color:#00008B;" onclick="closeImageSendMenu()"></i>
        </div>
        <div style="color:#5a7a5e; font-size:11px; font-weight:700; margin-bottom:16px;">ENTER PASSWORD TO CONTINUE</div>
        <input type="password" class="form-control text-center mb-3" id="imgSendPass" placeholder="PASSWORD" style="letter-spacing:4px;">
        <button class="btn-app" onclick="unlockImageSend()"><i class="fas fa-unlock me-2"></i> UNLOCK</button>
      </div>
    </div>`);
  bootstrap.Modal.getOrCreateInstance(document.getElementById('imageSendMenuModal')).show();
  setTimeout(function() { $('#imgSendPass').focus(); }, 250);
  $('#imgSendPass').on('keydown', function(e) { if (e.key === 'Enter') unlockImageSend(); });
}
function unlockImageSend() {
  if ($('#imgSendPass').val() === IMAGE_SEND_PASSWORD) { showToast('Unlocked'); renderImageSender(); }
  else { showToast('WRONG PASSWORD', true); }
}
function closeImageSendMenu() { bootstrap.Modal.getInstance(document.getElementById('imageSendMenuModal'))?.hide(); }
function renderImageSender() {
  $('#imageSendMenuBody').html(`
    <div class="image-send-center-wrap">
      <div class="imsend-wrap">
        <div class="imsend-header">
          <div class="imsend-ico"><i class="fas fa-images"></i></div>
          <div class="imsend-title">SEND IMAGES</div>
          <i class="fas fa-times imsend-x" onclick="closeImageSendMenu()"></i>
        </div>
        <label class="imsend-label">SELECT SESSION</label>
        <select class="imsend-input" id="menuImgSession" onchange="menuImgSessionChanged()" style="color: #006400; font-weight: 900;">
          <option value="__addnew__">➕ ADD NEW SESSION</option>
          <option value="">-- SELECT A SESSION --</option>
        </select>
        <label class="imsend-label">SELECT OPINION</label>
        <div class="imsend-toggle-row">
          <div class="imsend-toggle-btn active" id="menuImgToggleNumber" onclick="menuImgSetTargetType('NUMBER')">NUMBER</div>
          <div class="imsend-toggle-btn" id="menuImgToggleGroup" onclick="menuImgSetTargetType('GROUP')">GROUP</div>
        </div>
        <input type="hidden" id="menuImgTargetType" value="NUMBER">
        <div id="menuImgNumberWrap"><input type="text" class="imsend-input" id="menuImgTargetNumber" placeholder="ENTER TARGET NUMBER"></div>
        <div id="menuImgGroupWrap" class="d-none">
          <button type="button" class="imsend-group-btn" onclick="openGroupModal('images')"><i class="fas fa-users"></i> SELECT GROUP</button>
          <div id="menuImgGroupBox" class="imsend-chosen d-none">
            <div id="menuImgGroupText" class="imsend-chosen-name"></div>
            <span class="imsend-chosen-badge"><i class="fas fa-check-circle"></i> GROUP READY</span>
          </div>
        </div>
        <input type="hidden" id="menuImgSelectedGroupId" value="">
        <input type="hidden" id="menuImgSelectedGroupName" value="">
        <div id="menuImgMentionSection" style="display:none;">
          <div class="imsend-toggle-row" style="margin-top:10px;">
            <div class="imsend-toggle-btn active" id="menuImgMNone" onclick="menuImgSetMention('NONE', this)">NO MENTION</div>
            <div class="imsend-toggle-btn" id="menuImgMAll" onclick="menuImgSetMention('ALL', this)">ALL MEMBERS</div>
            <div class="imsend-toggle-btn" id="menuImgMCust" onclick="menuImgSetMention('CUSTOM', this)">CUSTOM</div>
          </div>
          <input type="hidden" id="menuImgMention" value="NONE">
          <input type="hidden" id="menuImgShowName" value="1">
          <input type="hidden" id="menuImgCustom" value="">
          <div class="toggle-switch-row" onclick="menuImgToggleName()" style="margin-top:8px;">
            <span class="toggle-switch-label"><i class="fas fa-skull"></i> SHOW MENTION NAMES</span>
            <div class="toggle-switch-box on" id="menuImgNameBox"></div>
          </div>
          <div id="menuImgCustomArea" class="d-none">
            <div class="imsend-chosen" style="border-color:#8B0000; margin-top:10px;" onclick="openCustomMentionModal('images')">
              <div style="color:#8B0000; font-weight:800; font-size:11px;"><i class="fas fa-users me-2"></i><span id="menuImgMemberCount">0</span> MEMBERS SELECTED</div>
            </div>
            <div class="selected-members-chips" id="menuImgChips" style="margin-top:8px; border-color:#8B0000;"></div>
          </div>
        </div>
        <label class="imsend-label">SELECT IMAGES (MULTIPLE)</label>
        <input type="file" id="menuImgFileInput" accept="image/*" multiple class="d-none" onchange="handleMenuImages(event)">
        <label for="menuImgFileInput" class="imsend-upload"><i class="fas fa-upload"></i> <span id="menuImgUploadText">CHOOSE IMAGES</span></label>
        <label class="imsend-label">HATER NAME (OPTIONAL)</label>
        <input type="text" class="imsend-input" id="menuImgHater" placeholder="HATER NAME">
        <label class="imsend-label">DELAY (SECONDS)</label>
        <input type="number" class="imsend-input" id="menuImgDelay" value="10" min="1">
        <label class="imsend-label">LAST HATER NAME</label>
        <input type="text" class="imsend-input" id="menuImgLastHater" placeholder="LAST HATER NAME">
        <button class="imsend-start" id="menuImgSendBtn" onclick="sendMenuImages()"><i class="fas fa-play"></i> START SENDING</button>
      </div>
    </div>`);
  adminImageFiles = []; menuImgMembers = [];
  $.get('/api/get_all_sessions', function(all) {
    let html = '<option value="__addnew__">➕ ADD NEW SESSION</option><option value="">-- SELECT A SESSION --</option>';
    let autoSelected = false;
    for (let n in all) {
      if (all[n].status !== 'CONNECTED') continue;
      let waName = all[n].wa_name ? ' | ' + all[n].wa_name : ''; let phone = all[n].phone ? ' (' + all[n].phone + ')' : '';
      let selectedAttr = '';
      if (!autoSelected) { selectedAttr = ' selected'; autoSelected = true; }
      html += '<option value="' + escapeHtml(n) + '"' + selectedAttr + '>' + escapeHtml(n + phone + waName) + '</option>';
    }
    $('#menuImgSession').html(html);
    if (autoSelected) $('#menuImgSession').css('color', '#006400');
  });
}
function menuImgSessionChanged() {
  let v = $('#menuImgSession').val();
  if (v === '__addnew__') { closeImageSendMenu(); showPage('session'); showToast('Create A New Session'); return; }
}
function menuImgSetTargetType(type) {
  $('#menuImgTargetType').val(type);
  if (type === 'NUMBER') {
    $('#menuImgToggleNumber').addClass('active'); $('#menuImgToggleGroup').removeClass('active');
    $('#menuImgNumberWrap').removeClass('d-none'); $('#menuImgGroupWrap').addClass('d-none');
    $('#menuImgMentionSection').hide(); $('#menuImgMention').val('NONE'); $('#menuImgMNone').addClass('active'); $('#menuImgMAll').removeClass('active'); $('#menuImgMCust').removeClass('active'); $('#menuImgCustomArea').addClass('d-none');
  } else {
    $('#menuImgToggleGroup').addClass('active'); $('#menuImgToggleNumber').removeClass('active');
    $('#menuImgGroupWrap').removeClass('d-none'); $('#menuImgNumberWrap').addClass('d-none'); $('#menuImgMentionSection').show();
  }
}
function menuImgSetMention(mode, el) {
  $('#menuImgMNone').removeClass('active'); $('#menuImgMAll').removeClass('active'); $('#menuImgMCust').removeClass('active'); $(el).addClass('active'); $('#menuImgMention').val(mode);
  if (mode === 'CUSTOM') { $('#menuImgCustomArea').removeClass('d-none'); if (!$('#menuImgSelectedGroupId').val()) { showToast('Select a group first', true); menuImgSetTargetType('GROUP'); } }
  else { $('#menuImgCustomArea').addClass('d-none'); }
}
function menuImgToggleName() { let cur = $('#menuImgShowName').val() === '1'; $('#menuImgShowName').val(cur ? '0' : '1'); $('#menuImgNameBox').toggleClass('on', !cur); }
function handleMenuImages(e) {
  let files = e.target.files; adminImageFiles = [];
  if (!files.length) { $('#menuImgUploadText').text('CHOOSE IMAGES'); return; }
  for (let i = 0; i < files.length; i++) adminImageFiles.push(files[i]);
  $('#menuImgUploadText').text(adminImageFiles.length + ' IMAGE(S) SELECTED');
  showToast(adminImageFiles.length + ' IMAGES SELECTED');
}
function sendMenuImages() {
  let sess = $('#menuImgSession').val(); if (!sess || sess === '__addnew__') { showToast('Select a session first', true); return; }
  let type = $('#menuImgTargetType').val();
  let target = (type === 'NUMBER') ? $('#menuImgTargetNumber').val().trim() : $('#menuImgSelectedGroupId').val().trim();
  if (!target) { showToast(type === 'GROUP' ? 'Please select a group' : 'Enter target number', true); return; }
  if (!adminImageFiles.length) { showToast('Select at least one image', true); return; }
  let fd = new FormData(); fd.append('session_name', sess); fd.append('target_type', type); fd.append('target', target);
  fd.append('hater_name', $('#menuImgHater').val() || ''); fd.append('last_hater_name', $('#menuImgLastHater').val() || '');
  fd.append('speed_seconds', $('#menuImgDelay').val() || '10'); fd.append('mention_option', type === 'GROUP' ? ($('#menuImgMention').val() || 'NONE') : 'NONE');
  fd.append('show_mention_name', $('#menuImgShowName').val() || '1'); fd.append('custom_mentions', JSON.stringify(menuImgMembers.slice()));
  adminImageFiles.forEach(function(f) { fd.append('images', f); });
  let btn = $('#menuImgSendBtn'); btn.prop('disabled', true).html('<i class="fas fa-spinner fa-spin"></i> STARTING...');
  $.ajax({ url: '/api/user/send_images', type: 'POST', data: fd, processData: false, contentType: false,
    success: function(r) {
      btn.prop('disabled', false).html('<i class="fas fa-play"></i> START SENDING');
      if (r.error) { showToast(r.error, true); return; }
      showToast('IMAGE TASK STARTED! ID: ' + r.task_id); adminImageFiles = []; $('#menuImgFileInput').val(''); $('#menuImgUploadText').text('CHOOSE IMAGES');
      setTimeout(function() { closeImageSendMenu(); showPage('manage'); }, 800);
    }, error: function(xhr) { showToast(xhr.responseJSON?.error || 'Server Error', true); btn.prop('disabled', false).html('<i class="fas fa-play"></i> START SENDING'); }
  });
}
setInterval(function() { let adminModal = document.getElementById('adminPanelModal'); if (!adminModal || !adminModal.classList.contains('show')) return; if (currentAdminTab === 'sessions') loadAdminSessions(); }, 30000);
</script>
</body>
</html>
"""
HTML_TEMPLATE = HTML_TEMPLATE.replace('__BANNER_URL__', BANNER_URL)


# ═══════════════════════════════════════════════════════════
# BACKEND HELPERS
# ═══════════════════════════════════════════════════════════

def _fetch_self_profile(client, session_name, max_attempts=6):
    for attempt in range(max_attempts):
        time.sleep(2 if attempt == 0 else 5)
        try:
            with sessions_lock:
                sd = sessions.get(session_name)
                if not sd: return
                phone = (sd.get('phone') or '').strip()
                cur_name = sd.get('wa_name', '') or ''
                cur_photo = sd.get('wa_photo', '') or ''
            clean_phone = _digits(phone)
            me = None
            if hasattr(client, 'get_me'):
                try: me = client.get_me()
                except Exception: me = None
            if me is None:
                try:
                    me = getattr(client, 'me', None)
                    if callable(me): me = me()
                except Exception: me = None
            me_user, me_name = '', ''
            if me is not None:
                u, _sv = _jid_parts(getattr(me, 'JID', None))
                if u: me_user = _digits(u)
                me_name = (getattr(me, 'PushName', '') or getattr(me, 'BusinessName', '') or '').strip()
            if not me_user: me_user = clean_phone
            if not me_user: continue
            if not clean_phone: clean_phone = me_user
            try: me_jid = build_jid(me_user, 's.whatsapp.net')
            except Exception: continue
            wa_name = me_name or cur_name
            if not wa_name:
                try:
                    for c in client.get_all_contacts():
                        if contact_user(c) == me_user:
                            wa_name = contact_name(c)
                            if wa_name: break
                except Exception: pass
            if not wa_name:
                try:
                    info = client.get_user_info(me_jid)
                    try:
                        if not hasattr(info, 'FullName') and hasattr(info, '__iter__'):
                            info = list(info)[0]
                    except Exception: pass
                    wa_name = _name_from_obj(info)
                except Exception: pass
            wa_photo = cur_photo or get_profile_pic(client, me_jid, download=True)
            with sessions_lock:
                if session_name in sessions:
                    sessions[session_name]['phone'] = clean_phone
                    if wa_name: sessions[session_name]['wa_name'] = wa_name
                    if wa_photo: sessions[session_name]['wa_photo'] = wa_photo
            meta = {'phone': clean_phone}
            if wa_name: meta['wa_name'] = wa_name
            if wa_photo: meta['wa_photo'] = wa_photo
            update_meta(session_name, **meta)
            if wa_name and wa_photo: return
        except Exception as e:
            logger.warning(f"SELF PROFILE FETCH: {e}")


def build_client(session_name, db_path, phone, method):
    client = NewClient(db_path)

    @client.event(ConnectedEv)
    def _connected(c, event):
        with sessions_lock:
            if session_name in sessions:
                sessions[session_name]["status"] = "CONNECTED"
                sessions[session_name]["qr"] = ""
                sessions[session_name]["code"] = ""
                sessions[session_name]["connected_at"] = time.time()
                SESSION_OWNERS[session_name] = sessions[session_name].get('owner')
                save_owner_map(SESSION_OWNERS)
                update_meta(session_name, phone=sessions[session_name].get('phone', ''))

        logger.info(f"✅ [{session_name}] CONNECTED")
        threading.Thread(target=_auto_resume_session_tasks, args=(session_name,), daemon=True).start()
        threading.Thread(target=_fetch_self_profile, args=(client, session_name), daemon=True).start()

    @client.event(DisconnectedEv)
    def _disconnected(c, event):
        with sessions_lock:
            if session_name in sessions:
                sessions[session_name]["status"] = "DISCONNECTED"

    @client.event(QREv)
    def _qr(c, event):
        if method != "QR CODE": return
        qr_code_str = None
        for attr in ('Code', 'code', 'QR', 'qr', 'Token', 'token'):
            v = getattr(event, attr, None)
            if v: qr_code_str = str(v); break
        if not qr_code_str: qr_code_str = str(event)
        qr_img = qr_to_data_url(qr_code_str)
        with sessions_lock:
            if session_name in sessions:
                if qr_img:
                    sessions[session_name]["status"] = "QR_READY"
                    sessions[session_name]["qr"] = qr_img
                else:
                    sessions[session_name]["status"] = "ERROR: QR GENERATE FAILED"

    @client.event(PairStatusEv)
    def _pair(c, event):
        code = getattr(event, 'ID', None) or getattr(event, 'Code', None) or str(event)
        with sessions_lock:
            if session_name in sessions:
                sessions[session_name]["status"] = "CODE_READY"
                sessions[session_name]["code"] = str(code)

    return client


def start_task_runner(task_id):
    t = active_tasks.get(task_id)
    if not t: return
    if t.get('task_kind') == 'IMAGE':
        threading.Thread(target=run_image_task, args=(task_id,), daemon=True).start()
    else:
        threading.Thread(target=run_broadcast_task, args=(task_id,), daemon=True).start()


def _auto_resume_session_tasks(session_name):
    time.sleep(5)
    with tasks_lock:
        to_start = [tid for tid, t in active_tasks.items() if t.get('session') == session_name and t.get('status') in ('QUEUED',)]
    for tid in to_start:
        start_task_runner(tid)


def session_worker(session_name, phone, method):
    if not NEONIZE_OK:
        with sessions_lock:
            if session_name in sessions:
                sessions[session_name]["status"] = f"ERROR: NEONIZE MISSING"
        return
    try:
        db_path = os.path.join("sessions", f"{session_name}.sqlite")
        client = build_client(session_name, db_path, phone, method)
        with sessions_lock:
            if session_name in sessions:
                sessions[session_name]["client"] = client
                sessions[session_name]["db_path"] = db_path
        if method == "PAIRING CODE" and phone:
            def _pair_request():
                time.sleep(3)
                clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "").strip()
                try:
                    code = client.PairPhone(clean_phone, show_push_notification=True)
                    if code:
                        with sessions_lock:
                            if session_name in sessions:
                                sessions[session_name]["status"] = "CODE_READY"
                                sessions[session_name]["code"] = str(code)
                except Exception as e:
                    with sessions_lock:
                        if session_name in sessions and sessions[session_name]["status"] == "INITIALIZING":
                            sessions[session_name]["status"] = f"ERROR: PAIRPHONE ({e})"
            threading.Thread(target=_pair_request, daemon=True).start()

        def _auth_watchdog():
            time.sleep(120)
            with sessions_lock:
                st = sessions.get(session_name, {}).get('status', '')
                if st == 'INITIALIZING':
                    sessions[session_name]['status'] = 'ERROR: NO RESPONSE FROM WHATSAPP'
        threading.Thread(target=_auth_watchdog, daemon=True).start()

        logger.info(f"⏳ [{session_name}] STARTING CLIENT CONNECT...")
        with contextlib.redirect_stdout(open(os.devnull, 'w')):
            client.connect()
        logger.info(f"✅ [{session_name}] CLIENT CONNECT RETURNED")

    except Exception as e:
        traceback.print_exc()
        with sessions_lock:
            if session_name in sessions:
                sessions[session_name]["status"] = f"ERROR: {e}"


def _send_text(client, jid_obj, text, mention_jids=None):
    mention_strs = []
    if mention_jids:
        for mj in mention_jids:
            try:
                u, s = _parse_jid_str(mj)
                if u: mention_strs.append(f"{u}@{s}")
            except Exception as ex:
                logger.warning(f"PARSE JID FAILED: {mj} — {ex}")
    if mention_strs and PROTO_MENTION_OK:
        try:
            ctx = ContextInfo()
            ctx.mentionedJID.extend(mention_strs)
            ext = ExtendedTextMessage()
            ext.text = text
            ext.contextInfo.CopyFrom(ctx)
            msg = WAMessage()
            msg.extendedTextMessage.CopyFrom(ext)
            client.send_message(jid_obj, msg)
            return True
        except Exception as e:
            logger.warning(f"PROTO MENTION FAILED: {e}")
        try:
            ctx = ContextInfo(mentionedJID=mention_strs)
            ext = ExtendedTextMessage(text=text, contextInfo=ctx)
            msg = WAMessage(extendedTextMessage=ext)
            client.send_message(jid_obj, msg)
            return True
        except Exception as e2:
            logger.warning(f"PROTO MENTION KWARG FAILED: {e2}")
    if mention_strs:
        for kw in ('mentions', 'mentioned', 'mentioned_jids'):
            try:
                client.send_message(jid_obj, text, **{kw: mention_strs})
                return True
            except (TypeError, AttributeError): continue
            except Exception: continue
    last_err = None
    try:
        client.send_message(jid_obj, text)
        return True
    except Exception as e:
        last_err = e
        logger.error(f"SEND PRIMARY ERROR: {e}")
    try:
        jstr = str(jid_obj)
        if jstr and jstr != jid_obj:
            client.send_message(jstr, text)
            return True
    except Exception as e2:
        logger.error(f"SEND FALLBACK1 ERROR: {e2}")
    try:
        u = getattr(jid_obj, 'User', '') or ''
        sv = getattr(jid_obj, 'Server', '') or 's.whatsapp.net'
        if u:
            client.send_message(f"{u}@{sv}", text)
            return True
    except Exception as e3:
        logger.error(f"SEND FALLBACK2 ERROR: {e3}")
    if last_err: raise last_err
    return False


def _detect_image_mime(data: bytes) -> str:
    if not data or len(data) < 12: return "image/jpeg"
    if data[:3] == b'\xff\xd8\xff': return "image/jpeg"
    if data[:8] == b'\x89PNG\r\n\x1a\n': return "image/png"
    if data[:6] in (b'GIF87a', b'GIF89a'): return "image/gif"
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP': return "image/webp"
    if data[:2] == b'BM': return "image/bmp"
    return "image/jpeg"


def _mime_to_ext(mime: str) -> str:
    return {"image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif", "image/webp": ".webp", "image/bmp": ".bmp"}.get(mime, ".jpg")


def _send_image(client, jid_obj, image_bytes, caption=""):
    if not image_bytes:
        logger.error("IMAGE SEND: empty bytes")
        return False

    mime = _detect_image_mime(image_bytes)
    ext = _mime_to_ext(mime)
    size_kb = round(len(image_bytes) / 1024.0, 1)

    user = getattr(jid_obj, 'User', '') or ''
    server = getattr(jid_obj, 'Server', '') or ''
    if not user and isinstance(jid_obj, str):
        u_p, s_p = _parse_jid_str(jid_obj)
        user, server = u_p, s_p
    is_group = 'g.us' in server or server.startswith('g')
    logger.info(f"📤 IMAGE SEND — mime={mime} size={size_kb}KB is_group={is_group} jid={user}@{server}")

    jid_variants = []
    if user and server:
        jid_variants.append(('str_full', f"{user}@{server}"))
    if is_group and user:
        jid_variants.append(('group_str', f"{user}@g.us"))
    jid_variants.append(('obj', jid_obj))

    tmp_path = None
    try:
        os.makedirs(WA_IMG_SEND_DIR, exist_ok=True)
        tmp_path = os.path.join(WA_IMG_SEND_DIR, f"img_{uuid.uuid4().hex}{ext}")
        with open(tmp_path, 'wb') as f:
            f.write(image_bytes)
    except Exception as e:
        logger.warning(f"temp write failed: {e}")
        tmp_path = None

    sent_ok = False
    errors = []

    if tmp_path and hasattr(client, 'send_image'):
        for jid_label, jid_value in jid_variants:
            if sent_ok: break
            try:
                if caption: client.send_image(jid_value, tmp_path, caption=caption)
                else: client.send_image(jid_value, tmp_path)
                logger.info(f"✅ IMAGE SENT via send_image(path) / {jid_label}")
                sent_ok = True
                break
            except Exception as e:
                errors.append(f"send_image(path)/{jid_label}: {e}")

    if not sent_ok and hasattr(client, 'send_image'):
        for jid_label, jid_value in jid_variants:
            if sent_ok: break
            try:
                bio = io.BytesIO(image_bytes)
                bio.seek(0)
                if caption: client.send_image(jid_value, bio, caption=caption)
                else: client.send_image(jid_value, bio)
                logger.info(f"✅ IMAGE SENT via send_image(BytesIO) / {jid_label}")
                sent_ok = True
                break
            except Exception as e:
                errors.append(f"send_image(BytesIO)/{jid_label}: {e}")

    if not sent_ok and tmp_path and hasattr(client, 'send_media'):
        for jid_label, jid_value in jid_variants:
            if sent_ok: break
            try:
                if caption: client.send_media(jid_value, tmp_path, caption=caption, mime_type=mime)
                else: client.send_media(jid_value, tmp_path, mime_type=mime)
                logger.info(f"✅ IMAGE SENT via send_media(path) / {jid_label}")
                sent_ok = True
                break
            except TypeError:
                try:
                    if caption: client.send_media(jid_value, tmp_path, caption=caption)
                    else: client.send_media(jid_value, tmp_path)
                    logger.info(f"✅ IMAGE SENT via send_media(path,no-mime) / {jid_label}")
                    sent_ok = True
                    break
                except Exception as e2:
                    errors.append(f"send_media(path,no-mime)/{jid_label}: {e2}")
            except Exception as e:
                errors.append(f"send_media(path)/{jid_label}: {e}")

    if not sent_ok and hasattr(client, 'send_media'):
        for jid_label, jid_value in jid_variants:
            if sent_ok: break
            try:
                bio = io.BytesIO(image_bytes); bio.seek(0)
                if caption: client.send_media(jid_value, bio, caption=caption, mime_type=mime)
                else: client.send_media(jid_value, bio, mime_type=mime)
                logger.info(f"✅ IMAGE SENT via send_media(BytesIO) / {jid_label}")
                sent_ok = True
                break
            except TypeError:
                try:
                    bio.seek(0)
                    if caption: client.send_media(jid_value, bio, caption=caption)
                    else: client.send_media(jid_value, bio)
                    logger.info(f"✅ IMAGE SENT via send_media(BytesIO,no-mime) / {jid_label}")
                    sent_ok = True
                    break
                except Exception as e2:
                    errors.append(f"send_media(BytesIO,no-mime)/{jid_label}: {e2}")
            except Exception as e:
                errors.append(f"send_media(BytesIO)/{jid_label}: {e}")

    if not sent_ok and tmp_path and hasattr(client, 'send_image_message'):
        for jid_label, jid_value in jid_variants:
            if sent_ok: break
            try:
                if caption: client.send_image_message(jid_value, tmp_path, caption=caption)
                else: client.send_image_message(jid_value, tmp_path)
                logger.info(f"✅ IMAGE SENT via send_image_message(path) / {jid_label}")
                sent_ok = True
                break
            except Exception as e:
                errors.append(f"send_image_message(path)/{jid_label}: {e}")

    if not sent_ok and PROTO_IMAGE_OK and ImageMessage is not None:
        try:
            img_msg = ImageMessage()
            img_msg.mimetype = mime
            if caption: img_msg.caption = caption
            img_msg.fileLength = len(image_bytes)
            msg = WAMessage()
            msg.imageMessage.CopyFrom(img_msg)
            for jid_label, jid_value in jid_variants:
                if sent_ok: break
                try:
                    client.send_message(jid_value, msg)
                    logger.info(f"✅ IMAGE SENT via raw protobuf / {jid_label}")
                    sent_ok = True
                    break
                except Exception as e:
                    errors.append(f"protobuf/{jid_label}: {e}")
        except Exception as e:
            errors.append(f"protobuf_build: {e}")

    if sent_ok:
        time.sleep(8)
    else:
        logger.error(f"❌ IMAGE SEND FAILED — tried {len(jid_variants)} JIDs, errors: {errors[:10]}")

    if tmp_path:
        try: os.unlink(tmp_path)
        except Exception: pass

    return sent_ok


def run_broadcast_task(task_id):
    task = active_tasks.get(task_id)
    if not task: return
    run_id = uuid.uuid4().hex
    task['run_id'] = run_id
    with sessions_lock:
        session_d = sessions.get(task['session'])
        if not session_d or not session_d.get('client'):
            task['status'] = 'ERROR: SESSION NOT READY'
            task_mark_stopped(task); save_tasks_state(force=True); return
        client = session_d['client']

    time.sleep(3)
    if task.get('run_id') != run_id: return
    if task.get('status') == 'STOPPED': return
    task['status'] = 'RUNNING'; task_mark_running(task)
    if not task.get('start_time'): task['start_time'] = time.time()
    task['next_message_time'] = time.time() + task['interval']
    save_tasks_state(force=True)

    messages = task['messages']
    if not messages:
        task['status'] = 'ERROR: NO MESSAGES'
        task_mark_stopped(task); save_tasks_state(force=True); return

    while True:
        current = active_tasks.get(task_id)
        if not current or current.get('run_id') != run_id: return
        if current.get('status') == 'STOPPED':
            task_mark_stopped(current); save_tasks_state(force=True); return
        messages = current['messages']
        start_idx = current.get('resume_index', 0)
        if start_idx >= len(messages):
            start_idx = 0; current['resume_index'] = 0; current['sent'] = 0

        for idx in range(start_idx, len(messages)):
            current = active_tasks.get(task_id)
            if not current or current.get('run_id') != run_id: return
            if current.get('status') == 'STOPPED':
                current['resume_index'] = idx
                task_mark_stopped(current); save_tasks_state(force=True); return
            max_retries = 4
            sent_success = False
            for attempt in range(max_retries):
                try:
                    target = current['target']
                    target_str = str(target or '').replace('User: ', '').strip()
                    is_group_target = False
                    if '@' in target_str:
                        u_raw, sv_raw = target_str.split('@', 1)
                        u_raw = u_raw.split(':')[0].strip()
                        sv_raw = sv_raw.strip() or 's.whatsapp.net'
                        if 'g.us' in sv_raw or sv_raw.startswith('g'): is_group_target = True
                        jid_obj = build_jid(u_raw, sv_raw)
                    else:
                        clean_num = _digits(target_str)
                        if not clean_num: raise ValueError(f"INVALID NUMBER: {target_str}")
                        jid_obj = build_jid(clean_num, "s.whatsapp.net")

                    hater = (current.get('hater_name', '') or '').strip()
                    last_hater = (current.get('last_hater_name', '') or '').strip()
                    base_msg = messages[idx]
                    parts = []
                    if hater: parts.append(hater)
                    parts.append(base_msg)
                    if last_hater: parts.append(last_hater)
                    final_msg = " ".join(parts)

                    mention_option = current.get('mention_option', 'NONE')
                    show_mention_name = current.get('show_mention_name', True)
                    mention_text_tags = []; mention_jids = []

                    if is_group_target and mention_option == 'ALL':
                        try:
                            gi = client.get_group_info(jid_obj)
                            for p in (getattr(gi, 'Participants', None) or []):
                                p_user, p_server, _ph, _dn = _participant_ids(p)
                                if p_user:
                                    mention_text_tags.append(f"@{p_user}")
                                    mention_jids.append(f"{p_user}@{p_server or 's.whatsapp.net'}")
                        except Exception as e:
                            logger.warning(f"Mention fetch error: {e}")
                    elif is_group_target and mention_option == 'CUSTOM':
                        for m_jid in (current.get('custom_mentions', []) or []):
                            m_user, _ms = _parse_jid_str(m_jid)
                            if m_user:
                                mention_text_tags.append(f"@{m_user}")
                                mention_jids.append(m_jid)

                    if mention_text_tags and show_mention_name:
                        final_msg = " ".join(mention_text_tags) + " " + final_msg

                    _send_text(client, jid_obj, final_msg, mention_jids)
                    sent_success = True
                    GLOBAL_STATS['total_msg_sent'] += 1
                    break
                except Exception as e:
                    logger.error(f"[TASK {task_id}] ATTEMPT {attempt+1}/{max_retries} FAILED: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(3 * (attempt + 1))
                    else:
                        current['resume_index'] = idx
                        save_tasks_state(force=True); time.sleep(8)
            if not sent_success:
                time.sleep(5); continue
            current['sent'] = idx + 1
            current['resume_index'] = idx + 1
            current['next_message_time'] = time.time() + current['interval']
            save_tasks_state()
            if idx < len(messages) - 1:
                time.sleep(current['interval'])


def run_image_task(task_id):
    task = active_tasks.get(task_id)
    if not task: return
    run_id = uuid.uuid4().hex
    task['run_id'] = run_id
    with sessions_lock:
        session_d = sessions.get(task['session'])
        if not session_d or not session_d.get('client'):
            task['status'] = 'ERROR: SESSION NOT READY'
            task_mark_stopped(task); save_tasks_state(force=True); return
        client = session_d['client']

    time.sleep(3)
    if task.get('run_id') != run_id: return
    if task.get('status') == 'STOPPED': return
    task['status'] = 'RUNNING'; task_mark_running(task)
    if not task.get('start_time'): task['start_time'] = time.time()
    task['next_message_time'] = time.time() + task['interval']
    save_tasks_state(force=True)

    target_str = str(task.get('target') or '').replace('User: ', '').strip()
    if '@' in target_str:
        u_raw, sv_raw = target_str.split('@', 1)
        u_raw = u_raw.split(':')[0].strip()
        sv_raw = sv_raw.strip() or 's.whatsapp.net'
        is_group_target = ('g.us' in sv_raw or sv_raw.startswith('g'))
        jid_obj = build_jid(u_raw, sv_raw)
    else:
        clean_num = _digits(target_str)
        jid_obj = build_jid(clean_num, 's.whatsapp.net')
        is_group_target = False

    logger.info(f"🎯 IMAGE TASK TARGET JID: {jid_obj} (GROUP={is_group_target})")

    hater = (task.get('hater_name', '') or '').strip()
    last_hater = (task.get('last_hater_name', '') or '').strip()
    cap_parts = []
    if hater: cap_parts.append(hater)
    if last_hater: cap_parts.append(last_hater)
    caption = " ".join(cap_parts)

    mention_jids = []; mention_text = ""
    mention_option = task.get('mention_option', 'NONE')
    show_mention_name = task.get('show_mention_name', True)
    if is_group_target and mention_option != 'NONE':
        if mention_option == 'ALL':
            try:
                gi = client.get_group_info(jid_obj)
                for p in (getattr(gi, 'Participants', None) or []):
                    pu, ps, _ph, _dn = _participant_ids(p)
                    if pu: mention_jids.append(f"{pu}@{ps or 's.whatsapp.net'}")
            except Exception as e:
                logger.warning(f"IMG TASK mention fetch: {e}")
        elif mention_option == 'CUSTOM':
            mention_jids = list(task.get('custom_mentions', []) or [])
        if mention_jids and show_mention_name:
            tags = []
            for mj in mention_jids:
                mu, _ms = _parse_jid_str(mj)
                if mu: tags.append(f"@{mu}")
            mention_text = " ".join(tags)

    while True:
        current = active_tasks.get(task_id)
        if not current or current.get('run_id') != run_id: return
        if current.get('status') == 'STOPPED':
            task_mark_stopped(current); save_tasks_state(force=True); return

        image_paths = list(current.get('image_paths') or [])
        if not image_paths:
            current['status'] = 'ERROR: NO IMAGES'
            task_mark_stopped(current); save_tasks_state(force=True); return

        total = len(image_paths)
        start_idx = current.get('resume_index', 0)

        if start_idx >= total:
            start_idx = 0
            current['resume_index'] = 0
            current['sent'] = 0
            logger.info(f"🔄 IMAGE TASK {task_id}: RESTARTING CYCLE (continuous mode)")

        if mention_text or mention_jids:
            try:
                _send_text(client, jid_obj, mention_text, mention_jids)
                GLOBAL_STATS['total_msg_sent'] += 1
                time.sleep(1)
            except Exception as e:
                logger.warning(f"IMG TASK mention send: {e}")

        for idx in range(start_idx, total):
            current = active_tasks.get(task_id)
            if not current or current.get('run_id') != run_id: return
            if current.get('status') == 'STOPPED':
                current['resume_index'] = idx
                task_mark_stopped(current); save_tasks_state(force=True); return

            img_path = image_paths[idx]
            sent_ok = False
            for attempt in range(3):
                try:
                    with open(img_path, 'rb') as fh:
                        data = fh.read()
                    if not data:
                        logger.warning(f"IMG TASK {task_id}: empty file {img_path}")
                        break
                    ok = _send_image(client, jid_obj, data, caption)
                    if ok:
                        sent_ok = True
                        GLOBAL_STATS['total_img_sent'] += 1
                        logger.info(f"✅ IMG {idx+1}/{total} SENT to {jid_obj}")
                        break
                    else:
                        logger.warning(f"IMG TASK {task_id} attempt {attempt+1}: send returned False")
                        time.sleep(2)
                except Exception as e:
                    logger.error(f"IMG TASK {task_id} attempt {attempt+1}: {e}")
                    time.sleep(2)

            if not sent_ok:
                time.sleep(4)
                continue

            current['sent'] = idx + 1
            current['resume_index'] = idx + 1
            current['next_message_time'] = time.time() + current['interval']
            save_tasks_state()

            if idx < total - 1:
                time.sleep(current['interval'])

        time.sleep(2)


# ═══════════════════════════════════════════════════════════
# WORKERS
# ═══════════════════════════════════════════════════════════

def heartbeat_worker():
    while True:
        time.sleep(120)
        try:
            with tasks_lock: has = bool(active_tasks)
            if has: save_tasks_state(force=True)
        except Exception: pass


def stopped_task_purge_worker():
    while True:
        time.sleep(30)
        try:
            now = time.time(); to_delete = []
            with tasks_lock:
                for tid, t in list(active_tasks.items()):
                    status = (t.get('status') or '').upper()
                    if status in ('RUNNING', 'QUEUED'): continue
                    if status == 'STOPPED' or status.startswith('ERROR'):
                        stopped_at = t.get('stopped_at') or 0
                        if stopped_at and (now - stopped_at) >= 120:
                            to_delete.append(tid)
            if to_delete:
                with tasks_lock:
                    for tid in to_delete:
                        t = active_tasks.pop(tid, None)
                        if t and t.get('task_kind') == 'IMAGE':
                            try: shutil.rmtree(os.path.join(IMAGETASKS_DIR, tid), ignore_errors=True)
                            except Exception: pass
                save_tasks_state(force=True)
                logger.info(f"🧹 AUTO-DELETED {len(to_delete)} STOPPED TASKS")
        except Exception as e:
            logger.error(f"PURGE ERROR: {e}")


def auto_cleanup_worker():
    while True:
        time.sleep(300)
        try:
            now = time.time()
            logger.info("🧹 [5-MIN RESET] Cleaning memory & disk...")
            for _ in range(5): gc.collect()
            with PHOTO_CACHE_LOCK: PHOTO_CACHE.clear()
            if os.path.exists(app.config['UPLOAD_FOLDER']):
                for f in os.listdir(app.config['UPLOAD_FOLDER']):
                    fp = os.path.join(app.config['UPLOAD_FOLDER'], f)
                    try:
                        if os.path.isfile(fp): os.remove(fp)
                    except Exception: pass
            with sessions_lock:
                live_dbs = set()
                for _n, _s in sessions.items():
                    _dp = _s.get('db_path')
                    if _dp: live_dbs.add(os.path.abspath(_dp))
            if os.path.isdir('sessions'):
                for f in os.listdir('sessions'):
                    fp = os.path.join('sessions', f)
                    base = f.replace('.sqlite', '').replace('-journal', '').replace('-wal', '').replace('-shm', '')
                    if base not in SESSION_OWNERS and os.path.abspath(fp) not in live_dbs:
                        try:
                            if now - os.stat(fp).st_mtime > 600: os.remove(fp)
                        except Exception: pass
            with sessions_lock: live_sessions = set(sessions.keys())
            with tasks_lock:
                rm_ids = [tid for tid, t in active_tasks.items() if t.get('session') not in live_sessions and t.get('status') not in ('RUNNING', 'QUEUED')]
                for tid in rm_ids: active_tasks.pop(tid, None)
            if rm_ids: save_tasks_state(force=True)
            try:
                with tasks_lock:
                    live_img_tids = set(tid for tid, t in active_tasks.items() if t.get('task_kind') == 'IMAGE')
                if os.path.isdir(IMAGETASKS_DIR):
                    for d in os.listdir(IMAGETASKS_DIR):
                        if d not in live_img_tids:
                            try: shutil.rmtree(os.path.join(IMAGETASKS_DIR, d), ignore_errors=True)
                            except Exception: pass
            except Exception: pass
            try:
                if os.path.isdir(WA_IMG_SEND_DIR):
                    for f in os.listdir(WA_IMG_SEND_DIR):
                        fp = os.path.join(WA_IMG_SEND_DIR, f)
                        try:
                            if os.path.isfile(fp) and (now - os.stat(fp).st_mtime) > 300:
                                os.remove(fp)
                        except Exception: pass
            except Exception: pass
            for _ in range(5): gc.collect()
            logger.info("✅ [5-MIN RESET] Cleanup complete.")
        except Exception as e:
            logger.error(f"CLEANUP ERROR: {e}")


# ═══════════════════════════════════════════════════════════
# LOGIN TEMPLATE (WITHOUT VERIFICATION CODE — INSTANT REGISTRATION)
# ═══════════════════════════════════════════════════════════
LOGIN_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>ARJUN THAKUR — WhatsApp Server Login</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
<style>
* { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
body {
  min-height: 100vh; margin: 0; display: flex; align-items: center; justify-content: center;
  background: #FFF8DC; font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  padding: 20px; position: relative; overflow: hidden; text-transform: uppercase;
}
body::before {
  content: ""; position: absolute; inset: -10%; z-index: 0;
  background: radial-gradient(500px 400px at 20% 20%, rgba(0,100,0,.12), transparent 60%),
              radial-gradient(600px 500px at 80% 30%, rgba(0,0,139,.11), transparent 60%),
              radial-gradient(550px 550px at 50% 90%, rgba(139,0,0,.10), transparent 60%),
              radial-gradient(500px 400px at 70% 80%, rgba(139,0,139,.08), transparent 60%);
  filter: blur(70px); animation: bgPulse 14s ease-in-out infinite alternate;
}
@keyframes bgPulse { 0% { opacity:.8; transform: scale(1); } 100% { opacity:1; transform: scale(1.08); } }
.login-card {
  position: relative; z-index: 1; width: 100%; max-width: 420px;
  background: #FFFDF0; backdrop-filter: blur(20px);
  border: 4px solid #00008B; border-radius: 26px;
  overflow: hidden; box-shadow: 0 30px 70px rgba(0,0,0,.25);
  animation: cardIn 0.7s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}
@keyframes cardIn { from { opacity: 0; transform: translateY(30px) scale(0.95); } to { opacity: 1; transform: none; } }
.login-banner { width: 100%; display: block; margin: 0; padding: 0; border-bottom: 4px solid #006400; background: #FFF8DC; line-height: 0; }
.login-banner img { width: 100%; height: auto; display: block; max-height: 220px; object-fit: cover; }
.login-content { padding: 28px 32px 36px; }
.login-title {
  text-align: center; font-weight: 900; font-size: 26px; letter-spacing: 3px;
  text-transform: uppercase; margin-bottom: 8px; line-height: 1.3;
  color: #8B0000;
  filter: drop-shadow(0 0 12px rgba(139,0,0,.2));
}
.login-sub {
  text-align: center; font-size: 10px; margin-bottom: 24px;
  text-transform: uppercase; letter-spacing: 3px; font-weight: 800;
  color: #006400;
}
.field-label {
  display: block; font-size: 10px; font-weight: 900;
  color: #00008B; letter-spacing: 1.5px;
  margin-bottom: 6px; margin-left: 4px;
}
.form-control { background: #FFFDF0 !important; border: 3px solid #006400 !important; color: #0d2b14 !important; border-radius: 14px; padding: 13px 14px 13px 44px; font-size: 13.5px; font-weight: 500; transition: all .25s ease; text-transform: uppercase; }
.form-control::placeholder { text-transform: uppercase; color: #5a7a5e !important; }
.form-control:focus { background: #FFF8DC !important; border-color: #8B0000 !important; box-shadow: 0 0 0 4px rgba(139,0,0,.12); }
.input-ico { position: relative; margin-bottom: 14px; }
.input-ico i { position: absolute; left: 15px; top: 50%; transform: translateY(-50%); color: #5a7a5e; }
.btn-neon { width: 100%; border: 3px solid #006400; border-radius: 999px; padding: 14px; background: #006400; color: #fff; font-weight: 800; letter-spacing: 1.2px; text-transform: uppercase; font-size: 13px; transition: all .28s ease; margin-top: 8px; box-shadow: 0 8px 20px rgba(0,100,0,.30); }
.btn-neon:hover { transform: translateY(-2px); box-shadow: 0 12px 28px rgba(0,100,0,.45); background: #008000; }
.btn-neon:disabled { opacity: 0.65; }
.switch-link { text-align: center; margin-top: 20px; font-size: 12.5px; color: #5a7a5e; font-weight: 600; text-transform: uppercase; }
.switch-link a { color: #8B0000; font-weight: 800; cursor: pointer; text-decoration: none; text-transform: uppercase; letter-spacing: .5px; }
.err-box { display: none; background: #FFEBEE; border: 3px solid #8B0000; color: #8B0000; border-radius: 12px; padding: 11px 15px; font-size: 12px; font-weight: 700; margin-bottom: 14px; text-transform: uppercase; text-align: center; letter-spacing: .3px; }
</style></head><body>
<div class="login-card">
  <div class="login-banner"><img src="__BANNER_URL__" alt="Banner"></div>
  <div class="login-content">
    <div class="login-title">ARJUN THAKUR SERVER</div>
    <div class="login-sub">🔥 ARJUN THAKUR 🔥 · MULTI-USER PANEL</div>
    <div class="err-box" id="errBox"></div>
    <form id="loginForm">
      <label class="field-label"><i class="fas fa-user me-1"></i> USERNAME</label>
      <div class="input-ico"><i class="fas fa-user"></i><input type="text" class="form-control" id="l_user" placeholder="ENTER USERNAME" autocomplete="username"></div>
      <label class="field-label"><i class="fas fa-lock me-1"></i> PASSWORD</label>
      <div class="input-ico"><i class="fas fa-lock"></i><input type="password" class="form-control" id="l_pass" placeholder="ENTER PASSWORD" autocomplete="current-password"></div>
      <button type="submit" class="btn-neon" id="loginBtn"><i class="fas fa-sign-in-alt me-2"></i>Login</button>
    </form>
    <form id="regForm" style="display:none;">
      <label class="field-label"><i class="fas fa-user-plus me-1"></i> NEW USERNAME</label>
      <div class="input-ico"><i class="fas fa-user-plus"></i><input type="text" class="form-control" id="r_user" placeholder="ENTER NEW USERNAME"></div>
      <label class="field-label"><i class="fas fa-lock me-1"></i> PASSWORD (MIN 4 CHARS)</label>
      <div class="input-ico"><i class="fas fa-lock"></i><input type="password" class="form-control" id="r_pass" placeholder="ENTER PASSWORD"></div>
      <label class="field-label"><i class="fas fa-lock me-1"></i> REPEAT PASSWORD</label>
      <div class="input-ico"><i class="fas fa-lock"></i><input type="password" class="form-control" id="r_pass2" placeholder="REPEAT PASSWORD"></div>
      <button type="submit" class="btn-neon" id="regBtn"><i class="fas fa-user-plus me-2"></i>Create Account</button>
    </form>
    <div class="switch-link" id="swLogin">New here? <a onclick="showReg()">Create Account</a></div>
    <div class="switch-link" id="swReg" style="display:none;">Have an account? <a onclick="showLogin()">Login</a></div>
  </div>
</div>
<script>
function showErr(m) { $('#errBox').text(m).fadeIn(200); }
function showReg() { $('#loginForm').hide(); $('#swLogin').hide(); $('#regForm').show(); $('#swReg').show(); $('#errBox').hide(); }
function showLogin() { $('#regForm').hide(); $('#swReg').hide(); $('#loginForm').show(); $('#swLogin').show(); $('#errBox').hide(); }
$('#loginForm').submit(function(e) {
  e.preventDefault(); let b = $('#loginBtn'); b.prop('disabled', true).text('LOGGING IN...');
  $.post('/api/login', { username: $('#l_user').val().trim(), password: $('#l_pass').val() })
    .done(function() { location.reload(); })
    .fail(function(x) { showErr((x.responseJSON && x.responseJSON.error) || 'LOGIN FAILED'); b.prop('disabled', false).html('<i class="fas fa-sign-in-alt me-2"></i>Login'); });
});
$('#regForm').submit(function(e) {
  e.preventDefault();
  if ($('#r_pass').val() !== $('#r_pass2').val()) { showErr('PASSWORDS DO NOT MATCH'); return; }
  let b = $('#regBtn'); b.prop('disabled', true).text('CREATING...');
  $.post('/api/register', { username: $('#r_user').val().trim(), password: $('#r_pass').val() })
    .done(function(r) {
        if (r.status === 'success') {
            showErr('ACCOUNT CREATED! LOGGING IN...');
            setTimeout(() => location.reload(), 1000);
        } else {
            location.reload();
        }
    })
    .fail(function(x) { showErr((x.responseJSON && x.responseJSON.error) || 'REGISTER FAILED'); b.prop('disabled', false).html('<i class="fas fa-user-plus me-2"></i>Create Account'); });
});
</script></body></html>"""
LOGIN_TEMPLATE = LOGIN_TEMPLATE.replace('__BANNER_URL__', BANNER_URL)


# ═══════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════

@app.before_request
def require_login():
    if request.endpoint in ('login', 'register', 'verify_register', 'index', 'static', None): return
    if not session.get('user'):
        return jsonify({'error': 'UNAUTHORIZED', 'login': True}), 401


@app.route('/api/login', methods=['POST'])
def login():
    u = request.form.get('username', '').strip()
    pw = request.form.get('password', '')
    info = USERS.get(u)
    if not info or hash_pass(info['salt'], pw) != info['pass']:
        return jsonify({'error': 'WRONG USERNAME OR PASSWORD'}), 401
    if u in BLOCKED_USERS:
        return jsonify({'error': 'ACCOUNT BLOCKED BY ADMIN'}), 403
    session['user'] = u; session.permanent = True
    logger.info(f"🔓 LOGIN: {u}")
    return jsonify({'status': 'ok', 'user': u})


@app.route('/api/register', methods=['POST'])
def register():
    u = request.form.get('username', '').strip()
    pw = request.form.get('password', '')
    if not u or len(pw) < 4:
        return jsonify({'error': 'USERNAME REQUIRED & PASSWORD MIN 4 CHARS'}), 400
    if u in USERS:
        return jsonify({'error': 'USERNAME ALREADY EXISTS'}), 400

    # Instant registration — no verification code
    salt = secrets.token_hex(8)
    USERS[u] = {'salt': salt, 'pass': hash_pass(salt, pw), 'created': time.time()}
    save_users()
    session['user'] = u; session.permanent = True
    logger.info(f"✅ USER REGISTERED (INSTANT): {u}")
    return jsonify({'status': 'success', 'user': u})


@app.route('/api/verify_register', methods=['POST'])
def verify_register():
    # Kept for compatibility, but not used
    return jsonify({'error': 'VERIFICATION DISABLED'}), 400


@app.route('/api/logout', methods=['POST'])
def logout():
    u = session.get('user'); session.clear()
    logger.info(f"🚪 LOGOUT: {u}")
    return jsonify({'status': 'ok'})


@app.route('/api/me')
def me():
    u = session.get('user')
    return jsonify({'user': u, 'user_display': display_name_for(u)})


@app.route('/api/admin/switch_user', methods=['POST'])
def admin_switch_user():
    if not _is_admin(): return jsonify({'error': 'ACCESS DENIED'}), 403
    username = request.form.get('username', '').strip()
    if username not in USERS: return jsonify({'error': 'USER NOT FOUND'}), 404
    session['user'] = username
    logger.info(f"👑 ADMIN SWITCHED TO USER: {username}")
    return jsonify({'status': 'success', 'user': username})


@app.route('/api/dashboard_stats')
def dashboard_stats():
    user = session.get('user')
    if not user: return jsonify({'error': 'UNAUTHORIZED'}), 401
    st = get_server_stats()
    user_msg_sent = 0
    with tasks_lock:
        for tid, t in active_tasks.items():
            if t.get('owner') == user: user_msg_sent += t.get('sent', 0)
    return jsonify({
        'user': user, 'user_display': display_name_for(user),
        'cpu_percent': st['cpu_percent'],
        'sys_cpu_percent': st['sys_cpu_percent'],
        'proc_mem_used_mb': st['proc_mem_used_mb'],
        'proc_mem_total_mb': st['proc_mem_total_mb'],
        'total_msg_sent': GLOBAL_STATS['total_msg_sent'] + user_msg_sent,
        'total_img_sent': GLOBAL_STATS['total_img_sent'],
        'uptime_str': st['uptime_str'], 'disk_used_mb': st['disk_used_mb'],
        'disk_total_mb': st['disk_total_mb'], 'sys_mem_used_gb': st['sys_mem_used_gb'],
        'sys_mem_total_gb': st['sys_mem_total_gb'],
        'net_in_kbps': st['net_in_kbps']
    })


@app.route('/')
def index():
    if not session.get('user'): return render_template_string(LOGIN_TEMPLATE)
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/init_auth', methods=['POST'])
def init_auth():
    try:
        if not NEONIZE_OK:
            return jsonify({'error': f'NEONIZE ERROR: {NEONIZE_ERROR}'}), 500
        name = request.form.get('session_name', '').strip()
        phone = request.form.get('whatsapp_number', '').strip()
        method = request.form.get('login_method', 'PAIRING CODE')
        if not name or not phone:
            return jsonify({'error': 'NAME & PHONE REQUIRED'}), 400
        existing_owner = SESSION_OWNERS.get(name)
        if existing_owner and existing_owner != session.get('user'):
            return jsonify({'error': 'SESSION NAME ALREADY USED BY ANOTHER USER'}), 400
        with sessions_lock:
            if name in sessions and sessions[name].get('status') == 'CONNECTED':
                return jsonify({'error': 'SESSION ALREADY CONNECTED'}), 400
            sessions[name] = {
                "client": None, "status": "INITIALIZING",
                "qr": "", "code": "",
                "phone": _digits(phone), "method": method,
                "db_path": os.path.join("sessions", f"{name}.sqlite"),
                "owner": session.get('user'), "created_at": time.time(),
            }
        threading.Thread(target=session_worker, args=(name, phone, method), daemon=True).start()
        return jsonify({'status': 'processing'})
    except Exception as e:
        return jsonify({'error': f'SERVER ERROR: {str(e)}'}), 500


@app.route('/api/get_auth_status/<session_name>', methods=['GET'])
def get_auth_status(session_name):
    with sessions_lock:
        s = sessions.get(session_name)
        if not s or s.get('owner') != session.get('user'):
            return jsonify({'status': 'NOT_FOUND'})
        return jsonify({'status': s.get('status'), 'qr_img': s.get('qr'), 'code': s.get('code')})


def _fmt_phone(p):
    d = _digits(p); return ('+' + d) if d else ''


@app.route('/api/get_all_sessions', methods=['GET'])
def get_all_sessions():
    user = session.get('user')
    with sessions_lock:
        out = {n: {'status': s['status'], 'phone': _fmt_phone(s.get('phone', '')),
                   'wa_name': s.get('wa_name', ''), 'wa_photo': ''}
               for n, s in sessions.items() if (s.get('owner') or SESSION_OWNERS.get(n)) == user}
    return jsonify(out)


@app.route('/api/session_manage_stats', methods=['GET'])
def session_manage_stats():
    user = session.get('user')
    result = []
    with sessions_lock:
        my_sessions = {n: dict(s) for n, s in sessions.items() if (s.get('owner') or SESSION_OWNERS.get(n)) == user}
    for name, s in my_sessions.items():
        meta = SESSION_META.get(name, {})
        base = {'name': name, 'status': s.get('status', 'UNKNOWN'),
                'phone': _fmt_phone(s.get('phone') or meta.get('phone', '')),
                'wa_name': s.get('wa_name') or meta.get('wa_name', ''),
                'wa_photo': s.get('wa_photo') or meta.get('wa_photo', '')}
        session_tasks = []
        with tasks_lock:
            for tid, t in active_tasks.items():
                if t.get('session') == name:
                    status = (t.get('status') or '').upper()
                    if status not in ('RUNNING', 'QUEUED'):
                        continue
                    session_tasks.append({
                        'task_id': tid, 'status': status,
                        'uptime': task_uptime(t), 'target': t.get('target', ''),
                        'target_name': t.get('target_name', ''), 'target_type': t.get('target_type', ''),
                        'file_name': t.get('file_name', ''), 'hater_name': t.get('hater_name', ''),
                        'last_hater_name': t.get('last_hater_name', ''),
                        'interval': t.get('interval', 5), 'mention_option': t.get('mention_option', 'NONE'),
                        'custom_mentions': t.get('custom_mentions', []),
                        'show_mention_name': t.get('show_mention_name', True),
                        'next_message_time': t.get('next_message_time', 0),
                        'task_kind': t.get('task_kind', 'MESSAGE'),
                        'image_count': t.get('image_count', 0),
                        'sent': t.get('sent', 0), 'total': t.get('total', 0),
                    })
        if session_tasks:
            session_tasks.sort(key=lambda x: 0 if x['status'] in ('RUNNING', 'QUEUED') else 1)
            for tk in session_tasks:
                entry = dict(base)
                entry.update({
                    'task_id': tk['task_id'], 'task_status': tk['status'],
                    'uptime_str': format_uptime_long(tk['uptime']),
                    'target': tk['target'], 'target_name': tk['target_name'],
                    'target_type': tk['target_type'], 'file_name': tk['file_name'],
                    'hater_name': tk['hater_name'], 'last_hater_name': tk['last_hater_name'],
                    'interval': tk['interval'], 'mention_option': tk['mention_option'],
                    'custom_mentions': tk['custom_mentions'],
                    'show_mention_name': tk['show_mention_name'],
                    'next_message_time': tk['next_message_time'],
                    'task_kind': tk['task_kind'], 'image_count': tk['image_count'],
                    'sent': tk['sent'], 'total': tk['total'],
                })
                result.append(entry)
    return jsonify(result)


def _is_admin(): return session.get('user') == ADMIN_USERNAME


@app.route('/api/admin/active_sessions', methods=['GET'])
def admin_active_sessions():
    if not _is_admin(): return jsonify({'error': 'ACCESS DENIED'}), 403
    result = []
    with sessions_lock:
        all_sessions = {n: dict(s) for n, s in sessions.items()}
    for name, s in all_sessions.items():
        meta = SESSION_META.get(name, {})
        primary_task = {}; task_count = 0
        with tasks_lock:
            for tid, t in active_tasks.items():
                if t.get('session') == name:
                    status = (t.get('status') or '').upper()
                    if status not in ('RUNNING', 'QUEUED'):
                        continue
                    task_count += 1
                    if not primary_task:
                        primary_task = {'file_name': t.get('file_name', ''),
                                        'uptime_str': format_uptime_long(task_uptime(t)),
                                        'status': status}
        result.append({
            'name': name, 'status': s.get('status', 'UNKNOWN'),
            'phone': _fmt_phone(s.get('phone') or meta.get('phone', '')),
            'wa_name': s.get('wa_name') or meta.get('wa_name', ''),
            'wa_photo': s.get('wa_photo') or meta.get('wa_photo', ''),
            'owner': s.get('owner') or SESSION_OWNERS.get(name) or 'unknown',
            'task_count': task_count, 'primary_task': primary_task,
        })
    result.sort(key=lambda x: (0 if x['status'] == 'CONNECTED' else 1, -x['task_count']))
    return jsonify(result)


@app.route('/api/admin/registered_users', methods=['GET'])
def admin_registered_users():
    if not _is_admin(): return jsonify({'error': 'ACCESS DENIED'}), 403
    result = []
    for uname, info in USERS.items():
        created = info.get('created', 0)
        try: created_str = time.strftime('%d %b %Y', time.localtime(created)) if created else '—'
        except Exception: created_str = '—'
        sc = 0
        with sessions_lock:
            for n, s in sessions.items():
                if (s.get('owner') or SESSION_OWNERS.get(n)) == uname: sc += 1
        tc = 0
        with tasks_lock:
            for tid, t in active_tasks.items():
                if t.get('owner') == uname: tc += 1
        result.append({'username': uname, 'display_name': display_name_for(uname),
                       'created': created, 'created_str': created_str,
                       'is_admin': (uname == ADMIN_USERNAME),
                       'is_blocked': uname in BLOCKED_USERS,
                       'session_count': sc, 'task_count': tc})
    result.sort(key=lambda x: (0 if x['is_admin'] else 1, x['username'].lower()))
    return jsonify(result)


@app.route('/api/admin/delete_user', methods=['POST'])
def admin_delete_user():
    if not _is_admin(): return jsonify({'error': 'ACCESS DENIED'}), 403
    username = request.form.get('username', '').strip()
    if not username: return jsonify({'error': 'USERNAME REQUIRED'}), 400
    if username == ADMIN_USERNAME: return jsonify({'error': 'CANNOT DELETE ADMIN'}), 400
    if username not in USERS: return jsonify({'error': 'USER NOT FOUND'}), 404
    USERS.pop(username, None); save_users()
    with sessions_lock:
        user_sessions = [n for n, s in sessions.items() if (s.get('owner') or SESSION_OWNERS.get(n)) == username]
        for s_name in user_sessions:
            sessions.pop(s_name, None); SESSION_OWNERS.pop(s_name, None)
            with META_LOCK: SESSION_META.pop(s_name, None)
            _save_meta()
            db_path = os.path.join("sessions", f"{s_name}.sqlite")
            for p in [db_path, db_path + "-journal", db_path + "-wal", db_path + "-shm"]:
                try:
                    if os.path.isfile(p): os.remove(p)
                except Exception: pass
        save_owner_map(SESSION_OWNERS)
    with tasks_lock:
        to_del = [tid for tid, t in active_tasks.items() if t.get('owner') == username]
        for tid in to_del:
            t = active_tasks.pop(tid, None)
            if t and t.get('task_kind') == 'IMAGE':
                try: shutil.rmtree(os.path.join(IMAGETASKS_DIR, tid), ignore_errors=True)
                except Exception: pass
    save_tasks_state(force=True)
    logger.info(f"👑 ADMIN DELETED USER: {username}")
    return jsonify({'status': 'success'})


def _task_access_ok(t, user):
    if user == ADMIN_USERNAME: return True
    so = SESSION_OWNERS.get(t.get('session', ''))
    with sessions_lock:
        ss = sessions.get(t.get('session', ''), {})
        if ss: so = ss.get('owner') or so
    return t.get('owner') == user or so == user


@app.route('/api/delete_single_task', methods=['POST'])
def delete_single_task():
    user = session.get('user')
    task_id = request.form.get('task_id', '').strip()
    if not task_id: return jsonify({'error': 'TASK ID REQUIRED'}), 400
    with tasks_lock:
        if task_id not in active_tasks: return jsonify({'error': 'TASK NOT FOUND'}), 404
        t = active_tasks[task_id]
        if not _task_access_ok(t, user): return jsonify({'error': 'ACCESS DENIED'}), 403
        t['status'] = 'STOPPED'; t['run_id'] = None
        del active_tasks[task_id]
    save_tasks_state(force=True)
    try: shutil.rmtree(os.path.join(IMAGETASKS_DIR, task_id), ignore_errors=True)
    except Exception: pass
    return jsonify({'status': 'success'})


@app.route('/api/refresh_task', methods=['POST'])
def refresh_task():
    user = session.get('user')
    task_id = request.form.get('task_id', '').strip()
    if not task_id: return jsonify({'error': 'TASK ID REQUIRED'}), 400
    with tasks_lock:
        if task_id not in active_tasks: return jsonify({'error': 'TASK NOT FOUND'}), 404
        t = active_tasks[task_id]
        if not _task_access_ok(t, user): return jsonify({'error': 'ACCESS DENIED'}), 403
        t['run_id'] = None; t['status'] = 'QUEUED'
    save_tasks_state(force=True)
    start_task_runner(task_id)
    return jsonify({'status': 'success'})


@app.route('/api/get_task_full/<task_id>', methods=['GET'])
def get_task_full(task_id):
    user = session.get('user')
    with tasks_lock:
        t = active_tasks.get(task_id)
        if not t: return jsonify({'error': 'TASK NOT FOUND'}), 404
        if not _task_access_ok(t, user): return jsonify({'error': 'ACCESS DENIED'}), 403
        return jsonify({'task_id': task_id, 'session': t.get('session'),
                        'target': t.get('target', ''), 'target_name': t.get('target_name', ''),
                        'target_type': t.get('target_type', 'NUMBER'), 'status': t.get('status', ''),
                        'file_name': t.get('file_name', ''), 'hater_name': t.get('hater_name', ''),
                        'last_hater_name': t.get('last_hater_name', ''),
                        'interval': t.get('interval', 5),
                        'mention_option': t.get('mention_option', 'NONE'),
                        'custom_mentions': t.get('custom_mentions', []),
                        'show_mention_name': t.get('show_mention_name', True),
                        'task_kind': t.get('task_kind', 'MESSAGE'),
                        'image_count': t.get('image_count', 0)})


@app.route('/api/update_task_full', methods=['POST'])
def update_task_full():
    task_id = request.form.get('task_id', '').strip()
    if not task_id: return jsonify({'error': 'TASK ID MISSING'}), 400
    user = session.get('user')
    with tasks_lock:
        if task_id not in active_tasks: return jsonify({'error': 'TASK NOT FOUND'}), 404
        t = active_tasks[task_id]
        if not _task_access_ok(t, user): return jsonify({'error': 'ACCESS DENIED'}), 403
        new_target = request.form.get('new_target', '').strip()
        new_type = request.form.get('target_type', t.get('target_type', 'NUMBER'))
        if new_target:
            clean_target = new_target.replace('User: ', '').strip()
            if new_type == 'NUMBER':
                digits_only = _digits(clean_target)
                if digits_only: clean_target = digits_only
            t['target'] = clean_target; t['target_type'] = new_type
        nm = request.form.get('target_name', '').strip()
        t['target_name'] = nm if (new_type == 'GROUP' and nm) else t['target']
        mo = request.form.get('mention_option')
        if mo in ('NONE', 'ALL', 'CUSTOM'):
            t['mention_option'] = mo if new_type == 'GROUP' else 'NONE'
        smn = request.form.get('show_mention_name')
        if smn is not None:
            t['show_mention_name'] = (smn == '1' or str(smn).lower() == 'true')
        cm_raw = request.form.get('custom_mentions', '[]')
        try: t['custom_mentions'] = json.loads(cm_raw)
        except Exception: t['custom_mentions'] = []
        if request.form.get('hater_name') is not None:
            t['hater_name'] = request.form.get('hater_name', '').strip()
        if request.form.get('last_hater_name') is not None:
            t['last_hater_name'] = request.form.get('last_hater_name', '').strip()
        try: t['interval'] = max(1, int(request.form.get('speed_seconds', t['interval'])))
        except Exception: pass
        file = request.files.get('message_file')
        if file and file.filename and t.get('task_kind', 'MESSAGE') == 'MESSAGE':
            content = file.read().decode('utf-8', errors='ignore')
            messages = [l.strip() for l in content.splitlines() if l.strip()]
            if messages:
                t['messages'] = messages; t['file_name'] = file.filename
                t['total'] = len(messages); t['resume_index'] = 0; t['sent'] = 0
        t['status'] = 'QUEUED'; t['stopped_at'] = 0
        t['next_message_time'] = time.time() + t.get('interval', 5)
    save_tasks_state(force=True)
    start_task_runner(task_id)
    return jsonify({'status': 'success'})


@app.route('/api/get_groups/<session_name>', methods=['GET'])
def get_groups(session_name):
    user = session.get('user')
    with sessions_lock:
        s = sessions.get(session_name)
        if not s or s['status'] != 'CONNECTED' or not s.get('client'): return jsonify([])
        owner = s.get('owner') or SESSION_OWNERS.get(session_name)
        if owner != user and user != ADMIN_USERNAME: return jsonify([])
        client = s['client']
    try:
        raw = client.get_joined_groups(); out = []
        for g in raw:
            try:
                u = getattr(g.JID, 'User', ''); sv = getattr(g.JID, 'Server', '')
                jid = f"{u}@{sv}" if u and sv else str(g.JID).replace('User: ', '').strip()
                name = jid
                if hasattr(g, 'GroupName') and g.GroupName:
                    name = g.GroupName.Name if hasattr(g.GroupName, 'Name') else str(g.GroupName)
                member_count = 0; group_pic = ""
                try:
                    jid_obj = build_jid(u, sv); gi = client.get_group_info(jid_obj)
                    if hasattr(gi, 'Participants'): member_count = len(gi.Participants)
                    group_pic = get_profile_pic(client, jid_obj, download=False)
                except Exception: pass
                if not group_pic:
                    group_pic = f"https://ui-avatars.com/api/?name={quote(name)}&background=006400&color=fff&bold=true"
                out.append({'id': jid, 'name': name, 'members': member_count, 'photo': group_pic})
            except Exception as e:
                logger.warning(f"Error parsing group: {e}")
        with sessions_lock:
            if session_name in sessions: sessions[session_name]['groups_count'] = len(out)
        return jsonify(out)
    except Exception as e:
        logger.error(f"GET_GROUPS ERROR: {e}"); return jsonify([])


@app.route('/api/get_group_members/<session_name>/<path:group_id>', methods=['GET'])
def get_group_members(session_name, group_id):
    user = session.get('user')
    with sessions_lock:
        s = sessions.get(session_name)
        if not s or s['status'] != 'CONNECTED' or not s.get('client'):
            return jsonify({'error': 'SESSION NOT CONNECTED'})
        owner = s.get('owner') or SESSION_OWNERS.get(session_name)
        if owner != user and user != ADMIN_USERNAME:
            return jsonify({'error': 'ACCESS DENIED'})
        client = s['client']
    if '@' in group_id: g_user, g_server = group_id.split('@', 1)
    else: g_user, g_server = group_id, 'g.us'
    result = {}
    def _fetch_members():
        try:
            jid_obj = build_jid(g_user, g_server); gi = client.get_group_info(jid_obj)
            members = []; seen = set()
            for p in (getattr(gi, 'Participants', None) or []):
                u, sv, phone, dname = _participant_ids(p)
                if not u: continue
                key = f"{u}@{sv}"
                if key in seen: continue
                seen.add(key)
                members.append({'jid': key, 'number': phone or u, 'lookup': u,
                                'name': dname, 'photo': '', 'checked': False})
            try:
                cmap = {}
                for c in client.get_all_contacts():
                    cu = contact_user(c); cn = contact_name(c)
                    if cu and cn: cmap[cu] = cn
                for m in members:
                    if not m['name']:
                        m['name'] = cmap.get(m['number']) or cmap.get(m['lookup']) or ''
            except Exception: pass
            now = time.time()
            with PHOTO_CACHE_LOCK:
                for m in members:
                    c = PHOTO_CACHE.get((session_name, m['number']))
                    if c and now - c.get('ts', 0) < PHOTO_CACHE_TTL:
                        if c.get('photo'): m['photo'] = c['photo']
                        if c.get('name') and not m['name']: m['name'] = c['name']
                        m['checked'] = True
            result['members'] = members
        except Exception as e: result['error'] = str(e)
    t = threading.Thread(target=_fetch_members, daemon=True)
    t.start(); t.join(timeout=35)
    if t.is_alive(): return jsonify({'error': 'FETCH TIMEOUT — PLEASE RETRY'})
    if 'error' in result: return jsonify({'error': result['error']})
    return jsonify(result.get('members', []))


@app.route('/api/get_member_photo/<session_name>/<number>', methods=['GET'])
def get_member_photo(session_name, number):
    user = session.get('user')
    with sessions_lock:
        s = sessions.get(session_name)
        if not s or not s.get('client'): return jsonify({'photo': '', 'name': ''})
        owner = s.get('owner') or SESSION_OWNERS.get(session_name)
        if owner != user and user != ADMIN_USERNAME: return jsonify({'photo': '', 'name': ''})
        client = s['client']
    clean_num = _digits(number); cache_key = (session_name, clean_num)
    with PHOTO_CACHE_LOCK:
        c = PHOTO_CACHE.get(cache_key)
        if c and time.time() - c.get('ts', 0) < PHOTO_CACHE_TTL:
            return jsonify({'photo': c.get('photo', ''), 'name': c.get('name', '')})
    jid_q = request.args.get('jid', '').strip(); photo_result = {}
    def _fetch_photo():
        try:
            targets = [('s.whatsapp.net', clean_num)]
            if jid_q:
                u, sv = _parse_jid_str(jid_q)
                if u and (sv, u) not in [(a, b) for a, b in targets]:
                    targets.append((sv, u))
            photo = ''
            for sv, u in targets:
                if photo: break
                try: photo = get_profile_pic(client, build_jid(u, sv), download=True)
                except Exception: pass
            photo_result['photo'] = photo
            name = ''
            for sv, u in targets:
                if name: break
                try: m_jid = build_jid(u, sv)
                except Exception: continue
                for mname in ('get_contact', 'get_user_info'):
                    if name: break
                    if hasattr(client, mname):
                        try:
                            info = getattr(client, mname)(m_jid)
                            if isinstance(info, dict):
                                name = (info.get('FullName') or info.get('PushName') or info.get('Name') or '').strip()
                            else:
                                try:
                                    if not hasattr(info, 'FullName') and hasattr(info, '__iter__'):
                                        info = list(info)[0]
                                except Exception: pass
                                name = contact_name(info) or _name_from_obj(info)
                        except Exception: pass
            photo_result['name'] = name
        except Exception:
            photo_result.setdefault('photo', '')
    t = threading.Thread(target=_fetch_photo, daemon=True)
    t.start(); t.join(timeout=10)
    if not t.is_alive():
        with PHOTO_CACHE_LOCK:
            PHOTO_CACHE[cache_key] = {'photo': photo_result.get('photo', ''),
                                       'name': photo_result.get('name', ''), 'ts': time.time()}
    return jsonify({'photo': photo_result.get('photo', ''), 'name': photo_result.get('name', '')})


@app.route('/api/cleanup_session/<session_name>', methods=['POST'])
def cleanup_session(session_name):
    user = session.get('user')
    with sessions_lock:
        _s = sessions.get(session_name)
        owner = (_s.get('owner') or SESSION_OWNERS.get(session_name)) if _s else None
        if owner != user and user != ADMIN_USERNAME:
            return jsonify({'error': 'ACCESS DENIED'}), 403
        s = sessions.pop(session_name, None)
        SESSION_OWNERS.pop(session_name, None)
    save_owner_map(SESSION_OWNERS)
    with META_LOCK: SESSION_META.pop(session_name, None)
    _save_meta()
    with tasks_lock:
        task_ids_to_clean = []
        for tid in list(active_tasks.keys()):
            if active_tasks[tid].get('session') == session_name:
                active_tasks[tid]['status'] = 'STOPPED'
                task_mark_stopped(active_tasks[tid])
                task_ids_to_clean.append(tid)
    save_tasks_state(force=True)
    for tid in task_ids_to_clean:
        try: shutil.rmtree(os.path.join(IMAGETASKS_DIR, tid), ignore_errors=True)
        except Exception: pass
    if s:
        db_path = s.get('db_path') or os.path.join("sessions", f"{session_name}.sqlite")
        for p in [db_path, db_path + "-journal", db_path + "-wal", db_path + "-shm"]:
            try:
                if os.path.isfile(p): os.remove(p)
                elif os.path.isdir(p): shutil.rmtree(p, ignore_errors=True)
            except Exception: pass
    gc.collect()
    return jsonify({'status': 'success'})


@app.route('/api/start_task', methods=['POST'])
def start_task():
    session_name = request.form.get('convo_session')
    target_type = request.form.get('target_type', 'NUMBER')
    if target_type == 'GROUP':
        target = request.form.get('selected_group_id')
        target_name = request.form.get('selected_group_name', 'GROUP')
    else:
        target = request.form.get('target_number'); target_name = target
    if target:
        target = target.replace('User: ', '').strip()
        if target_type == 'NUMBER':
            only_digits = _digits(target)
            if only_digits: target = only_digits
    try: interval = max(1, int(request.form.get('speed_seconds', 5)))
    except Exception: interval = 5
    hater_name = request.form.get('hater_name', '')
    last_hater_name = request.form.get('last_hater_name', '')
    mention_option = request.form.get('mention_option', 'NONE')
    if target_type != 'GROUP': mention_option = 'NONE'
    show_mention_name = request.form.get('show_mention_name', '1') == '1'
    try: custom_mentions = json.loads(request.form.get('custom_mentions', '[]'))
    except Exception: custom_mentions = []
    if not session_name or not target:
        return jsonify({'error': 'SESSION AND TARGET REQUIRED'}), 400
    with sessions_lock:
        s = sessions.get(session_name)
        if not s or s['status'] != 'CONNECTED':
            return jsonify({'error': 'SESSION NOT CONNECTED'}), 400
        if s.get('owner') != session.get('user'):
            return jsonify({'error': 'ACCESS DENIED'}), 403
    file = request.files.get('message_file')
    if not file: return jsonify({'error': 'MESSAGE FILE REQUIRED'}), 400
    file_name = file.filename
    content = file.read().decode('utf-8', errors='ignore')
    messages = [l.strip() for l in content.splitlines() if l.strip()]
    if not messages: return jsonify({'error': 'FILE IS EMPTY'}), 400
    task_id = str(uuid.uuid4())[:8]
    with tasks_lock:
        active_tasks[task_id] = {
            'session': session_name, 'target': target, 'target_name': target_name,
            'target_type': target_type, 'status': 'QUEUED', 'task_kind': 'MESSAGE',
            'messages': messages, 'file_name': file_name,
            'hater_name': hater_name, 'last_hater_name': last_hater_name,
            'interval': interval, 'sent': 0, 'total': len(messages),
            'resume_index': 0, 'start_time': int(time.time()),
            'next_message_time': int(time.time() + interval),
            'mention_option': mention_option, 'custom_mentions': custom_mentions,
            'show_mention_name': show_mention_name, 'owner': session.get('user'),
            'uptime_acc': 0, 'run_since': 0, 'stopped_at': 0,
            'image_paths': [], 'image_count': 0,
        }
    save_tasks_state(force=True)
    start_task_runner(task_id)
    return jsonify({'status': 'success', 'task_id': task_id})


@app.route('/api/user/send_images', methods=['POST'])
def user_send_images():
    user = session.get('user')
    if not user: return jsonify({'error': 'UNAUTHORIZED'}), 401
    session_name = request.form.get('session_name', '').strip()
    target_type = request.form.get('target_type', 'NUMBER')
    target = request.form.get('target', '').strip()
    hater_name = request.form.get('hater_name', '').strip()
    last_hater_name = request.form.get('last_hater_name', '').strip()
    mention_option = request.form.get('mention_option', 'NONE')
    if target_type != 'GROUP': mention_option = 'NONE'
    show_mention_name = request.form.get('show_mention_name', '1') == '1'
    try: custom_mentions = json.loads(request.form.get('custom_mentions', '[]'))
    except Exception: custom_mentions = []
    try: img_delay = max(1, int(request.form.get('speed_seconds', 10)))
    except Exception: img_delay = 10
    files = request.files.getlist('images')
    if not session_name or not target or not files:
        return jsonify({'error': 'SESSION, TARGET & IMAGES REQUIRED'}), 400
    with sessions_lock:
        s = sessions.get(session_name)
        if not s: return jsonify({'error': 'SESSION NOT FOUND'}), 404
        owner = s.get('owner') or SESSION_OWNERS.get(session_name)
        if owner != user: return jsonify({'error': 'ACCESS DENIED'}), 403
        if s.get('status') != 'CONNECTED' or not s.get('client'):
            return jsonify({'error': 'SESSION NOT CONNECTED'}), 400
    if target_type == 'NUMBER':
        clean = _digits(target)
        if not clean: return jsonify({'error': 'INVALID TARGET NUMBER'}), 400
        target = clean
    else:
        target = target.replace('User: ', '').strip()
    task_id = str(uuid.uuid4())[:8]
    task_dir = os.path.join(IMAGETASKS_DIR, task_id)
    os.makedirs(task_dir, exist_ok=True)
    image_paths = []
    for i, f in enumerate(files):
        try:
            data = f.read()
            if not data: continue
            mime = _detect_image_mime(data)
            ext = _mime_to_ext(mime)
            p = os.path.join(task_dir, f"img_{i}{ext}")
            with open(p, 'wb') as out: out.write(data)
            image_paths.append(p)
        except Exception as e:
            logger.error(f"Save image err: {e}")
    if not image_paths:
        shutil.rmtree(task_dir, ignore_errors=True)
        return jsonify({'error': 'NO VALID IMAGES'}), 400
    with tasks_lock:
        active_tasks[task_id] = {
            'session': session_name, 'target': target,
            'target_name': target if target_type == 'NUMBER' else target,
            'target_type': target_type, 'status': 'QUEUED', 'task_kind': 'IMAGE',
            'messages': [], 'image_paths': image_paths, 'image_count': len(image_paths),
            'file_name': f"{len(image_paths)} IMAGES",
            'hater_name': hater_name, 'last_hater_name': last_hater_name,
            'interval': img_delay, 'sent': 0, 'total': len(image_paths),
            'resume_index': 0, 'start_time': int(time.time()),
            'next_message_time': int(time.time() + img_delay),
            'mention_option': mention_option, 'custom_mentions': custom_mentions,
            'show_mention_name': show_mention_name, 'owner': user,
            'uptime_acc': 0, 'run_since': 0, 'stopped_at': 0,
        }
    save_tasks_state(force=True)
    start_task_runner(task_id)
    return jsonify({'status': 'success', 'task_id': task_id, 'sent': len(image_paths)})


# ═══════════════════════════════════════════════════════════
# AUTO-RESTORE
# ═══════════════════════════════════════════════════════════

def auto_restore_sessions():
    session_dir = 'sessions'
    if not os.path.isdir(session_dir): return
    for f in os.listdir(session_dir):
        if f.endswith('.sqlite'):
            name = f[:-7]
            owner = SESSION_OWNERS.get(name)
            if not owner: continue
            meta = SESSION_META.get(name, {})
            with sessions_lock:
                if name in sessions: continue
                sessions[name] = {"client": None, "status": "INITIALIZING",
                                  "qr": "", "code": "", "phone": meta.get('phone', ''),
                                  "method": "PAIRING CODE",
                                  "wa_name": meta.get('wa_name', ''),
                                  "wa_photo": meta.get('wa_photo', ''),
                                  "db_path": os.path.join(session_dir, f), "owner": owner}
            threading.Thread(target=session_worker, args=(name, "", "PAIRING CODE"), daemon=True).start()


def resume_tasks_on_startup():
    time.sleep(20)
    with tasks_lock:
        to_start = [tid for tid, t in active_tasks.items() if t.get('status') in ('RUNNING', 'QUEUED')]
        for tid in to_start: active_tasks[tid]['status'] = 'QUEUED'
    for tid in to_start:
        with tasks_lock:
            if tid not in active_tasks: continue
            sess_name = active_tasks[tid]['session']
        with sessions_lock:
            s = sessions.get(sess_name)
            ok = bool(s and s.get('status') == 'CONNECTED')
        if ok: start_task_runner(tid)


if __name__ == '__main__':
    logger.info("🚀 INITIALIZING ARJUN THAKUR WHATSAPP SERVER v48...")
    try:
        threading.Thread(target=_cpu_sampler_worker, daemon=True).start()
        load_tasks_state()
        auto_restore_sessions()
        threading.Thread(target=auto_cleanup_worker, daemon=True).start()
        threading.Thread(target=heartbeat_worker, daemon=True).start()
        threading.Thread(target=stopped_task_purge_worker, daemon=True).start()
        threading.Thread(target=resume_tasks_on_startup, daemon=True).start()
        port = int(os.environ.get('PORT', 25999))
        logger.info(f"🌐 BINDING TO 0.0.0.0:{port}")
        app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
    except Exception as e:
        logger.critical(f"STARTUP ERROR: {e}")
        traceback.print_exc()
