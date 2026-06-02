"""Nickets SMS v5.2 - Number Slot Manager (Cloud Sync)"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import json
import time
import os
import sys
from urllib.request import Request, urlopen
import re

# ─── Config ─────────────────────────────────────────────────────────────────

_LOGIN_USER = 'Nickets@gmail.com'
_LOGIN_PASS = 'NickNick#100'
SLOTS_PER_NUMBER = 4

# TextVerified account
_API_USER = 'chingmarkjohn12@gmail.com'
_API_KEY = 'RT9tYFQIBajurTBrDuLzzfMfR1bmcOFRqsjDgTjw6tZPmdhRYOsFKeIDYFvwoZG'

# Cloud sync for shared slot data
_CLOUD_URL = 'https://jsonblob.com/api/jsonBlob/019e8818-776e-7f6e-a176-3dfdac6873d6'
_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

# ─── Paths ──────────────────────────────────────────────────────────────────

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

# ─── Cloud Sync (email slots + notes shared across all VAs) ───────────────

def cloud_pull():
    try:
        req = Request(_CLOUD_URL, headers={'Accept': 'application/json',
                      'User-Agent': _UA})
        with urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return {}

def cloud_push(data):
    shared = {}
    for num, info in data.items():
        slots = info.get('email_slots', ['', '', '', ''])
        notes = info.get('notes', '')
        if any(s.strip() for s in slots) or notes.strip():
            shared[num] = {'email_slots': slots, 'notes': notes}
    try:
        body = json.dumps(shared).encode()
        req = Request(_CLOUD_URL, data=body, method='PUT',
                      headers={'Content-Type': 'application/json',
                               'Accept': 'application/json',
                               'User-Agent': _UA})
        urlopen(req, timeout=10)
    except Exception:
        pass

def cloud_merge(local_data, remote):
    for num, rinfo in remote.items():
        if num not in local_data:
            local_data[num] = {'reservation_id': '', 'codes': [], 'messages': [],
                               'email_slots': rinfo.get('email_slots', ['', '', '', '']),
                               'notes': rinfo.get('notes', '')}
        else:
            local_slots = local_data[num].get('email_slots', ['', '', '', ''])
            remote_slots = rinfo.get('email_slots', ['', '', '', ''])
            merged = []
            for i in range(SLOTS_PER_NUMBER):
                ls = local_slots[i].strip() if i < len(local_slots) else ''
                rs = remote_slots[i].strip() if i < len(remote_slots) else ''
                merged.append(rs if rs else ls)
            local_data[num]['email_slots'] = merged
            rn = rinfo.get('notes', '').strip()
            ln = local_data[num].get('notes', '').strip()
            if rn:
                local_data[num]['notes'] = rn
            elif ln:
                local_data[num]['notes'] = ln

# ─── TextVerified API ──────────────────────────────────────────────────────

_TV_BASE = 'https://www.textverified.com'

class API:
    def __init__(self):
        self._token = None
        self._exp = 0

    def _auth(self):
        if self._token and time.time() < self._exp:
            return self._token, None
        try:
            req = Request(f'{_TV_BASE}/api/pub/v2/auth', data=b'', method='POST')
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

# ─── Login ──────────────────────────────────────────────────────────────────

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

        tk.Button(form, text='Login', font=('Segoe UI', 10, 'bold'),
                  bg='#238636', fg='white', activebackground='#2ea043',
                  relief='flat', cursor='hand2', pady=6,
                  command=self._do_login).pack(fill='x')

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

# ─── Main App ───────────────────────────────────────────────────────────────

class NicketsSMS:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('Nickets SMS v5.2')
        self.root.geometry('980x580')
        self.root.minsize(860, 480)
        self.root.resizable(True, True)
        self.root.configure(bg='#0d1117')

        self.data = load_data()
        self.api = API()
        self.numbers = []
        self._selected_number = None
        self._slot_entries = []

        self._setup_styles()
        self._build_ui()
        self._load_numbers()
        self._start_auto_poll()

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
        self.status_lbl = tk.Label(hdr, text='', font=('Segoe UI', 8),
                                   bg='#0d1117', fg='#8b949e')
        self.status_lbl.pack(side='right')
        self.count_lbl = tk.Label(hdr, text='0 numbers', font=('Segoe UI', 9, 'bold'),
                                  bg='#0d1117', fg='#3fb950')
        self.count_lbl.pack(side='right', padx=(0, 12))

        # Main split
        main = tk.PanedWindow(self.root, orient='horizontal', bg='#30363d',
                              sashwidth=3, sashrelief='flat')
        main.pack(fill='both', expand=True, padx=10, pady=(0, 6))

        # LEFT: Number list
        left = tk.Frame(main, bg='#0d1117')
        main.add(left, width=360, minsize=280)

        tk.Label(left, text='Phone Numbers', font=('Segoe UI', 10, 'bold'),
                 bg='#0d1117', fg='#c9d1d9').pack(anchor='w', pady=(4, 4))

        tbl_frame = tk.Frame(left, bg='#0d1117')
        tbl_frame.pack(fill='both', expand=True)

        cols = ('number', 'slots', 'code', 'notes')
        self.tree = ttk.Treeview(tbl_frame, columns=cols, show='headings', height=20)
        self.tree.heading('number', text='Number')
        self.tree.heading('slots', text='Status')
        self.tree.heading('code', text='Last Code')
        self.tree.heading('notes', text='Notes')
        self.tree.column('number', width=120, minwidth=100)
        self.tree.column('slots', width=50, minwidth=40)
        self.tree.column('code', width=70, minwidth=50)
        self.tree.column('notes', width=80, minwidth=60)

        sb = ttk.Scrollbar(tbl_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')

        self.tree.bind('<<TreeviewSelect>>', lambda e: self._on_number_click())
        self.tree.bind('<Double-1>', self._on_double_click_notes)
        self._edit_widget = None

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

        # RIGHT: SMS + Email Slots
        right = tk.Frame(main, bg='#0d1117')
        main.add(right, minsize=380)

        # SMS panel
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
                                highlightthickness=0)
        self.sms_text.pack(fill='both', expand=True, padx=8, pady=(0, 6))
        self.sms_text.insert('end', 'Click a number on the left to view its SMS messages.')
        self.sms_text.config(state='disabled')
        self.sms_text.tag_config('ts', foreground='#8b949e')
        self.sms_text.tag_config('body', foreground='#e6edf3')
        self.sms_text.tag_config('hint', foreground='#8b949e')

        # Email slots panel (per number)
        slots_frame = tk.LabelFrame(right, text='  Email Slots  ',
                                     font=('Segoe UI', 9, 'bold'),
                                     bg='#161b22', fg='#58a6ff',
                                     highlightbackground='#30363d', highlightthickness=1,
                                     relief='groove', bd=1)
        slots_frame.pack(fill='x', pady=(0, 2))

        slots_top = tk.Frame(slots_frame, bg='#161b22')
        slots_top.pack(fill='x', padx=8, pady=(4, 4))

        self.slots_status_lbl = tk.Label(slots_top, text='Select a number first',
                                          font=('Segoe UI', 9, 'bold'),
                                          bg='#161b22', fg='#8b949e')
        self.slots_status_lbl.pack(side='left')

        self._slot_entries = []
        slots_grid = tk.Frame(slots_frame, bg='#161b22')
        slots_grid.pack(fill='x', padx=8, pady=(0, 8))

        for i in range(SLOTS_PER_NUMBER):
            row = tk.Frame(slots_grid, bg='#161b22')
            row.pack(fill='x', pady=(0, 3))

            dot = tk.Label(row, text='*', font=('Segoe UI', 10),
                          bg='#161b22', fg='#30363d')
            dot.pack(side='left', padx=(0, 4))

            tk.Label(row, text=f'{i+1}', font=('Consolas', 8, 'bold'),
                     bg='#161b22', fg='#58a6ff', width=2).pack(side='left')

            e = tk.Entry(row, font=('Consolas', 9), bg='#0d1117', fg='#e6edf3',
                         insertbackground='#e6edf3', relief='flat',
                         highlightthickness=1, highlightbackground='#30363d')
            e.pack(side='left', fill='x', expand=True, padx=(4, 4), ipady=2)

            save_btn = tk.Button(row, text='Set', font=('Segoe UI', 7, 'bold'),
                                  bg='#238636', fg='white', activebackground='#2ea043',
                                  relief='flat', padx=8, cursor='hand2',
                                  command=lambda idx=i: self._save_slot(idx))
            save_btn.pack(side='right')

            self._slot_entries.append((e, dot))

    def _get_slot_count(self, num):
        info = self.data.get(num, {})
        slots = info.get('email_slots', ['', '', '', ''])
        return len([s for s in slots if s.strip()])

    def _get_slot_status(self, num):
        count = self._get_slot_count(num)
        if count >= SLOTS_PER_NUMBER:
            return 'FULL'
        return f'{count}/{SLOTS_PER_NUMBER}'

    def _load_slots_for_number(self, num):
        info = self.data.get(num, {})
        slots = info.get('email_slots', ['', '', '', ''])
        while len(slots) < SLOTS_PER_NUMBER:
            slots.append('')
        filled = 0
        for i in range(SLOTS_PER_NUMBER):
            e, dot = self._slot_entries[i]
            e.config(state='normal')
            e.delete(0, 'end')
            e.insert(0, slots[i])
            if slots[i].strip():
                dot.config(fg='#3fb950')
                filled += 1
            else:
                dot.config(fg='#30363d')
        if filled >= SLOTS_PER_NUMBER:
            self.slots_status_lbl.config(text='FULL', fg='#f85149')
        else:
            self.slots_status_lbl.config(text=f'{filled}/{SLOTS_PER_NUMBER} used', fg='#3fb950')

    def _save_slot(self, slot_idx):
        num = self._selected_number
        if not num or num not in self.data:
            return
        info = self.data[num]
        slots = info.get('email_slots', ['', '', '', ''])
        while len(slots) < SLOTS_PER_NUMBER:
            slots.append('')
        e, dot = self._slot_entries[slot_idx]
        email = e.get().strip()
        slots[slot_idx] = email
        info['email_slots'] = slots
        save_data(self.data)
        dot.config(fg='#3fb950' if email else '#30363d')
        filled = len([s for s in slots if s.strip()])
        if filled >= SLOTS_PER_NUMBER:
            self.slots_status_lbl.config(text='FULL', fg='#f85149')
        else:
            self.slots_status_lbl.config(text=f'{filled}/{SLOTS_PER_NUMBER} used', fg='#3fb950')
        self._refresh_list()
        self.info_lbl.config(text=f'Slot {slot_idx+1} saved & synced', fg='#3fb950')
        threading.Thread(target=lambda: cloud_push(self.data), daemon=True).start()

    def _on_double_click_notes(self, event):
        region = self.tree.identify('region', event.x, event.y)
        if region != 'cell':
            return
        col = self.tree.identify_column(event.x)
        if col != '#4':
            return
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        vals = self.tree.item(iid, 'values')
        num = vals[0] if vals else None
        if not num:
            return
        bbox = self.tree.bbox(iid, column='notes')
        if not bbox:
            return
        x, y, w, h = bbox
        if self._edit_widget:
            self._edit_widget.destroy()
        entry = tk.Entry(self.tree, font=('Consolas', 9), bg='#0d1117',
                         fg='#e6edf3', insertbackground='#e6edf3', relief='flat',
                         highlightthickness=1, highlightbackground='#58a6ff')
        entry.place(x=x, y=y, width=w, height=h)
        current = self.data.get(num, {}).get('notes', '')
        entry.insert(0, current)
        entry.select_range(0, 'end')
        entry.focus()
        self._edit_widget = entry

        def save(e=None):
            new_val = entry.get().strip()
            if num in self.data:
                self.data[num]['notes'] = new_val
                save_data(self.data)
                threading.Thread(target=lambda: cloud_push(self.data), daemon=True).start()
            entry.destroy()
            self._edit_widget = None
            self._refresh_list()

        entry.bind('<Return>', save)
        entry.bind('<FocusOut>', save)
        entry.bind('<Escape>', lambda e: (entry.destroy(), setattr(self, '_edit_widget', None)))

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
        self._load_slots_for_number(num)

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
            remote = cloud_pull()
            if remote:
                cloud_merge(self.data, remote)
            self._load_numbers_sync()
            cloud_push(self.data)
            self.root.after(0, self._refresh_list)
            self.root.after(0, self.status_lbl.config, {'text': 'live', 'fg': '#3fb950'})
        threading.Thread(target=do, daemon=True).start()

    def _load_numbers_sync(self):
        self.numbers = []
        total = 0
        all_rentals = []
        for ep in ('/api/pub/v2/reservations/rental/renewable',
                   '/api/pub/v2/reservations/rental/nonrenewable'):
            resp, err = self.api.call('GET', ep)
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
                self.data[phone] = {'reservation_id': res_id,
                                    'codes': [], 'messages': [],
                                    'email_slots': ['', '', '', ''],
                                    'notes': ''}
            else:
                self.data[phone]['reservation_id'] = res_id
                if 'email_slots' not in self.data[phone]:
                    self.data[phone]['email_slots'] = ['', '', '', '']
                if 'notes' not in self.data[phone]:
                    self.data[phone]['notes'] = ''
            self.numbers.append(phone)
            total += 1
            self.root.after(0, self.count_lbl.config, {'text': f'{total} numbers'})
        save_data(self.data)

    def _refresh_list(self):
        sel_num = self._get_selected_number()
        for item in self.tree.get_children():
            self.tree.delete(item)
        sel_iid = None
        for num in self.numbers:
            info = self.data.get(num, {})
            status = self._get_slot_status(num)
            code = ''
            if info.get('codes'):
                code = info['codes'][-1].get('code', '')
            notes = info.get('notes', '')
            iid = self.tree.insert('', 'end', values=(num, status, code, notes))
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
                    self.root.after(0, self.status_lbl.config, {'text': 'syncing...', 'fg': '#8b949e'})
                    remote = cloud_pull()
                    if remote:
                        cloud_merge(self.data, remote)
                        save_data(self.data)
                    if self.numbers:
                        for num in list(self.numbers):
                            self._poll_number(num)
                    self.root.after(0, self._refresh_list)
                    if self._selected_number:
                        self.root.after(0, lambda: self._show_sms(self._selected_number))
                        self.root.after(0, lambda: self._load_slots_for_number(self._selected_number))
                    self.root.after(0, self.status_lbl.config,
                                    {'text': 'live', 'fg': '#3fb950'})
                except Exception:
                    pass
        threading.Thread(target=loop, daemon=True).start()

    def _manual_refresh(self):
        def do():
            self.root.after(0, self.info_lbl.config, {'text': 'Refreshing...', 'fg': '#8b949e'})
            remote = cloud_pull()
            if remote:
                cloud_merge(self.data, remote)
            self._load_numbers_sync()
            for num in list(self.numbers):
                self._poll_number(num)
            cloud_push(self.data)
            self.root.after(0, self._refresh_list)
            if self._selected_number:
                self.root.after(0, lambda: self._show_sms(self._selected_number))
                self.root.after(0, lambda: self._load_slots_for_number(self._selected_number))
            self.root.after(0, self.info_lbl.config, {'text': 'Synced', 'fg': '#3fb950'})
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
