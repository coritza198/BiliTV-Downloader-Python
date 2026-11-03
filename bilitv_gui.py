#!/usr/bin/env python3
"""Tkinter GUI for the BiliTV Downloader backend."""
from __future__ import annotations
import http.cookiejar
import queue
import re
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import requests
import bilitv_downloader as core


class GUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('BiliTV Downloader — Python GUI')
        self.geometry('850x670')
        self.minsize(700, 560)
        self.events = queue.Queue()
        self.stop_flag = threading.Event()
        self.worker = None
        self.output = tk.StringVar(value=str(Path.home() / 'Downloads' / 'BiliTV'))
        self.prefix = tk.StringVar(value='tập_')
        self.start_number = tk.StringVar(value='1')
        self.cookies = tk.StringVar()
        self.cookie_source = tk.StringVar(value="Không dùng")
        self.subtitle = tk.BooleanVar(value=True)
        self.retry = tk.IntVar(value=3)
        self.status = tk.StringVar(value='Sẵn sàng')
        self.build_ui()
        self.after(100, self.drain)

    def build_ui(self):
        outer = ttk.Frame(self, padding=16)
        outer.pack(fill='both', expand=True)
        ttk.Label(outer, text='BiliTV Downloader', font=('Segoe UI', 18, 'bold')).pack(anchor='w')
        ttk.Label(outer, text='Dán mỗi link trên một dòng. Có thể đặt tên riêng bằng dấu |, ví dụ: URL | Tap 01').pack(anchor='w', pady=(3, 10))
        self.links = tk.Text(outer, height=10, wrap='none', font=('Consolas', 10))
        self.links.pack(fill='both', expand=True)
        linkbuttons = ttk.Frame(outer)
        linkbuttons.pack(fill='x', pady=(6, 12))
        ttk.Button(linkbuttons, text='Nhập file TXT', command=self.import_txt).pack(side='left')
        ttk.Button(linkbuttons, text='Xóa danh sách', command=lambda: self.links.delete('1.0', 'end')).pack(side='left', padx=8)

        settings = ttk.LabelFrame(outer, text='Cài đặt', padding=10)
        settings.pack(fill='x')
        settings.columnconfigure(1, weight=1)
        ttk.Label(settings, text='Thư mục lưu').grid(row=0, column=0, sticky='w', pady=4)
        ttk.Entry(settings, textvariable=self.output).grid(row=0, column=1, sticky='ew', padx=8)
        ttk.Button(settings, text='Chọn...', command=self.pick_folder).grid(row=0, column=2)
        ttk.Label(settings, text='Tên file (tiền tố)').grid(row=1, column=0, sticky='w', pady=4)
        naming = ttk.Frame(settings)
        naming.grid(row=1, column=1, columnspan=2, sticky='ew', padx=8)
        naming.columnconfigure(1, weight=1)
        ttk.Entry(naming, textvariable=self.prefix).grid(row=0, column=0, sticky='ew')
        ttk.Label(naming, text='Số bắt đầu').grid(row=0, column=1, padx=(16, 6))
        ttk.Entry(naming, textvariable=self.start_number, width=9).grid(row=0, column=2)
        self.preview = ttk.Label(settings, text='')
        self.preview.grid(row=2, column=1, columnspan=2, sticky='w', padx=8, pady=(0, 5))
        self.prefix.trace_add('write', self.update_preview)
        self.start_number.trace_add('write', self.update_preview)
        self.update_preview()
        ttk.Label(settings, text='Nguồn cookie').grid(row=3, column=0, sticky='w', pady=4)
        ttk.Combobox(settings, textvariable=self.cookie_source, values=('Không dùng', 'Chrome', 'Edge', 'File TXT'), state='readonly').grid(row=3, column=1, sticky='ew', padx=8)
        ttk.Label(settings, text='File cookie (nếu chọn TXT)').grid(row=4, column=0, sticky='w', pady=4)
        ttk.Entry(settings, textvariable=self.cookies).grid(row=4, column=1, sticky='ew', padx=8)
        ttk.Button(settings, text='Chọn...', command=self.pick_cookies).grid(row=4, column=2)

        ttk.Checkbutton(settings, text='Tải phụ đề nếu có', variable=self.subtitle).grid(row=5, column=0, columnspan=2, sticky='w', pady=5)
        ttk.Label(settings, text='Số lần thử').grid(row=5, column=2, sticky='w')
        ttk.Spinbox(settings, from_=1, to=10, textvariable=self.retry, width=4).grid(row=5, column=2, sticky='e')

        bar = ttk.Frame(outer)
        bar.pack(fill='x', pady=(12, 6))
        self.start_btn = ttk.Button(bar, text='▶ Bắt đầu tải', command=self.start)
        self.start_btn.pack(side='left')
        self.stop_btn = ttk.Button(bar, text='Dừng sau video hiện tại', command=self.stop, state='disabled')
        self.stop_btn.pack(side='left', padx=8)
        ttk.Label(bar, textvariable=self.status).pack(side='right')
        self.progress = ttk.Progressbar(outer, mode='determinate', maximum=100)
        self.progress.pack(fill='x', pady=(0, 8))
        ttk.Label(outer, text='Nhật ký tải').pack(anchor='w')
        self.log = tk.Text(outer, height=9, state='disabled', wrap='word', font=('Consolas', 9))
        self.log.pack(fill='both', expand=True)

    def update_preview(self, *_):
        try:
            names = [numbered_name(self.prefix.get(), self.start_number.get(), i) + '.mp4' for i in range(1, 4)]
            self.preview.configure(text='Ví dụ: ' + ', '.join(names))
        except ValueError:
            self.preview.configure(text='Tên file hoặc số bắt đầu không hợp lệ')

    def import_txt(self):
        f = filedialog.askopenfilename(filetypes=[('Text files', '*.txt'), ('All files', '*.*')])
        if f:
            try:
                self.links.insert('end', Path(f).read_text(encoding='utf-8-sig').rstrip() + '\n')
            except OSError as e:
                messagebox.showerror('Lỗi', str(e))

    def pick_folder(self):
        p = filedialog.askdirectory()
        if p:
            self.output.set(p)

    def pick_cookies(self):
        p = filedialog.askopenfilename(filetypes=[('Cookie TXT', '*.txt'), ('All files', '*.*')])
        if p:
            self.cookies.set(p)

    def append_log(self, msg):
        self.log.configure(state='normal')
        self.log.insert('end', msg + '\n')
        self.log.see('end')
        self.log.configure(state='disabled')

    def start(self):
        if self.worker and self.worker.is_alive():
            return
        try:
            jobs = parse_jobs(self.links.get('1.0', 'end'))
            if not jobs:
                raise ValueError('Hãy nhập ít nhất một URL.')
            prefix = validate_name(self.prefix.get().strip())
            start_number = self.start_number.get().strip()
            generated = [name or numbered_name(prefix, start_number, i) for i, (_, name) in enumerate(jobs, 1)]
            if len({n.casefold() for n in generated}) != len(generated):
                raise ValueError('Tên file bị trùng giữa các video. Hãy đổi tên riêng hoặc số bắt đầu.')
            attempts = int(self.retry.get())
            if not 1 <= attempts <= 10:
                raise ValueError('Số lần thử phải từ 1 đến 10.')
            ffmpeg = core.ffmpeg_path()
            if not ffmpeg:
                raise ValueError('Không tìm thấy FFmpeg. Hãy cài FFmpeg hoặc đặt ffmpeg.exe cạnh chương trình.')
            output = Path(self.output.get()).expanduser().resolve()
            source = self.cookie_source.get()
            cookie = (self.cookies.get().strip() or None) if source == 'File TXT' else None
            if source == 'File TXT' and not cookie:
                raise ValueError('Hãy chọn file cookie TXT.')
            if cookie and not Path(cookie).is_file():
                raise ValueError('Không tìm thấy file cookies.')
        except (ValueError, tk.TclError) as e:
            messagebox.showerror('Dữ liệu chưa hợp lệ', str(e))
            return
        self.stop_flag.clear()
        self.progress['value'] = 0
        self.start_btn.configure(state='disabled')
        self.stop_btn.configure(state='normal')
        self.worker = threading.Thread(target=self.download, args=(jobs, output, prefix, start_number, cookie, source, attempts, self.subtitle.get(), ffmpeg), daemon=True)
        self.worker.start()

    def stop(self):
        self.stop_flag.set()
        self.status.set('Đang chờ video hiện tại hoàn thành...')
        self.stop_btn.configure(state='disabled')

    def download(self, jobs, output, prefix, start_number, cookie, source, attempts, subtitle, ffmpeg):
        stats = {'ok': 0, 'skip': 0, 'fail': 0}
        try:
            output.mkdir(parents=True, exist_ok=True)
            session = core.make_session()
            if source in ('Chrome', 'Edge'):
                self.events.put(('log', f'Đang đọc cookie Bilibili.tv từ {source} trên máy này...'))
                count = core.load_browser_cookies(session, source.lower())
                self.events.put(('log', f'Đã nạp {count} cookie Bilibili.tv (không hiển thị giá trị).'))
            elif source == 'File TXT':
                core.load_cookies(session, cookie)
            for i, (url, name) in enumerate(jobs, 1):
                if self.stop_flag.is_set():
                    break
                stem = name or numbered_name(prefix, start_number, i)
                self.events.put(('status', f'Đang tải {i}/{len(jobs)}: {stem}'))
                self.events.put(('log', f'[{i}/{len(jobs)}] {stem}: {url}'))
                try:
                    result = core.run_job(session, url, i, len(jobs), output, prefix, attempts, subtitle, ffmpeg, stem_override=stem, progress_callback=lambda label, done, total, index=i: self.events.put(('transfer', (index, len(jobs), label, done, total))))
                    stats[result] += 1
                    self.events.put(('log', f'  {"Đã lưu" if result == "ok" else "Đã bỏ qua"}: {stem}.mp4'))
                except (ValueError, RuntimeError, requests.RequestException, OSError, subprocess.TimeoutExpired) as e:
                    stats['fail'] += 1
                    self.events.put(('log', f'  LỖI: {e}'))
                self.events.put(('progress', 100 * i / len(jobs)))
        except (ValueError, RuntimeError, OSError, http.cookiejar.LoadError) as e:
            self.events.put(('log', f'Lỗi khởi tạo: {e}'))
        finally:
            self.events.put(('done', f'Hoàn tất: {stats["ok"]} thành công, {stats["skip"]} bỏ qua, {stats["fail"]} lỗi.' + (' Đã dừng sớm.' if self.stop_flag.is_set() else '')))

    def drain(self):
        try:
            while True:
                typ, value = self.events.get_nowait()
                if typ == 'log':
                    self.append_log(value)
                elif typ == 'status':
                    self.status.set(value)
                elif typ == 'progress':
                    self.progress['value'] = value
                elif typ == 'transfer':
                    i, n, label, done, total = value
                    self.status.set(f'{i}/{n} · {label}: {done / 1048576:.1f} MB' + (f' / {total / 1048576:.1f} MB' if total else ''))
                    if total:
                        self.progress['value'] = 100 * ((i - 1) + min(done / total, 1)) / n
                elif typ == 'done':
                    self.status.set(value)
                    self.append_log(value)
                    self.start_btn.configure(state='normal')
                    self.stop_btn.configure(state='disabled')
        except queue.Empty:
            pass
        self.after(100, self.drain)


def validate_name(name):
    if not name or len(name) > 100 or name in ('.', '..') or name.endswith(('.', ' ')) or re.search(r'[<>:"/\\|?*\x00-\x1f]', name):
        raise ValueError(f'Tên file không hợp lệ: {name!r}')
    if name.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}:
        raise ValueError('Tên file trùng tên thiết bị Windows.')
    return name


def numbered_name(prefix, start_number, index):
    validate_name(prefix)
    start_number = str(start_number).strip()
    if not start_number.isascii() or not start_number.isdecimal():
        raise ValueError('Số bắt đầu phải là số nguyên không âm (ví dụ: 22).')
    number = int(start_number) + index - 1
    name = prefix + str(number).zfill(len(start_number))
    return validate_name(name)

def parse_jobs(text):
    jobs = []
    used = set()
    for line_no, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        url, sep, name = line.partition('|')
        url = url.strip()
        try:
            core.parse_link(url)
            if sep:
                name = validate_name(name.strip())
                if name.casefold() in used:
                    raise ValueError('Tên file bị trùng')
                used.add(name.casefold())
            else:
                name = None
        except ValueError as e:
            raise ValueError(f'Dòng {line_no}: {e}') from e
        jobs.append((url, name))
    return jobs


if __name__ == '__main__':
    GUI().mainloop()
