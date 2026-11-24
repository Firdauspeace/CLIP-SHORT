import json
import math
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from urllib.parse import urlsplit


HERE = Path(sys.executable if getattr(sys, 'frozen', False) else __file__).resolve().parent
HOSTS = ('youtube.com', 'youtu.be', 'facebook.com', 'fb.watch', 'fb.com',
         'tiktok.com', 'instagram.com', 'instagr.am')
QUALITY = ('Terbaik', '1080p', '720p', '480p')
MODES = ('Muat turun sahaja', 'Render penuh', 'Potong manual', 'Auto-cut')
FRAMES = ('9:16  ·  Shorts', '16:9  ·  Landskap', '1:1  ·  Persegi', '4:5  ·  Feed', 'Nisbah asal')
SIZES = ((1080, 1920), (1920, 1080), (1080, 1080), (1080, 1350), None)
PALETTE = ('#60e3cb', '#a9a0ff', '#ffb487', '#ff8bb9', '#f4d76f')
VIDEO_TYPES = {'.mp4', '.mov', '.mkv', '.webm', '.avi', '.m4v', '.ts', '.mxf', '.flv', '.wmv', '.3gp', '.ogv', '.mpg', '.mpeg'}
HIDDEN = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def executable(name):
    filename = name + '.exe'
    bundled = Path(getattr(sys, '_MEIPASS', HERE))
    for path in (HERE / 'bin' / filename, HERE / filename, bundled / filename):
        if path.is_file():
            return str(path)
    return shutil.which(name)


def run(args, update=None):
    lines = []
    with subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          encoding='utf-8', errors='replace', creationflags=HIDDEN) as process:
        for line in process.stdout:
            line = line.strip()
            if line:
                lines.append(line)
                if update:
                    update(line)
        if process.wait():
            raise ValueError('\n'.join(lines[-8:]) or f'Proses gagal ({process.returncode}).')
    return lines


def downloader():
    commands = []
    binary = executable('yt-dlp')
    if binary:
        commands.append([binary])
    python = shutil.which('python') if getattr(sys, 'frozen', False) else str(Path(sys.executable).with_name('python.exe'))
    if python:
        commands.append([python, '-m', 'yt_dlp'])
    # A Microsoft Store Python install can leave a launcher that fails outside its runtime.
    packages = Path(os.environ.get('LOCALAPPDATA', '')) / 'Packages'
    for site in sorted(packages.glob('PythonSoftwareFoundation.Python.*/LocalCache/local-packages/Python*/site-packages'), reverse=True):
        if python and (site / 'yt_dlp' / '__main__.py').is_file():
            commands.append([python, '-c',
                             "import runpy,sys; sys.path.append(sys.argv.pop(1)); runpy.run_module('yt_dlp',run_name='__main__')",
                             str(site)])
    for command in commands:
        try:
            run([*command, '--ignore-config', '--version'])
            return command
        except (OSError, ValueError):
            continue
    raise ValueError('yt-dlp tidak ditemui. Letakkan yt-dlp.exe dalam folder bin atau pasang yt-dlp untuk Python.')


def validate_url(value):
    parsed = urlsplit(value)
    host = (parsed.hostname or '').lower()
    if (parsed.scheme != 'https' or parsed.username is not None or parsed.port not in (None, 443)
            or not any(host == domain or host.endswith('.' + domain) for domain in HOSTS)):
        raise ValueError('Tampal pautan HTTPS YouTube, Facebook, TikTok atau Instagram.')
    return value


def download_args(url, quality, ffmpeg, staging):
    args = ['--ignore-config', '--no-playlist', '--playlist-items', '1', '--no-live-from-start',
            '--match-filter', '!is_live', '--no-mtime', '--newline', '--no-colors',
            '--encoding', 'utf-8', '--socket-timeout', '20', '--retries', '2', '--extractor-retries', '1',
            '--ffmpeg-location', ffmpeg, '--merge-output-format', 'mp4', '-f', 'bv*+ba/b',
            '--windows-filenames', '-P', str(staging), '-o', '%(title).110B [%(id)s].%(ext)s',
            '--print', 'after_move:CLIP_FILE:%(filepath)s', '--progress']
    sorting = 'ext:mp4:m4a'
    if quality != 'Terbaik':
        sorting = f'res:{quality[:-1]},{sorting}'
    args += ['-S', sorting]
    if node := executable('node'):
        args += ['--js-runtimes', 'node:' + node]
    args += ['--remote-components', 'ejs:github']
    return [*args, '--', url]


def download(url, quality, ffmpeg, staging, update):
    lines = run([*downloader(), *download_args(url, quality, ffmpeg, staging)], update=update)
    for line in reversed(lines):
        if line.startswith('CLIP_FILE:'):
            source = Path(line.removeprefix('CLIP_FILE:')).resolve()
            if source.parent == staging.resolve() and source.is_file():
                return source
    raise ValueError('Tiada video yang boleh dimuat turun untuk pautan ini.')


def time_value(value):
    parts = value.strip().replace(',', '.').split(':')
    if len(parts) > 3 or any(not re.fullmatch(r'\d+(?:\.\d+)?', part) for part in parts):
        raise ValueError('Masukkan masa dalam saat atau format minit:saat.')
    if any('.' in part for part in parts[:-1]) or any(float(part) >= 60 for part in parts[1:]):
        raise ValueError('Semak minit dan saat dalam masa yang dimasukkan.')
    result = sum(float(part) * 60 ** i for i, part in enumerate(reversed(parts)))
    if not math.isfinite(result):
        raise ValueError('Masa yang dimasukkan terlalu besar.')
    return result


def video_info(ffprobe, source):
    info = json.loads('\n'.join(run([ffprobe, '-v', 'error', '-show_streams', '-show_format',
                                     '-of', 'json', str(source)])))
    streams = info.get('streams', [])
    video = next((s for s in streams if s.get('codec_type') == 'video'
                  and not s.get('disposition', {}).get('attached_pic')), None)
    if video is None:
        raise ValueError('Fail ini tiada trek video.')
    for candidate in (video.get('duration'), info.get('format', {}).get('duration')):
        try:
            duration = float(candidate)
            if math.isfinite(duration) and duration > 0:
                break
        except (TypeError, ValueError):
            continue
    else:
        raise ValueError('Durasi video tidak dapat dibaca.')
    audio = next((s['index'] for s in streams if s.get('codec_type') == 'audio'), None)
    return duration, video['index'], audio


def silence_positions(ffmpeg, source, audio):
    if audio is None:
        return []
    lines = run([ffmpeg, '-hide_banner', '-nostdin', '-nostats', '-i', str(source),
                 '-map', f'0:{audio}', '-af', 'silencedetect=n=-35dB:d=0.35', '-f', 'null', '-'])
    positions = []
    for line in lines:
        match = re.search(r'silence_end:\s*([\d.]+)\s*\|\s*silence_duration:\s*([\d.]+)', line)
        if match:
            end, length = map(float, match.groups())
            positions.append(end - length / 2)
    return positions


def auto_ranges(duration, target, pauses):
    start = 0.0
    # shortcut: Audio gaps are a timing cue. Add speech analysis if semantic highlights are needed.
    while duration - start > target + .05:
        preferred = start + target
        if duration - preferred < target * .25:
            preferred = start + (duration - start) / 2
        earliest = max(start + target * .5, preferred - min(4, target * .2))
        latest = min(start + target, duration - target * .25, preferred + min(2, target * .1))
        end = min((point for point in pauses if earliest <= point <= latest),
                  key=lambda point: abs(point - preferred), default=preferred)
        yield start, end
        start = end
    yield start, duration


def publish(source, folder, name):
    candidate = folder / name
    number = 2
    while True:
        try:
            # The staging directory is on the output volume. Windows rename never overwrites.
            return source.rename(candidate)
        except FileExistsError:
            candidate = folder / f'{Path(name).stem} ({number}){Path(name).suffix}'
            number += 1


def render(ffmpeg, source, destination, start, end, video, audio, size, crop, update):
    filters = 'scale=trunc(iw*sar/2)*2:trunc(ih/2)*2,setsar=1'
    if size:
        w, h = size
        if crop:
            filters += f',scale={w}:{h}:force_original_aspect_ratio=increase:force_divisible_by=2,crop={w}:{h}'
        else:
            filters += f',scale={w}:{h}:force_original_aspect_ratio=decrease:force_divisible_by=2,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2'
    duration = end - start
    command = [ffmpeg, '-hide_banner', '-nostdin', '-v', 'error', '-nostats',
               '-progress', 'pipe:1', '-ss', f'{start:.6f}', '-i', str(source),
               '-t', f'{duration:.6f}', '-map', f'0:{video}']
    if audio is not None:
        command += ['-map', f'0:{audio}', '-c:a', 'aac', '-b:a', '160k']
    command += ['-vf', filters, '-r', '30', '-c:v', 'libx264', '-preset', 'fast',
                '-crf', '19', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(destination)]

    def progress(line):
        if line.startswith('out_time_us=') and line[12:].lstrip('-').isdigit():
            update(f'Render {min(100, max(0, int(int(line[12:]) / 1e4 / duration)))}%')

    run(command, update=progress)


class App:
    def __init__(self, root):
        self.root = root
        self.events = queue.Queue()
        self.busy = False
        self.results = []
        self.preview_path = None
        self.preview_id = 0
        self.preview_image = None
        root.title('CLIP SHORT')
        root.geometry('1130x760')
        root.minsize(980, 695)
        root.configure(bg='#111125')
        root.protocol('WM_DELETE_WINDOW', self.close)

        self.style = style = ttk.Style()
        style.theme_use('clam')
        background, card, field = '#111125', '#1c1d36', '#131529'
        border, ink, muted, accent = '#3e4060', '#f4f3ff', '#b9bbd8', PALETTE[0]
        style.configure('TFrame', background=background)
        style.configure('Card.TFrame', background=card)
        style.configure('Rail.TFrame', background='#191a30')
        style.configure('TLabel', background=background, foreground=ink, font=('Segoe UI', 10))
        style.configure('Card.TLabel', background=card)
        style.configure('CardTitle.TLabel', background=card, font=('Segoe UI', 11, 'bold'))
        style.configure('CardMuted.TLabel', background=card, foreground=muted)
        style.configure('Muted.TLabel', foreground=muted)
        style.configure('Title.TLabel', font=('Segoe UI', 29, 'bold'))
        style.configure('RailTitle.TLabel', background='#191a30', font=('Segoe UI', 15, 'bold'))
        for name, tone in zip(('Mint', 'Violet', 'Peach'), PALETTE, strict=False):
            style.configure(f'{name}.TLabel', background=card, foreground=tone, font=('Segoe UI', 11, 'bold'))
        style.configure('Mark.TLabel', background=accent, foreground='#172413',
                        font=('Segoe UI Symbol', 19), anchor='center')
        style.configure('TButton', background='#292b4a', foreground=ink, bordercolor=border,
                        lightcolor='#292b4a', darkcolor='#292b4a', focuscolor=accent,
                        font=('Segoe UI', 10, 'bold'), padding=(12, 6))
        style.map('TButton', background=[('pressed', '#242540'), ('active', '#3c3d62')])
        style.configure('Nav.TButton', anchor='w', padding=(10, 10), borderwidth=0)
        style.configure('Active.Nav.TButton', background='#36345b', foreground='#e0d9ff', lightcolor='#36345b', darkcolor='#36345b')
        style.configure('Primary.TButton', background=accent, foreground='#162411',
                        bordercolor=accent, lightcolor=accent, darkcolor=accent,
                        focuscolor='#385223', font=('Segoe UI', 11, 'bold'), padding=(12, 7))
        style.map('Primary.TButton', background=[('disabled', '#3b4160'), ('pressed', '#a9a0ff'), ('active', '#bdf7e9')],
                  foreground=[('disabled', '#b4b9d3')])
        for number, tone in enumerate(PALETTE):
            style.configure(f'Tone{number}.TButton', foreground=tone, padding=(5, 6))
            style.configure(f'Active.Tone{number}.TButton', foreground='#14152b', background=tone,
                            bordercolor=tone, lightcolor=tone, darkcolor=tone, padding=(5, 6))
            style.map(f'Active.Tone{number}.TButton', background=[('active', tone)])
        for widget, padding in (('TEntry', 5), ('TCombobox', 4)):
            style.configure(widget, fieldbackground=field, background=field, foreground=ink,
                            insertcolor=ink, arrowcolor=muted, bordercolor=border,
                            lightcolor=field, darkcolor=field, padding=padding)
            style.map(widget, fieldbackground=[('disabled', card), ('readonly', field)],
                      bordercolor=[('focus', accent), ('disabled', '#29374c')],
                      foreground=[('disabled', '#74849b'), ('readonly', ink)],
                      selectbackground=[('readonly', field)], selectforeground=[('readonly', ink)])
        root.option_add('*TCombobox*Listbox.background', field)
        root.option_add('*TCombobox*Listbox.foreground', ink)
        root.option_add('*TCombobox*Listbox.selectBackground', accent)
        root.option_add('*TCombobox*Listbox.selectForeground', '#162411')
        root.option_add('*TCombobox*Listbox.font', ('Segoe UI', 10))
        style.configure('Horizontal.TProgressbar', background=accent, lightcolor=accent,
                        darkcolor=accent, bordercolor=field, troughcolor=field, thickness=4)

        root.columnconfigure(1, weight=1)
        root.rowconfigure(0, weight=1)
        rail = ttk.Frame(root, style='Rail.TFrame', padding=(14, 22))
        rail.grid(row=0, column=0, sticky='ns')
        ttk.Label(rail, text='▶', style='Mark.TLabel', width=3, padding=(0, 4)).pack(anchor='w', pady=(0, 9))
        ttk.Label(rail, text='CLIP SHORT', style='RailTitle.TLabel').pack(anchor='w', pady=(0, 24))
        self.nav = {}
        for name in ('Studio', 'Pustaka', 'Gaya'):
            button = ttk.Button(rail, text=name, width=13, style='Nav.TButton', command=lambda page=name: self.show_page(page))
            button.pack(fill='x', pady=(0, 7))
            self.nav[name] = button

        panel = ttk.Frame(root, padding=(20, 18))
        panel.grid(row=0, column=1, sticky='nsew')
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(1, weight=1)
        header = ttk.Frame(panel)
        header.grid(row=0, column=0, sticky='ew', pady=(0, 12))
        self.page_title, self.page_hint = tk.StringVar(), tk.StringVar()
        ttk.Label(header, textvariable=self.page_title, style='Title.TLabel').pack(anchor='w')
        ttk.Label(header, textvariable=self.page_hint, style='Muted.TLabel').pack(anchor='w', pady=(2, 0))
        self.pages = {name: ttk.Frame(panel) for name in self.nav}
        for page in self.pages.values():
            page.grid(row=1, column=0, sticky='nsew')
        studio = self.pages['Studio']
        studio.columnconfigure(0, weight=3, minsize=430)
        studio.columnconfigure(1, weight=2, minsize=310)
        studio.rowconfigure(0, weight=1)
        form = ttk.Frame(studio)
        form.grid(row=0, column=0, sticky='nsew', padx=(0, 12))
        form.columnconfigure(0, weight=1)
        form.rowconfigure(3, weight=1)

        self.source = tk.StringVar()
        self.folder = tk.StringVar(value=str(HERE / 'Exports'))
        self.quality = tk.StringVar(value=QUALITY[0])
        self.mode = tk.StringVar(value=MODES[3])
        self.frame = tk.StringVar(value=FRAMES[0])
        self.fit = tk.StringVar(value='Muatkan semua')
        self.duration = tk.StringVar(value='30')
        self.start = tk.StringVar(value='0')
        self.end = tk.StringVar()
        self.status = tk.StringVar(value='Sedia')
        self.fields = {}
        paths = ttk.Frame(form, style='Card.TFrame', padding=(13, 8))
        paths.grid(row=0, column=0, sticky='ew', pady=(0, 10))
        paths.columnconfigure(1, weight=1)
        ttk.Label(paths, text='Sumber video', style='Mint.TLabel').grid(row=0, columnspan=3, sticky='w', pady=(0, 4))
        self.path_row(paths, 1, 'Pautan / fail', self.source, 'Pilih video', self.choose_source)
        self.path_row(paths, 2, 'Simpan ke', self.folder, 'Pilih folder', self.choose_folder)

        settings = ttk.Frame(form, style='Card.TFrame', padding=(13, 9))
        settings.grid(row=1, column=0, sticky='ew', pady=(0, 10))
        settings.columnconfigure((0, 1, 2), weight=1, uniform='setting')
        ttk.Label(settings, text='Tetapan klip', style='Violet.TLabel').grid(row=0, columnspan=3, sticky='w', pady=(0, 6))
        modes = ttk.Frame(settings, style='Card.TFrame')
        modes.grid(row=1, columnspan=3, sticky='ew', pady=(0, 5))
        modes.columnconfigure((0, 1, 2, 3), weight=1, uniform='mode')
        self.mode_buttons = []
        for number, label in enumerate(('Muat turun', 'Render penuh', 'Manual', 'Auto-cut')):
            button = ttk.Button(modes, text=label, command=lambda mode=MODES[number]: self.mode.set(mode))
            button.grid(row=0, column=number, sticky='ew', padx=(0, 5 if number < 3 else 0))
            self.mode_buttons.append(button)
        self.field(settings, 2, 0, 'Kualiti pautan', self.quality, QUALITY)
        self.field(settings, 2, 1, 'Bingkai', self.frame, FRAMES)
        self.field(settings, 2, 2, 'Isi bingkai', self.fit, ('Muatkan semua', 'Crop tengah'))
        self.auto_fields = self.field(settings, 4, 0, 'Auto-cut (saat)', self.duration)
        self.manual_fields = (*self.field(settings, 4, 0, 'Masa mula', self.start),
                              *self.field(settings, 4, 1, 'Masa akhir', self.end))
        self.hint = ttk.Label(settings, style='CardMuted.TLabel', wraplength=395)
        self.hint.grid(row=6, column=0, columnspan=3, sticky='w', pady=(5, 0))

        actions = ttk.Frame(form)
        actions.grid(row=2, column=0, sticky='ew', pady=(0, 11))
        actions.columnconfigure(0, weight=1)
        self.action = ttk.Button(actions, text='Mula', style='Primary.TButton', command=self.start_job)
        self.action.grid(row=0, column=0, sticky='ew', padx=(0, 10))
        ttk.Button(actions, text='Buka folder hasil', command=self.open_folder).grid(row=0, column=1, sticky='e')

        activity = ttk.Frame(form, style='Card.TFrame', padding=(13, 9))
        activity.grid(row=3, column=0, sticky='nsew')
        activity.columnconfigure(0, weight=1)
        activity.rowconfigure(2, weight=1)
        ttk.Label(activity, text='Aktiviti', style='Peach.TLabel').grid(row=0, column=0, sticky='w')
        ttk.Label(activity, textvariable=self.status, style='CardMuted.TLabel', wraplength=270, justify='right').grid(row=0, column=1, sticky='e')
        self.progress = ttk.Progressbar(activity, mode='determinate', maximum=100)
        self.progress.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(7, 7))
        self.log = tk.Text(activity, width=1, height=3, bg=field, fg=ink, relief='flat', padx=10,
                           pady=8, font=('Consolas', 10), state='disabled', wrap='word')
        self.log.grid(row=2, column=0, columnspan=2, sticky='nsew')
        self.build_preview(studio)
        self.build_library(self.pages['Pustaka'])
        self.build_appearance(self.pages['Gaya'])
        for var in (self.mode, self.frame, self.source):
            var.trace_add('write', self.refresh)
        self.refresh()
        self.show_page('Studio')
        root.after(100, self.poll)

    def show_page(self, name):
        self.pages[name].tkraise()
        for page, button in self.nav.items():
            button.configure(style='Active.Nav.TButton' if name == page else 'Nav.TButton')
        titles = {
            'Studio': ('Buat klip', 'YouTube  /  Facebook  /  TikTok  /  Instagram'),
            'Pustaka': ('Pustaka video', 'Video yang disimpan dalam folder hasil.'),
            'Gaya': ('Gaya studio', 'Pilih warna antaramuka CLIP SHORT.'),
        }
        title, hint = titles[name]
        self.page_title.set(title)
        self.page_hint.set(hint)
        if name == 'Pustaka':
            self.refresh_library()

    def build_preview(self, studio):
        card = ttk.Frame(studio, style='Card.TFrame', padding=(13, 10))
        card.grid(row=0, column=1, sticky='nsew')
        card.columnconfigure(0, weight=1)
        card.rowconfigure(6, weight=1)
        ttk.Label(card, text='Pratonton', style='Mint.TLabel').grid(row=0, sticky='w', pady=(0, 8))
        self.preview = tk.Canvas(card, height=190, width=280, bg='#101126', highlightthickness=0)
        self.preview.grid(row=1, sticky='ew')
        self.preview.bind('<Configure>', self.draw_preview)
        self.preview_text = tk.StringVar(value='Pilih fail video untuk pratonton')
        ttk.Label(card, textvariable=self.preview_text, style='CardMuted.TLabel', wraplength=268).grid(
            row=2, sticky='w', pady=(7, 7))
        self.play = ttk.Button(card, text='Main video', command=lambda: self.open_video(self.preview_path))
        self.play.grid(row=3, sticky='ew')
        self.play.state(['disabled'])
        ttk.Label(card, text='Garis masa klip', style='Violet.TLabel').grid(row=4, sticky='w', pady=(14, 7))
        self.timeline = tk.Canvas(card, width=280, height=31, bg='#131529', highlightthickness=0)
        self.timeline.grid(row=5, sticky='ew', pady=(0, 7))
        self.timeline.bind('<Configure>', self.draw_timeline)
        self.timeline.bind('<Button-1>', self.select_range)
        self.clips = self.make_list(card, height=4)
        self.clips.grid(row=6, sticky='nsew')
        self.clips.bind('<<ListboxSelect>>', self.select_clip)
        self.clips.bind('<Double-Button-1>', lambda _: self.open_video(self.preview_path))

    def build_library(self, page):
        card = ttk.Frame(page, style='Card.TFrame', padding=15)
        card.pack(fill='both', expand=True)
        card.columnconfigure(0, weight=1)
        card.rowconfigure(1, weight=1)
        self.library_count = tk.StringVar()
        ttk.Label(card, textvariable=self.library_count, style='Violet.TLabel').grid(row=0, sticky='w', pady=(0, 12))
        ttk.Button(card, text='Buka folder hasil', command=self.open_folder).grid(row=0, column=2, sticky='e')
        self.library = self.make_list(card, height=5)
        self.library.grid(row=1, columnspan=3, sticky='nsew', pady=(8, 12))
        self.library.bind('<Double-Button-1>', lambda _: self.open_library_preview())
        ttk.Button(card, text='Pratonton pilihan', style='Primary.TButton', command=self.open_library_preview).grid(row=2, sticky='w')
        ttk.Button(card, text='Muat semula', command=self.refresh_library).grid(row=2, column=2, sticky='e')

    def build_appearance(self, page):
        card = ttk.Frame(page, style='Card.TFrame', padding=16)
        card.pack(fill='x')
        ttk.Label(card, text='Warna aksen', style='Peach.TLabel').grid(row=0, columnspan=5, sticky='w', pady=(0, 12))
        self.swatches = []
        for index, name in enumerate(('Pudina', 'Lavender', 'Pic', 'Ros', 'Emas')):
            button = ttk.Button(card, text=name, width=10, command=lambda number=index: self.apply_accent(number))
            button.grid(row=1, column=index, padx=(0, 8), sticky='w')
            self.swatches.append(button)
        self.apply_accent(0)

    def apply_accent(self, index):
        color = PALETTE[index]
        self.style.configure('Primary.TButton', background=color, bordercolor=color, lightcolor=color, darkcolor=color)
        self.style.map('Primary.TButton', background=[('disabled', '#3b4160'), ('pressed', PALETTE[1]), ('active', color)])
        self.style.configure('Mark.TLabel', background=color)
        self.style.configure('Horizontal.TProgressbar', background=color, lightcolor=color, darkcolor=color)
        for number, button in enumerate(self.swatches):
            button.configure(style=f'{"Active." if index == number else ""}Tone{number}.TButton')

    def make_list(self, parent, height):
        return tk.Listbox(parent, height=height, width=1, bg='#131529', fg='#f4f3ff',
                          highlightthickness=0, borderwidth=0, activestyle='none',
                          selectbackground='#39375e', selectforeground='#f4f3ff',
                          font=('Segoe UI', 10), exportselection=False)

    def refresh_library(self):
        self.library.delete(0, 'end')
        self.library_paths = []
        value = self.folder.get().strip()
        if value:
            try:
                folder = Path(value).expanduser().resolve()
                self.library_paths = sorted((p for p in folder.iterdir() if p.suffix.lower() in VIDEO_TYPES and p.is_file()),
                                            key=lambda p: p.stat().st_mtime, reverse=True)
            except OSError:
                pass
        for path in self.library_paths:
            self.library.insert('end', '  ' + path.name)
        total = len(self.library_paths)
        self.library_count.set(f'{total} video' if total else 'Belum ada video dalam folder ini')

    def open_library_preview(self):
        if selected := self.library.curselection():
            self.show_page('Studio')
            self.set_preview(self.library_paths[selected[0]])

    def draw_preview(self, _=None):
        width = self.preview.winfo_width()
        self.preview.delete('all')
        if self.preview_image:
            self.preview.create_image(width / 2, 95, image=self.preview_image)
            return
        self.preview.create_oval(width / 2 - 32, 63, width / 2 + 32, 127, fill='#302a51', outline='')
        self.preview.create_text(width / 2 + 2, 95, text='▶', fill=PALETTE[1], font=('Segoe UI Symbol', 25))

    def set_preview(self, path):
        self.preview_path = Path(path)
        self.preview_id += 1
        self.preview_image = None
        self.preview_text.set(self.preview_path.name)
        self.play.state(['!disabled'])
        self.draw_preview()
        threading.Thread(target=self.load_thumbnail, args=(self.preview_id, self.preview_path), daemon=True).start()

    def load_thumbnail(self, token, path):
        ffmpeg = executable('ffmpeg')
        if not ffmpeg:
            return
        filters = 'thumbnail=6,scale=280:176:force_original_aspect_ratio=decrease,setsar=1'
        try:
            frame = subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-nostdin', '-i', str(path),
                                    '-map', '0:V:0', '-vf', filters, '-frames:v', '1', '-f', 'image2pipe',
                                    '-c:v', 'png', '-threads', '1', '-'], capture_output=True,
                                   timeout=20, creationflags=HIDDEN, check=True).stdout
            if frame:
                self.events.put(('preview', (token, frame)))
        except (OSError, subprocess.SubprocessError):
            pass

    def draw_timeline(self, _=None):
        self.timeline.delete('all')
        width = self.timeline.winfo_width()
        if not self.results:
            self.timeline.create_text(8, 15, text='Belum ada klip dalam sesi ini', anchor='w', fill='#9b9dbf', font=('Segoe UI', 9))
            return
        duration = self.results[-1][2]
        for index, (_, start, end) in enumerate(self.results):
            left = width * start / duration
            right = width * end / duration
            self.timeline.create_rectangle(left, 4, max(left + 1, right - 2), 26, outline='', fill=PALETTE[index % len(PALETTE)])

    def select_range(self, event):
        if self.results:
            moment = event.x / max(1, self.timeline.winfo_width()) * self.results[-1][2]
            for index, (_, start, end) in enumerate(self.results):
                if start <= moment <= end:
                    self.clips.selection_clear(0, 'end')
                    self.clips.selection_set(index)
                    self.clips.see(index)
                    self.select_clip()
                    break

    def select_clip(self, _=None):
        if selected := self.clips.curselection():
            self.set_preview(self.results[selected[0]][0])

    def open_video(self, path):
        if path:
            try:
                os.startfile(path)
            except OSError as error:
                messagebox.showerror('CLIP SHORT', str(error))

    def path_row(self, panel, row, label, var, action, callback):
        ttk.Label(panel, text=label, style='Card.TLabel').grid(row=row, column=0, sticky='w', padx=(0, 13), pady=3)
        ttk.Entry(panel, textvariable=var).grid(row=row, column=1, sticky='ew', padx=(0, 10), pady=3)
        ttk.Button(panel, text=action, width=12, command=callback).grid(row=row, column=2, sticky='ew', pady=3)

    def field(self, panel, row, column, label, var, values=None):
        pad = (0, 8 if column < 2 else 0)
        caption = ttk.Label(panel, text=label, style='CardMuted.TLabel')
        caption.grid(row=row, column=column, sticky='w', padx=pad, pady=(2, 2))
        field = (ttk.Combobox(panel, textvariable=var, values=values, state='readonly', width=10)
                 if values else ttk.Entry(panel, textvariable=var, width=10))
        field.grid(row=row + 1, column=column, sticky='ew', padx=pad, pady=(0, 4))
        self.fields[label] = field
        return caption, field

    def refresh(self, *_):
        mode = self.mode.get()
        for index, button in enumerate(self.mode_buttons):
            button.configure(style=f'{"Active." if mode == MODES[index] else ""}Tone{index}.TButton')
        enabled = {'Kualiti pautan': self.source.get().strip().lower().startswith(('https://', 'http://')),
                   'Bingkai': mode != MODES[0], 'Isi bingkai': mode != MODES[0] and self.frame.get() != FRAMES[-1],
                   'Auto-cut (saat)': mode == MODES[3], 'Masa mula': mode == MODES[2], 'Masa akhir': mode == MODES[2]}
        for name, usable in enabled.items():
            field = self.fields[name]
            field.configure(state=('readonly' if isinstance(field, ttk.Combobox) else 'normal') if usable else 'disabled')
        for widgets, visible in ((self.auto_fields, mode == MODES[3]), (self.manual_fields, mode == MODES[2])):
            for widget in widgets:
                widget.grid() if visible else widget.grid_remove()
        self.hint.configure(text=(
            'Simpan video dalam format sumber yang tersedia.',
            'Eksport video penuh sebagai MP4.',
            'Masukkan masa dalam saat atau minit:saat. Masa akhir kosong bermaksud hingga tamat.',
            'Bahagi video mengikut durasi sasaran dan utamakan jeda audio berdekatan titik potong.',
        )[MODES.index(mode)])

    def choose_source(self):
        path = filedialog.askopenfilename(filetypes=[('Video', '*.mp4 *.mov *.mkv *.webm *.avi *.m4v *.ts *.mxf'), ('Semua fail', '*.*')])
        if path:
            self.source.set(path)
            self.set_preview(path)

    def choose_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.folder.set(path)

    def open_folder(self):
        try:
            path = Path(self.folder.get().strip()).expanduser().resolve()
            if not self.folder.get().strip() or not path.is_dir():
                raise ValueError('Folder hasil belum tersedia.')
            os.startfile(path)
        except (OSError, ValueError) as error:
            messagebox.showerror('CLIP SHORT', str(error))

    def close(self):
        if self.busy:
            messagebox.showinfo('CLIP SHORT', 'Tunggu proses semasa selesai dahulu.')
            return
        self.root.destroy()

    def start_job(self):
        try:
            value = self.source.get().strip()
            if not value or not self.folder.get().strip():
                raise ValueError('Masukkan sumber video dan folder hasil.')
            remote = value.lower().startswith(('https://', 'http://'))
            source = validate_url(value) if remote else Path(value).expanduser().resolve()
            if not remote and not source.is_file():
                raise ValueError('Fail video tidak ditemui.')
            mode = MODES.index(self.mode.get())
            if not remote and mode == 0:
                raise ValueError('Muat turun sahaja memerlukan pautan video.')
            start = time_value(self.start.get()) if mode == 2 else 0
            end = time_value(self.end.get()) if mode == 2 and self.end.get().strip() else None
            target = time_value(self.duration.get()) if mode == 3 else 30
            if mode == 3 and not 5 <= target <= 180:
                raise ValueError('Gunakan durasi auto-cut antara 5 hingga 180 saat.')
            if end is not None and end <= start:
                raise ValueError('Masa akhir mesti selepas masa mula.')
            folder = Path(self.folder.get().strip()).expanduser().resolve()
            settings = (source, remote, folder, mode, self.quality.get(),
                        SIZES[FRAMES.index(self.frame.get())], self.fit.get() == 'Crop tengah', start, end, target)
        except (OSError, ValueError) as error:
            messagebox.showerror('CLIP SHORT', str(error))
            return
        self.busy = True
        self.action.state(['disabled'])
        self.results.clear()
        self.clips.delete(0, 'end')
        self.draw_timeline()
        if not remote and self.preview_path != source:
            self.set_preview(source)
        self.log.configure(state='normal')
        self.log.delete('1.0', 'end')
        self.log.configure(state='disabled')
        self.progress.configure(value=0)
        self.status.set('Memulakan proses…')
        threading.Thread(target=self.job, args=settings, daemon=True).start()

    def job(self, *settings):
        def emit(kind, message):
            self.events.put((kind, message))

        try:
            count = process_video(*settings, emit)
            emit('done', f'Siap · {count} fail disimpan')
        except Exception as error:
            emit('error', str(error))

    def poll(self):
        status = None
        while True:
            try:
                kind, message = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == 'preview':
                token, data = message
                if token == self.preview_id:
                    self.preview_image = tk.PhotoImage(data=data)
                    self.draw_preview()
                continue
            if kind == 'file':
                path, start, end = message
                if end > start:
                    self.results.append(message)
                    self.clips.insert('end', f'  {len(self.results):02d}   {start:.1f}–{end:.1f}s   {path.name}')
                    self.draw_timeline()
                if len(self.results) <= 1:
                    self.set_preview(path)
                continue
            if kind == 'status':
                status = message
                percent = re.search(r'(\d+(?:\.\d+)?)\s*%', message)
                if percent:
                    self.progress.configure(value=min(100, float(percent.group(1))))
                elif not message.startswith('[download]'):
                    self.progress.configure(value=0)
                continue
            if kind in ('done', 'error'):
                self.busy = False
                self.action.state(['!disabled'])
                status = message if kind == 'done' else 'Proses gagal. Semak butiran di bawah.'
                self.progress.configure(value=100 if kind == 'done' else 0)
                if self.page_title.get() == 'Pustaka video':
                    self.refresh_library()
            self.log.configure(state='normal')
            self.log.insert('end', message + '\n')
            self.log.see('end')
            self.log.configure(state='disabled')
        if status:
            self.status.set(status)
        self.root.after(100, self.poll)


def process_video(source, remote, folder, mode, quality, size, crop, start, end, target, emit):
    ffmpeg, ffprobe = executable('ffmpeg'), executable('ffprobe')
    if not ffmpeg or (mode and not ffprobe):
        raise ValueError('FFmpeg/FFprobe tidak ditemui. Letakkan executable dalam folder bin atau PATH.')
    folder.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.clip-short-', dir=folder) as temp:
        staging = Path(temp)
        if remote:
            emit('status', 'Menghubungi platform…')

            def download_update(line):
                if line.startswith('[download]'):
                    emit('status', line)
                elif not line.startswith('CLIP_FILE:'):
                    emit('log', line)

            source = download(source, quality, ffmpeg, staging, download_update)
        if mode == 0:
            result = publish(source, folder, source.name)
            emit('file', (result, 0, 0))
            emit('log', str(result))
            return 1
        emit('status', 'Membaca video…')
        duration, video, audio = video_info(ffprobe, source)
        if mode == 2 and (start >= duration or (end is not None and end > duration + .05)):
            raise ValueError(f'Masa potong di luar durasi video ({duration:.2f} saat).')
        if mode == 3:
            emit('status', 'Menganalisis jeda audio…')
            ranges = list(auto_ranges(duration, target, silence_positions(ffmpeg, source, audio)))
        else:
            ranges = [(start, duration if end is None else min(end, duration))]
        for number, (begin, finish) in enumerate(ranges, 1):
            label = f'Klip {number}/{len(ranges)}'
            emit('status', f'{label} · Menyediakan render…')
            render(ffmpeg, source, staging / 'render.mp4', begin, finish, video, audio, size, crop,
                   lambda status: emit('status', f'{label} · {status}'))
            suffix = f' - {number:03d}' if mode == 3 else ''
            name = f'{source.stem[:100]} - CLIP SHORT{suffix}.mp4'
            result = publish(staging / 'render.mp4', folder, name)
            emit('file', (result, begin, finish))
            emit('log', f'{begin:07.2f}–{finish:07.2f}s  {result.name}')
        return len(ranges)


if __name__ == '__main__':
    window = tk.Tk()
    App(window)
    window.mainloop()
