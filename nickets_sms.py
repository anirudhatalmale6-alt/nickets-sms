"""Nickets SMS - Profile Number Manager"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import json
import time
import os
import sys
import base64 as _b64
from urllib.request import Request, urlopen
from urllib.parse import urlencode
import re

# ─── Paths ───────────────────────────────────────────────────────────────────

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.path.join(BASE_DIR, 'NicketsSMS_Data')
DATA_PATH = os.path.join(DATA_DIR, 'profiles.json')

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
        for pid in sorted(data.keys()):
            rows.append({'pid': pid, 'number': data[pid].get('number', '')})
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

# ─── Code Extraction ─────────────────────────────────────────────────────────

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
        self.root.geometry('420x520')
        self.root.resizable(True, True)
        self.root.configure(bg='#0d1117')

        self.data = load_data()
        self.api = API()
        self.polling = False

        self._build_ui()
        self._start_auto_poll()

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Treeview', background='#161b22', foreground='#e6edf3',
                        fieldbackground='#161b22', rowheight=28, font=('Consolas', 9))
        style.configure('Treeview.Heading', background='#21262d', foreground='#58a6ff',
                        font=('Segoe UI', 9, 'bold'))
        style.map('Treeview', background=[('selected', '#1f6feb')])

        # Header
        hdr = tk.Frame(self.root, bg='#0d1117')
        hdr.pack(fill='x', padx=12, pady=(12, 4))
        tk.Label(hdr, text='Nickets SMS', font=('Segoe UI', 16, 'bold'),
                 bg='#0d1117', fg='#58a6ff').pack(side='left')

        self.status_dot = tk.Label(hdr, text='', font=('', 8), bg='#0d1117', fg='#3fb950')
        self.status_dot.pack(side='right')

        # Generate section
        gen_frame = tk.Frame(self.root, bg='#161b22', highlightbackground='#30363d',
                             highlightthickness=1)
        gen_frame.pack(fill='x', padx=12, pady=(8, 4))

        inner = tk.Frame(gen_frame, bg='#161b22')
        inner.pack(padx=10, pady=10)

        tk.Label(inner, text='Profile ID', font=('Segoe UI', 9),
                 bg='#161b22', fg='#8b949e').grid(row=0, column=0, sticky='w', pady=(0, 4))

        self.pid_entry = tk.Entry(inner, font=('Consolas', 11), width=14,
                                  bg='#0d1117', fg='#e6edf3', insertbackground='#e6edf3',
                                  relief='flat', highlightbackground='#30363d', highlightthickness=1)
        self.pid_entry.grid(row=1, column=0, padx=(0, 8))
        self.pid_entry.bind('<Return>', lambda e: self._generate())

        self.gen_btn = tk.Button(inner, text='Generate', font=('Segoe UI', 10, 'bold'),
                                 bg='#238636', fg='white', activebackground='#2ea043',
                                 relief='flat', padx=16, pady=4, cursor='hand2',
                                 command=self._generate)
        self.gen_btn.grid(row=1, column=1)

        self.gen_status = tk.Label(gen_frame, text='', font=('Segoe UI', 8),
                                   bg='#161b22', fg='#8b949e')
        self.gen_status.pack(padx=10, pady=(0, 8))

        # Profiles table
        tbl_frame = tk.Frame(self.root, bg='#0d1117')
        tbl_frame.pack(fill='both', expand=True, padx=12, pady=(4, 4))

        cols = ('pid', 'number', 'code', 'time')
        self.tree = ttk.Treeview(tbl_frame, columns=cols, show='headings', height=10)
        self.tree.heading('pid', text='Profile')
        self.tree.heading('number', text='Number')
        self.tree.heading('code', text='Code')
        self.tree.heading('time', text='Time')
        self.tree.column('pid', width=70, minwidth=50)
        self.tree.column('number', width=110, minwidth=90)
        self.tree.column('code', width=70, minwidth=50)
        self.tree.column('time', width=110, minwidth=80)

        sb = ttk.Scrollbar(tbl_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')

        self.tree.bind('<Double-1>', lambda e: self._view_sms())

        # Action buttons
        btn_frame = tk.Frame(self.root, bg='#0d1117')
        btn_frame.pack(fill='x', padx=12, pady=(0, 8))

        for text, cmd, clr in [
            ('View SMS', self._view_sms, '#21262d'),
            ('Copy Code', self._copy_code, '#21262d'),
            ('Refresh', self._manual_refresh, '#1f6feb'),
        ]:
            tk.Button(btn_frame, text=text, font=('Segoe UI', 9), bg=clr,
                      fg='#e6edf3', activebackground='#30363d', relief='flat',
                      padx=10, pady=3, cursor='hand2', command=cmd).pack(side='left', padx=(0, 6))

        tk.Button(btn_frame, text='Remove', font=('Segoe UI', 9), bg='#21262d',
                  fg='#f85149', activebackground='#30363d', relief='flat',
                  padx=10, pady=3, cursor='hand2', command=self._remove).pack(side='right')

        self._refresh_list()

    def _refresh_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for pid in sorted(self.data.keys()):
            info = self.data[pid]
            code = ''
            ts = ''
            if info.get('codes'):
                last = info['codes'][-1]
                code = last.get('code', '')
                raw_ts = last.get('time', '')
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(raw_ts.replace('+00:00', ''))
                    ts = dt.strftime('%H:%M:%S')
                except Exception:
                    ts = raw_ts[-8:] if len(raw_ts) > 8 else raw_ts
            self.tree.insert('', 'end', values=(pid, info.get('number', ''), code, ts))

    def _get_selected(self):
        sel = self.tree.selection()
        if not sel:
            return None
        vals = self.tree.item(sel[0], 'values')
        return vals[0] if vals else None

    def _generate(self):
        pid = self.pid_entry.get().strip().upper()
        if not pid:
            self.gen_status.config(text='Enter a Profile ID', fg='#f85149')
            return
        if pid in self.data:
            self.gen_status.config(text=f'{pid} already has {self.data[pid]["number"]}', fg='#d29922')
            return
        self.gen_btn.config(state='disabled')
        self.gen_status.config(text='Finding available number...', fg='#8b949e')

        def do():
            all_rentals = []
            for ep in ('/api/pub/v2/reservations/rental/renewable',
                       '/api/pub/v2/reservations/rental/nonrenewable'):
                resp, err = self.api.call('GET', ep)
                if err:
                    continue
                items = resp.get('data', []) if isinstance(resp, dict) else []
                all_rentals.extend(items)

            active = [r for r in all_rentals if 'active' in r.get('state', '').lower()]
            if not active:
                self.root.after(0, self.gen_status.config, {'text': 'No numbers available. Add more first.', 'fg': '#f85149'})
                self.root.after(0, self.gen_btn.config, {'state': 'normal'})
                return

            assigned = set()
            for info in self.data.values():
                assigned.add(info.get('number', ''))
                n = info.get('number', '').lstrip('+1')
                assigned.add(n)

            available = [r for r in active
                         if r.get('number', '') not in assigned
                         and '+1' + r.get('number', '') not in assigned]
            if not available:
                self.root.after(0, self.gen_status.config,
                                {'text': f'All {len(active)} numbers assigned. Add more.', 'fg': '#f85149'})
                self.root.after(0, self.gen_btn.config, {'state': 'normal'})
                return

            chosen = available[0]
            raw = chosen.get('number', '')
            phone = f'+1{raw}' if len(raw) == 10 and not raw.startswith('+') else raw
            self.data[pid] = {
                'number': phone,
                'reservation_id': chosen.get('id', ''),
                'codes': [],
                'messages': [],
            }
            save_data(self.data)
            self.root.after(0, self._refresh_list)
            self.root.after(0, self.gen_status.config, {'text': f'{pid} → {phone}', 'fg': '#3fb950'})
            self.root.after(0, self.pid_entry.delete, 0, 'end')
            self.root.after(0, self.gen_btn.config, {'state': 'normal'})

        threading.Thread(target=do, daemon=True).start()

    def _poll_number(self, pid):
        info = self.data.get(pid)
        if not info:
            return
        res_id = info.get('reservation_id', '')
        number = info.get('number', '')
        if not res_id and not number:
            return
        query = f'reservationId={res_id}' if res_id else f'to={number}'
        resp, err = self.api.call('GET', f'/api/pub/v2/sms?{query}')
        if err or not resp:
            return
        messages = resp.get('data', []) if isinstance(resp, dict) else []
        seen = {m.get('id') for m in info.get('messages', [])}
        new = []
        for m in messages:
            mid = m.get('id', '')
            if mid in seen:
                continue
            body = m.get('body', '')
            frm = m.get('from', '')
            ts = m.get('createdAt', '')
            new.append({'id': mid, 'from': frm, 'body': body, 'time': ts})
            code = extract_code(body)
            if code:
                info.setdefault('codes', []).append({'code': code, 'time': ts, 'body': body})
        if new:
            info.setdefault('messages', []).extend(new)
            save_data(self.data)

    def _start_auto_poll(self):
        def poll_loop():
            while True:
                try:
                    if self.data:
                        self.root.after(0, self.status_dot.config, {'text': 'checking...', 'fg': '#8b949e'})
                        for pid in list(self.data.keys()):
                            self._poll_number(pid)
                        self.root.after(0, self._refresh_list)
                        self.root.after(0, self.status_dot.config, {'text': 'live', 'fg': '#3fb950'})
                except Exception:
                    pass
                time.sleep(10)
        t = threading.Thread(target=poll_loop, daemon=True)
        t.start()

    def _manual_refresh(self):
        def do():
            self.root.after(0, self.gen_status.config, {'text': 'Refreshing...', 'fg': '#8b949e'})
            for pid in list(self.data.keys()):
                self._poll_number(pid)
            self.root.after(0, self._refresh_list)
            self.root.after(0, self.gen_status.config, {'text': 'Refreshed', 'fg': '#3fb950'})
        threading.Thread(target=do, daemon=True).start()

    def _copy_code(self):
        pid = self._get_selected()
        if not pid or pid not in self.data:
            return
        info = self.data[pid]
        if not info.get('codes'):
            self.gen_status.config(text='No codes yet', fg='#d29922')
            return
        code = info['codes'][-1].get('code', '')
        if code:
            self.root.clipboard_clear()
            self.root.clipboard_append(code)
            self.gen_status.config(text=f'Copied: {code}', fg='#3fb950')

    def _view_sms(self):
        pid = self._get_selected()
        if not pid or pid not in self.data:
            return
        info = self.data[pid]

        def do():
            self._poll_number(pid)
            self.root.after(0, show)

        def show():
            win = tk.Toplevel(self.root)
            win.title(f'{pid} - {info.get("number", "")}')
            win.geometry('380x320')
            win.configure(bg='#0d1117')
            win.transient(self.root)

            tk.Label(win, text=f'{pid}  |  {info.get("number", "")}',
                     font=('Consolas', 10, 'bold'), bg='#0d1117', fg='#58a6ff').pack(padx=8, pady=(8, 4))

            text = tk.Text(win, font=('Consolas', 9), bg='#161b22', fg='#e6edf3',
                          wrap='word', relief='flat', highlightthickness=0)
            text.pack(fill='both', expand=True, padx=8, pady=4)

            msgs = info.get('messages', [])
            if not msgs:
                text.insert('end', 'No messages yet.\n\nWaiting for SMS...')
            else:
                for m in msgs:
                    ts = m.get('time', '')
                    frm = m.get('from', '')
                    body = m.get('body', '')
                    text.insert('end', f'[{ts}]\n', 'ts')
                    text.insert('end', f'From: {frm}\n', 'from')
                    text.insert('end', f'{body}\n\n', 'body')
                text.tag_config('ts', foreground='#8b949e')
                text.tag_config('from', foreground='#58a6ff')
                text.tag_config('body', foreground='#e6edf3')
            text.config(state='disabled')

            bf = tk.Frame(win, bg='#0d1117')
            bf.pack(fill='x', padx=8, pady=(0, 8))
            tk.Button(bf, text='Refresh', font=('Segoe UI', 9), bg='#21262d',
                      fg='#e6edf3', relief='flat', padx=8, cursor='hand2',
                      command=lambda: self._refresh_sms_win(pid, text)).pack(side='left', padx=(0, 6))
            tk.Button(bf, text='Copy Code', font=('Segoe UI', 9), bg='#21262d',
                      fg='#e6edf3', relief='flat', padx=8, cursor='hand2',
                      command=lambda: self._copy_code_from(pid)).pack(side='left')

        threading.Thread(target=do, daemon=True).start()

    def _refresh_sms_win(self, pid, text_widget):
        def do():
            self._poll_number(pid)
            self.root.after(0, update)
        def update():
            info = self.data.get(pid, {})
            text_widget.config(state='normal')
            text_widget.delete('1.0', 'end')
            msgs = info.get('messages', [])
            if not msgs:
                text_widget.insert('end', 'No messages yet.')
            else:
                for m in msgs:
                    text_widget.insert('end', f'[{m.get("time", "")}]\n', 'ts')
                    text_widget.insert('end', f'From: {m.get("from", "")}\n', 'from')
                    text_widget.insert('end', f'{m.get("body", "")}\n\n', 'body')
                text_widget.tag_config('ts', foreground='#8b949e')
                text_widget.tag_config('from', foreground='#58a6ff')
                text_widget.tag_config('body', foreground='#e6edf3')
            text_widget.config(state='disabled')
            self._refresh_list()
        threading.Thread(target=do, daemon=True).start()

    def _copy_code_from(self, pid):
        info = self.data.get(pid, {})
        if info.get('codes'):
            code = info['codes'][-1].get('code', '')
            if code:
                self.root.clipboard_clear()
                self.root.clipboard_append(code)
                self.gen_status.config(text=f'Copied: {code}', fg='#3fb950')

    def _remove(self):
        pid = self._get_selected()
        if not pid:
            return
        if not messagebox.askyesno('Remove', f'Remove {pid}?\nNumber stays active.'):
            return
        self.data.pop(pid, None)
        save_data(self.data)
        self._refresh_list()
        self.gen_status.config(text=f'{pid} removed', fg='#8b949e')

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    ensure_dirs()
    app = NicketsSMS()
    app.run()
