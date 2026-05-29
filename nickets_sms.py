"""Nickets SMS"""

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

# ─── Paths ───────────────────────────────────────────────────────────────────

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.path.join(BASE_DIR, 'NicketsSMS_Data')
DATA_PATH = os.path.join(DATA_DIR, 'sms_data.json')

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

# ─── Web Sheet Sync ──────────────────────────────────────────────────────────

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

# ─── API ─────────────────────────────────────────────────────────────────────

_API_USER = 'chingmarkjohn12@gmail.com'
_API_KEY = 'RT9tYFQIBajurTBrDuLzzfMfR1bmcOFRqsjDgTjw6tZPmdhRYOsFKeIDYFvwoZG'
_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
_BASE = 'https://www.textverified.com'

class API:
    def __init__(self):
        self._token = None
        self._exp = 0

    def _auth(self):
        if self._token and time.time() < self._exp:
            return self._token, None
        try:
            req = Request(f'{_BASE}/api/pub/v2/auth', data=b'', method='POST')
            req.add_header('X-API-USERNAME', _API_USER)
            req.add_header('X-API-KEY', _API_KEY)
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

# ─── App ─────────────────────────────────────────────────────────────────────

class NicketsSMS:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('Nickets SMS')
        self.root.geometry('460x420')
        self.root.resizable(True, True)
        self.root.configure(bg='#0d1117')

        self.data = load_data()
        self.api = API()
        self.numbers = []

        self._build_ui()
        self._load_numbers()
        self._start_auto_poll()

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Treeview', background='#161b22', foreground='#e6edf3',
                        fieldbackground='#161b22', rowheight=28, font=('Consolas', 10))
        style.configure('Treeview.Heading', background='#21262d', foreground='#58a6ff',
                        font=('Segoe UI', 9, 'bold'))
        style.map('Treeview', background=[('selected', '#1f6feb')])

        hdr = tk.Frame(self.root, bg='#0d1117')
        hdr.pack(fill='x', padx=12, pady=(12, 8))
        tk.Label(hdr, text='Nickets SMS', font=('Segoe UI', 16, 'bold'),
                 bg='#0d1117', fg='#58a6ff').pack(side='left')
        self.status_lbl = tk.Label(hdr, text='loading...', font=('Segoe UI', 8),
                                    bg='#0d1117', fg='#8b949e')
        self.status_lbl.pack(side='right')

        tbl_frame = tk.Frame(self.root, bg='#0d1117')
        tbl_frame.pack(fill='both', expand=True, padx=12, pady=(0, 4))

        cols = ('number', 'code', 'time')
        self.tree = ttk.Treeview(tbl_frame, columns=cols, show='headings', height=12)
        self.tree.heading('number', text='Number')
        self.tree.heading('code', text='Last Code')
        self.tree.heading('time', text='Time')
        self.tree.column('number', width=140, minwidth=120)
        self.tree.column('code', width=100, minwidth=70)
        self.tree.column('time', width=140, minwidth=100)

        sb = ttk.Scrollbar(tbl_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')

        self.tree.bind('<Double-1>', lambda e: self._view_sms())

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
                  command=self._manual_refresh).pack(side='left')

        self.info_lbl = tk.Label(self.root, text='', font=('Segoe UI', 8),
                                  bg='#0d1117', fg='#8b949e')
        self.info_lbl.pack(padx=12, pady=(0, 6))

    def _load_numbers(self):
        def do():
            self.root.after(0, self.status_lbl.config, {'text': 'loading numbers...', 'fg': '#8b949e'})
            all_rentals = []
            for ep in ('/api/pub/v2/reservations/rental/renewable',
                       '/api/pub/v2/reservations/rental/nonrenewable'):
                resp, err = self.api.call('GET', ep)
                if err:
                    continue
                items = resp.get('data', []) if isinstance(resp, dict) else []
                all_rentals.extend(items)

            active = [r for r in all_rentals if 'active' in r.get('state', '').lower()]
            self.numbers = []
            for r in active:
                raw = r.get('number', '')
                phone = f'+1{raw}' if len(raw) == 10 and not raw.startswith('+') else raw
                res_id = r.get('id', '')
                if phone not in self.data:
                    self.data[phone] = {
                        'reservation_id': res_id,
                        'codes': [],
                        'messages': [],
                    }
                else:
                    self.data[phone]['reservation_id'] = res_id
                self.numbers.append(phone)

            save_data(self.data)
            self.root.after(0, self._refresh_list)
            count = len(self.numbers)
            self.root.after(0, self.status_lbl.config,
                            {'text': f'{count} number{"s" if count != 1 else ""} active', 'fg': '#3fb950'})
        threading.Thread(target=do, daemon=True).start()

    def _refresh_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for num in self.numbers:
            info = self.data.get(num, {})
            code = ''
            ts = ''
            if info.get('codes'):
                last = info['codes'][-1]
                code = last.get('code', '')
                raw_ts = last.get('time', '')
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(raw_ts.replace('+00:00', '+00:00').split('+')[0])
                    ts = dt.strftime('%Y-%m-%d %H:%M')
                except Exception:
                    ts = raw_ts[:19] if len(raw_ts) > 19 else raw_ts
            self.tree.insert('', 'end', values=(num, code, ts))

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
        resp, err = self.api.call('GET', f'/api/pub/v2/sms?reservationId={res_id}')
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
                                        {'text': f'{n} number{"s" if n != 1 else ""} | live', 'fg': '#3fb950'})
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
        all_rentals = []
        for ep in ('/api/pub/v2/reservations/rental/renewable',
                   '/api/pub/v2/reservations/rental/nonrenewable'):
            resp, err = self.api.call('GET', ep)
            if err:
                continue
            items = resp.get('data', []) if isinstance(resp, dict) else []
            all_rentals.extend(items)
        active = [r for r in all_rentals if 'active' in r.get('state', '').lower()]
        self.numbers = []
        for r in active:
            raw = r.get('number', '')
            phone = f'+1{raw}' if len(raw) == 10 and not raw.startswith('+') else raw
            res_id = r.get('id', '')
            if phone not in self.data:
                self.data[phone] = {'reservation_id': res_id, 'codes': [], 'messages': []}
            else:
                self.data[phone]['reservation_id'] = res_id
            self.numbers.append(phone)
        save_data(self.data)
        n = len(self.numbers)
        self.root.after(0, self.status_lbl.config,
                        {'text': f'{n} number{"s" if n != 1 else ""} active', 'fg': '#3fb950'})

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
            win.geometry('400x340')
            win.configure(bg='#0d1117')
            win.transient(self.root)

            tk.Label(win, text=num, font=('Consolas', 12, 'bold'),
                     bg='#0d1117', fg='#58a6ff').pack(padx=10, pady=(10, 4))

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
                    frm = m.get('from', '')
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
    app = NicketsSMS()
    app.run()
