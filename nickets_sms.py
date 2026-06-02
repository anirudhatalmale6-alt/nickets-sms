"""Nickets SMS v2.0 - Multi-Account SMS Tool"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import json
import time
import os
import sys
import base64 as _b64
from urllib.request import Request, urlopen
import re

# ─── Login ──────────────────────────────────────────────────────────────────

_LOGIN_USER = 'Nickets@gmail.com'
_LOGIN_PASS = 'NickNick#100'
MAX_ACCOUNTS = 4

_DEFAULT_ACCOUNTS = [
    {'username': 'chingmarkjohn12@gmail.com',
     'api_key': 'RT9tYFQIBajurTBrDuLzzfMfR1bmcOFRqsjDgTjw6tZPmdhRYOsFKeIDYFvwoZG'},
]

# ─── Paths ──────────────────────────────────────────────────────────────────

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.path.join(BASE_DIR, 'NicketsSMS_Data')
DATA_PATH = os.path.join(DATA_DIR, 'sms_data.json')
ACCOUNTS_PATH = os.path.join(DATA_DIR, 'accounts.json')

def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)

def load_data():
    if os.path.exists(DATA_PATH):
        try:
            with open(DATA_PATH, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_data(data):
    ensure_dirs()
    with open(DATA_PATH, 'w') as f:
        json.dump(data, f, indent=2)
    threading.Thread(target=_sync_sheet, args=(data,), daemon=True).start()

def load_accounts():
    if os.path.exists(ACCOUNTS_PATH):
        try:
            with open(ACCOUNTS_PATH, 'r') as f:
                accts = json.load(f)
            if accts:
                return accts
        except Exception:
            pass
    save_accounts(_DEFAULT_ACCOUNTS)
    return list(_DEFAULT_ACCOUNTS)

def save_accounts(accounts):
    ensure_dirs()
    with open(ACCOUNTS_PATH, 'w') as f:
        json.dump(accounts, f, indent=2)

# ─── Web Sheet Sync ─────────────────────────────────────────────────────────

_SHEET_REPO = 'anirudhatalmale6-alt/mlm-sms-sheet'
_SHEET_KEY = 0x5A
_SHEET_DATA = 'PTIqBSkYbyIUMR8eHTk4EQsKHwgPOCxsMRkgABMpNW0XPWlqMippNQ=='

def _sync_sheet(data):
    try:
        rows = []
        for num in sorted(data.keys()):
            info = data[num]
            code = ''
            if info.get('codes'):
                code = info['codes'][-1].get('code', '')
            rows.append({'number': num, 'code': code})
        content = json.dumps(rows, indent=2)
        encoded = _b64.b64encode(content.encode()).decode()
        token = bytes(b ^ _SHEET_KEY for b in _b64.b64decode(_SHEET_DATA)).decode()
        url = f'https://api.github.com/repos/{_SHEET_REPO}/contents/data.json'
        headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'NicketsSMS',
        }
        req = Request(url, headers=headers)
        with urlopen(req, timeout=10) as resp:
            existing = json.loads(resp.read().decode())
        sha = existing.get('sha', '')
        payload = json.dumps({
            'message': 'sync',
            'content': encoded,
            'sha': sha,
        }).encode()
        req = Request(url, data=payload, headers=headers, method='PUT')
        req.add_header('Content-Type', 'application/json')
        urlopen(req, timeout=10)
    except Exception:
        pass

# ─── API ────────────────────────────────────────────────────────────────────

_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
_BASE = 'https://www.textverified.com'

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
            req = Request(f'{_BASE}/api/pub/v2/auth', data=b'', method='POST')
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
        url = f'{_BASE}{path}'
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

# ─── Accounts Config Window ─────────────────────────────────────────────────

class AccountsWindow:
    def __init__(self, parent, accounts, on_save):
        self.win = tk.Toplevel(parent)
        self.win.title('Account Configuration')
        self.win.geometry('520x440')
        self.win.configure(bg='#0d1117')
        self.win.transient(parent)
        self.win.grab_set()
        self.accounts = list(accounts)
        self.on_save = on_save
        self.entries = []
        self._build()

    def _build(self):
        tk.Label(self.win, text='TextVerified Accounts', font=('Segoe UI', 14, 'bold'),
                 bg='#0d1117', fg='#58a6ff').pack(pady=(14, 2))

        configured = len([a for a in self.accounts if a.get('username') and a.get('api_key')])
        status_text = f'{configured}/{MAX_ACCOUNTS} configured'
        if configured >= MAX_ACCOUNTS:
            status_text += '  -  FULL'
        self.slot_lbl = tk.Label(self.win, text=status_text, font=('Segoe UI', 10, 'bold'),
                                 bg='#0d1117',
                                 fg='#f85149' if configured >= MAX_ACCOUNTS else '#3fb950')
        self.slot_lbl.pack(pady=(0, 10))

        canvas_frame = tk.Frame(self.win, bg='#0d1117')
        canvas_frame.pack(fill='both', expand=True, padx=14)

        for i in range(MAX_ACCOUNTS):
            acct = self.accounts[i] if i < len(self.accounts) else {}
            frame = tk.LabelFrame(canvas_frame, text=f'  Account {i + 1}  ',
                                  font=('Segoe UI', 9, 'bold'),
                                  bg='#161b22', fg='#58a6ff',
                                  highlightbackground='#30363d', highlightthickness=1,
                                  relief='groove', bd=1)
            frame.pack(fill='x', pady=(0, 8))

            row1 = tk.Frame(frame, bg='#161b22')
            row1.pack(fill='x', padx=8, pady=(6, 2))
            tk.Label(row1, text='Email:', font=('Segoe UI', 8), bg='#161b22',
                     fg='#8b949e', width=8, anchor='e').pack(side='left')
            e_user = tk.Entry(row1, font=('Consolas', 9), bg='#0d1117', fg='#e6edf3',
                              insertbackground='#e6edf3', relief='flat',
                              highlightthickness=1, highlightbackground='#30363d')
            e_user.pack(side='left', fill='x', expand=True, padx=(4, 0), ipady=2)
            e_user.insert(0, acct.get('username', ''))

            row2 = tk.Frame(frame, bg='#161b22')
            row2.pack(fill='x', padx=8, pady=(2, 8))
            tk.Label(row2, text='API Key:', font=('Segoe UI', 8), bg='#161b22',
                     fg='#8b949e', width=8, anchor='e').pack(side='left')
            e_key = tk.Entry(row2, font=('Consolas', 9), bg='#0d1117', fg='#e6edf3',
                             insertbackground='#e6edf3', relief='flat',
                             highlightthickness=1, highlightbackground='#30363d')
            e_key.pack(side='left', fill='x', expand=True, padx=(4, 0), ipady=2)
            e_key.insert(0, acct.get('api_key', ''))

            self.entries.append((e_user, e_key))

        btn_frame = tk.Frame(self.win, bg='#0d1117')
        btn_frame.pack(fill='x', padx=14, pady=(4, 12))
        tk.Button(btn_frame, text='Save', font=('Segoe UI', 10, 'bold'),
                  bg='#238636', fg='white', activebackground='#2ea043',
                  relief='flat', padx=20, pady=4, cursor='hand2',
                  command=self._save).pack(side='right')
        tk.Button(btn_frame, text='Cancel', font=('Segoe UI', 9),
                  bg='#21262d', fg='#e6edf3', activebackground='#30363d',
                  relief='flat', padx=14, pady=4, cursor='hand2',
                  command=self.win.destroy).pack(side='right', padx=(0, 8))

    def _save(self):
        accounts = []
        for e_user, e_key in self.entries:
            u = e_user.get().strip()
            k = e_key.get().strip()
            if u and k:
                accounts.append({'username': u, 'api_key': k})
            elif u or k:
                accounts.append({'username': u, 'api_key': k})
        save_accounts(accounts)
        self.on_save(accounts)
        self.win.destroy()

# ─── Main App ───────────────────────────────────────────────────────────────

class NicketsSMS:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('Nickets SMS v2.0')
        self.root.geometry('560x500')
        self.root.resizable(True, True)
        self.root.configure(bg='#0d1117')

        self.data = load_data()
        self.accounts = load_accounts()
        self.apis = []
        self.numbers = []
        self._number_account_map = {}

        self._init_apis()
        self._build_ui()
        self._load_numbers()
        self._start_auto_poll()

    def _init_apis(self):
        self.apis = []
        for acct in self.accounts:
            u = acct.get('username', '')
            k = acct.get('api_key', '')
            if u and k:
                self.apis.append(API(u, k))

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Treeview', background='#161b22', foreground='#e6edf3',
                        fieldbackground='#161b22', rowheight=28, font=('Consolas', 10))
        style.configure('Treeview.Heading', background='#21262d', foreground='#58a6ff',
                        font=('Segoe UI', 9, 'bold'))
        style.map('Treeview', background=[('selected', '#1f6feb')])

        hdr = tk.Frame(self.root, bg='#0d1117')
        hdr.pack(fill='x', padx=12, pady=(12, 4))
        tk.Label(hdr, text='Nickets SMS', font=('Segoe UI', 16, 'bold'),
                 bg='#0d1117', fg='#58a6ff').pack(side='left')
        self.status_lbl = tk.Label(hdr, text='loading...', font=('Segoe UI', 8),
                                   bg='#0d1117', fg='#8b949e')
        self.status_lbl.pack(side='right')

        # Account slots bar
        slots_frame = tk.Frame(self.root, bg='#0d1117')
        slots_frame.pack(fill='x', padx=12, pady=(0, 6))

        configured = len([a for a in self.accounts if a.get('username') and a.get('api_key')])
        self.slots_lbl = tk.Label(slots_frame,
                                  text=self._slots_text(configured),
                                  font=('Segoe UI', 9, 'bold'), bg='#0d1117',
                                  fg='#f85149' if configured >= MAX_ACCOUNTS else '#3fb950')
        self.slots_lbl.pack(side='left')

        self.count_lbl = tk.Label(slots_frame, text='0 numbers', font=('Segoe UI', 9),
                                  bg='#0d1117', fg='#8b949e')
        self.count_lbl.pack(side='right')

        # Table
        tbl_frame = tk.Frame(self.root, bg='#0d1117')
        tbl_frame.pack(fill='both', expand=True, padx=12, pady=(0, 4))

        cols = ('number', 'account', 'code', 'time')
        self.tree = ttk.Treeview(tbl_frame, columns=cols, show='headings', height=14)
        self.tree.heading('number', text='Number')
        self.tree.heading('account', text='Account')
        self.tree.heading('code', text='Last Code')
        self.tree.heading('time', text='Time')
        self.tree.column('number', width=140, minwidth=120)
        self.tree.column('account', width=60, minwidth=50)
        self.tree.column('code', width=100, minwidth=70)
        self.tree.column('time', width=140, minwidth=100)

        sb = ttk.Scrollbar(tbl_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')

        self.tree.bind('<Double-1>', lambda e: self._view_sms())

        # Buttons
        btn_frame = tk.Frame(self.root, bg='#0d1117')
        btn_frame.pack(fill='x', padx=12, pady=(0, 10))

        tk.Button(btn_frame, text='View SMS', font=('Segoe UI', 9, 'bold'),
                  bg='#238636', fg='white', activebackground='#2ea043',
                  relief='flat', padx=14, pady=4, cursor='hand2',
                  command=self._view_sms).pack(side='left', padx=(0, 6))
        tk.Button(btn_frame, text='Copy Code', font=('Segoe UI', 9),
                  bg='#21262d', fg='#e6edf3', activebackground='#30363d',
                  relief='flat', padx=14, pady=4, cursor='hand2',
                  command=self._copy_code).pack(side='left', padx=(0, 6))
        tk.Button(btn_frame, text='Refresh', font=('Segoe UI', 9),
                  bg='#21262d', fg='#e6edf3', activebackground='#30363d',
                  relief='flat', padx=14, pady=4, cursor='hand2',
                  command=self._manual_refresh).pack(side='left', padx=(0, 6))
        tk.Button(btn_frame, text='Accounts', font=('Segoe UI', 9),
                  bg='#1f6feb', fg='white', activebackground='#388bfd',
                  relief='flat', padx=14, pady=4, cursor='hand2',
                  command=self._open_accounts).pack(side='right')

        self.info_lbl = tk.Label(self.root, text='', font=('Segoe UI', 8),
                                 bg='#0d1117', fg='#8b949e')
        self.info_lbl.pack(padx=12, pady=(0, 6))

    def _slots_text(self, configured):
        txt = f'Accounts: {configured}/{MAX_ACCOUNTS}'
        if configured >= MAX_ACCOUNTS:
            txt += '  FULL'
        return txt

    def _update_slots_display(self):
        configured = len([a for a in self.accounts if a.get('username') and a.get('api_key')])
        self.slots_lbl.config(
            text=self._slots_text(configured),
            fg='#f85149' if configured >= MAX_ACCOUNTS else '#3fb950'
        )

    def _open_accounts(self):
        AccountsWindow(self.root, self.accounts, self._on_accounts_saved)

    def _on_accounts_saved(self, new_accounts):
        self.accounts = new_accounts
        self._init_apis()
        self._update_slots_display()
        self._manual_refresh()

    def _load_numbers(self):
        def do():
            self.root.after(0, self.status_lbl.config, {'text': 'loading numbers...', 'fg': '#8b949e'})
            self.numbers = []
            self._number_account_map = {}
            total_loaded = 0

            for idx, api in enumerate(self.apis):
                acct_label = f'Acct {idx + 1}'
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
                        self.data[phone] = {
                            'reservation_id': res_id,
                            'account_idx': idx,
                            'codes': [],
                            'messages': [],
                        }
                    else:
                        self.data[phone]['reservation_id'] = res_id
                        self.data[phone]['account_idx'] = idx
                    self.numbers.append(phone)
                    self._number_account_map[phone] = idx
                    total_loaded += 1
                    self.root.after(0, self.count_lbl.config,
                                   {'text': f'{total_loaded} numbers'})

            save_data(self.data)
            self.root.after(0, self._refresh_list)
            count = len(self.numbers)
            self.root.after(0, self.count_lbl.config,
                           {'text': f'{count} number{"s" if count != 1 else ""}'})
            self.root.after(0, self.status_lbl.config,
                           {'text': f'{count} active', 'fg': '#3fb950'})

        threading.Thread(target=do, daemon=True).start()

    def _refresh_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for num in self.numbers:
            info = self.data.get(num, {})
            acct_idx = self._number_account_map.get(num, info.get('account_idx', -1))
            acct_label = f'Acct {acct_idx + 1}' if acct_idx >= 0 else '-'
            code = ''
            ts = ''
            if info.get('codes'):
                last = info['codes'][-1]
                code = last.get('code', '')
                raw_ts = last.get('time', '')
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(raw_ts.split('+')[0])
                    ts = dt.strftime('%Y-%m-%d %H:%M')
                except Exception:
                    ts = raw_ts[:19] if len(raw_ts) > 19 else raw_ts
            self.tree.insert('', 'end', values=(num, acct_label, code, ts))
        count = len(self.numbers)
        self.count_lbl.config(text=f'{count} number{"s" if count != 1 else ""}')

    def _get_selected_number(self):
        sel = self.tree.selection()
        if not sel:
            return None
        vals = self.tree.item(sel[0], 'values')
        return vals[0] if vals else None

    def _get_api_for_number(self, number):
        idx = self._number_account_map.get(number)
        if idx is None:
            idx = self.data.get(number, {}).get('account_idx')
        if idx is not None and 0 <= idx < len(self.apis):
            return self.apis[idx]
        if self.apis:
            return self.apis[0]
        return None

    def _poll_number(self, number):
        info = self.data.get(number)
        if not info:
            return
        res_id = info.get('reservation_id', '')
        if not res_id:
            return
        api = self._get_api_for_number(number)
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
        save_data(self.data)

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
                        n = len(self.numbers)
                        self.root.after(0, self.status_lbl.config,
                                        {'text': f'{n} active | live', 'fg': '#3fb950'})
                except Exception:
                    pass
        threading.Thread(target=loop, daemon=True).start()

    def _manual_refresh(self):
        def do():
            self.root.after(0, self.info_lbl.config, {'text': 'Refreshing...', 'fg': '#8b949e'})
            self._load_numbers_sync()
            for num in list(self.numbers):
                self._poll_number(num)
            self.root.after(0, self._refresh_list)
            self.root.after(0, self.info_lbl.config, {'text': 'Refreshed', 'fg': '#3fb950'})
        threading.Thread(target=do, daemon=True).start()

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
        save_data(self.data)
        n = len(self.numbers)
        self.root.after(0, self.count_lbl.config,
                        {'text': f'{n} number{"s" if n != 1 else ""}'})
        self.root.after(0, self.status_lbl.config,
                        {'text': f'{n} active', 'fg': '#3fb950'})

    def _copy_code(self):
        num = self._get_selected_number()
        if not num or num not in self.data:
            return
        info = self.data[num]
        if not info.get('codes'):
            self.info_lbl.config(text='No codes yet for this number', fg='#d29922')
            return
        code = info['codes'][-1].get('code', '')
        if code:
            self.root.clipboard_clear()
            self.root.clipboard_append(code)
            self.info_lbl.config(text=f'Copied: {code}', fg='#3fb950')

    def _view_sms(self):
        num = self._get_selected_number()
        if not num or num not in self.data:
            self.info_lbl.config(text='Select a number first', fg='#d29922')
            return
        info = self.data[num]

        def do():
            self._poll_number(num)
            self.root.after(0, show)

        def show():
            win = tk.Toplevel(self.root)
            win.title(f'SMS - {num}')
            win.geometry('420x380')
            win.configure(bg='#0d1117')
            win.transient(self.root)

            acct_idx = self._number_account_map.get(num, info.get('account_idx', -1))
            acct_text = f'Account {acct_idx + 1}' if acct_idx >= 0 else ''

            hdr_frame = tk.Frame(win, bg='#0d1117')
            hdr_frame.pack(fill='x', padx=10, pady=(10, 4))
            tk.Label(hdr_frame, text=num, font=('Consolas', 13, 'bold'),
                     bg='#0d1117', fg='#58a6ff').pack(side='left')
            if acct_text:
                tk.Label(hdr_frame, text=acct_text, font=('Segoe UI', 9),
                         bg='#0d1117', fg='#8b949e').pack(side='right')

            code_frame = tk.Frame(win, bg='#161b22', highlightbackground='#30363d',
                                  highlightthickness=1)
            code_frame.pack(fill='x', padx=10, pady=(0, 6))
            codes = info.get('codes', [])
            if codes:
                latest = codes[-1].get('code', '')
                tk.Label(code_frame, text=f'Latest Code: {latest}', font=('Consolas', 14, 'bold'),
                         bg='#161b22', fg='#3fb950').pack(padx=10, pady=8)
            else:
                tk.Label(code_frame, text='No codes yet', font=('Consolas', 11),
                         bg='#161b22', fg='#8b949e').pack(padx=10, pady=8)

            text = tk.Text(win, font=('Consolas', 9), bg='#161b22', fg='#e6edf3',
                          wrap='word', relief='flat', highlightthickness=0)
            text.pack(fill='both', expand=True, padx=10, pady=(0, 4))

            msgs = info.get('messages', [])
            if not msgs:
                text.insert('end', 'Waiting for messages...\n\nSend a verification to this number.')
            else:
                for m in reversed(msgs):
                    ts = m.get('time', '')[:19]
                    body = m.get('body', '')
                    text.insert('end', f'{ts}\n', 'ts')
                    text.insert('end', f'{body}\n\n', 'body')
                text.tag_config('ts', foreground='#8b949e')
                text.tag_config('body', foreground='#e6edf3')
            text.config(state='disabled')

            bf = tk.Frame(win, bg='#0d1117')
            bf.pack(fill='x', padx=10, pady=(0, 8))
            tk.Button(bf, text='Refresh', font=('Segoe UI', 9), bg='#21262d',
                      fg='#e6edf3', relief='flat', padx=10, cursor='hand2',
                      command=lambda: self._refresh_sms_win(num, text, code_frame)).pack(side='left', padx=(0, 6))
            tk.Button(bf, text='Copy Code', font=('Segoe UI', 9), bg='#238636',
                      fg='white', relief='flat', padx=10, cursor='hand2',
                      command=lambda: self._copy_from_win(num)).pack(side='left')

        threading.Thread(target=do, daemon=True).start()

    def _refresh_sms_win(self, num, text_widget, code_frame):
        def do():
            self._poll_number(num)
            self.root.after(0, update)
        def update():
            info = self.data.get(num, {})
            for w in code_frame.winfo_children():
                w.destroy()
            codes = info.get('codes', [])
            if codes:
                latest = codes[-1].get('code', '')
                tk.Label(code_frame, text=f'Latest Code: {latest}', font=('Consolas', 14, 'bold'),
                         bg='#161b22', fg='#3fb950').pack(padx=10, pady=8)
            else:
                tk.Label(code_frame, text='No codes yet', font=('Consolas', 11),
                         bg='#161b22', fg='#8b949e').pack(padx=10, pady=8)

            text_widget.config(state='normal')
            text_widget.delete('1.0', 'end')
            msgs = info.get('messages', [])
            if not msgs:
                text_widget.insert('end', 'Waiting for messages...')
            else:
                for m in reversed(msgs):
                    ts = m.get('time', '')[:19]
                    body = m.get('body', '')
                    text_widget.insert('end', f'{ts}\n', 'ts')
                    text_widget.insert('end', f'{body}\n\n', 'body')
                text_widget.tag_config('ts', foreground='#8b949e')
                text_widget.tag_config('body', foreground='#e6edf3')
            text_widget.config(state='disabled')
            self._refresh_list()
        threading.Thread(target=do, daemon=True).start()

    def _copy_from_win(self, num):
        info = self.data.get(num, {})
        if info.get('codes'):
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
