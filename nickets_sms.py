"""Nickets SMS v2.1 - Split Panel Layout"""

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

# ─── Main App (Split Panel) ────────────────────────────────────────────────

class NicketsSMS:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('Nickets SMS v2.1')
        self.root.geometry('920x600')
        self.root.minsize(800, 500)
        self.root.resizable(True, True)
        self.root.configure(bg='#0d1117')

        self.data = load_data()
        self.accounts = load_accounts()
        self.apis = []
        self.numbers = []
        self._number_account_map = {}
        self._selected_number = None
        self._acct_entries = []

        self._init_apis()
        self._setup_styles()
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
        self.status_lbl = tk.Label(hdr, text='loading...', font=('Segoe UI', 8),
                                   bg='#0d1117', fg='#8b949e')
        self.status_lbl.pack(side='right')
        self.count_lbl = tk.Label(hdr, text='0 numbers', font=('Segoe UI', 9, 'bold'),
                                  bg='#0d1117', fg='#3fb950')
        self.count_lbl.pack(side='right', padx=(0, 12))

        # Main split: left (numbers) | right (SMS + accounts)
        main = tk.PanedWindow(self.root, orient='horizontal', bg='#30363d',
                              sashwidth=3, sashrelief='flat')
        main.pack(fill='both', expand=True, padx=10, pady=(0, 6))

        # ── LEFT: Number list ──
        left = tk.Frame(main, bg='#0d1117')
        main.add(left, width=340, minsize=250)

        left_hdr = tk.Frame(left, bg='#0d1117')
        left_hdr.pack(fill='x', pady=(4, 4))
        tk.Label(left_hdr, text='Phone Numbers', font=('Segoe UI', 10, 'bold'),
                 bg='#0d1117', fg='#c9d1d9').pack(side='left')

        tbl_frame = tk.Frame(left, bg='#0d1117')
        tbl_frame.pack(fill='both', expand=True)

        cols = ('number', 'acct', 'code')
        self.tree = ttk.Treeview(tbl_frame, columns=cols, show='headings', height=20)
        self.tree.heading('number', text='Number')
        self.tree.heading('acct', text='Acct')
        self.tree.heading('code', text='Last Code')
        self.tree.column('number', width=130, minwidth=100)
        self.tree.column('acct', width=40, minwidth=35)
        self.tree.column('code', width=80, minwidth=60)

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

        # ── RIGHT: SMS view + Account slots ──
        right = tk.Frame(main, bg='#0d1117')
        main.add(right, minsize=350)

        # SMS panel (top part of right)
        sms_frame = tk.LabelFrame(right, text='  SMS Messages  ',
                                   font=('Segoe UI', 9, 'bold'),
                                   bg='#161b22', fg='#58a6ff',
                                   highlightbackground='#30363d', highlightthickness=1,
                                   relief='groove', bd=1)
        sms_frame.pack(fill='both', expand=True, pady=(4, 6))

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
                                highlightthickness=0, height=12)
        self.sms_text.pack(fill='both', expand=True, padx=8, pady=(0, 6))
        self.sms_text.insert('end', 'Click a number on the left to view its SMS messages.')
        self.sms_text.config(state='disabled')
        self.sms_text.tag_config('ts', foreground='#8b949e')
        self.sms_text.tag_config('body', foreground='#e6edf3')
        self.sms_text.tag_config('hint', foreground='#8b949e')

        # Accounts panel (bottom part of right)
        acct_outer = tk.LabelFrame(right, text='  Accounts  ',
                                    font=('Segoe UI', 9, 'bold'),
                                    bg='#161b22', fg='#58a6ff',
                                    highlightbackground='#30363d', highlightthickness=1,
                                    relief='groove', bd=1)
        acct_outer.pack(fill='x', pady=(0, 2))

        acct_top = tk.Frame(acct_outer, bg='#161b22')
        acct_top.pack(fill='x', padx=8, pady=(4, 4))

        configured = len([a for a in self.accounts if a.get('username') and a.get('api_key')])
        self.slots_lbl = tk.Label(acct_top, text=self._slots_text(configured),
                                  font=('Segoe UI', 9, 'bold'), bg='#161b22',
                                  fg='#f85149' if configured >= MAX_ACCOUNTS else '#3fb950')
        self.slots_lbl.pack(side='left')

        tk.Button(acct_top, text='Save', font=('Segoe UI', 8, 'bold'),
                  bg='#238636', fg='white', activebackground='#2ea043',
                  relief='flat', padx=10, pady=1, cursor='hand2',
                  command=self._save_accounts).pack(side='right')

        self._acct_entries = []
        acct_grid = tk.Frame(acct_outer, bg='#161b22')
        acct_grid.pack(fill='x', padx=8, pady=(0, 8))

        for i in range(MAX_ACCOUNTS):
            acct = self.accounts[i] if i < len(self.accounts) else {}
            row = tk.Frame(acct_grid, bg='#161b22')
            row.pack(fill='x', pady=(0, 3))

            has_creds = bool(acct.get('username') and acct.get('api_key'))
            dot_color = '#3fb950' if has_creds else '#30363d'
            dot = tk.Label(row, text='●', font=('Segoe UI', 10),
                          bg='#161b22', fg=dot_color)
            dot.pack(side='left', padx=(0, 4))

            tk.Label(row, text=f'{i+1}', font=('Consolas', 8, 'bold'),
                     bg='#161b22', fg='#58a6ff', width=2).pack(side='left')

            e_user = tk.Entry(row, font=('Consolas', 8), bg='#0d1117', fg='#e6edf3',
                              insertbackground='#e6edf3', relief='flat', width=22,
                              highlightthickness=1, highlightbackground='#30363d')
            e_user.pack(side='left', padx=(4, 3), ipady=1)
            e_user.insert(0, acct.get('username', ''))

            e_key = tk.Entry(row, font=('Consolas', 8), bg='#0d1117', fg='#e6edf3',
                             insertbackground='#e6edf3', relief='flat',
                             highlightthickness=1, highlightbackground='#30363d')
            e_key.pack(side='left', fill='x', expand=True, padx=(0, 0), ipady=1)
            e_key.insert(0, acct.get('api_key', ''))

            self._acct_entries.append((e_user, e_key, dot))

    def _slots_text(self, configured):
        txt = f'{configured}/{MAX_ACCOUNTS}'
        if configured >= MAX_ACCOUNTS:
            txt += '  FULL'
        return txt

    def _save_accounts(self):
        accounts = []
        for e_user, e_key, dot in self._acct_entries:
            u = e_user.get().strip()
            k = e_key.get().strip()
            has = bool(u and k)
            dot.config(fg='#3fb950' if has else '#30363d')
            if u or k:
                accounts.append({'username': u, 'api_key': k})
        save_accounts(accounts)
        self.accounts = accounts
        self._init_apis()
        configured = len([a for a in accounts if a.get('username') and a.get('api_key')])
        self.slots_lbl.config(
            text=self._slots_text(configured),
            fg='#f85149' if configured >= MAX_ACCOUNTS else '#3fb950'
        )
        self.info_lbl.config(text='Accounts saved', fg='#3fb950')
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

    def _load_numbers(self):
        def do():
            self.root.after(0, self.status_lbl.config, {'text': 'loading...', 'fg': '#8b949e'})
            self.numbers = []
            self._number_account_map = {}
            total_loaded = 0

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
                           {'text': 'live', 'fg': '#3fb950'})
        threading.Thread(target=do, daemon=True).start()

    def _refresh_list(self):
        sel_num = self._get_selected_number()
        for item in self.tree.get_children():
            self.tree.delete(item)
        sel_iid = None
        for num in self.numbers:
            info = self.data.get(num, {})
            acct_idx = self._number_account_map.get(num, info.get('account_idx', -1))
            acct_label = str(acct_idx + 1) if acct_idx >= 0 else '-'
            code = ''
            if info.get('codes'):
                code = info['codes'][-1].get('code', '')
            iid = self.tree.insert('', 'end', values=(num, acct_label, code))
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
                        if self._selected_number:
                            self.root.after(0, lambda: self._show_sms(self._selected_number))
                        self.root.after(0, self.status_lbl.config,
                                        {'text': 'live', 'fg': '#3fb950'})
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
            if self._selected_number:
                self.root.after(0, lambda: self._show_sms(self._selected_number))
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
                        {'text': 'live', 'fg': '#3fb950'})

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
