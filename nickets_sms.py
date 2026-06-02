"""Nickets SMS v3.1 - Cloud Synced, Zero-Config for VAs"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import json
import time
import os
import sys
import base64 as _b64
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import re
import uuid

# ─── Config ─────────────────────────────────────────────────────────────────

_LOGIN_USER = 'Nickets@gmail.com'
_LOGIN_PASS = 'NickNick#100'
_ADMIN_PASS = 'NickAdmin#100'
MAX_ACCOUNTS = 4

# ─── Paths ──────────────────────────────────────────────────────────────────

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.path.join(BASE_DIR, 'NicketsSMS_Data')
DATA_PATH = os.path.join(DATA_DIR, 'sms_data.json')
INSTANCE_PATH = os.path.join(DATA_DIR, 'instance_id.txt')

def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)

def get_instance_id():
    ensure_dirs()
    if os.path.exists(INSTANCE_PATH):
        with open(INSTANCE_PATH, 'r') as f:
            return f.read().strip()
    iid = uuid.uuid4().hex[:8]
    with open(INSTANCE_PATH, 'w') as f:
        f.write(iid)
    return iid

INSTANCE_ID = get_instance_id()

def load_data():
    if os.path.exists(DATA_PATH):
        try:
            with open(DATA_PATH, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_data_local(data):
    ensure_dirs()
    with open(DATA_PATH, 'w') as f:
        json.dump(data, f, indent=2)

# ─── Cloud Sync (GitHub) ───────────────────────────────────────────────────

_SYNC_REPO = 'anirudhatalmale6-alt/mlm-sms-sheet'
_SYNC_KEY = 0x5A
_SYNC_DATA = 'PTIqBSkYbyIUMR8eHTk4EQsKHwgPOCxsMRkgABMpNW0XPWlqMippNQ=='
_SYNC_SMS_FILE = 'cloud_sms.json'
_SYNC_ACCOUNTS_FILE = 'cloud_accounts.json'

def _get_sync_token():
    return bytes(b ^ _SYNC_KEY for b in _b64.b64decode(_SYNC_DATA)).decode()

def _sync_headers():
    return {
        'Authorization': f'token {_get_sync_token()}',
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'NicketsSMS',
    }

def _cloud_read(filename):
    try:
        url = f'https://api.github.com/repos/{_SYNC_REPO}/contents/{filename}'
        req = Request(url, headers=_sync_headers())
        with urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
        content = _b64.b64decode(result.get('content', '')).decode()
        sha = result.get('sha', '')
        return json.loads(content), sha, None
    except HTTPError as e:
        if e.code == 404:
            return {}, '', None
        return None, '', str(e)
    except Exception as e:
        return None, '', str(e)

def _cloud_write(filename, data, old_sha=''):
    try:
        content = json.dumps(data, indent=2)
        encoded = _b64.b64encode(content.encode()).decode()
        url = f'https://api.github.com/repos/{_SYNC_REPO}/contents/{filename}'
        payload = {'message': f'sync {INSTANCE_ID}', 'content': encoded}
        if old_sha:
            payload['sha'] = old_sha
        body = json.dumps(payload).encode()
        req = Request(url, data=body, headers=_sync_headers(), method='PUT')
        req.add_header('Content-Type', 'application/json')
        with urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
        return result.get('content', {}).get('sha', ''), None
    except HTTPError as e:
        if e.code in (409, 422):
            return '', 'conflict'
        return '', str(e)
    except Exception as e:
        return '', str(e)

# ─── Cloud Accounts ─────────────────────────────────────────────────────────

_acct_sha = ''

def cloud_load_accounts():
    global _acct_sha
    data, sha, err = _cloud_read(_SYNC_ACCOUNTS_FILE)
    if err:
        return None
    _acct_sha = sha
    if isinstance(data, dict):
        return data.get('accounts', [])
    return []

def cloud_save_accounts(accounts):
    global _acct_sha
    data = {'accounts': accounts}
    new_sha, err = _cloud_write(_SYNC_ACCOUNTS_FILE, data, _acct_sha)
    if err == 'conflict':
        _, sha2, _ = _cloud_read(_SYNC_ACCOUNTS_FILE)
        _acct_sha = sha2
        new_sha, err = _cloud_write(_SYNC_ACCOUNTS_FILE, data, _acct_sha)
    if not err:
        _acct_sha = new_sha
        return True
    return False

# ─── Cloud SMS Sync ─────────────────────────────────────────────────────────

_sms_sha = ''
_sms_lock = threading.Lock()

def merge_sms(local, cloud):
    merged = dict(cloud) if cloud else {}
    for num, info in (local or {}).items():
        if num not in merged:
            merged[num] = info
        else:
            cloud_info = merged[num]
            local_msgs = len(info.get('messages', []))
            cloud_msgs = len(cloud_info.get('messages', []))
            if local_msgs > cloud_msgs:
                merged[num] = info
            elif local_msgs == cloud_msgs:
                local_codes = len(info.get('codes', []))
                cloud_codes = len(cloud_info.get('codes', []))
                if local_codes > cloud_codes:
                    merged[num] = info
    return merged

def cloud_sync_sms(local_data):
    global _sms_sha
    with _sms_lock:
        cloud_data, sha, err = _cloud_read(_SYNC_SMS_FILE)
        if err:
            return local_data, False
        if cloud_data is None:
            cloud_data = {}
        _sms_sha = sha
        merged = merge_sms(local_data, cloud_data)
        if merged != cloud_data:
            new_sha, push_err = _cloud_write(_SYNC_SMS_FILE, merged, _sms_sha)
            if push_err == 'conflict':
                cloud_data2, sha2, _ = _cloud_read(_SYNC_SMS_FILE)
                if cloud_data2:
                    _sms_sha = sha2
                    merged = merge_sms(local_data, cloud_data2)
                    new_sha, push_err = _cloud_write(_SYNC_SMS_FILE, merged, _sms_sha)
                    if not push_err:
                        _sms_sha = new_sha
            elif not push_err:
                _sms_sha = new_sha
        save_data_local(merged)
        return merged, True

# ─── TextVerified API ──────────────────────────────────────────────────────

_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
_TV_BASE = 'https://www.textverified.com'

class API:
    def __init__(self, username, api_key):
        self._username = username
        self._api_key = api_key
        self._token = None
        self._exp = 0

    def _auth(self):
        if self._token and time.time() < self._exp:
            return self._token, None
        try:
            req = Request(f'{_TV_BASE}/api/pub/v2/auth', data=b'', method='POST')
            req.add_header('X-API-USERNAME', self._username)
            req.add_header('X-API-KEY', self._api_key)
            req.add_header('Content-Type', 'application/json')
            req.add_header('User-Agent', _UA)
            with urlopen(req, timeout=15) as resp:
                d = json.loads(resp.read().decode())
            self._token = d.get('token', '')
            self._exp = time.time() + d.get('expiresIn', 800) - 30
            return self._token, None
        except Exception as e:
            return None, self._err(e)

    def call(self, method, path):
        token, err = self._auth()
        if err:
            return None, err
        url = f'{_TV_BASE}{path}'
        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json',
            'User-Agent': _UA,
        }
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=20) as resp:
                raw = resp.read().decode()
                return json.loads(raw) if raw else {}, None
        except Exception as e:
            return None, self._err(e)

    def _err(self, e):
        s = str(e)
        if hasattr(e, 'read'):
            try:
                s = e.read().decode()
            except Exception:
                pass
        return s

def extract_code(body):
    for pat in (r'G-(\d{4,8})', r'code[:\s]+(\d{4,8})', r'verification[:\s]+(\d{4,8})', r'\b(\d{4,8})\b'):
        m = re.search(pat, body, re.IGNORECASE)
        if m:
            return m.group(1)
    return ''

# ─── Login Window ───────────────────────────────────────────────────────────

class LoginWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('Nickets SMS - Login')
        self.root.geometry('360x280')
        self.root.resizable(False, False)
        self.root.configure(bg='#0d1117')
        self.authenticated = False
        self._build()

    def _build(self):
        tk.Label(self.root, text='Nickets SMS', font=('Segoe UI', 20, 'bold'),
                 bg='#0d1117', fg='#58a6ff').pack(pady=(30, 4))
        tk.Label(self.root, text='Sign in to continue', font=('Segoe UI', 9),
                 bg='#0d1117', fg='#8b949e').pack(pady=(0, 20))

        form = tk.Frame(self.root, bg='#0d1117')
        form.pack(padx=40, fill='x')

        tk.Label(form, text='Email', font=('Segoe UI', 9),
                 bg='#0d1117', fg='#c9d1d9', anchor='w').pack(fill='x')
        self.user_entry = tk.Entry(form, font=('Consolas', 10), bg='#161b22',
                                   fg='#e6edf3', insertbackground='#e6edf3',
                                   relief='flat', highlightthickness=1,
                                   highlightcolor='#58a6ff', highlightbackground='#30363d')
        self.user_entry.pack(fill='x', pady=(2, 10), ipady=4)

        tk.Label(form, text='Password', font=('Segoe UI', 9),
                 bg='#0d1117', fg='#c9d1d9', anchor='w').pack(fill='x')
        self.pass_entry = tk.Entry(form, font=('Consolas', 10), bg='#161b22',
                                   fg='#e6edf3', insertbackground='#e6edf3',
                                   relief='flat', show='*', highlightthickness=1,
                                   highlightcolor='#58a6ff', highlightbackground='#30363d')
        self.pass_entry.pack(fill='x', pady=(2, 16), ipady=4)

        self.login_btn = tk.Button(form, text='Login', font=('Segoe UI', 10, 'bold'),
                                   bg='#238636', fg='white', activebackground='#2ea043',
                                   relief='flat', cursor='hand2', pady=6,
                                   command=self._do_login)
        self.login_btn.pack(fill='x')

        self.err_lbl = tk.Label(self.root, text='', font=('Segoe UI', 8),
                                bg='#0d1117', fg='#f85149')
        self.err_lbl.pack(pady=(6, 0))

        self.pass_entry.bind('<Return>', lambda e: self._do_login())
        self.user_entry.bind('<Return>', lambda e: self.pass_entry.focus())
        self.user_entry.focus()

    def _do_login(self):
        user = self.user_entry.get().strip()
        pwd = self.pass_entry.get().strip()
        if user == _LOGIN_USER and pwd == _LOGIN_PASS:
            self.authenticated = True
            self.root.destroy()
        else:
            self.err_lbl.config(text='Invalid email or password')
            self.pass_entry.delete(0, 'end')

    def run(self):
        self.root.mainloop()
        return self.authenticated

# ─── Admin Window (for boss to configure accounts) ─────────────────────────

class AdminWindow:
    def __init__(self, parent, accounts, on_save):
        self.win = tk.Toplevel(parent)
        self.win.title('Admin - Account Setup')
        self.win.geometry('520x400')
        self.win.configure(bg='#0d1117')
        self.win.transient(parent)
        self.win.grab_set()
        self.accounts = list(accounts)
        self.on_save = on_save
        self.entries = []

        pw_frame = tk.Frame(self.win, bg='#0d1117')
        pw_frame.pack(fill='x', padx=20, pady=(16, 0))
        tk.Label(pw_frame, text='Admin Password:', font=('Segoe UI', 9),
                 bg='#0d1117', fg='#c9d1d9').pack(side='left')
        self.pw_entry = tk.Entry(pw_frame, font=('Consolas', 10), bg='#161b22',
                                  fg='#e6edf3', insertbackground='#e6edf3',
                                  relief='flat', show='*', width=20,
                                  highlightthickness=1, highlightbackground='#30363d')
        self.pw_entry.pack(side='left', padx=(8, 8), ipady=2)
        self.unlock_btn = tk.Button(pw_frame, text='Unlock', font=('Segoe UI', 9, 'bold'),
                                     bg='#238636', fg='white', relief='flat', padx=10,
                                     command=self._unlock)
        self.unlock_btn.pack(side='left')
        self.pw_err = tk.Label(pw_frame, text='', font=('Segoe UI', 8),
                                bg='#0d1117', fg='#f85149')
        self.pw_err.pack(side='left', padx=(8, 0))

        self.pw_entry.bind('<Return>', lambda e: self._unlock())

        self.content_frame = tk.Frame(self.win, bg='#0d1117')
        self.content_frame.pack(fill='both', expand=True, padx=20, pady=(10, 14))

        self._locked = True

    def _unlock(self):
        if self.pw_entry.get().strip() == _ADMIN_PASS:
            self._locked = False
            self.pw_entry.config(state='disabled')
            self.unlock_btn.config(state='disabled', text='Unlocked')
            self.pw_err.config(text='')
            self._build_accounts()
        else:
            self.pw_err.config(text='Wrong password')

    def _build_accounts(self):
        for w in self.content_frame.winfo_children():
            w.destroy()

        tk.Label(self.content_frame, text='TextVerified Accounts',
                 font=('Segoe UI', 12, 'bold'),
                 bg='#0d1117', fg='#58a6ff').pack(pady=(0, 8))

        configured = len([a for a in self.accounts if a.get('username') and a.get('api_key')])
        status = f'{configured}/{MAX_ACCOUNTS}'
        if configured >= MAX_ACCOUNTS:
            status += '  FULL'
        tk.Label(self.content_frame, text=status, font=('Segoe UI', 10, 'bold'),
                 bg='#0d1117',
                 fg='#f85149' if configured >= MAX_ACCOUNTS else '#3fb950').pack(pady=(0, 8))

        self.entries = []
        for i in range(MAX_ACCOUNTS):
            acct = self.accounts[i] if i < len(self.accounts) else {}
            frame = tk.Frame(self.content_frame, bg='#161b22',
                             highlightbackground='#30363d', highlightthickness=1)
            frame.pack(fill='x', pady=(0, 6))

            row = tk.Frame(frame, bg='#161b22')
            row.pack(fill='x', padx=8, pady=6)

            tk.Label(row, text=f'Acct {i+1}', font=('Consolas', 9, 'bold'),
                     bg='#161b22', fg='#58a6ff', width=6).pack(side='left')

            e_user = tk.Entry(row, font=('Consolas', 9), bg='#0d1117', fg='#e6edf3',
                              insertbackground='#e6edf3', relief='flat', width=24,
                              highlightthickness=1, highlightbackground='#30363d')
            e_user.pack(side='left', padx=(4, 4), ipady=2)
            e_user.insert(0, acct.get('username', ''))

            e_key = tk.Entry(row, font=('Consolas', 9), bg='#0d1117', fg='#e6edf3',
                             insertbackground='#e6edf3', relief='flat',
                             highlightthickness=1, highlightbackground='#30363d')
            e_key.pack(side='left', fill='x', expand=True, ipady=2)
            e_key.insert(0, acct.get('api_key', ''))

            self.entries.append((e_user, e_key))

        btn_frame = tk.Frame(self.content_frame, bg='#0d1117')
        btn_frame.pack(fill='x', pady=(8, 0))
        self.save_status = tk.Label(btn_frame, text='', font=('Segoe UI', 8),
                                     bg='#0d1117', fg='#8b949e')
        self.save_status.pack(side='left')
        tk.Button(btn_frame, text='Save to Cloud', font=('Segoe UI', 10, 'bold'),
                  bg='#238636', fg='white', activebackground='#2ea043',
                  relief='flat', padx=16, pady=4, cursor='hand2',
                  command=self._save).pack(side='right')

    def _save(self):
        accounts = []
        for e_user, e_key in self.entries:
            u = e_user.get().strip()
            k = e_key.get().strip()
            if u or k:
                accounts.append({'username': u, 'api_key': k})
        self.save_status.config(text='Saving to cloud...', fg='#d29922')
        self.win.update()

        def do():
            ok = cloud_save_accounts(accounts)
            self.win.after(0, lambda: self._on_saved(ok, accounts))
        threading.Thread(target=do, daemon=True).start()

    def _on_saved(self, ok, accounts):
        if ok:
            self.save_status.config(text='Saved! All VAs will get this automatically.', fg='#3fb950')
            self.on_save(accounts)
        else:
            self.save_status.config(text='Failed to save. Try again.', fg='#f85149')

# ─── Main App ───────────────────────────────────────────────────────────────

class NicketsSMS:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('Nickets SMS v3.1')
        self.root.geometry('920x580')
        self.root.minsize(800, 480)
        self.root.resizable(True, True)
        self.root.configure(bg='#0d1117')

        self.data = load_data()
        self.accounts = []
        self.apis = []
        self.numbers = []
        self._number_account_map = {}
        self._selected_number = None

        self._setup_styles()
        self._build_ui()

        # Load accounts from cloud first, then start
        threading.Thread(target=self._initial_load, daemon=True).start()

    def _initial_load(self):
        self.root.after(0, self.sync_lbl.config,
                        {'text': 'CLOUD: loading accounts...', 'fg': '#d29922'})
        cloud_accts = cloud_load_accounts()
        if cloud_accts:
            self.accounts = cloud_accts
        self._init_apis()
        self.root.after(0, self._update_acct_display)
        self._load_numbers_sync()
        self.root.after(0, self._refresh_list)
        self.root.after(0, self.sync_lbl.config,
                        {'text': 'CLOUD: connected', 'fg': '#3fb950'})
        self._start_auto_poll()
        self._start_cloud_sync()

    def _init_apis(self):
        self.apis = []
        for acct in self.accounts:
            u = acct.get('username', '')
            k = acct.get('api_key', '')
            if u and k:
                self.apis.append(API(u, k))

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Treeview', background='#161b22', foreground='#e6edf3',
                        fieldbackground='#161b22', rowheight=26, font=('Consolas', 9))
        style.configure('Treeview.Heading', background='#21262d', foreground='#58a6ff',
                        font=('Segoe UI', 8, 'bold'))
        style.map('Treeview', background=[('selected', '#1f6feb')])

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self.root, bg='#0d1117')
        hdr.pack(fill='x', padx=10, pady=(8, 4))
        tk.Label(hdr, text='Nickets SMS', font=('Segoe UI', 14, 'bold'),
                 bg='#0d1117', fg='#58a6ff').pack(side='left')

        self.sync_lbl = tk.Label(hdr, text='CLOUD: connecting...',
                                 font=('Segoe UI', 8, 'bold'),
                                 bg='#0d1117', fg='#d29922')
        self.sync_lbl.pack(side='left', padx=(10, 0))

        self.status_lbl = tk.Label(hdr, text='', font=('Segoe UI', 8),
                                   bg='#0d1117', fg='#8b949e')
        self.status_lbl.pack(side='right')
        self.count_lbl = tk.Label(hdr, text='0 numbers', font=('Segoe UI', 9, 'bold'),
                                  bg='#0d1117', fg='#3fb950')
        self.count_lbl.pack(side='right', padx=(0, 12))

        # Account status bar
        acct_bar = tk.Frame(self.root, bg='#0d1117')
        acct_bar.pack(fill='x', padx=10, pady=(0, 4))

        self.acct_dots = []
        for i in range(MAX_ACCOUNTS):
            f = tk.Frame(acct_bar, bg='#0d1117')
            f.pack(side='left', padx=(0, 12))
            dot = tk.Label(f, text='*', font=('Segoe UI', 9),
                          bg='#0d1117', fg='#30363d')
            dot.pack(side='left', padx=(0, 3))
            lbl = tk.Label(f, text=f'Slot {i+1}: empty', font=('Segoe UI', 8),
                           bg='#0d1117', fg='#484f58')
            lbl.pack(side='left')
            self.acct_dots.append((dot, lbl))

        self.full_lbl = tk.Label(acct_bar, text='', font=('Segoe UI', 9, 'bold'),
                                 bg='#0d1117', fg='#f85149')
        self.full_lbl.pack(side='right')

        tk.Button(acct_bar, text='Admin', font=('Segoe UI', 7),
                  bg='#21262d', fg='#8b949e', activebackground='#30363d',
                  relief='flat', padx=8, pady=1, cursor='hand2',
                  command=self._open_admin).pack(side='right', padx=(0, 8))

        # Main split
        main = tk.PanedWindow(self.root, orient='horizontal', bg='#30363d',
                              sashwidth=3, sashrelief='flat')
        main.pack(fill='both', expand=True, padx=10, pady=(0, 6))

        # LEFT: Number list
        left = tk.Frame(main, bg='#0d1117')
        main.add(left, width=320, minsize=240)

        left_hdr = tk.Frame(left, bg='#0d1117')
        left_hdr.pack(fill='x', pady=(4, 4))
        tk.Label(left_hdr, text='Phone Numbers', font=('Segoe UI', 10, 'bold'),
                 bg='#0d1117', fg='#c9d1d9').pack(side='left')

        tbl_frame = tk.Frame(left, bg='#0d1117')
        tbl_frame.pack(fill='both', expand=True)

        cols = ('number', 'code')
        self.tree = ttk.Treeview(tbl_frame, columns=cols, show='headings', height=20)
        self.tree.heading('number', text='Number')
        self.tree.heading('code', text='Last Code')
        self.tree.column('number', width=150, minwidth=120)
        self.tree.column('code', width=100, minwidth=70)

        sb = ttk.Scrollbar(tbl_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')

        self.tree.bind('<<TreeviewSelect>>', lambda e: self._on_number_click())

        left_btn = tk.Frame(left, bg='#0d1117')
        left_btn.pack(fill='x', pady=(4, 2))
        tk.Button(left_btn, text='Copy Code', font=('Segoe UI', 8),
                  bg='#238636', fg='white', activebackground='#2ea043',
                  relief='flat', padx=10, pady=2, cursor='hand2',
                  command=self._copy_code).pack(side='left', padx=(0, 4))
        tk.Button(left_btn, text='Refresh', font=('Segoe UI', 8),
                  bg='#21262d', fg='#e6edf3', activebackground='#30363d',
                  relief='flat', padx=10, pady=2, cursor='hand2',
                  command=self._manual_refresh).pack(side='left')
        self.info_lbl = tk.Label(left_btn, text='', font=('Segoe UI', 7),
                                 bg='#0d1117', fg='#8b949e')
        self.info_lbl.pack(side='right')

        # RIGHT: SMS view
        right = tk.Frame(main, bg='#0d1117')
        main.add(right, minsize=350)

        sms_frame = tk.LabelFrame(right, text='  SMS Messages  ',
                                   font=('Segoe UI', 9, 'bold'),
                                   bg='#161b22', fg='#58a6ff',
                                   highlightbackground='#30363d', highlightthickness=1,
                                   relief='groove', bd=1)
        sms_frame.pack(fill='both', expand=True, pady=(4, 2))

        self.sms_hdr = tk.Frame(sms_frame, bg='#161b22')
        self.sms_hdr.pack(fill='x', padx=8, pady=(6, 4))
        self.sms_number_lbl = tk.Label(self.sms_hdr, text='Select a number',
                                        font=('Consolas', 11, 'bold'),
                                        bg='#161b22', fg='#8b949e')
        self.sms_number_lbl.pack(side='left')
        self.sms_code_lbl = tk.Label(self.sms_hdr, text='',
                                      font=('Consolas', 11, 'bold'),
                                      bg='#161b22', fg='#3fb950')
        self.sms_code_lbl.pack(side='right')

        self.sms_text = tk.Text(sms_frame, font=('Consolas', 9), bg='#0d1117',
                                fg='#e6edf3', wrap='word', relief='flat',
                                highlightthickness=0)
        self.sms_text.pack(fill='both', expand=True, padx=8, pady=(0, 6))
        self.sms_text.insert('end', 'Click a number on the left to view its SMS messages.')
        self.sms_text.config(state='disabled')
        self.sms_text.tag_config('ts', foreground='#8b949e')
        self.sms_text.tag_config('body', foreground='#e6edf3')
        self.sms_text.tag_config('hint', foreground='#8b949e')

    def _update_acct_display(self):
        configured = 0
        for i in range(MAX_ACCOUNTS):
            dot, lbl = self.acct_dots[i]
            if i < len(self.accounts):
                acct = self.accounts[i]
                if acct.get('username') and acct.get('api_key'):
                    configured += 1
                    email = acct['username']
                    short = email[:12] + '...' if len(email) > 15 else email
                    dot.config(fg='#3fb950')
                    lbl.config(text=f'Slot {i+1}: {short}', fg='#8b949e')
                    continue
            dot.config(fg='#30363d')
            lbl.config(text=f'Slot {i+1}: empty', fg='#484f58')

        if configured >= MAX_ACCOUNTS:
            self.full_lbl.config(text='FULL')
        else:
            self.full_lbl.config(text=f'{configured}/{MAX_ACCOUNTS}')

    def _open_admin(self):
        AdminWindow(self.root, self.accounts, self._on_admin_save)

    def _on_admin_save(self, new_accounts):
        self.accounts = new_accounts
        self._init_apis()
        self._update_acct_display()
        self._manual_refresh()

    def _on_number_click(self):
        num = self._get_selected_number()
        if not num:
            return
        self._selected_number = num
        self.sms_number_lbl.config(text=num, fg='#58a6ff')
        self.sms_code_lbl.config(text='loading...')
        self.sms_text.config(state='normal')
        self.sms_text.delete('1.0', 'end')
        self.sms_text.insert('end', 'Loading messages...', 'hint')
        self.sms_text.config(state='disabled')

        def do():
            self._poll_number(num)
            self.root.after(0, lambda: self._show_sms(num))
        threading.Thread(target=do, daemon=True).start()

    def _show_sms(self, num):
        if self._selected_number != num:
            return
        info = self.data.get(num, {})

        codes = info.get('codes', [])
        if codes:
            latest = codes[-1].get('code', '')
            self.sms_code_lbl.config(text=f'Code: {latest}', fg='#3fb950')
        else:
            self.sms_code_lbl.config(text='No code yet', fg='#8b949e')

        self.sms_text.config(state='normal')
        self.sms_text.delete('1.0', 'end')

        msgs = info.get('messages', [])
        if not msgs:
            self.sms_text.insert('end', 'Waiting for messages...\n\n', 'hint')
            self.sms_text.insert('end', 'Send a verification to this number.', 'hint')
        else:
            for m in reversed(msgs):
                ts = m.get('time', '')[:19]
                frm = m.get('from', '')
                body = m.get('body', '')
                self.sms_text.insert('end', f'{ts}', 'ts')
                if frm:
                    self.sms_text.insert('end', f'  from {frm}', 'ts')
                self.sms_text.insert('end', '\n')
                self.sms_text.insert('end', f'{body}\n\n', 'body')

        self.sms_text.config(state='disabled')

    def _refresh_list(self):
        sel_num = self._get_selected_number()
        for item in self.tree.get_children():
            self.tree.delete(item)
        sel_iid = None
        for num in self.numbers:
            info = self.data.get(num, {})
            code = ''
            if info.get('codes'):
                code = info['codes'][-1].get('code', '')
            iid = self.tree.insert('', 'end', values=(num, code))
            if num == sel_num:
                sel_iid = iid
        if sel_iid:
            self.tree.selection_set(sel_iid)
            self.tree.see(sel_iid)
        count = len(self.numbers)
        self.count_lbl.config(text=f'{count} number{"s" if count != 1 else ""}')

    def _get_selected_number(self):
        sel = self.tree.selection()
        if not sel:
            return None
        vals = self.tree.item(sel[0], 'values')
        return vals[0] if vals else None

    def _poll_number(self, number):
        info = self.data.get(number)
        if not info:
            return
        res_id = info.get('reservation_id', '')
        if not res_id:
            return
        idx = info.get('account_idx', 0)
        api = self.apis[idx] if 0 <= idx < len(self.apis) else (self.apis[0] if self.apis else None)
        if not api:
            return
        resp, err = api.call('GET', f'/api/pub/v2/sms?reservationId={res_id}')
        if err or not resp:
            return
        api_messages = resp.get('data', []) if isinstance(resp, dict) else []
        if not api_messages:
            return
        messages = []
        codes = []
        for m in api_messages:
            mid = m.get('id', '')
            body = m.get('smsContent', '') or m.get('body', '')
            frm = m.get('from', '')
            ts = m.get('createdAt', '')
            messages.append({'id': mid, 'from': frm, 'body': body, 'time': ts})
            code = m.get('parsedCode', '') or extract_code(body)
            if code:
                codes.append({'code': code, 'time': ts, 'body': body})
        info['messages'] = messages
        info['codes'] = codes
        save_data_local(self.data)

    def _load_numbers_sync(self):
        self.numbers = []
        self._number_account_map = {}
        for idx, api in enumerate(self.apis):
            all_rentals = []
            for ep in ('/api/pub/v2/reservations/rental/renewable',
                       '/api/pub/v2/reservations/rental/nonrenewable'):
                resp, err = api.call('GET', ep)
                if err:
                    continue
                items = resp.get('data', []) if isinstance(resp, dict) else []
                all_rentals.extend(items)
            active = [r for r in all_rentals if 'active' in r.get('state', '').lower()]
            for r in active:
                raw = r.get('number', '')
                phone = f'+1{raw}' if len(raw) == 10 and not raw.startswith('+') else raw
                res_id = r.get('id', '')
                if phone not in self.data:
                    self.data[phone] = {'reservation_id': res_id, 'account_idx': idx,
                                        'codes': [], 'messages': []}
                else:
                    self.data[phone]['reservation_id'] = res_id
                    self.data[phone]['account_idx'] = idx
                self.numbers.append(phone)
                self._number_account_map[phone] = idx
        save_data_local(self.data)
        n = len(self.numbers)
        self.root.after(0, self.count_lbl.config,
                        {'text': f'{n} number{"s" if n != 1 else ""}'})

    def _start_auto_poll(self):
        def loop():
            while True:
                time.sleep(8)
                try:
                    if self.numbers:
                        self.root.after(0, self.status_lbl.config, {'text': 'checking...', 'fg': '#8b949e'})
                        for num in list(self.numbers):
                            self._poll_number(num)
                        self.root.after(0, self._refresh_list)
                        if self._selected_number:
                            self.root.after(0, lambda: self._show_sms(self._selected_number))
                        self.root.after(0, self.status_lbl.config,
                                        {'text': 'live', 'fg': '#3fb950'})
                except Exception:
                    pass
        threading.Thread(target=loop, daemon=True).start()

    def _start_cloud_sync(self):
        def loop():
            while True:
                try:
                    # Sync SMS data
                    self.data, ok = cloud_sync_sms(self.data)
                    if ok:
                        # Include cloud-only numbers
                        cloud_nums = set(self.data.keys()) - set(self._number_account_map.keys())
                        local_nums = [n for n in self.numbers if n in self._number_account_map]
                        self.numbers = local_nums + sorted(cloud_nums)
                        self.root.after(0, self._refresh_list)
                        if self._selected_number:
                            self.root.after(0, lambda: self._show_sms(self._selected_number))
                        self.root.after(0, self.sync_lbl.config,
                                        {'text': 'CLOUD: synced', 'fg': '#3fb950'})

                    # Check for account updates from admin
                    cloud_accts = cloud_load_accounts()
                    if cloud_accts is not None and cloud_accts != self.accounts:
                        self.accounts = cloud_accts
                        self._init_apis()
                        self.root.after(0, self._update_acct_display)
                        self._load_numbers_sync()
                        self.root.after(0, self._refresh_list)

                    if not ok:
                        self.root.after(0, self.sync_lbl.config,
                                        {'text': 'CLOUD: offline', 'fg': '#f85149'})
                except Exception:
                    self.root.after(0, self.sync_lbl.config,
                                    {'text': 'CLOUD: error', 'fg': '#f85149'})
                time.sleep(10)
        threading.Thread(target=loop, daemon=True).start()

    def _manual_refresh(self):
        def do():
            self.root.after(0, self.info_lbl.config, {'text': 'Refreshing...', 'fg': '#8b949e'})
            cloud_accts = cloud_load_accounts()
            if cloud_accts is not None:
                self.accounts = cloud_accts
                self._init_apis()
                self.root.after(0, self._update_acct_display)
            self._load_numbers_sync()
            for num in list(self.numbers):
                self._poll_number(num)
            self.data, _ = cloud_sync_sms(self.data)
            self.root.after(0, self._refresh_list)
            if self._selected_number:
                self.root.after(0, lambda: self._show_sms(self._selected_number))
            self.root.after(0, self.info_lbl.config, {'text': 'Refreshed', 'fg': '#3fb950'})
        threading.Thread(target=do, daemon=True).start()

    def _copy_code(self):
        num = self._get_selected_number()
        if not num or num not in self.data:
            return
        info = self.data[num]
        if not info.get('codes'):
            self.info_lbl.config(text='No codes yet', fg='#d29922')
            return
        code = info['codes'][-1].get('code', '')
        if code:
            self.root.clipboard_clear()
            self.root.clipboard_append(code)
            self.info_lbl.config(text=f'Copied: {code}', fg='#3fb950')

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    ensure_dirs()

    login = LoginWindow()
    if not login.run():
        sys.exit(0)

    app = NicketsSMS()
    app.run()
