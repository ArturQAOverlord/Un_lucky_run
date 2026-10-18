from pathlib import Path
from contextlib import redirect_stdout
from io import StringIO
import json
import math
import random
import re
import textwrap
import unicodedata
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk, font as tkfont

import audio
import main
import data
import Fight
import Tournament


CHARACTERS_DIR = Path(__file__).resolve().parent / 'Characters'
VILLAINS_DIR = Path(__file__).resolve().parent / 'Villains'
LADDER_RUNS_DIR = Path(__file__).resolve().parent / 'LadderRuns'
LORE_PATH = Path(__file__).resolve().parent / 'lore.md'
ENDING_LORE_PATH = Path(__file__).resolve().parent / 'lore_ending.md'
LADDER_INDEX_KEY = 'ladder_index'


def character_files_by_creation_date(living_only=False):
    if not CHARACTERS_DIR.exists():
        return []
    paths = sorted(
        CHARACTERS_DIR.glob('*.txt'),
        key=lambda path: (path.stat().st_ctime, path.name.casefold()),
        reverse=True,
    )
    if living_only:
        paths = [path for path in paths if Fight.is_character_alive(path)]
    return paths


def villain_files_by_ladder_index():
    diagnostics = [f'Папка поиска: {VILLAINS_DIR.resolve()}']
    if not VILLAINS_DIR.exists():
        diagnostics.append('Папка Villains не найдена.')
        return [], [], diagnostics

    villains = []
    invalid_files = []
    paths = sorted(VILLAINS_DIR.glob('*.txt'), key=lambda path: path.name.casefold())
    diagnostics.append(f'Найдено файлов *.txt: {len(paths)}')
    for path in paths:
        try:
            properties = {}
            for line in path.read_text(encoding='utf-8').splitlines():
                key, separator, value = line.partition(':')
                if separator:
                    properties[key.strip()] = value.strip()
        except (OSError, UnicodeError) as error:
            invalid_files.append(f'{path.name}: не удалось прочитать файл ({error})')
            diagnostics.append(f'{path.name}: ошибка чтения ({error})')
            continue
        raw_index = properties.get(LADDER_INDEX_KEY)
        try:
            index = int(raw_index)
        except (TypeError, ValueError):
            reason = f'нет целого индекса {LADDER_INDEX_KEY}' if raw_index is None else (
                f'некорректный индекс {LADDER_INDEX_KEY}: {raw_index!r}'
            )
            invalid_files.append(f'{path.name}: {reason}')
            diagnostics.append(f'{path.name}: пропущен — {reason}')
            continue
        if index < 1:
            reason = f'{LADDER_INDEX_KEY} должен быть больше нуля'
            invalid_files.append(f'{path.name}: {reason}')
            diagnostics.append(f'{path.name}: пропущен — {reason}')
            continue
        villains.append((index, path))
        diagnostics.append(f'{path.name}: принят, {LADDER_INDEX_KEY}={index}')

    villains.sort(key=lambda item: (item[0], item[1].name.casefold()))
    diagnostics.append('Порядок боёв: ' + ', '.join(path.name for _index, path in villains))
    return [path for _index, path in villains], invalid_files, diagnostics


def ladder_run_files():
    if not LADDER_RUNS_DIR.exists():
        return []
    return sorted(LADDER_RUNS_DIR.glob('run_*.json'), key=lambda path: path.name.casefold())


def ladder_run_count():
    return len(ladder_run_files())


def create_ladder_run_record(hero_path, villain_paths):
    hero = Fight.load_character(hero_path)
    now = datetime.now().astimezone().isoformat(timespec='seconds')
    return {
        'started_at': now,
        'updated_at': now,
        'finished_at': None,
        'character': {
            'name': hero.get('name', Path(hero_path).stem),
            'file': Path(hero_path).name,
        },
        'villain_order': [Path(path).stem for path in villain_paths],
        'current_opponent': Path(villain_paths[0]).stem if villain_paths else None,
        'last_opponent': None,
        'fights_completed': 0,
        'last_fight_result': None,
        'result': 'В процессе',
    }


def write_completed_ladder_run_record(record):
    if record.get('result') not in ('Победа', 'Поражение'):
        raise ValueError('В историю записываются только завершённые победой или поражением забеги.')
    LADDER_RUNS_DIR.mkdir(parents=True, exist_ok=True)
    existing_numbers = []
    for path in ladder_run_files():
        suffix = path.stem.partition('_')[2]
        if suffix.isdigit():
            existing_numbers.append(int(suffix))
    run_number = max(existing_numbers, default=0) + 1
    run_path = LADDER_RUNS_DIR / f'run_{run_number:06d}.json'
    while run_path.exists():
        run_number += 1
        run_path = LADDER_RUNS_DIR / f'run_{run_number:06d}.json'

    record['run_number'] = run_number
    record['updated_at'] = datetime.now().astimezone().isoformat(timespec='seconds')
    temporary_path = run_path.with_suffix(run_path.suffix + '.tmp')
    try:
        temporary_path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8',
        )
        temporary_path.replace(run_path)
    except OSError:
        try:
            temporary_path.unlink()
        except OSError:
            pass
        raise
    return run_path


def load_ladder_run_records():
    records = []
    unreadable_files = []
    for path in ladder_run_files():
        try:
            record = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, UnicodeError, json.JSONDecodeError):
            unreadable_files.append(path.name)
            continue
        if isinstance(record, dict):
            records.append(record)
        else:
            unreadable_files.append(path.name)
    def run_number(record):
        try:
            return int(record.get('run_number', 0))
        except (TypeError, ValueError):
            return 0

    records.sort(key=run_number, reverse=True)
    return records, unreadable_files


class CharacterApp:
    def __init__(self, root):
        self.root = root
        root.title('Неудачный забег')
        root.geometry('600x640')
        root.minsize(480, 420)
        self.page_geometry = '600x640'
        self.window_resolution = None
        self.fullscreen = False
        self.dark_theme = False
        self.sound_enabled = True
        self.sound_volume = 0.7
        self.settings_path = Path(__file__).resolve().parent / 'settings.json'
        self._load_settings()
        self.audio = audio.AudioManager(
            enabled=self.sound_enabled, volume=self.sound_volume,
        )
        self._bind_button_sounds()
        root.protocol('WM_DELETE_WINDOW', self.close)
        if self.fullscreen:
            root.attributes('-fullscreen', True)
        elif self.window_resolution:
            root.geometry(self.window_resolution)
        root.bind('<Escape>', self._leave_fullscreen)
        style = ttk.Style(root)
        self.style = style
        style.configure('Menu.TButton', font=('Segoe UI', 13, 'bold'), padding=(16, 14))
        self._apply_theme()
        self.show_intro()

    def _load_settings(self):
        try:
            settings = json.loads(self.settings_path.read_text(encoding='utf-8'))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return
        if not isinstance(settings, dict):
            return
        self.dark_theme = bool(settings.get('dark_theme', False))
        self.fullscreen = bool(settings.get('fullscreen', False))
        self.sound_enabled = bool(settings.get('sound_enabled', self.sound_enabled))
        try:
            self.sound_volume = max(0.0, min(1.0, float(settings.get('sound_volume', self.sound_volume))))
        except (TypeError, ValueError):
            pass
        resolution = settings.get('window_resolution')
        if isinstance(resolution, str) and 'x' in resolution:
            try:
                width, height = (int(part) for part in resolution.split('x', 1))
            except ValueError:
                return
            if width >= 480 and height >= 420:
                self.window_resolution = f'{width}x{height}'

    def _save_settings(self):
        settings = {
            'dark_theme': self.dark_theme,
            'fullscreen': self.fullscreen,
            'window_resolution': self.window_resolution,
            'sound_enabled': self.sound_enabled,
            'sound_volume': self.sound_volume,
        }
        try:
            self.settings_path.write_text(
                json.dumps(settings, ensure_ascii=False, indent=2), encoding='utf-8'
            )
        except OSError:
            pass

    def _bind_button_sounds(self):
        for binding_tag in ('TButton', 'Button', 'TCheckbutton', 'Checkbutton'):
            self.root.bind_class(
                binding_tag, '<ButtonPress-1>', self._play_button_sound, add='+',
            )

    def _play_button_sound(self, _event=None):
        self.audio.play_effect('button_click')

    def _show_error(self, *args, **kwargs):
        self.audio.play_effect('error')
        return messagebox.showerror(*args, **kwargs)

    def _activate_menu_tile(self, command):
        self.audio.play_effect('button_click')
        command()

    def close(self):
        self.audio.close()
        self.root.destroy()

    def clear(self):
        self.generation_active = False
        self.current_spin_finish = None
        after_id = getattr(self, 'spin_after_id', None)
        if after_id is not None:
            try:
                self.root.after_cancel(after_id)
            except tk.TclError:
                pass
            self.spin_after_id = None
        for attribute in ('intro_after_id', 'intro_manual_pause_id'):
            after_id = getattr(self, attribute, None)
            if after_id is not None:
                try:
                    self.root.after_cancel(after_id)
                except tk.TclError:
                    pass
                setattr(self, attribute, None)
        for child in self.root.winfo_children():
            child.destroy()
        self.root.after_idle(self._apply_theme)

    def _apply_theme(self):
        if not self.root.winfo_exists():
            return
        if 'clam' in self.style.theme_names():
            self.style.theme_use('clam')
        if self.dark_theme:
            colors = {'background': '#111820', 'surface': '#1b2632', 'input': '#253342',
                      'foreground': '#e8eef3', 'muted': '#9aabb9', 'accent': '#477c86',
                      'accent_hover': '#568f98', 'border': '#2b3947', 'hover': '#3a5e6a'}
        else:
            colors = {'background': '#f3f6f8', 'surface': '#ffffff', 'input': '#ffffff',
                      'foreground': '#182530', 'muted': '#657681', 'accent': '#356d78',
                      'accent_hover': '#2c5962', 'border': '#dce4e9', 'hover': '#80a3ab'}
        self.ui_colors = colors
        self.style.configure('.', background=colors['background'], foreground=colors['foreground'])
        self.style.configure('TFrame', background=colors['background'])
        self.style.configure('TLabel', background=colors['background'], foreground=colors['foreground'])
        self.style.configure('TButton', background=colors['surface'], foreground=colors['foreground'],
                             bordercolor=colors['border'], padding=(12, 9),
                             font=('Segoe UI', 10), relief='flat')
        self.style.map('TButton', background=[('active', colors['accent_hover'])],
                       foreground=[('active', '#ffffff')])
        self.style.configure('Menu.TButton', font=('Segoe UI', 12, 'bold'), padding=(18, 14),
                             anchor='w')
        self.style.configure('Section.TLabel', font=('Segoe UI', 10, 'bold'))
        self.style.configure('Metric.TLabel', font=('Segoe UI', 20, 'bold'),
                             foreground=colors['accent'])
        self.style.configure('Muted.TLabel', background=colors['surface'], foreground=colors['muted'])
        self.style.configure('CreationSummary.TFrame', background=colors['surface'])
        self.style.configure('CreationSummary.Muted.TLabel', background=colors['surface'],
                             foreground=colors['muted'])
        self.style.configure('CreationSummary.Value.TLabel', background=colors['surface'],
                             foreground=colors['foreground'])
        self.style.configure('Creation.Horizontal.TProgressbar', troughcolor=colors['input'],
                             background=colors['accent'], bordercolor=colors['border'], thickness=10)
        self.style.configure('Primary.TButton', background=colors['accent'],
                             foreground='#ffffff', padding=(16, 10),
                             font=('Segoe UI', 10, 'bold'), borderwidth=0)
        self.style.map(
            'Primary.TButton',
            background=[('disabled', colors['surface']), ('active', colors['accent_hover'])],
            foreground=[('disabled', colors['muted']), ('active', '#ffffff')],
        )
        self.style.configure('LadderCount.TLabel', background=colors['surface'],
                             foreground=colors['muted'], padding=(12, 10),
                             font=('Segoe UI', 10, 'bold'))
        skip_background = '#e0ad4f' if self.dark_theme else '#d99a2b'
        skip_hover = '#efc46d' if self.dark_theme else '#bd7e18'
        skip_foreground = '#17212b'
        self.style.configure('Skip.TButton', background=skip_background,
                             foreground=skip_foreground, padding=(18, 11),
                             font=('Segoe UI', 10, 'bold'), borderwidth=0)
        self.style.map(
            'Skip.TButton',
            background=[('disabled', colors['surface']), ('pressed', skip_hover),
                        ('active', skip_hover)],
            foreground=[('disabled', colors['muted']), ('!disabled', skip_foreground)],
        )
        self.style.configure('TEntry', fieldbackground=colors['input'], foreground=colors['foreground'],
                             bordercolor=colors['border'], padding=7)
        self.style.configure('TCombobox', fieldbackground=colors['input'], foreground=colors['foreground'])
        self.style.map('TCombobox', fieldbackground=[('readonly', colors['input'])],
                       foreground=[('readonly', colors['foreground'])],
                       background=[('active', colors['surface'])])
        self.style.configure('TCheckbutton', background=colors['background'], foreground=colors['foreground'])
        self.style.map('TCheckbutton', background=[('active', colors['background'])],
                       foreground=[('active', colors['foreground'])])
        self.style.configure('Treeview', background=colors['surface'], fieldbackground=colors['surface'],
                             foreground=colors['foreground'], rowheight=32, borderwidth=0,
                             font=('Segoe UI', 9))
        self.style.configure('Treeview.Heading', background=colors['background'],
                             foreground=colors['muted'], font=('Segoe UI', 9, 'bold'), padding=8)
        self.style.map('Treeview', background=[('selected', colors['accent'])],
                       foreground=[('selected', colors['foreground'])])
        self.style.configure('TLabelframe', background=colors['surface'], bordercolor=colors['border'],
                             relief='solid', borderwidth=1)
        self.style.configure('TLabelframe.Label', background=colors['surface'],
                             foreground=colors['muted'], font=('Segoe UI', 9, 'bold'))
        self.style.configure('TNotebook', background=colors['background'], borderwidth=0)
        self.style.configure('TNotebook.Tab', background=colors['surface'],
                             foreground=colors['foreground'], padding=(10, 5))
        self.style.map('TNotebook.Tab', background=[('selected', colors['accent'])],
                       foreground=[('selected', colors['foreground'])])
        self.style.configure('TScrollbar', background=colors['surface'],
                             troughcolor=colors['background'], arrowcolor=colors['foreground'])

        def recolor(widget):
            if isinstance(widget, (tk.Text, tk.Listbox)):
                widget.configure(bg=colors['input'], fg=colors['foreground'],
                                 selectbackground=colors['accent'],
                                 highlightbackground=colors['background'],
                                 highlightcolor=colors['accent'])
                if isinstance(widget, tk.Text):
                    widget.configure(insertbackground=colors['foreground'])
            elif isinstance(widget, tk.Canvas):
                widget.configure(background=colors['surface'], highlightbackground=colors['border'])
            for child in widget.winfo_children():
                recolor(child)

        recolor(self.root)

    def _toggle_dark_theme(self):
        self.dark_theme = self.dark_theme_var.get()
        self._apply_theme()
        self._save_settings()

    def _set_page_geometry(self, geometry):
        self.page_geometry = geometry
        self._apply_window_geometry()

    def _apply_window_geometry(self):
        if self.fullscreen:
            return
        geometry = self.window_resolution or self.page_geometry
        width, height = (int(value) for value in geometry.split('x'))
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

    def _wheel_scale(self, reference_width, reference_height):
        if self.fullscreen:
            width = self.root.winfo_screenwidth()
            height = self.root.winfo_screenheight()
        else:
            geometry = self.window_resolution or self.page_geometry
            width, height = (int(value) for value in geometry.split('x'))
            width = min(width, self.root.winfo_screenwidth())
            height = min(height, self.root.winfo_screenheight())
        return max(0.65, min(1.7, width / reference_width, height / reference_height))

    def _automatic_page_scale(self, reference_width, reference_height):
        if self.fullscreen:
            width = self.root.winfo_screenwidth()
            height = self.root.winfo_screenheight()
        elif self.window_resolution:
            width, height = (int(value) for value in self.window_resolution.split('x'))
        else:
            width = self.root.winfo_screenwidth()
            height = max(420, self.root.winfo_screenheight() - 80)
        return max(0.65, min(1.5, width / reference_width, height / reference_height))

    def _resolution_options(self):
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        sizes = ((800, 600), (1024, 768), (1280, 720), (1280, 800),
                 (1366, 768), (1600, 900), (1920, 1080), (screen_width, screen_height))
        return ['Авто'] + [
            f'{width}x{height}' for width, height in dict.fromkeys(sizes)
            if 480 <= width <= screen_width and 420 <= height <= screen_height
        ]

    def _change_resolution(self, _event=None):
        choice = self.resolution_var.get()
        self.window_resolution = None if choice == 'Авто' else choice
        self._apply_window_geometry()
        self._save_settings()

    def _toggle_fullscreen(self):
        self.fullscreen = self.fullscreen_var.get()
        self.root.attributes('-fullscreen', self.fullscreen)
        self._apply_window_geometry()
        self._save_settings()

    def _leave_fullscreen(self, _event=None):
        if self.fullscreen:
            self.fullscreen = False
            self.root.attributes('-fullscreen', False)
            if hasattr(self, 'fullscreen_var'):
                self.fullscreen_var.set(False)
            self._apply_window_geometry()
            self._save_settings()

    def heading(self, parent, text):
        ttk.Label(parent, text=text, font=('Segoe UI', 19, 'bold')).pack(anchor='w', pady=(0, 16))

    def _render_markdown(self, widget, markdown):
        """Render the common Markdown elements used by the intro lore."""
        colors = self.ui_colors
        widget.tag_configure('h1', font=('Segoe UI', 24, 'bold'), foreground=colors['accent'],
                             spacing1=12, spacing3=14)
        widget.tag_configure('h2', font=('Segoe UI', 17, 'bold'), foreground=colors['foreground'],
                             spacing1=10, spacing3=8)
        widget.tag_configure('h3', font=('Segoe UI', 13, 'bold'), foreground=colors['accent'],
                             spacing1=8, spacing3=5)
        widget.tag_configure('paragraph', font=('Segoe UI', 11), spacing1=2, spacing3=10,
                             lmargin1=2, lmargin2=2)
        widget.tag_configure('quote', font=('Segoe UI', 11, 'italic'),
                             foreground=colors['muted'], lmargin1=18, lmargin2=18,
                             spacing1=4, spacing3=10)
        widget.tag_configure('list', font=('Segoe UI', 11), lmargin1=18, lmargin2=38,
                             spacing1=1, spacing3=4)
        widget.tag_configure('code', font=('Consolas', 10), background=colors['input'],
                             lmargin1=14, lmargin2=14, spacing1=4, spacing3=8)
        widget.tag_configure('bold', font=('Segoe UI', 11, 'bold'))
        widget.tag_configure('italic', font=('Segoe UI', 11, 'italic'))
        widget.tag_configure('strike', overstrike=True)
        widget.tag_configure('inline_code', font=('Consolas', 10), background=colors['input'])
        widget.tag_configure('link', foreground=colors['accent'], underline=True)
        widget.tag_configure('rule', foreground=colors['muted'], justify='center', spacing1=5, spacing3=12)

        inline_pattern = re.compile(
            r'(\*\*.+?\*\*|__.+?__|~~.+?~~|`[^`]+`|\*[^*]+\*|_[^_]+_|\[[^\]]+\]\([^)]+\))'
        )

        def add_inline(value, block_tag):
            cursor = 0
            for match in inline_pattern.finditer(value):
                if match.start() > cursor:
                    widget.insert('end', value[cursor:match.start()], block_tag)
                token = match.group(0)
                if token.startswith(('**', '__')):
                    widget.insert('end', token[2:-2], (block_tag, 'bold'))
                elif token.startswith('~~'):
                    widget.insert('end', token[2:-2], (block_tag, 'strike'))
                elif token.startswith('`'):
                    widget.insert('end', token[1:-1], (block_tag, 'inline_code'))
                elif token.startswith(('*', '_')):
                    widget.insert('end', token[1:-1], (block_tag, 'italic'))
                else:
                    link_match = re.fullmatch(r'\[([^\]]+)\]\(([^)]+)\)', token)
                    if link_match:
                        widget.insert('end', link_match.group(1), (block_tag, 'link'))
                cursor = match.end()
            if cursor < len(value):
                widget.insert('end', value[cursor:], block_tag)

        lines = markdown.splitlines()
        paragraph = []

        def flush_paragraph():
            if paragraph:
                add_inline(' '.join(part.strip() for part in paragraph), 'paragraph')
                widget.insert('end', '\n', 'paragraph')
                paragraph.clear()

        index = 0
        while index < len(lines):
            line = lines[index]
            stripped = line.strip()
            if not stripped:
                flush_paragraph()
                index += 1
                continue

            heading_match = re.match(r'^(#{1,3})\s+(.+?)\s*#*$', stripped)
            if heading_match:
                flush_paragraph()
                level = len(heading_match.group(1))
                add_inline(heading_match.group(2), f'h{level}')
                widget.insert('end', '\n', f'h{level}')
                index += 1
                continue

            if re.fullmatch(r'([-*_]\s*){3,}', stripped):
                flush_paragraph()
                widget.insert('end', '────────────────────────────────────────\n', 'rule')
                index += 1
                continue

            if stripped.startswith('```'):
                flush_paragraph()
                index += 1
                while index < len(lines) and not lines[index].strip().startswith('```'):
                    widget.insert('end', lines[index] + '\n', 'code')
                    index += 1
                index += 1
                widget.insert('end', '\n')
                continue

            if stripped.startswith('>'):
                flush_paragraph()
                quote_lines = []
                while index < len(lines) and lines[index].strip().startswith('>'):
                    quote_lines.append(re.sub(r'^\s*>\s?', '', lines[index]).strip())
                    index += 1
                add_inline(' '.join(quote_lines), 'quote')
                widget.insert('end', '\n', 'quote')
                continue

            unordered = re.match(r'^\s*[-+*]\s+(.+)$', line)
            ordered = re.match(r'^\s*\d+[.)]\s+(.+)$', line)
            if unordered or ordered:
                flush_paragraph()
                list_index = 1
                while index < len(lines):
                    current = lines[index]
                    unordered_item = re.match(r'^\s*[-+*]\s+(.+)$', current)
                    ordered_item = re.match(r'^\s*\d+[.)]\s+(.+)$', current)
                    item = unordered_item or ordered_item
                    if not item:
                        break
                    prefix = '• ' if unordered_item else f'{list_index}. '
                    widget.insert('end', prefix, 'list')
                    add_inline(item.group(1), 'list')
                    widget.insert('end', '\n', 'list')
                    list_index += 1
                    index += 1
                continue

            paragraph.append(line)
            index += 1

        flush_paragraph()

    def show_intro(self):
        self.show_lore_page(
            LORE_PATH,
            'Хроники Неудачного забега',
            'Летопись мира и тех, кому предстоит в нём сразиться.',
            'Пропустить → меню',
            self.show_home,
        )

    def show_ending_lore(self):
        self.show_lore_page(
            ENDING_LORE_PATH,
            'Последняя летопись',
            'История о том, чем закончился этот забег.',
            'Завершить → меню',
            self.show_home,
        )

    def show_lore_page(self, lore_path, title, subtitle, finish_label, finish_command):
        self.clear()
        self.ladder_selection_mode = False
        self.root.title(f'Неудачный забег — {title.lower()}')
        self.audio.play_music('lore')
        page_scale = self._automatic_page_scale(900, 720)
        self._set_page_geometry(f'{int(900 * page_scale)}x{int(720 * page_scale)}')
        frame = ttk.Frame(self.root, padding=(30, 22))
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text=title,
                  font=('Segoe UI', 24, 'bold')).pack(anchor='w')
        ttk.Label(frame, text=subtitle,
                  foreground=self.ui_colors['muted'], font=('Segoe UI', 10)).pack(
                      anchor='w', pady=(2, 14)
                  )

        text_area = ttk.Frame(frame)
        text_area.pack(fill='both', expand=True)
        text = tk.Text(
            text_area, wrap='word', padx=26, pady=22, relief='flat', borderwidth=0,
            font=('Segoe UI', 11), spacing1=2, spacing3=8, takefocus=True,
        )
        scrollbar = ttk.Scrollbar(
            text_area, orient='vertical', command=self._intro_scrollbar_command,
        )
        text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        text.pack(side='left', fill='both', expand=True)
        self.intro_text = text
        try:
            markdown = lore_path.read_text(encoding='utf-8')
        except (OSError, UnicodeError) as error:
            markdown = f'# LORE FILE UNAVAILABLE\n\nCould not read `{lore_path.name}`: {error}'
        self._render_markdown(text, markdown)
        text.configure(state='disabled')
        text.yview_moveto(0)

        controls = ttk.Frame(frame)
        controls.pack(fill='x', pady=(14, 0))
        self.intro_pause_button = ttk.Button(
            controls, text='Пауза', command=self._toggle_intro_scroll,
        )
        self.intro_pause_button.pack(side='left')
        ttk.Label(
            controls, text='Колесо мыши или полоса прокрутки — вручную',
            foreground=self.ui_colors['muted'],
        ).pack(side='left', padx=12)
        ttk.Button(
            controls, text=finish_label, command=finish_command, style='Primary.TButton',
        ).pack(side='right')

        text.bind('<MouseWheel>', self._on_intro_mousewheel)
        text.bind('<Button-4>', self._on_intro_mousewheel)
        text.bind('<Button-5>', self._on_intro_mousewheel)
        text.bind('<KeyPress>', self._on_intro_keypress)
        self.intro_user_paused = False
        self.intro_after_id = None
        self.intro_manual_pause_id = None
        self._schedule_intro_scroll()

    def _schedule_intro_scroll(self, delay=180):
        if (getattr(self, 'intro_user_paused', True)
                or getattr(self, 'intro_manual_pause_id', None) is not None
                or not getattr(self, 'intro_text', None)):
            return
        if self.intro_after_id is None:
            self.intro_after_id = self.root.after(delay, self._advance_intro_scroll)

    def _advance_intro_scroll(self):
        self.intro_after_id = None
        if getattr(self, 'intro_user_paused', True) or not getattr(self, 'intro_text', None):
            return
        try:
            if self.intro_text.yview()[1] >= 1.0:
                return
            self.intro_text.yview_scroll(1, 'units')
            self._schedule_intro_scroll()
        except tk.TclError:
            return

    def _toggle_intro_scroll(self):
        self.intro_user_paused = not self.intro_user_paused
        self.intro_pause_button.configure(
            text='Продолжить' if self.intro_user_paused else 'Пауза',
        )
        if self.intro_user_paused:
            if self.intro_after_id is not None:
                self.root.after_cancel(self.intro_after_id)
                self.intro_after_id = None
        else:
            self._schedule_intro_scroll()

    def _pause_intro_for_manual_scroll(self):
        if getattr(self, 'intro_user_paused', True):
            return
        if self.intro_after_id is not None:
            self.root.after_cancel(self.intro_after_id)
            self.intro_after_id = None
        if self.intro_manual_pause_id is not None:
            self.root.after_cancel(self.intro_manual_pause_id)
        self.intro_manual_pause_id = self.root.after(2200, self._resume_intro_after_manual_scroll)

    def _resume_intro_after_manual_scroll(self):
        self.intro_manual_pause_id = None
        self._schedule_intro_scroll()

    def _intro_scrollbar_command(self, *arguments):
        self._pause_intro_for_manual_scroll()
        self.intro_text.yview(*arguments)

    def _on_intro_mousewheel(self, event):
        self._pause_intro_for_manual_scroll()
        if getattr(event, 'num', None) == 4:
            delta = -1
        elif getattr(event, 'num', None) == 5:
            delta = 1
        else:
            delta = -1 if event.delta > 0 else 1
        self.intro_text.yview_scroll(delta * 3, 'units')
        return 'break'

    def _on_intro_keypress(self, event):
        key_scroll = {
            'Up': (-1, 'units'), 'Down': (1, 'units'),
            'Prior': (-1, 'pages'), 'Next': (1, 'pages'),
            'Home': ('top', None), 'End': ('bottom', None),
        }
        movement = key_scroll.get(event.keysym)
        if movement is None:
            return
        self._pause_intro_for_manual_scroll()
        amount, unit = movement
        if amount == 'top':
            self.intro_text.yview_moveto(0)
        elif amount == 'bottom':
            self.intro_text.yview_moveto(1)
        else:
            self.intro_text.yview_scroll(amount, unit)
        return 'break'

    def show_home(self):
        self.clear()
        self.ladder_selection_mode = False
        self.root.title('Неудачный забег')
        self.audio.play_music('main_menu')
        self._set_page_geometry('600x700')
        colors = self.ui_colors
        frame = ttk.Frame(self.root, padding=(36, 26))
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Неудачный забег',
                  font=('Segoe UI', 25, 'bold')).pack(pady=(6, 3))
        ttk.Label(frame, text='Создай героя, собери команду и узнай, кто победит.',
                  foreground=colors['muted'], font=('Segoe UI', 10)).pack(pady=(0, 16))
        menu = ttk.Frame(frame)
        menu.pack(fill='both', expand=True)
        entries = (
            ('Генератор героев', 'Создай нового персонажа', self.show_create),
            ('Коллекция', 'Просматривай и прокачивай героев', self.show_characters),
            ('Арена', 'Сравни двух бойцов в сражении', self.show_fight),
            ('Турнир', 'Собери ростер и проведи чемпионат', self.show_tournament),
        )
        for title, description, command in entries:
            tile = tk.Frame(menu, bg=colors['surface'], highlightthickness=1,
                            highlightbackground=colors['border'], padx=14, pady=7, cursor='hand2')
            tile.configure(takefocus=True)
            tile.pack(fill='x', pady=4)
            title_label = tk.Label(tile, text=title, bg=colors['surface'], fg=colors['foreground'],
                                  font=('Segoe UI', 11, 'bold'), anchor='w')
            title_label.pack(fill='x')
            description_label = tk.Label(tile, text=description, bg=colors['surface'], fg=colors['muted'],
                                         font=('Segoe UI', 9), anchor='w')
            description_label.pack(fill='x', pady=(2, 0))
            for widget in (tile, title_label, description_label):
                widget.bind('<Button-1>', lambda _event, action=command: self._activate_menu_tile(action))
                widget.bind('<Return>', lambda _event, action=command: self._activate_menu_tile(action))
                widget.bind('<Enter>', lambda _event, card=tile: card.configure(highlightbackground=colors['accent']))
                widget.bind('<Leave>', lambda _event, card=tile: card.configure(highlightbackground=colors['border']))
            tile.bind('<FocusIn>', lambda _event, card=tile: card.configure(
                highlightbackground=colors['accent'], highlightthickness=2))
            tile.bind('<FocusOut>', lambda _event, card=tile: card.configure(
                highlightbackground=colors['border'], highlightthickness=1))
        ladder_area = ttk.Frame(menu)
        ladder_area.pack(fill='both', expand=True)
        ladder_actions = ttk.Frame(ladder_area)
        ladder_actions.pack(anchor='center', pady=(32, 0))
        ttk.Button(
            ladder_actions, text='⚔ Забег в ладдер', command=self.show_ladder_picker,
            style='Primary.TButton',
        ).pack(side='left')
        ttk.Label(
            ladder_actions, text=f'Запусков: {ladder_run_count()}', style='LadderCount.TLabel',
        ).pack(side='left', padx=(10, 0))
        footer = ttk.Frame(frame)
        footer.pack(fill='x', pady=(8, 0))
        ttk.Button(
            footer, text='📜 Читать лор', command=self.show_intro,
        ).pack(side='left', anchor='center')
        exit_container = ttk.Frame(footer)
        exit_container.pack(side='right')
        statistics_button = ttk.Button(
            exit_container, text='📊 Статистика забегов',
            command=self.show_ladder_statistics, width=24,
            state='normal' if ladder_run_files() else 'disabled',
        )
        statistics_button.pack(anchor='e', pady=(0, 5))
        ttk.Button(exit_container, text='⚙ Настройки', command=self.show_options, width=24).pack(
            anchor='e', pady=(0, 5)
        )
        exit_button = ttk.Button(
            exit_container, text='⇥ Выйти из игры', command=self.close, width=24,
        )
        exit_button.pack(anchor='e')

    def show_ladder_statistics(self):
        self.clear()
        self.audio.play_music(None)
        page_scale = self._automatic_page_scale(900, 650)
        self._set_page_geometry(f'{int(900 * page_scale)}x{int(650 * page_scale)}')
        frame = ttk.Frame(self.root, padding=22)
        frame.pack(fill='both', expand=True)
        ttk.Button(frame, text='← На главную', command=self.show_home).pack(
            anchor='w', pady=(0, 12)
        )
        self.heading(frame, 'Статистика забегов')

        records, unreadable_files = load_ladder_run_records()
        wins = sum(record.get('result') == 'Победа' for record in records)
        losses = sum(record.get('result') == 'Поражение' for record in records)
        summary = ttk.LabelFrame(frame, text='Итог', padding=10)
        summary.pack(fill='x', pady=(0, 12))
        ttk.Label(
            summary,
            text=f'Завершено забегов: {len(records)}    Побед: {wins}    Поражений: {losses}',
            font=('Segoe UI', 11, 'bold'),
        ).pack(anchor='w')

        history = ttk.LabelFrame(frame, text='История', padding=8)
        history.pack(fill='both', expand=True)
        table_area = ttk.Frame(history)
        table_area.pack(fill='both', expand=True)
        columns = ('number', 'finished', 'character', 'result', 'fights', 'opponent')
        table = ttk.Treeview(table_area, columns=columns, show='headings', height=12)
        headings = (
            ('number', '№', 58), ('finished', 'Дата завершения', 150),
            ('character', 'Персонаж', 180), ('result', 'Результат', 120),
            ('fights', 'Боев', 70), ('opponent', 'Последний соперник', 190),
        )
        for column, title, width in headings:
            table.heading(column, text=title)
            table.column(column, width=width, minwidth=55, anchor='center',
                         stretch=column in ('character', 'opponent'))
        scroll = ttk.Scrollbar(table_area, orient='vertical', command=table.yview)
        table.configure(yscrollcommand=scroll.set)
        table.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        table.tag_configure('victory', foreground='#25834b' if not self.dark_theme else '#91e2ac')
        table.tag_configure('defeat', foreground='#c34747' if not self.dark_theme else '#ffaaaa')

        for record in records:
            character = record.get('character', {})
            if isinstance(character, dict):
                character_name = character.get('name', 'Неизвестно')
            else:
                character_name = str(character)
            finished = record.get('finished_at') or record.get('started_at', '')
            try:
                finished = datetime.fromisoformat(finished).astimezone().strftime('%d.%m.%Y %H:%M')
            except (TypeError, ValueError):
                pass
            result = record.get('result', 'Неизвестно')
            last_opponent = record.get('last_opponent') or '—'
            tag = 'victory' if result == 'Победа' else 'defeat' if result == 'Поражение' else ''
            table.insert('', 'end', tags=(tag,) if tag else (), values=(
                record.get('run_number', '—'), finished, character_name, result,
                record.get('fights_completed', 0), last_opponent,
            ))

        if not records:
            ttk.Label(history, text='Нет читаемых файлов статистики.', style='Muted.TLabel').pack(
                anchor='w', pady=(8, 0)
            )
        if unreadable_files:
            ttk.Label(
                frame, text='Не удалось прочитать: ' + ', '.join(unreadable_files),
                style='Muted.TLabel',
            ).pack(anchor='w', pady=(8, 0))

    def show_ladder_picker(self):
        self.show_characters(ladder_selection=True)

    def start_ladder(self):
        hero_path = getattr(self, 'selected_character_path', None)
        if hero_path is None:
            messagebox.showwarning('Выберите героя', 'Для забега нужно выбрать персонажа из коллекции.')
            return
        if not Fight.is_character_alive(hero_path):
            messagebox.showwarning('Персонаж мёртв', 'Мёртвый персонаж не может участвовать в ладдере.')
            self.show_ladder_picker()
            return

        villains, invalid_files, diagnostics = villain_files_by_ladder_index()
        for diagnostic in diagnostics:
            print(f'[Ладдер] {diagnostic}')
        if invalid_files:
            invalid_list = '\n'.join(invalid_files)
            self._show_error(
                'Проверь файлы злодеев',
                f'Исправь ошибки в файлах злодеев:\n{invalid_list}\n\n'
                f'Диагностика:\n' + '\n'.join(diagnostics),
            )
            return
        if not villains:
            messagebox.showinfo(
                'Ладдер пока пуст',
                f'Добавь в папку Villains файлы злодеев с целым положительным '
                f'индексом {LADDER_INDEX_KEY}.\n\n'
                f'Диагностика:\n' + '\n'.join(diagnostics),
            )
            return

        self.ladder_hero_path = hero_path
        self.ladder_villains = villains
        self.ladder_index = 0
        try:
            self.ladder_run_record = create_ladder_run_record(hero_path, villains)
            self.ladder_run_path = None
        except (OSError, UnicodeError, ValueError) as error:
            self._show_error('Не удалось прочитать выбранного героя', str(error))
            return
        self.audio.play_effect('ladder_start')
        self.show_fight(ladder_mode=True)

    def _advance_ladder_fight(self):
        self.ladder_index += 1
        self.show_fight(ladder_mode=True)

    def _mark_ladder_loser_dead(self, winner_index):
        if winner_index != 1:
            return
        loser_path = self.ladder_hero_path
        try:
            Fight.set_character_live_status(loser_path, False)
        except (OSError, UnicodeError) as error:
            self._show_error(
                'Не удалось сохранить статус персонажа',
                f'Не удалось отметить {loser_path.stem} как мёртвого:\n{error}',
            )

    def _save_ladder_run_progress(self, fight_result=None, final_result=None):
        record = getattr(self, 'ladder_run_record', None)
        if record is None:
            return

        if fight_result is not None:
            opponent = self.ladder_villains[self.ladder_index]
            record['last_opponent'] = opponent.stem
            record['last_fight_result'] = fight_result
            record['fights_completed'] = self.ladder_index + 1
            next_index = self.ladder_index + 1
            record['current_opponent'] = (
                self.ladder_villains[next_index].stem
                if next_index < len(self.ladder_villains) else None
            )
        if final_result is not None:
            record['result'] = final_result
            record['finished_at'] = datetime.now().astimezone().isoformat(timespec='seconds')
        record['updated_at'] = datetime.now().astimezone().isoformat(timespec='seconds')
        if final_result is None:
            return
        try:
            self.ladder_run_path = write_completed_ladder_run_record(record)
        except (OSError, ValueError) as error:
            self._show_error('Не удалось сохранить историю забега', str(error))

    def _leave_ladder(self):
        self.ladder_run_record = None
        self.ladder_run_path = None
        self.show_home()

    def show_options(self):
        self.clear()
        frame = ttk.Frame(self.root, padding=24)
        frame.pack(fill='both', expand=True)
        ttk.Button(frame, text='← Назад', command=self.show_home).pack(
            anchor='w', pady=(0, 18)
        )
        settings = ttk.Frame(frame)
        settings.pack(expand=True)
        ttk.Label(settings, text='Опции',
                  font=('Segoe UI', 16, 'bold')).pack(pady=(0, 18))

        appearance = ttk.LabelFrame(settings, text='Внешний вид', padding=(18, 12))
        appearance.pack(fill='x', pady=(0, 12))
        self.dark_theme_var = tk.BooleanVar(value=self.dark_theme)
        ttk.Checkbutton(appearance, text='Тёмная тема',
                        variable=self.dark_theme_var, command=self._toggle_dark_theme).pack(anchor='w', pady=4)

        sound_settings = ttk.LabelFrame(settings, text='Звук', padding=(18, 12))
        sound_settings.pack(fill='x', pady=(0, 12))
        self.sound_enabled_var = tk.BooleanVar(value=self.sound_enabled)
        ttk.Checkbutton(
            sound_settings, text='Включить звук', variable=self.sound_enabled_var,
            command=self._toggle_sound_enabled,
        ).pack(anchor='w', pady=(0, 8))
        volume_row = ttk.Frame(sound_settings)
        volume_row.pack(fill='x')
        ttk.Label(volume_row, text='Громкость').pack(side='left', padx=(0, 10))
        self.sound_volume_var = tk.DoubleVar(value=self.sound_volume * 100)
        self.sound_volume_label_var = tk.StringVar(value=f'{round(self.sound_volume * 100)}%')
        self.sound_volume_scale = ttk.Scale(
            volume_row, from_=0, to=100, variable=self.sound_volume_var,
            command=self._change_sound_volume,
        )
        self.sound_volume_scale.pack(side='left', fill='x', expand=True)
        ttk.Label(volume_row, textvariable=self.sound_volume_label_var, width=5,
                  anchor='e').pack(side='left', padx=(10, 0))
        self.sound_volume_scale.configure(
            state='normal' if self.sound_enabled else 'disabled',
        )
        self.sound_volume_scale.bind('<ButtonRelease-1>', lambda _event: self._save_settings())
        self.sound_volume_scale.bind('<KeyRelease>', lambda _event: self._save_settings())

        display = ttk.LabelFrame(settings, text='Окно', padding=(18, 12))
        display.pack(fill='x')
        self.fullscreen_var = tk.BooleanVar(value=self.fullscreen)
        ttk.Checkbutton(display, text='Полноэкранный режим',
                        variable=self.fullscreen_var, command=self._toggle_fullscreen).pack(anchor='w', pady=(2, 8))
        ttk.Label(display, text='Разрешение окна').pack(anchor='w', pady=(2, 4))
        self.resolution_var = tk.StringVar(value=self.window_resolution or 'Авто')
        resolution_box = ttk.Combobox(
            display, textvariable=self.resolution_var, state='readonly',
            values=self._resolution_options(), width=18,
        )
        resolution_box.pack(anchor='w')
        resolution_box.bind('<<ComboboxSelected>>', self._change_resolution)

    def _toggle_sound_enabled(self):
        self.sound_enabled = self.sound_enabled_var.get()
        self.audio.set_enabled(self.sound_enabled)
        self.sound_volume_scale.configure(
            state='normal' if self.sound_enabled else 'disabled',
        )
        self._save_settings()

    def _change_sound_volume(self, value):
        self.sound_volume = max(0.0, min(1.0, float(value) / 100))
        self.sound_volume_label_var.set(f'{round(self.sound_volume * 100)}%')
        self.audio.set_volume(self.sound_volume)

    def show_tournament(self):
        self.clear()
        self.audio.play_music('tournament')
        page_scale = self._automatic_page_scale(900, 760)
        self._set_page_geometry(f'{int(900 * page_scale)}x{int(760 * page_scale)}')
        if page_scale < 0.95:
            page = ttk.Frame(self.root)
            page.pack(fill='both', expand=True)
            page_canvas = tk.Canvas(page, highlightthickness=0,
                                    background=self.ui_colors['background'])
            page_scroll = ttk.Scrollbar(page, orient='vertical', command=page_canvas.yview)
            page_canvas.configure(yscrollcommand=page_scroll.set)
            page_canvas.pack(side='left', fill='both', expand=True)
            page_scroll.pack(side='right', fill='y')
            frame = ttk.Frame(page_canvas, padding=18)
            page_window = page_canvas.create_window((0, 0), window=frame, anchor='nw')
            frame.bind('<Configure>', lambda _event: page_canvas.configure(
                scrollregion=page_canvas.bbox('all')))
            page_canvas.bind('<Configure>', lambda event: page_canvas.itemconfigure(
                page_window, width=event.width))
        else:
            frame = ttk.Frame(self.root, padding=18)
            frame.pack(fill='both', expand=True)
        ttk.Button(frame, text='← На главную', command=self.show_home).pack(anchor='w', pady=(0, 12))
        self.heading(frame, 'Турнир')
        files = character_files_by_creation_date(living_only=True)
        self.tournament_files = files

        ttk.Label(frame, text='Доступные персонажи').pack(anchor='w')
        tables = ttk.Frame(frame)
        tables.pack(fill='x', pady=(4, 8))
        available_frame = ttk.Frame(tables)
        available_frame.pack(side='left', fill='both', expand=True)
        self.tournament_search_var = tk.StringVar()
        tournament_search = ttk.Entry(available_frame, textvariable=self.tournament_search_var)
        tournament_search.pack(fill='x', pady=(0, 5))
        self.tournament_search_var.trace_add('write', lambda *_args: self._filter_tournament_available())
        roster_frame = ttk.Frame(tables)
        roster_frame.pack(side='right', fill='both', expand=True, padx=(12, 0))

        table_height = max(4, int(9 * page_scale))
        self.available_table = ttk.Treeview(available_frame, columns=('name',), show='headings', height=table_height, selectmode='browse')
        self.available_table.heading('name', text='Персонаж')
        self.available_table.column('name', anchor='w', width=260)
        self.available_table.pack(side='left', fill='both', expand=True)
        available_scroll = ttk.Scrollbar(available_frame, orient='vertical', command=self.available_table.yview)
        available_scroll.pack(side='right', fill='y')
        self.available_table.configure(yscrollcommand=available_scroll.set)
        for index, path in enumerate(files):
            self.available_table.insert('', 'end', iid=str(index), values=(path.stem,))

        controls = ttk.Frame(tables)
        controls.pack(side='left', fill='y', padx=12)
        ttk.Button(controls, text='Добавить →', command=self.add_to_roster).pack(pady=(32, 6))
        ttk.Button(controls, text='← Убрать', command=self.remove_from_roster).pack(pady=6)
        ttk.Button(controls, text='Очистить ростер', command=self.clear_roster).pack(pady=(12, 6))

        self.roster_table = ttk.Treeview(roster_frame, columns=('name',), show='headings', height=table_height, selectmode='browse')
        self.roster_table.heading('name', text='Ростер (0/20)')
        self.roster_table.column('name', anchor='w', width=260)
        self.roster_table.pack(side='left', fill='both', expand=True)
        roster_scroll = ttk.Scrollbar(roster_frame, orient='vertical', command=self.roster_table.yview)
        roster_scroll.pack(side='right', fill='y')
        self.roster_table.configure(yscrollcommand=roster_scroll.set)

        self.roster_count = ttk.Label(frame, text='Выбрано: 0 / 20')
        self.roster_count.pack(anchor='w', pady=(0, 6))
        self.update_roster_count()
        actions = ttk.Frame(frame)
        actions.pack(anchor='w', pady=(0, 8))
        ttk.Button(actions, text='Автозаполнить: первые 20',
                   command=self.auto_fill_roster).pack(side='left', padx=(0, 8))
        ttk.Button(actions, text='Провести турнир', command=self.start_tournament,
                   style='Primary.TButton').pack(side='left')
        self.tournament_tabs = ttk.Notebook(frame)
        self.tournament_tabs.pack(fill='both', expand=True)
        bracket_tab = ttk.Frame(self.tournament_tabs)
        groups_tab = ttk.Frame(self.tournament_tabs)
        report_tab = ttk.Frame(self.tournament_tabs)
        self.tournament_tabs.add(bracket_tab, text='Сетка плей-офф')
        self.tournament_tabs.add(groups_tab, text='Групповой этап')
        self.tournament_tabs.add(report_tab, text='Отчёт')
        self.group_tables = {}
        for index, group_name in enumerate('ABCD'):
            group_frame = ttk.LabelFrame(groups_tab, text=f'Группа {group_name}', padding=6)
            group_frame.grid(row=index // 2, column=index % 2, sticky='nsew',
                             padx=6, pady=6)
            groups_tab.rowconfigure(index // 2, weight=1)
            groups_tab.columnconfigure(index % 2, weight=1)
            table = ttk.Treeview(group_frame, columns=('rank', 'name', 'wins', 'score'),
                                 show='headings', height=5)
            table.tag_configure('leader', background='#d9f2df' if not self.dark_theme else '#214a36',
                                foreground='#176b35' if not self.dark_theme else '#a8efbd')
            table.tag_configure('eliminated', background='#f7dddd' if not self.dark_theme else '#512b32',
                                foreground='#9e2727' if not self.dark_theme else '#ffadb6')
            for column, title, width, anchor in (
                ('rank', '№', 32, 'center'), ('name', 'Персонаж', 145, 'w'),
                ('wins', 'Победы', 62, 'center'), ('score', 'Очки', 72, 'center'),
            ):
                table.heading(column, text=title)
                table.column(column, width=width, anchor=anchor, stretch=column == 'name')
            table.pack(fill='both', expand=True)
            self.group_tables[group_name] = table
        bracket_toolbar = ttk.Frame(bracket_tab, padding=(8, 6))
        bracket_toolbar.pack(fill='x')
        ttk.Label(bracket_toolbar, text='Масштаб', style='Muted.TLabel').pack(side='left', padx=(0, 8))
        ttk.Button(bracket_toolbar, text='−', width=3,
                   command=lambda: self._zoom_tournament_bracket(0.85)).pack(side='left', padx=2)
        ttk.Button(bracket_toolbar, text='Сбросить',
                   command=self._reset_tournament_bracket_view).pack(side='left', padx=2)
        ttk.Button(bracket_toolbar, text='Вписать в окно',
                   command=self._fit_tournament_bracket).pack(side='left', padx=2)
        ttk.Button(bracket_toolbar, text='+', width=3,
                   command=lambda: self._zoom_tournament_bracket(1.18)).pack(side='left', padx=2)
        ttk.Label(bracket_toolbar, text='Стрелки — перемещение · 0 — вписать',
                  style='Muted.TLabel').pack(side='left', padx=(10, 0))
        self.tournament_stage_label = ttk.Label(bracket_toolbar, text='Плей-офф',
                                                style='Section.TLabel')
        self.tournament_stage_label.pack(side='right', padx=(0, 10))
        legend = ttk.Frame(bracket_toolbar)
        legend.pack(side='right')
        for title, background, foreground in (
            ('Победитель', '#d8f3dc' if not self.dark_theme else '#254b39',
             '#205c38' if not self.dark_theme else '#d7f5df'),
            ('Выбыл', '#fce8e6' if not self.dark_theme else '#4a292c',
             '#9f3838' if not self.dark_theme else '#f0b8b8'),
        ):
            badge = tk.Label(legend, text=title, bg=background, fg=foreground,
                             font=('Segoe UI', 8, 'bold'), padx=8, pady=3)
            badge.pack(side='left', padx=(6, 0))
        self.bracket_canvas = tk.Canvas(bracket_tab, width=1120, height=390,
                                        highlightthickness=2, background=self.ui_colors['surface'],
                                        cursor='fleur', takefocus=True,
                                        highlightbackground=self.ui_colors['border'],
                                        highlightcolor=self.ui_colors['accent'])
        self.bracket_canvas.bind(
            '<ButtonPress-1>', lambda event: self.bracket_canvas.scan_mark(event.x, event.y),
        )
        self.bracket_canvas.bind(
            '<B1-Motion>', lambda event: self.bracket_canvas.scan_dragto(event.x, event.y, gain=1),
        )
        self.bracket_canvas.bind('<Control-MouseWheel>', self._on_bracket_zoom_wheel)
        for key in ('Left', 'Right', 'Up', 'Down'):
            self.bracket_canvas.bind(f'<{key}>', self._pan_tournament_bracket_key)
        self.bracket_canvas.bind('<Key-0>', lambda _event: self._fit_tournament_bracket())
        bracket_xscroll = ttk.Scrollbar(bracket_tab, orient='horizontal', command=self.bracket_canvas.xview)
        bracket_yscroll = ttk.Scrollbar(bracket_tab, orient='vertical', command=self.bracket_canvas.yview)
        self.bracket_canvas.configure(xscrollcommand=bracket_xscroll.set, yscrollcommand=bracket_yscroll.set)
        bracket_yscroll.pack(side='right', fill='y')
        self.bracket_canvas.pack(fill='both', expand=True)
        bracket_xscroll.pack(fill='x')
        self.tournament_tabs.bind('<<NotebookTabChanged>>', self._on_tournament_tab_changed)
        self._draw_tournament_bracket(None)
        result_frame = ttk.Frame(report_tab)
        result_frame.pack(fill='both', expand=True)
        self.tournament_result = tk.Text(result_frame, wrap='word', state='disabled', font=('Consolas', 10))
        self.tournament_result.pack(side='left', fill='both', expand=True)
        result_scroll = ttk.Scrollbar(result_frame, orient='vertical', command=self.tournament_result.yview)
        result_scroll.pack(side='right', fill='y')
        self.tournament_result.configure(yscrollcommand=result_scroll.set)

    def _draw_tournament_bracket(self, bracket):
        canvas = self.bracket_canvas
        self.current_bracket = bracket
        self.bracket_zoom = 1.0
        canvas.delete('all')
        foreground = '#e9edf2' if self.dark_theme else '#263448'
        card = '#252b33' if self.dark_theme else '#ffffff'
        muted = '#aab4c0' if self.dark_theme else '#667085'
        connector = '#64748b'
        champion_fill = '#d8f3dc' if not self.dark_theme else '#254b39'
        champion_text = '#205c38' if not self.dark_theme else '#d7f5df'
        eliminated_fill = '#fce8e6' if not self.dark_theme else '#4a292c'
        eliminated_text = '#9f3838' if not self.dark_theme else '#f0b8b8'
        canvas.configure(background='#17191c' if self.dark_theme else '#f0f0f0')
        columns = ((20, 'Четвертьфиналы'), (310, 'Полуфиналы'),
                   (600, 'Финал'), (890, 'Победитель'))
        for x, title in columns:
            canvas.create_text(x + 110, 18, text=title, anchor='center', fill=foreground,
                               font=('Segoe UI', 11, 'bold'))

        qf_y = (42, 129, 216, 303)
        sf_y = (86, 260)
        final_y = 173
        champion_y = 173
        card_width, card_height = 220, 58

        def center(y):
            return y + card_height / 2

        def connector_path(x1, y1, x2, y2):
            middle = (x1 + x2) / 2
            canvas.create_line(x1, y1, middle, y1, middle, y2, x2, y2,
                               fill=connector, width=2, smooth=True)

        quarterfinals = bracket['quarterfinals'] if bracket else [None] * 4
        semifinals = bracket['semifinals'] if bracket else [None] * 2
        if bracket:
            for first_index, second_index, target_index in ((0, 1, 0), (2, 3, 1)):
                for source_index, target_row in ((first_index, 0), (second_index, 1)):
                    connector_path(20 + card_width, center(qf_y[source_index]),
                                   310, sf_y[target_index] + 18 + target_row * 25)
            for index, y in enumerate(sf_y):
                connector_path(310 + card_width, center(y),
                               600, final_y + 18 + index * 25)
            connector_path(600 + card_width, center(final_y), 890, center(champion_y))

        def draw_match(x, y, match):
            if match is None:
                names = ('Участник 1', 'Участник 2')
                scores = ('—', '—')
                winner = None
            else:
                names = (match['first'], match['second'])
                scores = (match['first_score'], match['second_score'])
                winner = match['winner']
            canvas.create_rectangle(x, y, x + card_width, y + card_height,
                                    fill=card, outline=connector, width=1)
            for row, (name, score) in enumerate(zip(names, scores)):
                is_winner = name == winner
                is_eliminated = winner is not None and not is_winner
                line_y = y + 18 + row * 25
                if is_winner or is_eliminated:
                    canvas.create_rectangle(x + 1, line_y - 11, x + card_width - 1,
                                            line_y + 11,
                                            fill=champion_fill if is_winner else eliminated_fill,
                                            outline='')
                canvas.create_text(x + 10, line_y, text=textwrap.shorten(name, 24),
                                   anchor='w',
                                   fill=champion_text if is_winner else eliminated_text if is_eliminated else foreground,
                                   font=('Segoe UI', 9, 'bold' if is_winner or is_eliminated else 'normal'))
                canvas.create_text(x + card_width - 10, line_y, text=str(score),
                                   anchor='e', fill=muted, font=('Segoe UI', 9, 'bold'))

        for y, match in zip(qf_y, quarterfinals):
            draw_match(20, y, match)
        for y, match in zip(sf_y, semifinals):
            draw_match(310, y, match)
        draw_match(600, final_y, bracket['final'] if bracket else None)
        final_match = bracket['final'] if bracket else None
        champion = final_match['winner'] if final_match else 'Победитель турнира'
        canvas.create_rectangle(890, champion_y, 1110, champion_y + card_height,
                                fill=champion_fill, outline=connector, width=1)
        canvas.create_text(1000, champion_y + card_height / 2, text=textwrap.shorten(champion, 24),
                           fill=champion_text, font=('Segoe UI', 10, 'bold'))
        bounds = canvas.bbox('all')
        if bounds:
            canvas.configure(scrollregion=bounds)
            self.root.after(50, self._fit_tournament_bracket)

    def _on_tournament_tab_changed(self, _event=None):
        selected_tab = self.tournament_tabs.index('current')
        stage_names = ('Плей-офф', 'Групповой этап', 'Отчёт')
        if hasattr(self, 'tournament_stage_label'):
            self.tournament_stage_label.configure(text=stage_names[selected_tab])
        if selected_tab == 0:
            self.root.after_idle(self._fit_tournament_bracket)

    def _fit_tournament_bracket(self):
        if not hasattr(self, 'bracket_canvas') or not self.bracket_canvas.winfo_exists():
            return
        if self.tournament_tabs.index('current') != 0:
            return
        canvas = self.bracket_canvas
        bounds = canvas.bbox('all')
        if not bounds:
            return
        content_width = max(1, bounds[2] - bounds[0])
        content_height = max(1, bounds[3] - bounds[1])
        viewport_width = max(1, canvas.winfo_width() - 8)
        viewport_height = max(1, canvas.winfo_height() - 8)
        current_zoom = max(0.01, getattr(self, 'bracket_zoom', 1.0))
        base_width = content_width / current_zoom
        base_height = content_height / current_zoom
        target_zoom = min(1.0, viewport_width / base_width, viewport_height / base_height)
        target_zoom = max(0.25, target_zoom)
        factor = target_zoom / current_zoom
        canvas.scale('all', 0, 0, factor, factor)
        self.bracket_zoom = target_zoom
        bounds = canvas.bbox('all')
        if bounds:
            canvas.configure(scrollregion=bounds)
        canvas.xview_moveto(0)
        canvas.yview_moveto(0)

    def _pan_tournament_bracket_key(self, event):
        if event.keysym == 'Left':
            self.bracket_canvas.xview_scroll(-1, 'units')
        elif event.keysym == 'Right':
            self.bracket_canvas.xview_scroll(1, 'units')
        elif event.keysym == 'Up':
            self.bracket_canvas.yview_scroll(-1, 'units')
        elif event.keysym == 'Down':
            self.bracket_canvas.yview_scroll(1, 'units')
        return 'break'

    def _zoom_tournament_bracket(self, factor):
        if not hasattr(self, 'bracket_canvas') or not self.bracket_canvas.winfo_exists():
            return
        next_zoom = getattr(self, 'bracket_zoom', 1.0) * factor
        if not 0.25 <= next_zoom <= 2.4:
            return
        canvas = self.bracket_canvas
        anchor_x = canvas.canvasx(max(1, canvas.winfo_width()) / 2)
        anchor_y = canvas.canvasy(max(1, canvas.winfo_height()) / 2)
        canvas.scale('all', anchor_x, anchor_y, factor, factor)
        self.bracket_zoom = next_zoom
        bounds = canvas.bbox('all')
        if bounds:
            canvas.configure(scrollregion=bounds)

    def _on_bracket_zoom_wheel(self, event):
        self._zoom_tournament_bracket(1.12 if event.delta > 0 else 0.89)
        return 'break'

    def _reset_tournament_bracket_view(self):
        self._draw_tournament_bracket(getattr(self, 'current_bracket', None))

    def _filter_tournament_available(self):
        if not hasattr(self, 'available_table') or not self.available_table.winfo_exists():
            return
        query = self.tournament_search_var.get().strip().casefold()
        for item in self.available_table.get_children():
            self.available_table.delete(item)
        roster_names = {
            self.tournament_files[int(item)].stem.casefold()
            for item in self.roster_table.get_children()
        } if hasattr(self, 'roster_table') and self.roster_table.winfo_exists() else set()
        for index, path in enumerate(self.tournament_files):
            if not Fight.is_character_alive(path):
                continue
            if query and query not in path.stem.casefold():
                continue
            if path.stem.casefold() in roster_names:
                continue
            self.available_table.insert('', 'end', iid=str(index), values=(path.stem,))

    def add_to_roster(self):
        selection = self.available_table.selection()
        if not selection:
            return
        item_id = selection[0]
        path = self.tournament_files[int(item_id)]
        if not Fight.is_character_alive(path):
            messagebox.showwarning('Персонаж мёртв', 'Мёртвого персонажа нельзя добавить в турнир.')
            self._filter_tournament_available()
            return
        if self.roster_table.exists(item_id):
            return
        self.roster_table.insert('', 'end', iid=item_id, values=self.available_table.item(item_id, 'values'))
        self.update_roster_count()

    def auto_fill_roster(self):
        if len(self.tournament_files) < Tournament.MIN_ROSTER_SIZE:
            messagebox.showwarning(
                'Мало персонажей',
                f'Для автозаполнения нужно минимум {Tournament.MIN_ROSTER_SIZE} персонажей.',
            )
            return
        for item_id in self.roster_table.get_children():
            self.roster_table.delete(item_id)
        for index, path in enumerate(self.tournament_files[:Tournament.MIN_ROSTER_SIZE]):
            item_id = str(index)
            self.roster_table.insert('', 'end', iid=item_id, values=(path.stem,))
        self.update_roster_count()

    def show_group_standings(self, groups):
        for group in groups:
            table = self.group_tables[group['name']]
            table.delete(*table.get_children())
            for player in group['standings']:
                tags = ('leader',) if player['rank'] <= 2 else ('eliminated',)
                table.insert('', 'end', tags=tags, values=(
                    player['rank'], player['name'], player['wins'],
                    f"{player['for']}:{player['against']}",
                ))

    def remove_from_roster(self):
        selection = self.roster_table.selection()
        if not selection:
            return
        self.roster_table.delete(selection[0])
        self.update_roster_count()

    def clear_roster(self):
        for item_id in self.roster_table.get_children():
            self.roster_table.delete(item_id)
        self.update_roster_count()

    def update_roster_count(self):
        count = len(self.roster_table.get_children())
        self.roster_table.heading('name', text=f'Ростер ({count}/20)')
        self.roster_count.configure(text=f'Выбрано: {count} / 20')
        self._filter_tournament_available()

    def start_tournament(self):
        selected = self.roster_table.get_children()
        dead_ids = {
            item_id for item_id in selected
            if not Fight.is_character_alive(self.tournament_files[int(item_id)])
        }
        if dead_ids:
            for item_id in dead_ids:
                self.roster_table.delete(item_id)
            self.update_roster_count()
            messagebox.showwarning(
                'Персонаж мёртв',
                'Мёртвые персонажи удалены из ростера. Выбери живых участников.',
            )
            return
        if len(selected) < Tournament.MIN_ROSTER_SIZE:
            messagebox.showwarning('Мало участников', 'Для турнира нужно добавить в ростер минимум 20 персонажей.')
            return
        paths = [self.tournament_files[int(index)] for index in selected]
        self.audio.play_effect('tournament_start')
        try:
            result = Tournament.run_tournament(paths)
        except (OSError, ValueError) as error:
            self._show_error('Ошибка турнира', str(error))
            return
        self.set_text(self.tournament_result, result['report'])
        self._draw_tournament_bracket(result['bracket'])
        self.show_group_standings(result['group_standings'])
        self.tournament_tabs.select(1)
        self.audio.play_effect('tournament_complete')

    def show_fight(self, ladder_mode=False):
        self.clear()
        self.audio.play_music('combat')
        self.fight_ladder_mode = ladder_mode
        page_scale = self._automatic_page_scale(900, 760)
        self._set_page_geometry(f'{int(900 * page_scale)}x{int(760 * page_scale)}')
        if page_scale < 0.95:
            page = ttk.Frame(self.root)
            page.pack(fill='both', expand=True)
            page_canvas = tk.Canvas(page, highlightthickness=0,
                                    background=self.ui_colors['background'])
            page_scroll = ttk.Scrollbar(page, orient='vertical', command=page_canvas.yview)
            page_canvas.configure(yscrollcommand=page_scroll.set)
            page_canvas.pack(side='left', fill='both', expand=True)
            page_scroll.pack(side='right', fill='y')
            frame = ttk.Frame(page_canvas, padding=18)
            page_window = page_canvas.create_window((0, 0), window=frame, anchor='nw')
            frame.bind('<Configure>', lambda _event: page_canvas.configure(
                scrollregion=page_canvas.bbox('all')))
            page_canvas.bind('<Configure>', lambda event: page_canvas.itemconfigure(
                page_window, width=event.width))
        else:
            frame = ttk.Frame(self.root, padding=18)
            frame.pack(fill='both', expand=True)
        if not ladder_mode:
            ttk.Button(frame, text='← На главную', command=self.show_home).pack(
                anchor='w', pady=(0, 12)
            )
        if ladder_mode:
            current_villain = self.ladder_villains[self.ladder_index]
            files = [self.ladder_hero_path, current_villain]
            page_title = f'Забег в ладдер · бой {self.ladder_index + 1} из {len(self.ladder_villains)}'
        else:
            files = character_files_by_creation_date(living_only=True)
            page_title = 'Сражение персонажей'
        self.heading(frame, page_title)
        if len(files) < 2:
            ttk.Label(frame, text='Для сражения нужны минимум два живых персонажа.').pack(anchor='w')
            return
        self.fight_files = files
        names = [file.stem for file in files]
        row = ttk.Frame(frame)
        row.pack(fill='x', pady=(0, 8))
        compact_fight_layout = page_scale < 0.95
        left = ttk.LabelFrame(row, text='Боец 1', padding=8, labelanchor='n')
        center = ttk.LabelFrame(row, text='Арена', padding=8, labelanchor='n')
        right = ttk.LabelFrame(row, text='Боец 2', padding=8, labelanchor='n')
        if compact_fight_layout:
            center.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, 8))
            left.grid(row=1, column=0, sticky='nsew', padx=(0, 4))
            right.grid(row=1, column=1, sticky='nsew', padx=(4, 0))
            for column in (0, 1):
                row.columnconfigure(column, weight=1, uniform='fighter')
        else:
            left.pack(side='left', fill='y', expand=True, padx=(0, 8))
            center.pack(side='left', fill='y')
            right.pack(side='left', fill='y', expand=True, padx=(8, 0))
        if ladder_mode:
            fighter_name_style = {
                'background': self.ui_colors['surface'],
                'foreground': self.ui_colors['foreground'],
                'font': ('Segoe UI', 10, 'bold'),
                'anchor': 'center',
            }
            tk.Label(left, text=names[0], **fighter_name_style).pack(fill='x', padx=3, pady=(1, 3))
            tk.Label(right, text=names[1], **fighter_name_style).pack(fill='x', padx=3, pady=(1, 3))
            self.first_fighter = None
            self.second_fighter = None
            self.fight_names = (names[0], names[1])
        else:
            self.first_fighter = ttk.Combobox(left, state='readonly', values=names)
            self.first_fighter.pack(fill='x', padx=3)
            self.second_fighter = ttk.Combobox(right, state='readonly', values=names)
            self.second_fighter.pack(fill='x', padx=3)
            self.first_fighter.current(0)
            self.second_fighter.current(1)
            self.fight_names = (self.first_fighter.get(), self.second_fighter.get())
        self.fight_rotation = 0
        self.fight_portrait_canvases = []
        self.fight_stat_labels = []
        self.fight_panels = (left, right)
        self.fight_outcome_labels = []
        for panel in (left, right):
            outcome = tk.Label(panel, text='', font=('Segoe UI', 10, 'bold'),
                               background='#20242a' if self.dark_theme else '#f0f0f0',
                               foreground='#e9edf2' if self.dark_theme else '#263448')
            outcome.pack(fill='x', pady=(4, 0))
            outcome.pack_forget()
            self.fight_outcome_labels.append(outcome)
            portrait = tk.Canvas(panel, width=130, height=195, highlightthickness=0,
                                 background='#20242a' if self.dark_theme else '#e8e2d8')
            portrait.pack(pady=(6, 0))
            self.fight_portrait_canvases.append(portrait)
            card_bg = '#20242a' if self.dark_theme else '#fffaf0'
            card = tk.Frame(panel, background=card_bg, highlightthickness=1,
                            highlightbackground='#c69b4b' if self.dark_theme else '#d6bd88')
            card.pack(fill='x', padx=3, pady=(5, 0), anchor='nw')
            self.fight_stat_labels.append(card)
        self.fight_portrait_sources = {}
        if not ladder_mode:
            self.first_fighter.bind('<<ComboboxSelected>>', lambda _event: self._on_fight_selection_changed(0))
            self.second_fighter.bind('<<ComboboxSelected>>', lambda _event: self._on_fight_selection_changed(1))
        self.fight_status = ttk.Label(center, text='', anchor='center')
        self.fight_status.pack(fill='x', pady=(0, 4))
        wheel_scale = self._wheel_scale(600, 640)
        self.fight_wheel = tk.Canvas(center, width=int(280 * wheel_scale), height=int(280 * wheel_scale),
                                     highlightthickness=0, background='#20242a' if self.dark_theme else '#f0f0f0')
        self.fight_wheel.pack(pady=(0, 6))
        self._draw_fight_wheel(names[0], names[1], 0)
        self.fight_button = ttk.Button(center, text='Начать сражение',
                                       command=self.start_fight, style='Primary.TButton')
        history_frame = ttk.LabelFrame(center, text='История раундов', padding=6)
        history_frame.pack(fill='x', pady=(0, 6))
        self.fight_history = ttk.Treeview(
            history_frame, columns=('round', 'attribute', 'score', 'winner'),
            show='headings', height=max(2, min(3, int(4 * page_scale))), selectmode='none',
        )
        for column, title, width in (
            ('round', 'Раунд', 70), ('attribute', 'Параметр', 240),
            ('score', 'Счёт', 100), ('winner', 'Победитель', 220),
        ):
            self.fight_history.heading(column, text=title)
            self.fight_history.column(column, width=width, minwidth=60, anchor='center',
                                      stretch=column in ('attribute', 'winner'))
        self.fight_history.pack(fill='x')
        self.fight_button.pack()
        self.fight_history.tag_configure('first-wins', foreground='#25834b' if not self.dark_theme else '#91e2ac')
        self.fight_history.tag_configure('second-wins', foreground='#c34747' if not self.dark_theme else '#ffaaaa')
        self._draw_fight_portrait(0)
        self._draw_fight_portrait(1)

    def _on_fight_selection_changed(self, fighter_index):
        for panel, outcome, stats_card, portrait in zip(
            self.fight_panels, self.fight_outcome_labels,
            self.fight_stat_labels, self.fight_portrait_canvases,
        ):
            outcome.pack_forget()
            panel.configure(style='TLabelframe')
            card_bg = '#20242a' if self.dark_theme else '#fffaf0'
            for row in stats_card.winfo_children():
                row.configure(background=card_bg)
                if isinstance(row, tk.Frame):
                    row.configure(highlightbackground=self.ui_colors['border'])
                    for label in row.winfo_children():
                        label.configure(background=card_bg)
            stats_card.configure(
                background=card_bg,
                highlightbackground='#c69b4b' if self.dark_theme else '#d6bd88',
            )
            portrait.configure(highlightthickness=0)
        self._draw_fight_portrait(fighter_index)
        self.fight_names = (self.first_fighter.get(), self.second_fighter.get())
        self._draw_fight_wheel(*self.fight_names, getattr(self, 'fight_rotation', 0))

    def _draw_fight_portrait(self, fighter_index):
        if fighter_index not in (0, 1):
            return
        canvas = self.fight_portrait_canvases[fighter_index]
        canvas.delete('all')
        if self.fight_ladder_mode:
            character_path = self.fight_files[fighter_index]
            fighter_name = character_path.stem
        else:
            selector = self.first_fighter if fighter_index == 0 else self.second_fighter
            index = selector.current()
            if index < 0:
                return
            character_path = self.fight_files[index]
            fighter_name = selector.get()
        try:
            lines = character_path.read_text(encoding='utf-8').splitlines()
        except OSError:
            return
        properties = {}
        for line in lines:
            key, separator, value = line.partition(':')
            if separator:
                properties[key.strip()] = value.strip()

        def readable(value):
            try:
                return value.encode('latin-1').decode('utf-8')
            except (UnicodeEncodeError, UnicodeDecodeError):
                try:
                    return value.encode('cp1251').decode('utf-8')
                except (UnicodeEncodeError, UnicodeDecodeError):
                    return value

        stats_card = self.fight_stat_labels[fighter_index]
        for child in stats_card.winfo_children():
            child.destroy()
        card_bg = '#20242a' if self.dark_theme else '#fffaf0'
        main_fg = '#f4ead6' if self.dark_theme else '#332b20'
        muted_fg = '#d7b76f' if self.dark_theme else '#8b672a'
        tk.Label(stats_card, text='ХАРАКТЕРИСТИКИ',
                 font=('Segoe UI', 10, 'bold'), bg=card_bg, fg=muted_fg,
                 anchor='center').pack(fill='x', padx=4, pady=(5, 3))
        stat_fields = (
            ('Очки', 'points'),
            ('Раса', 'race'), ('Подраса', 'subrace'),
            ('Рост', 'size'), ('Сила', 'strength'),
            ('Скорость', 'speed'),
            ('Интеллект', 'iq'),
            ('Бой', 'fighting'), ('Оружие', 'weapon'),
            ('Мастерство', 'weapon_mastery'),
            ('Чары', 'weapon_enchantment'),
            ('Сила', 'ability'), ('Титул', 'title'),
        )
        for label_text, key in stat_fields:
            value = properties.get(key, '')
            if not value or value.casefold() == 'none':
                continue
            row = tk.Frame(
                stats_card, bg=card_bg, padx=7, pady=4, highlightthickness=1,
                highlightbackground=self.ui_colors['border'],
            )
            row.pack(fill='x', padx=3, pady=2)
            row.grid_columnconfigure(1, weight=1)
            tk.Label(row, text=label_text, font=('Segoe UI', 9, 'bold'),
                     bg=card_bg, fg=muted_fg, anchor='w').grid(
                         row=0, column=0, sticky='w', padx=(0, 6))
            tk.Label(row, text=readable(value), font=('Segoe UI', 9), bg=card_bg,
                     fg=main_fg, justify='right', anchor='e', wraplength=120).grid(
                         row=0, column=1, sticky='e')

        if self.fight_ladder_mode and fighter_index == 1:
            self._draw_ladder_villain_portrait(canvas, fighter_name, properties)
            return

        templates = dict(zip((race.casefold() for race in data.race_sum), ('human', 'orc', 'elf')))
        aliases = dict(templates)
        for race, template in templates.items():
            try:
                aliases[race.encode('utf-8').decode('cp1251').casefold()] = template
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
        template = aliases.get(properties.get('race', '').casefold())
        if not template:
            canvas.create_text(65, 97, text=fighter_name, width=120,
                               fill='#f1f3f5' if self.dark_theme else '#202124')
            return

        root = Path(__file__).resolve().parent / 'CardTemplates'
        for kind in ('races',):
            key = (kind, template)
            if key in self.fight_portrait_sources:
                continue
            image_path = root / kind / f'{template}.png'
            if not image_path.exists():
                continue
            try:
                image = tk.PhotoImage(file=str(image_path))
                scale = max(1, math.ceil(max(image.width() / 130, image.height() / 195)))
                self.fight_portrait_sources[key] = image.subsample(scale, scale)
            except tk.TclError:
                pass
        background = self.fight_portrait_sources.get(('races', template))
        if background:
            canvas.create_image(65, 97, image=background, anchor='center')
        size_names = dict(zip((size.casefold() for size in data.size_sum), (120, 140, 160, 180)))
        for size, target in zip(data.size_sum, (120, 140, 160, 180)):
            try:
                size_names[size.encode('utf-8').decode('cp1251').casefold()] = target
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
        target_height = size_names.get(properties.get('size', '').casefold(), 140)
        source_key = ('character_source', template)
        if source_key not in self.fight_portrait_sources:
            character_path = root / 'characters' / f'{template}.png'
            if character_path.exists():
                try:
                    self.fight_portrait_sources[source_key] = tk.PhotoImage(file=str(character_path))
                except tk.TclError:
                    pass
        character_key = ('characters', template, target_height)
        character = self.fight_portrait_sources.get(character_key)
        source = self.fight_portrait_sources.get(source_key)
        if character is None and source is not None:
            scale = max(1, math.ceil(source.height() / target_height))
            character = source.subsample(scale, scale)
            self.fight_portrait_sources[character_key] = character
        if character:
            weapon_files = ('katana', 'axe', 'sword', 'pistol', 'tank', 'portal_cannon')
            weapon_aliases = dict(zip((name.casefold() for name in data.weapon_sum[1:]), weapon_files))
            for name, weapon_file in zip(data.weapon_sum[1:], weapon_files):
                try:
                    weapon_aliases[name.encode('utf-8').decode('cp1251').casefold()] = weapon_file
                except (UnicodeEncodeError, UnicodeDecodeError):
                    pass
            weapon_template = weapon_aliases.get(properties.get('weapon', '').casefold())
            if weapon_template:
                target_weapon_size = max(16, round(32 * target_height / 140))
                weapon_key = ('weapons', weapon_template, target_weapon_size)
                if weapon_key not in self.fight_portrait_sources:
                    weapon_path = root / 'weapons' / f'{weapon_template}.png'
                    if weapon_path.exists():
                        try:
                            source = tk.PhotoImage(file=str(weapon_path))
                            scale = max(1, math.ceil(max(
                                source.width() / target_weapon_size,
                                source.height() / target_weapon_size,
                            )))
                            self.fight_portrait_sources[weapon_key] = source.subsample(scale, scale)
                        except tk.TclError:
                            pass
                weapon = self.fight_portrait_sources.get(weapon_key)
                if weapon:
                    hand_fraction = {'human': 0.17, 'orc': 0.12, 'elf': 0.17}.get(template, 0.16)
                    hand_x = 65 - character.width() / 2 + character.width() * hand_fraction
                    hand_y = 189 - character.height() * 0.62
                    if weapon_template == 'tank':
                        x, y = hand_x - weapon.width() * 0.58, hand_y - weapon.height() * 0.62
                    else:
                        grip_anchors = {
                            'katana': (0.90, 0.91), 'axe': (0.92, 0.93),
                            'sword': (0.90, 0.91), 'pistol': (0.83, 0.76),
                            'portal_cannon': (0.90, 0.90),
                        }
                        grip_x, grip_y = grip_anchors.get(weapon_template, (0.9, 0.9))
                        x, y = hand_x - weapon.width() * grip_x, hand_y - weapon.height() * grip_y
                    canvas.create_image(x, y, image=weapon, anchor='nw')
            canvas.create_image(65, 189, image=character, anchor='s')

    def _draw_ladder_villain_portrait(self, canvas, fighter_name, properties):
        image_reference = properties.get('image', '').strip()
        foreground = '#f1f3f5' if self.dark_theme else '#202124'
        fallback_text = f'{fighter_name}\n\nНет портрета'
        if not image_reference or image_reference.casefold() in ('none', 'null'):
            canvas.create_text(65, 97, text=fallback_text, width=120, fill=foreground)
            return

        relative_path = Path(image_reference)
        if relative_path.is_absolute():
            canvas.create_text(65, 97, text=fallback_text, width=120, fill=foreground)
            return
        project_root = Path(__file__).resolve().parent
        image_path = (project_root / relative_path).resolve()
        try:
            image_path.relative_to(project_root)
        except ValueError:
            canvas.create_text(65, 97, text=fallback_text, width=120, fill=foreground)
            return

        cache_key = ('villain_portrait', str(image_path))
        image = self.fight_portrait_sources.get(cache_key)
        if image is None and image_path.is_file():
            try:
                source = tk.PhotoImage(file=str(image_path))
                scale = max(1, math.ceil(max(source.width() / 130, source.height() / 195)))
                image = source.subsample(scale, scale)
                self.fight_portrait_sources[cache_key] = image
            except tk.TclError:
                image = None

        if image is None:
            canvas.create_text(
                65, 97, text=f'{fighter_name}\n\nПортрет не найден:\n{image_reference}',
                width=120, fill=foreground, font=('Segoe UI', 8),
            )
            return
        canvas.create_image(65, 97, image=image, anchor='center')

    def start_fight(self):
        if self.fight_ladder_mode:
            first_index, second_index = 0, 1
        else:
            first_index = self.first_fighter.current()
            second_index = self.second_fighter.current()
        if first_index < 0 or second_index < 0:
            messagebox.showwarning('Выберите персонажей', 'Нужно выбрать обоих участников.')
            return
        if first_index == second_index:
            messagebox.showwarning('Выберите разных', 'Один персонаж не может сражаться с самим собой.')
            return
        selected_paths = (
            (self.ladder_hero_path,) if self.fight_ladder_mode else
            (self.fight_files[first_index], self.fight_files[second_index])
        )
        if any(not Fight.is_character_alive(path) for path in selected_paths):
            messagebox.showwarning(
                'Персонаж мёртв', 'Мёртвые персонажи не могут участвовать в сражении.'
            )
            if self.fight_ladder_mode:
                self._leave_ladder()
            else:
                self.show_fight()
            return
        try:
            result = Fight.fight_match(
                self.fight_files[first_index], self.fight_files[second_index],
                award_points=not self.fight_ladder_mode,
                check_liveness=(True, not self.fight_ladder_mode),
            )
        except (OSError, ValueError) as error:
            self._show_error('Ошибка сражения', str(error))
            return
        self.audio.play_effect('combat_start')
        self.fight_button.configure(text='Бой идёт…', state='disabled')
        if not self.fight_ladder_mode:
            self.first_fighter.configure(state='disabled')
            self.second_fighter.configure(state='disabled')
        self.fight_rounds = result['comparisons']
        self.fight_report = result['report']
        self.fight_winner_index = result['winner_index']
        self.fight_winner = self.fight_names[self.fight_winner_index]
        self.fight_round_index = 0
        self.fight_rotation = 0
        if not self.fight_ladder_mode:
            self.fight_names = (self.first_fighter.get(), self.second_fighter.get())
        self.fight_history.delete(*self.fight_history.get_children())
        self.fight_status.configure(style='TLabel', wraplength=0)
        for panel, outcome, stats_card, portrait in zip(
            self.fight_panels, self.fight_outcome_labels,
            self.fight_stat_labels, self.fight_portrait_canvases,
        ):
            outcome.pack_forget()
            panel.configure(style='TLabelframe')
            card_bg = '#20242a' if self.dark_theme else '#fffaf0'
            for row in stats_card.winfo_children():
                row.configure(background=card_bg)
                if isinstance(row, tk.Frame):
                    row.configure(highlightbackground=self.ui_colors['border'])
                    for label in row.winfo_children():
                        label.configure(background=card_bg)
            stats_card.configure(background=card_bg)
            stats_card.configure(highlightbackground='#c69b4b' if self.dark_theme else '#d6bd88')
            portrait.configure(highlightthickness=0)
        self._spin_fight_round()

    def _draw_fight_wheel(self, first_name, second_name, rotation, first_points=1, second_points=1):
        canvas = self.fight_wheel
        canvas.delete('all')
        width, height = int(canvas['width']), int(canvas['height'])
        cx, cy = width / 2, height / 2 + 8
        radius = min(width, height) / 2 - 34
        box = (cx - radius, cy - radius, cx + radius, cy + radius)
        first_points = max(0, first_points)
        second_points = max(0, second_points)
        total_points = first_points + second_points
        first_extent = 180 if total_points == 0 else 360 * first_points / total_points
        canvas.create_oval(cx-radius-4, cy-radius-4, cx+radius+4, cy+radius+4,
                           fill='#263448', outline='')
        second_extent = 360 - first_extent
        canvas.create_arc(*box, start=rotation, extent=first_extent,
                          fill='#56b4d3', outline='#f7f8fa', width=4)
        canvas.create_arc(*box, start=rotation + first_extent, extent=second_extent,
                          fill='#f08a70', outline='#f7f8fa', width=4)
        for angle, label in ((rotation + first_extent / 2, first_name),
                             (rotation + first_extent + second_extent / 2, second_name)):
            radians = math.radians(angle)
            x = cx + math.cos(radians) * radius * 0.56
            y = cy - math.sin(radians) * radius * 0.56
            canvas.create_text(x, y, text=textwrap.fill(label, 16), width=110,
                              font=('Segoe UI', 10, 'bold'), fill='#17212b', justify='center')
        canvas.create_oval(cx-22, cy-22, cx+22, cy+22, fill='#263448', outline='#f7f8fa', width=3)
        canvas.create_oval(cx-8, cy-8, cx+8, cy+8, fill='#f7f8fa', outline='')
        canvas.create_polygon(cx-16, cy-radius-23, cx+16, cy-radius-23, cx, cy-radius+5,
                              fill='#263448', outline='#f7f8fa', width=2)
        canvas.create_polygon(cx-10, cy-radius-19, cx+10, cy-radius-19, cx, cy-radius-1,
                              fill='#f4c95d', outline='')

    def _spin_fight_round(self):
        if self.fight_round_index >= len(self.fight_rounds):
            self._draw_fight_portrait(0)
            self._draw_fight_portrait(1)
            last_comparison = self.fight_rounds[-1]
            self._draw_fight_wheel(
                *self.fight_names,
                self.fight_rotation,
                last_comparison['first_points'],
                last_comparison['second_points'],
            )
            self.fight_status.configure(text='Сражение завершено')
            winner = self.fight_winner
            winner_index = self.fight_winner_index
            win_bg = '#d9f2df' if not self.dark_theme else '#214a36'
            lose_bg = '#f8dddd' if not self.dark_theme else '#542d32'
            win_fg = '#176b35' if not self.dark_theme else '#a8efbd'
            lose_fg = '#a12d35' if not self.dark_theme else '#ffb5b5'
            for index, (panel, outcome, stats_card, portrait) in enumerate(zip(
                self.fight_panels, self.fight_outcome_labels,
                self.fight_stat_labels, self.fight_portrait_canvases,
            )):
                is_winner = index == winner_index
                color = '#25834b' if is_winner else '#c34747'
                background = win_bg if is_winner else lose_bg
                foreground = win_fg if is_winner else lose_fg
                style_name = f'Fight.{"Winner" if is_winner else "Loser"}.TLabelframe'
                self.style.configure(style_name, bordercolor=color, background=background)
                self.style.configure(f'{style_name}.Label', foreground=foreground, background=background)
                panel.configure(style=style_name)
                outcome.configure(
                    text='ПОБЕДИТЕЛЬ' if is_winner else 'ПРОИГРАВШИЙ',
                    background=background, foreground=foreground,
                )
                outcome.pack(fill='x', pady=(4, 0))
                stats_card.configure(background=background, highlightbackground=color)
                for row in stats_card.winfo_children():
                    row.configure(background=background)
                    if isinstance(row, tk.Frame):
                        row.configure(highlightbackground=color)
                    for label in row.winfo_children():
                        label.configure(background=background)
                portrait.configure(highlightthickness=3, highlightbackground=color)
            banner_bg = '#d9f2df' if not self.dark_theme else '#214a36'
            banner_fg = '#176b35' if not self.dark_theme else '#a8efbd'
            self.style.configure('FightWinner.TLabel', background=banner_bg, foreground=banner_fg,
                                 font=('Segoe UI', 14, 'bold'), padding=(10, 8))
            self.fight_status.configure(
                text=f'✦ ПОБЕДИТЕЛЬ: {winner} ✦', style='FightWinner.TLabel',
                wraplength=270, justify='center',
            )
            if self.fight_ladder_mode:
                final_ladder_fight = (
                    winner_index == 1
                    or self.ladder_index + 1 >= len(self.ladder_villains)
                )
                self.audio.play_effect(
                    ('ladder_run_win' if winner_index == 0 else 'ladder_run_loss')
                    if final_ladder_fight else 'ladder_battle_win',
                )
                self._mark_ladder_loser_dead(winner_index)
                if winner_index == 0 and self.ladder_index + 1 < len(self.ladder_villains):
                    self._save_ladder_run_progress(fight_result='Победа')
                    next_villain = self.ladder_villains[self.ladder_index + 1].stem
                    self.fight_status.configure(
                        text=f'ПОБЕДА! Следующий соперник: {next_villain}',
                        wraplength=270, justify='center',
                    )
                    self.fight_button.configure(
                        text='Следующий бой', command=self._advance_ladder_fight, state='normal',
                    )
                    return
                if winner_index == 0:
                    self._save_ladder_run_progress(fight_result='Победа', final_result='Победа')
                    messagebox.showinfo(
                        'Поздравляем с победой!',
                        f'{self.ladder_hero_path.stem} одолел всех {len(self.ladder_villains)} '
                        'противников и прошёл ладдер!\n\n'
                        'Теперь откроется последняя глава хроник.',
                    )
                    self.show_ending_lore()
                else:
                    self._save_ladder_run_progress(fight_result='Поражение', final_result='Поражение')
                    messagebox.showinfo(
                        'Поражение',
                        f'{self.ladder_hero_path.stem} проиграл бой с {self.ladder_villains[self.ladder_index].stem}.',
                    )
                    self.show_home()
                return
            self.audio.play_effect(
                'arena_battle_win' if winner_index == 0 else 'arena_battle_loss',
            )
            self.fight_button.configure(text='Начать сражение', state='normal')
            self.first_fighter.configure(state='readonly')
            self.second_fighter.configure(state='readonly')
            self.first_fighter.selection_clear()
            self.second_fighter.selection_clear()
            self.fight_button.focus_set()
            return

        comparison = self.fight_rounds[self.fight_round_index]
        winner_index = comparison['winner_index']
        first_points = max(0, comparison['first_points'])
        second_points = max(0, comparison['second_points'])
        total_points = first_points + second_points
        first_extent = 180 if total_points == 0 else 360 * first_points / total_points
        winner_midpoint = first_extent / 2 if winner_index == 0 else first_extent + (360 - first_extent) / 2
        start_rotation = self.fight_rotation
        target = (90 - winner_midpoint) % 360
        rotation_delta = (target - start_rotation % 360) % 360 + random.randint(4, 6) * 360
        frames = 75
        frame_index = 0
        self.fight_status.configure(text=(
            f"{comparison['attribute']}: {comparison['first_points']} — "
            f"{comparison['second_points']}"
        ))

        def animate():
            nonlocal frame_index
            frame_index += 1
            progress = frame_index / frames
            eased = 1 - (1 - progress) ** 3
            rotation = start_rotation + rotation_delta * eased
            self._draw_fight_wheel(*self.fight_names, rotation, first_points, second_points)
            if frame_index < frames:
                self.spin_after_id = self.root.after(24, animate)
                return
            self.fight_rotation = target
            self.fight_status.configure(text=f"{comparison['attribute']}: {comparison['winner']}")
            row_tag = 'first-wins' if comparison['winner_index'] == 0 else 'second-wins'
            round_item = self.fight_history.insert('', 'end', tags=(row_tag,), values=(
                self.fight_round_index + 1, comparison['attribute'],
                f"{comparison['first_points']}:{comparison['second_points']}",
                comparison['winner'],
            ))
            self.fight_history.see(round_item)
            self.audio.play_effect('round_win' if winner_index == 0 else 'round_loss')
            self.fight_round_index += 1
            self.spin_after_id = self.root.after(550, self._spin_fight_round)

        animate()

    def show_create(self):
        self.clear()
        self.audio.play_music(None)
        page_scale = self._automatic_page_scale(920, 850)
        self._set_page_geometry(f'{int(920 * page_scale)}x{int(850 * page_scale)}')
        frame = ttk.Frame(self.root, padding=(28, 22))
        frame.pack(fill='both', expand=True)
        ttk.Button(frame, text='← На главную', command=self.show_home).pack(
            anchor='w', pady=(0, 8)
        )
        self.heading(frame, 'Создание персонажа')

        form = ttk.Frame(frame)
        form.pack(fill='x', pady=(0, 12))
        ttk.Label(form, text='Имя героя').pack(anchor='w', pady=(0, 4))
        self.name_var = tk.StringVar()
        name_validator = self.root.register(self._name_characters_allowed)
        self.name_entry = ttk.Entry(form, textvariable=self.name_var, width=28,
                                    validate='key', validatecommand=(name_validator, '%P'))
        self.name_entry.pack(side='left', anchor='w')
        self.name_entry.bind('<Return>', lambda _event: self.generate())
        self.generate_button = ttk.Button(
            form, text='Начать генерацию',
            command=self.generate, style='Primary.TButton',
        )
        self.generate_button.pack(side='left', padx=(10, 0))

        progress_row = ttk.Frame(frame)
        progress_row.pack(fill='x', pady=(0, 12))
        self.create_progress_label = ttk.Label(progress_row, text='Подготовьтесь к генерации',
                                               style='Muted.TLabel')
        self.create_progress_label.pack(anchor='w', pady=(0, 5))
        self.create_progress = ttk.Progressbar(progress_row, mode='determinate', maximum=1, value=0,
                                               style='Creation.Horizontal.TProgressbar')
        self.create_progress.pack(fill='x')

        content = ttk.Frame(frame)
        content.pack(fill='both', expand=True)
        wheel_panel = ttk.LabelFrame(content, text='Случайный выбор', padding=12)
        wheel_panel.pack(side='left', fill='both', expand=True, padx=(0, 12))
        self.wheel_status = ttk.Label(wheel_panel, text='Каждый атрибут выбирается отдельно.',
                                       anchor='center', style='Muted.TLabel')
        self.wheel_status.pack(fill='x', pady=(0, 2))
        self.wheel_selection = ttk.Label(wheel_panel, text='', anchor='center', font=('Segoe UI', 11, 'bold'))
        self.wheel_selection.pack(fill='x', pady=(0, 5))
        wheel_size = int(390 * self._wheel_scale(920, 850))
        self.wheel_canvas = tk.Canvas(
            wheel_panel, width=wheel_size, height=wheel_size, highlightthickness=1,
            highlightbackground=self.ui_colors['border'], background=self.ui_colors['surface'],
        )
        self.wheel_canvas.pack(pady=4)
        self._draw_wheel(data.substory_sum, 0)
        self.fast_spin_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(wheel_panel, text='Быстрое вращение',
                        variable=self.fast_spin_var).pack(pady=(2, 0))
        self.skip_spin_button = ttk.Button(
            wheel_panel, text='Пропустить этот шаг',
            command=self._skip_current_spin, state='disabled', style='Skip.TButton',
        )
        self.skip_spin_button.pack(pady=(5, 0))
        summary = ttk.LabelFrame(content, text='Карточка героя', padding=10)
        summary.pack(side='right', fill='y', padx=(0, 2))
        summary.configure(width=250)
        summary.pack_propagate(False)
        self.create_summary_rows = {}
        name_card = tk.Frame(summary, background=self.ui_colors['surface'], padx=8, pady=6,
                             highlightthickness=1, highlightbackground=self.ui_colors['border'])
        name_card.pack(fill='x', pady=(0, 5))
        self.create_summary_name = tk.Label(
            name_card, text='Новый герой',
            bg=self.ui_colors['surface'], fg=self.ui_colors['foreground'],
            font=('Segoe UI', 12, 'bold'), wraplength=210, anchor='w', justify='left',
        )
        self.create_summary_name.pack(fill='x')
        for label, key in (
            ('Происхождение', 'substory'),
            ('Раса', 'race_line'), ('Рост', 'size'),
            ('Сила', 'strength'), ('Скорость', 'speed'),
            ('Ум', 'iq'), ('Боевые навыки', 'fighting'),
            ('Оружие', 'weapon'), ('Владение', 'weapon_mastery'),
            ('Зачарование', 'weapon_enchantment'),
            ('Способность', 'ability'),
            ('Мощь', 'ability_power'), ('Хаос', 'chaos'),
            ('Титул', 'title'),
        ):
            row = tk.Frame(summary, background=self.ui_colors['surface'], padx=7, pady=4,
                           highlightthickness=1, highlightbackground=self.ui_colors['border'])
            row.pack(fill='x', pady=2)
            row.grid_columnconfigure(1, weight=1)
            tk.Label(row, text=label, anchor='w', background=self.ui_colors['surface'],
                     foreground=self.ui_colors['muted'], font=('Segoe UI', 9, 'bold')).grid(
                         row=0, column=0, sticky='w', padx=(0, 6))
            value_label = tk.Label(row, text='—', anchor='e', justify='right',
                                   background=self.ui_colors['surface'], foreground=self.ui_colors['foreground'],
                                   font=('Segoe UI', 9, 'bold'), wraplength=125)
            value_label.grid(row=0, column=1, sticky='e')
            self.create_summary_rows[key] = value_label
        self.name_entry.focus_set()

    @staticmethod
    def _readable_creation_value(value):
        text = str(value)
        try:
            return text.encode('cp1251').decode('utf-8')
        except (UnicodeEncodeError, UnicodeDecodeError):
            return text

    def _update_creation_summary(self):
        hero = self.current_hero
        self.create_summary_name.configure(text=self._readable_creation_value(hero.name))
        values = {
            'substory': getattr(hero, 'substory', None),
            'race_line': ' '.join(filter(None, (
                getattr(hero, 'subrace', None), getattr(hero, 'race', None),
            ))),
            'size': getattr(hero, 'size', None), 'strength': getattr(hero, 'strength', None),
            'speed': getattr(hero, 'speed', None), 'iq': getattr(hero, 'iq', None),
            'fighting': getattr(hero, 'fighting', None), 'weapon': getattr(hero, 'weapon', None),
            'weapon_mastery': getattr(hero, 'weapon_mastery', None),
            'weapon_enchantment': getattr(hero, 'weapon_enchantment', None),
            'ability': getattr(hero, 'ability', None), 'ability_power': getattr(hero, 'ability_power', None),
            'chaos': getattr(hero, 'chaos', None), 'title': getattr(hero, 'title', None),
        }
        for key, widget in self.create_summary_rows.items():
            value = values.get(key)
            widget.configure(text=self._readable_creation_value(value) if value not in (None, '') else '—')

    def _update_creation_progress(self):
        total = max(1, len(self.wheel_steps))
        completed = min(self.spin_index, total)
        self.create_progress.configure(maximum=total, value=completed)
        if completed >= total:
            text = 'Генерация завершена'
        else:
            current_step = self._readable_creation_value(self.wheel_steps[self.spin_index][0])
            text = f'Шаг {completed + 1} из {total}  ·  {current_step}'
        self.create_progress_label.configure(text=text)

    def _make_wheel_steps(self, hero):
        def simple_step(label, attribute, options, weights):
            setter = lambda value, attribute=attribute: setattr(hero, attribute, value)
            return (label, options, weights, setter, str)

        race_options = [
            (race, subrace)
            for race, subraces in data.race_sum.items()
            for subrace in subraces
        ]
        race_weights = [
            data.race_weights[list(data.race_sum).index(race)]
            * data.race_subrace_weights[race][data.race_sum[race].index(subrace)]
            for race, subrace in race_options
        ]
        def set_race(value):
            hero.race, hero.subrace = value

        steps = [
            simple_step('Происхождение', 'substory', data.substory_sum, data.substory_weights),
            ('Раса', race_options, race_weights, set_race, lambda value: f'{value[1]} {value[0]}'),
            simple_step('Рост', 'size', data.size_sum, data.size_weights),
            simple_step('Сила', 'strength', data.strength_sum, data.strength_weights),
            simple_step('Скорость', 'speed', data.speed_sum, data.speed_weights),
            simple_step('Интеллект', 'iq', data.iq_sum, data.iq_weights),
            simple_step('Боевые навыки', 'fighting', data.fighting_sum, data.fighting_weights),
            simple_step('Оружие', 'weapon', data.weapon_sum, data.weapon_weights),
            None,
            None,
            simple_step('Способность', 'ability', data.ability_sum, data.ability_weights),
            None,
        ]
        chaos_options = [None] + data.chaos_sum
        no_chaos_weight = sum(data.chaos_weights) * 7 / 3
        steps.append((
            'Влияние хаоса',
            chaos_options,
            [no_chaos_weight] + data.chaos_weights,
            lambda value: setattr(hero, 'chaos', value),
            lambda value: value if value is not None else 'Нет',
        ))
        steps.append(simple_step('Титул', 'title', data.title_sum, data.title_weights))
        return steps

    def _draw_wheel(self, options, rotation, weights=None):
        canvas = self.wheel_canvas
        canvas.delete('all')
        width = int(canvas['width'])
        height = int(canvas['height'])
        center_x, center_y = width / 2, height / 2
        radius = min(width, height) / 2 - 30
        colors = ('#f4b860', '#4cae9b', '#6daedb', '#ef8068', '#9277c7',
                  '#e67fa2', '#67b9c2', '#dd9b55', '#77a86b')
        weights = list(weights) if weights is not None else [1] * len(options)
        total_weight = sum(weights)
        angle_before = 0.0
        for index, (option, weight) in enumerate(zip(options, weights)):
            segment = 360 * weight / total_weight
            start = (rotation + angle_before) % 360
            canvas.create_arc(center_x-radius, center_y-radius, center_x+radius, center_y+radius,
                              start=start, extent=segment, fill=colors[index % len(colors)],
                              outline='#fffaf1', width=3)
            middle = math.radians(start + segment / 2)
            label_radius = radius * 0.66
            x = center_x + math.cos(middle) * label_radius
            y = center_y - math.sin(middle) * label_radius
            label = textwrap.fill(str(option), width=17)
            canvas.create_text(x, y, text=label, width=105, font=('Segoe UI', 8, 'bold'),
                               fill='#202a35', justify='center')
            angle_before += segment
        canvas.create_oval(center_x-radius-4, center_y-radius-4, center_x+radius+4, center_y+radius+4,
                           outline='#263448', width=3)
        canvas.create_oval(center_x-25, center_y-25, center_x+25, center_y+25,
                           fill='#263448', outline='#fffaf1', width=3)
        canvas.create_oval(center_x-10, center_y-10, center_x+10, center_y+10,
                           fill='#f4c95d', outline='')
        canvas.create_polygon(center_x-17, center_y-radius-24, center_x+17, center_y-radius-24,
                              center_x, center_y-radius+7, fill='#263448', outline='#fffaf1', width=2)
        canvas.create_polygon(center_x-10, center_y-radius-19, center_x+10, center_y-radius-19,
                              center_x, center_y-radius, fill='#f4c95d', outline='')

    def _wheel_index_at_pointer(self, weights, rotation):
        pointer_angle = (90 - rotation) % 360
        angle_before = 0.0
        total_weight = sum(weights)
        for index, weight in enumerate(weights):
            extent = 360 * weight / total_weight
            if angle_before <= pointer_angle < angle_before + extent:
                return index
            angle_before += extent
        return len(weights) - 1

    def _spin_next(self):
        while self.spin_index < len(self.wheel_steps) and self.wheel_steps[self.spin_index] is None:
            self.spin_index += 1
        self._update_creation_progress()
        if self.spin_index >= len(self.wheel_steps):
            self._update_creation_summary()
            try:
                main.file_creation(self.current_hero)
            except OSError as error:
                self._show_error('Ошибка сохранения', str(error))
                self.generation_active = False
                self.generate_button.configure(state='normal')
                return
            self.wheel_status.configure(text='Герой создан!')
            self.audio.play_effect('character_created')
            self.generation_active = False
            self.generate_button.configure(state='normal')
            self.skip_spin_button.configure(state='disabled')
            return

        label, options, weights, assign, display = self.wheel_steps[self.spin_index]
        selected = random.choices(options, weights=weights, k=1)[0]
        selected_text = display(selected)
        wheel_options = [display(option) for option in options]
        selected_index = options.index(selected)
        self.skip_spin_button.configure(state='normal')
        self.wheel_status.configure(text=f'{label}: 0%')
        start_rotation = self.wheel_rotation
        total_weight = sum(weights)
        segment_start = 360 * sum(weights[:selected_index]) / total_weight
        segment_extent = 360 * weights[selected_index] / total_weight
        desired_rotation = (90 - (segment_start + segment_extent / 2)) % 360
        rotation_delta = (desired_rotation - start_rotation % 360) % 360 + 360 * random.randint(5, 7)
        total_frames = 95 if self.fast_spin_var.get() else 333
        self.spin_frame = 0
        self._draw_wheel(wheel_options, start_rotation, weights)

        finished = False

        def finish_spin():
            nonlocal finished
            if finished:
                return
            finished = True
            after_id = getattr(self, 'spin_after_id', None)
            if after_id is not None:
                try:
                    self.root.after_cancel(after_id)
                except tk.TclError:
                    pass
                self.spin_after_id = None
            self.current_spin_finish = None
            self.skip_spin_button.configure(state='disabled')
            self._draw_wheel(wheel_options, desired_rotation, weights)
            self.wheel_selection.configure(text=f'{label}: {selected_text}')
            assign(selected)
            self._update_creation_summary()
            self.wheel_rotation = desired_rotation
            self.wheel_status.configure(text=f'Выпало: {label} - {selected_text}')
            if self.spin_index == 7 and selected != data.weapon_sum[0]:
                self.wheel_steps[8] = (
                    'Владение оружием',
                    data.weapon_mastery_sum, data.weapon_mastery_weights,
                    lambda value: setattr(self.current_hero, 'weapon_mastery', value), str,
                )
                self.wheel_steps[9] = (
                    'Зачарование оружия',
                    data.weapon_enchantment_sum, data.weapon_enchantment_weights,
                    lambda value: setattr(self.current_hero, 'weapon_enchantment', value), str,
                )
            if self.spin_index == 10 and selected != data.ability_sum[0]:
                self.wheel_steps[11] = (
                    'Мощь способности',
                    data.ability_power_sum, data.ability_power_weights,
                    lambda value: setattr(self.current_hero, 'ability_power', value), str,
                )
            self.spin_index += 1
            while self.spin_index < len(self.wheel_steps) and self.wheel_steps[self.spin_index] is None:
                self.spin_index += 1
            self._update_creation_progress()
            self.spin_after_id = self.root.after(700, self._spin_next)

        self.current_spin_finish = finish_spin

        def animate():
            self.spin_after_id = None
            self.spin_frame += 1
            progress = min(self.spin_frame / total_frames, 1.0)
            eased = 1 - (1 - progress) ** 3
            rotation = start_rotation + rotation_delta * eased
            self._draw_wheel(wheel_options, rotation, weights)
            pointer_index = self._wheel_index_at_pointer(weights, rotation)
            self.wheel_selection.configure(text=f'{label}: {wheel_options[pointer_index]}')
            self.wheel_status.configure(text=f'{label}: {int(progress * 100)}%')
            if progress < 1.0:
                self.spin_after_id = self.root.after(30, animate)
                return
            finish_spin()

        animate()

    def _skip_current_spin(self):
        finish_spin = getattr(self, 'current_spin_finish', None)
        if finish_spin is None:
            return
        finish_spin()

    @staticmethod
    def _name_characters_allowed(value):
        return all(
            char in ' -' or unicodedata.name(char, '').startswith(('LATIN ', 'CYRILLIC '))
            for char in value
        )

    def generate(self):
        if getattr(self, 'generation_active', False):
            return
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning('Нужно имя', 'Введите имя персонажа.')
            self.name_entry.focus_set()
            return
        has_letter = any(unicodedata.name(char, '').startswith(('LATIN ', 'CYRILLIC ')) for char in name)
        if not self._name_characters_allowed(name) or not has_letter:
            messagebox.showwarning(
                'Некорректное имя',
                'Разрешены латинские и кириллические буквы, пробелы и дефисы; добавьте хотя бы одну букву.',
            )
            self.name_entry.focus_set()
            return
        try:
            greeting = StringIO()
            with redirect_stdout(greeting):
                self.current_hero = main.character(name)
        except (OSError, ValueError) as error:
            self._show_error('Ошибка', str(error))
            return
        self.generation_active = True
        self.wheel_steps = self._make_wheel_steps(self.current_hero)
        self.spin_index = 0
        self.wheel_rotation = 0
        self._update_creation_summary()
        self._update_creation_progress()
        self.generate_button.configure(state='disabled')
        self._spin_next()

    def show_characters(self, ladder_selection=False):
        self.clear()
        self.audio.play_music('collection')
        self.ladder_selection_mode = ladder_selection
        page_scale = self._automatic_page_scale(960, 760)
        self._set_page_geometry(f'{int(960 * page_scale)}x{int(760 * page_scale)}')
        frame = ttk.Frame(self.root, padding=20)
        frame.pack(fill='both', expand=True)
        ttk.Button(frame, text='← На главную', command=self.show_home).pack(anchor='w', pady=(0, 10))
        self.heading(frame, 'Выбор героя для ладдера' if ladder_selection else 'Коллекция героев')
        body = ttk.Frame(frame)
        body.pack(fill='both', expand=True)
        gallery = ttk.LabelFrame(body, text='Ваши персонажи', padding=8)
        gallery.pack(side='left', fill='both', expand=True)
        controls = ttk.Frame(gallery)
        controls.pack(fill='x', pady=(0, 7))
        self.character_search_var = tk.StringVar()
        search = ttk.Entry(controls, textvariable=self.character_search_var)
        search.pack(fill='x', pady=(0, 5))
        search.insert(0, '')
        self.character_sort_var = tk.StringVar(value='Сначала новые')
        sort_box = ttk.Combobox(controls, state='readonly', textvariable=self.character_sort_var,
                                values=(
                                    'Сначала новые', 'Сначала старые', 'По имени',
                                    'По очкам (по убыванию)', 'По очкам (по возрастанию)',
                                    'Живые сначала', 'Мёртвые сначала',
                                ), width=28)
        sort_box.pack(fill='x', pady=(0, 5))
        self.character_status_var = tk.StringVar(value='Живые' if ladder_selection else 'Все')
        if not ladder_selection:
            status_box = ttk.Combobox(
                controls, state='readonly', textvariable=self.character_status_var,
                values=('Все', 'Живые', 'Мёртвые'),
            )
            status_box.pack(fill='x', pady=(0, 5))
            status_box.bind('<<ComboboxSelected>>', lambda _event: self._refresh_character_gallery())
        races = ['Все расы'] + [self._readable_creation_value(race) for race in data.race_sum]
        self.character_race_var = tk.StringVar(value=races[0])
        race_box = ttk.Combobox(controls, state='readonly', textvariable=self.character_race_var,
                                values=races)
        race_box.pack(fill='x')
        ttk.Button(
            controls, text='Сбросить поиск и фильтры',
            command=self._reset_character_filters,
        ).pack(fill='x', pady=(5, 0))
        self.gallery_count = ttk.Label(controls, text='', style='Muted.TLabel')
        self.gallery_count.pack(anchor='w', pady=(6, 0))

        gallery_area = ttk.Frame(gallery)
        gallery_area.pack(fill='both', expand=True)
        colors = self.ui_colors
        self.gallery_canvas = tk.Canvas(gallery_area, highlightthickness=0,
                                        background=colors['surface'])
        gallery_scroll = ttk.Scrollbar(gallery_area, orient='vertical', command=self.gallery_canvas.yview)
        self.gallery_canvas.configure(yscrollcommand=gallery_scroll.set)
        self.gallery_canvas.pack(side='left', fill='both', expand=True)
        gallery_scroll.pack(side='right', fill='y')
        for widget in (self.gallery_canvas, gallery_area):
            widget.bind('<MouseWheel>', self._scroll_character_gallery)
            widget.bind('<Button-4>', self._scroll_character_gallery)
            widget.bind('<Button-5>', self._scroll_character_gallery)
        self.gallery_canvas.bind('<Configure>', self._resize_character_gallery_content)

        preview = ttk.LabelFrame(body, text='Предпросмотр', padding=10)
        preview.pack(side='right', fill='y', padx=(14, 0))
        self.card_canvas = tk.Canvas(preview, width=300, height=450,
                                     highlightthickness=0, background=colors['surface'])
        self.card_canvas.pack(pady=(0, 6))
        detail_frame = ttk.Frame(preview)
        detail_frame.pack(fill='both', expand=True)
        self.detail = tk.Canvas(detail_frame, width=300, highlightthickness=0,
                                background=colors['input'])
        detail_scroll = ttk.Scrollbar(detail_frame, orient='vertical', command=self.detail.yview)
        self.detail.configure(yscrollcommand=detail_scroll.set)
        self.detail.pack(side='left', fill='both', expand=True)
        detail_scroll.pack(side='right', fill='y')
        if ladder_selection:
            self.ladder_start_button = ttk.Button(
                preview, text='Начать забег', command=self.start_ladder,
                style='Primary.TButton', state='disabled',
            )
            self.ladder_start_button.pack(fill='x', pady=(8, 0))
        self.stat_upgrade_fields = {'strength', 'speed', 'iq', 'fighting', 'weapon_mastery', 'ability_power'}
        for widget in (detail_frame, self.detail):
            widget.bind('<MouseWheel>', self._scroll_character_preview)
            widget.bind('<Button-4>', self._scroll_character_preview)
            widget.bind('<Button-5>', self._scroll_character_preview)
        self.card_template_cache = {}
        self.card_character_sources = {}
        self.card_character_cache = {}
        self.card_weapon_sources = {}
        self.card_weapon_cache = {}
        self.files = character_files_by_creation_date(living_only=ladder_selection)
        self.visible_files = []
        self.selected_character_path = None
        self.character_search_var.trace_add('write', lambda *_args: self._refresh_character_gallery())
        sort_box.bind('<<ComboboxSelected>>', lambda _event: self._refresh_character_gallery())
        race_box.bind('<<ComboboxSelected>>', lambda _event: self._refresh_character_gallery())
        self._refresh_character_gallery(select_first=True)

    def _read_character_properties(self, path):
        try:
            lines = path.read_text(encoding='utf-8').splitlines()
        except (OSError, UnicodeError):
            return {}
        properties = {}
        for line in lines:
            key, separator, value = line.partition(':')
            if separator:
                properties[key.strip()] = value.strip()
        return properties

    def _draw_gallery_race_icon(self, canvas, x, y, race_value, tag):
        """Draw a compact, theme-friendly race marker for a collection tile."""
        race = self._readable_creation_value(race_value).casefold()
        templates = dict(zip((name.casefold() for name in data.race_sum), ('human', 'orc', 'elf')))
        for name, template in zip(data.race_sum, ('human', 'orc', 'elf')):
            try:
                templates[name.encode('utf-8').decode('cp1251').casefold()] = template
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
        kind = templates.get(race, 'human')
        palettes = {
            'human': ('#e8c9a6', '#684b39', '#bd8c65'),
            'orc': ('#9dbc88', '#3b5942', '#76976a'),
            'elf': ('#e3cba8', '#75628e', '#ad91c8'),
        }
        skin, hair, accent = palettes[kind]
        canvas.create_oval(x + 2, y + 2, x + 34, y + 34, fill=self.ui_colors['surface'],
                           outline=self.ui_colors['border'], width=1, tags=(tag,))
        if kind == 'elf':
            canvas.create_polygon(x + 7, y + 17, x + 1, y + 11, x + 8, y + 12,
                                  fill=skin, outline=hair, tags=(tag,))
            canvas.create_polygon(x + 29, y + 17, x + 35, y + 11, x + 28, y + 12,
                                  fill=skin, outline=hair, tags=(tag,))
        elif kind == 'orc':
            canvas.create_polygon(x + 7, y + 17, x + 1, y + 14, x + 7, y + 12,
                                  fill=skin, outline=hair, tags=(tag,))
            canvas.create_polygon(x + 29, y + 17, x + 35, y + 14, x + 29, y + 12,
                                  fill=skin, outline=hair, tags=(tag,))
        else:
            canvas.create_oval(x + 5, y + 15, x + 11, y + 23, fill=skin, outline=hair, tags=(tag,))
            canvas.create_oval(x + 25, y + 15, x + 31, y + 23, fill=skin, outline=hair, tags=(tag,))
        canvas.create_oval(x + 8, y + 8, x + 28, y + 29, fill=skin,
                           outline=hair, width=1, tags=(tag,))
        canvas.create_arc(x + 7, y + 5, x + 29, y + 24, start=0, extent=180,
                          style='pieslice', fill=hair, outline=hair, tags=(tag,))
        canvas.create_oval(x + 13, y + 17, x + 15, y + 19,
                           fill='#263448', outline='', tags=(tag,))
        canvas.create_oval(x + 21, y + 17, x + 23, y + 19,
                           fill='#263448', outline='', tags=(tag,))
        canvas.create_line(x + 15, y + 24, x + 21, y + 24,
                           fill=hair, width=1, tags=(tag,))
        if kind == 'orc':
            canvas.create_polygon(x + 13, y + 24, x + 15, y + 24, x + 14, y + 28,
                                  fill='#f3ead7', outline='', tags=(tag,))
            canvas.create_polygon(x + 21, y + 24, x + 23, y + 24, x + 22, y + 28,
                                  fill='#f3ead7', outline='', tags=(tag,))
        elif kind == 'elf':
            canvas.create_line(x + 11, y + 10, x + 6, y + 18,
                               fill=accent, width=2, tags=(tag,))
            canvas.create_line(x + 25, y + 10, x + 30, y + 18,
                               fill=accent, width=2, tags=(tag,))

    def _reset_character_filters(self):
        self.character_sort_var.set('Сначала новые')
        self.character_status_var.set('Живые' if self.ladder_selection_mode else 'Все')
        self.character_race_var.set('Все расы')
        self.character_search_var.set('')
        self._refresh_character_gallery()

    def _refresh_character_gallery(self, select_first=False):
        if not hasattr(self, 'gallery_canvas') or not self.gallery_canvas.winfo_exists():
            return
        self.gallery_canvas.delete('all')
        query = self.character_search_var.get().strip().casefold()
        selected_race = self.character_race_var.get()
        selected_status = self.character_status_var.get()
        all_races = 'Все расы'
        filtered = []
        properties_by_path = {}
        for path in self.files:
            props = self._read_character_properties(path)
            properties_by_path[path] = props
            is_alive = Fight.is_character_alive(props)
            if (self.ladder_selection_mode or selected_status == 'Живые') and not is_alive:
                continue
            if selected_status == 'Мёртвые' and is_alive:
                continue
            race = self._readable_creation_value(props.get('race', ''))
            haystack = ' '.join((path.stem, *(self._readable_creation_value(value) for value in props.values()))).casefold()
            if query and query not in haystack:
                continue
            if selected_race != all_races and race.casefold() != selected_race.casefold():
                continue
            filtered.append(path)
        sort_mode = self.character_sort_var.get()
        if sort_mode == 'По имени':
            filtered.sort(key=lambda path: path.stem.casefold())
        elif sort_mode == 'Сначала старые':
            filtered.sort(key=lambda path: path.stat().st_mtime)
        elif sort_mode == 'По очкам (по убыванию)':
            filtered.sort(key=lambda path: int(properties_by_path[path].get('points', 0) or 0), reverse=True)
        elif sort_mode == 'По очкам (по возрастанию)':
            filtered.sort(key=lambda path: int(properties_by_path[path].get('points', 0) or 0))
        elif sort_mode == 'Живые сначала':
            filtered.sort(key=lambda path: (
                not Fight.is_character_alive(properties_by_path[path]), -path.stat().st_mtime,
            ))
        elif sort_mode == 'Мёртвые сначала':
            filtered.sort(key=lambda path: (
                Fight.is_character_alive(properties_by_path[path]), -path.stat().st_mtime,
            ))
        else:
            filtered.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        self.visible_files = filtered
        self.gallery_count.configure(text=f'{len(filtered)} / {len(self.files)}')
        self.gallery_properties = properties_by_path
        self.gallery_tiles = {}
        self._render_character_gallery()
        if not filtered:
            self.selected_character_path = None
            if getattr(self, 'ladder_selection_mode', False) and hasattr(self, 'ladder_start_button'):
                self.ladder_start_button.configure(state='disabled')
            self._draw_character_card({})
            self._clear_preview_rows()
            return
        if select_first or self.selected_character_path not in filtered:
            self._select_character(filtered[0])
        else:
            self._select_character(self.selected_character_path)

    def _select_character(self, path):
        same_selection = path == self.selected_character_path
        self.selected_character_path = path
        if getattr(self, 'ladder_selection_mode', False) and hasattr(self, 'ladder_start_button'):
            self.ladder_start_button.configure(state='normal')
        for tile_path, background_id in self.gallery_tiles.items():
            selected = tile_path == path
            is_dead = not Fight.is_character_alive(self.gallery_properties.get(tile_path, {}))
            dead_outline = '#c73d46' if not self.dark_theme else '#ff707a'
            self.gallery_canvas.itemconfigure(
                background_id,
                outline=dead_outline if is_dead else (
                    self.ui_colors['accent'] if selected else self.ui_colors['border']
                ),
                width=2 if selected else 1,
            )
        if not same_selection:
            self.open_selected()

    def _set_gallery_tile_hover(self, path, background_id, hovering):
        if not Fight.is_character_alive(self.gallery_properties.get(path, {})):
            outline, width = (
                ('#c73d46', 2) if not self.dark_theme else ('#ff707a', 2)
            )
            self.gallery_canvas.itemconfigure(background_id, outline=outline, width=width)
            return
        selected = path == self.selected_character_path
        if selected:
            outline, width = self.ui_colors['accent'], 2
        elif hovering:
            outline, width = self.ui_colors['hover'], 1.5
        else:
            outline, width = self.ui_colors['border'], 1
        self.gallery_canvas.itemconfigure(background_id, outline=outline, width=width)

    def _upgrade_character_stat(self, stat):
        if getattr(self, 'ladder_selection_mode', False):
            return
        path = getattr(self, 'selected_character_path', None)
        pools = {
            'strength': (data.strength_sum, data.strength_weights),
            'speed': (data.speed_sum, data.speed_weights),
            'iq': (data.iq_sum, data.iq_weights),
            'fighting': (data.fighting_sum, data.fighting_weights),
            'weapon_mastery': (data.weapon_mastery_sum, data.weapon_mastery_weights),
            'ability_power': (data.ability_power_sum, data.ability_power_weights),
        }
        if path is None or stat not in pools:
            return
        properties = self._read_character_properties(path)
        options, weights = pools[stat]
        try:
            next_index = options.index(properties.get(stat, '')) - 1
            points = int(properties.get('points', '0'))
        except (ValueError, TypeError):
            return
        if next_index < 0:
            return
        cost = weights[next_index] * 4
        if points < cost:
            return

        lines = path.read_text(encoding='utf-8').splitlines()
        updates = {stat: options[next_index], 'points': str(points - cost)}
        found = set()
        for index, line in enumerate(lines):
            key, separator, _value = line.partition(':')
            key = key.strip()
            if separator and key in updates:
                lines[index] = f'{key}: {updates[key]}'
                found.add(key)
        for key, value in updates.items():
            if key not in found:
                lines.append(f'{key}: {value}')
        try:
            path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        except OSError as error:
            self._show_error('Не удалось улучшить характеристику', str(error))
            return
        self.audio.play_effect('stat_upgrade')
        self.open_selected()
        self._refresh_character_gallery()

    def _scroll_character_gallery(self, event):
        event_number = getattr(event, 'num', None)
        if event_number == 4:
            direction = -1
        elif event_number == 5:
            direction = 1
        else:
            direction = -1 if getattr(event, 'delta', 0) > 0 else 1
        self.gallery_canvas.yview_scroll(direction * 3, 'units')
        return 'break'

    def _resize_character_gallery_content(self, _event=None):
        if not getattr(self, '_gallery_render_pending', False):
            self._gallery_render_pending = True
            self.gallery_canvas.after_idle(self._render_character_gallery)

    def _render_character_gallery(self):
        self._gallery_render_pending = False
        if not self.gallery_canvas.winfo_exists():
            return
        canvas = self.gallery_canvas
        old_top = canvas.yview()[0] if canvas.yview() else 0
        canvas.delete('all')
        self.gallery_tiles = {}
        canvas_width = max(canvas.winfo_width(), 240)
        if not self.visible_files:
            canvas.create_text(
                canvas_width / 2, 24, text='Ничего не найдено',
                fill=self.ui_colors['muted'], font=('Segoe UI', 10), anchor='center',
            )
            canvas.configure(scrollregion=(0, 0, canvas_width, 48))
            return

        margin, gap, columns = 6, 8, 2
        tile_width = max(90, (canvas_width - 2 * margin - gap) // columns)
        tile_height = 116
        y = margin
        for row_start in range(0, len(self.visible_files), columns):
            row_items = []
            for column in range(columns):
                index = row_start + column
                if index >= len(self.visible_files):
                    break
                path = self.visible_files[index]
                props = self.gallery_properties[path]
                is_dead = not Fight.is_character_alive(props)
                dead_fill = '#fbe4e4' if not self.dark_theme else '#3c2429'
                dead_outline = '#c73d46' if not self.dark_theme else '#ff707a'
                dead_foreground = '#a8232d' if not self.dark_theme else '#ff9aa0'
                x = margin + column * (tile_width + gap)
                tag = f'gallery_tile_{index}'
                selected = path == self.selected_character_path
                background_id = canvas.create_rectangle(
                    x, y, x + tile_width, y + tile_height,
                    fill=dead_fill if is_dead else self.ui_colors['input'],
                    outline=dead_outline if is_dead else (
                        self.ui_colors['accent'] if selected else self.ui_colors['border']
                    ),
                    width=2 if selected else 1, tags=(tag,),
                )
                self.gallery_tiles[path] = background_id
                self._draw_gallery_race_icon(canvas, x + 10, y + 8, props.get('race', ''), tag)
                canvas.create_text(
                    x + 54, y + 9, text=path.stem, anchor='nw',
                    width=max(40, tile_width - 64),
                    fill=dead_foreground if is_dead else self.ui_colors['foreground'],
                    font=('Segoe UI', 9, 'bold'), tags=(tag,),
                )
                race = self._readable_creation_value(' '.join(filter(None, (
                    props.get('subrace', ''), props.get('race', ''),
                ))))
                size = self._readable_creation_value(props.get('size', ''))
                canvas.create_text(
                    x + 10, y + 52,
                    text='\n'.join(value for value in (race, size) if value), anchor='nw',
                    width=max(50, tile_width - 20),
                    fill=dead_foreground if is_dead else self.ui_colors['muted'],
                    font=('Segoe UI', 8), tags=(tag,),
                )
                points = props.get('points', '0').strip() or '0'
                badge_width = min(92, tile_width - 16)
                badge_left = x + tile_width - badge_width - 8
                badge_top = y + tile_height - 27
                canvas.create_rectangle(
                    badge_left, badge_top, x + tile_width - 8, y + tile_height - 7,
                    fill=dead_fill if is_dead else self.ui_colors['surface'],
                    outline=dead_outline if is_dead else self.ui_colors['accent'],
                    width=1, tags=(tag,),
                )
                canvas.create_text(
                    (badge_left + x + tile_width - 8) / 2, badge_top + 10,
                    text='Мёртв' if is_dead else f'Очки: {points}',
                    fill=dead_foreground if is_dead else self.ui_colors['foreground'],
                    font=('Segoe UI', 8, 'bold'), tags=(tag,),
                )
                row_items.append((path, tag, background_id))

            for path, tag, _background_id in row_items:
                background_id = self.gallery_tiles[path]
                canvas.tag_bind(
                    tag, '<Button-1>',
                    lambda _event, selected_path=path: self._select_character(selected_path),
                )
                canvas.tag_bind(
                    tag, '<Enter>',
                    lambda _event, selected_path=path, item_id=background_id:
                    self._set_gallery_tile_hover(selected_path, item_id, True),
                )
                canvas.tag_bind(
                    tag, '<Leave>',
                    lambda _event, selected_path=path, item_id=background_id:
                    self._set_gallery_tile_hover(selected_path, item_id, False),
                )
            y += tile_height + gap

        canvas.configure(scrollregion=(0, 0, canvas_width, y))
        if old_top:
            canvas.yview_moveto(old_top)

    def _draw_character_card(self, properties):
        canvas = self.card_canvas
        canvas.delete('all')
        is_dead = not Fight.is_character_alive(properties)
        dead_border = '#c73d46' if not self.dark_theme else '#ff707a'
        dead_background = '#fbe4e4' if not self.dark_theme else '#3c2429'
        dead_bar = '#8f2730' if not self.dark_theme else '#55232a'
        dead_label = '#ffe8e9'
        canvas.configure(background=dead_background if is_dead else self.ui_colors['surface'])
        race = properties.get('race', '').casefold()
        race_template_names = dict(zip((race.casefold() for race in data.race_sum), ('human', 'orc', 'elf')))
        for race_value, template in zip(data.race_sum, ('human', 'orc', 'elf')):
            try:
                race_template_names[race_value.encode('utf-8').decode('cp1251').casefold()] = template
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
        template_name = race_template_names.get(race)
        if template_name is None:
            try:
                repaired_race = race.encode('cp1251').decode('utf-8').casefold()
                template_name = race_template_names.get(repaired_race)
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
        template_path = (
            Path(__file__).resolve().parent / 'CardTemplates' / 'races' / f'{template_name}.png'
            if template_name else None
        )
        photo = self.card_template_cache.get(template_name)
        if photo is None and template_path is not None and template_path.exists():
            try:
                source = tk.PhotoImage(file=str(template_path))
                scale = max(1, math.ceil(max(source.width() / 256, source.height() / 384)))
                photo = source.subsample(scale, scale)
                self.card_template_cache[template_name] = photo
            except tk.TclError:
                photo = None
        if photo is not None:
            left = (int(canvas['width']) - photo.width()) // 2
            top = (int(canvas['height']) - photo.height()) // 2
            canvas.create_image(left, top, image=photo, anchor='nw')
        else:
            left, top = 12, 12
            canvas.create_rectangle(left, top, left + 256, top + 384,
                                    fill='#263448', outline='#d3aa56', width=3)

        size_name = properties.get('size', '').casefold()
        target_heights = dict(zip((size.casefold() for size in data.size_sum), (160, 185, 210, 235)))
        for size, height in zip(data.size_sum, (160, 185, 210, 235)):
            try:
                target_heights[size.encode('utf-8').decode('cp1251').casefold()] = height
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
        target_height = target_heights.get(size_name, 185)
        if size_name not in target_heights:
            try:
                repaired_size = size_name.encode('cp1251').decode('utf-8').casefold()
                target_height = target_heights.get(repaired_size, target_height)
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
        figure_key = (template_name, target_height)
        figure = self.card_character_cache.get(figure_key)
        figure_path = (
            Path(__file__).resolve().parent / 'CardTemplates' / 'characters' / f'{template_name}.png'
            if template_name else None
        )
        if figure is None and figure_path is not None and figure_path.exists():
            try:
                source = self.card_character_sources.get(template_name)
                if source is None:
                    source = tk.PhotoImage(file=str(figure_path))
                    self.card_character_sources[template_name] = source
                scale = max(1, math.ceil(source.height() / target_height))
                figure = source.subsample(scale, scale)
                self.card_character_cache[figure_key] = figure
            except tk.TclError:
                figure = None

        figure_x = left + 130
        figure_bottom = top + 300
        ability = properties.get('ability', '—')

        if figure is not None:
            hand_fractions = {'human': 0.17, 'orc': 0.12, 'elf': 0.17}
            hand_x = figure_x - figure.width() / 2 + figure.width() * hand_fractions.get(template_name, 0.16)
            hand_y = figure_bottom - figure.height() * 0.62
            self._draw_card_weapon(
                canvas, properties.get('weapon', ''), hand_x, hand_y,
                size_factor=target_height / 185,
            )
            canvas.create_image(figure_x, figure_bottom, image=figure, anchor='s')

        bar_background = dead_bar if is_dead else '#17212b'
        canvas.create_rectangle(left + 3, top + 4, left + 257, top + 60,
                                fill=bar_background, outline='')
        canvas.create_rectangle(left + 3, top + 306, left + 257, top + 387,
                                fill=bar_background, outline='')

        def label(y, text, size=9, bold=False, width=224):
            options = dict(text=text, width=width, justify='center',
                           font=('Segoe UI', size, 'bold' if bold else 'normal'))
            canvas.create_text(left + 130, top + y + 1, fill='#17191c', **options)
            canvas.create_text(left + 129, top + y, fill=dead_label if is_dead else '#fff4d6', **options)

        label(17, textwrap.shorten(properties.get('name', 'Новый персонаж'), 26), 12, True)
        race_line = ' '.join(filter(None, (properties.get('subrace'), properties.get('race'))))
        label(39, 'Мёртв' if is_dead else textwrap.shorten(race_line, 32), 8, True)
        label(315, textwrap.shorten(properties.get('title', ''), 32), 8, True)
        label(338, f"Рост: {properties.get('size', '—')}", 8, True)
        label(357, f"Оружие: {properties.get('weapon', '—')}", 8)
        ability_power = properties.get('ability_power')
        if ability_power and ability_power != 'None':
            ability = f'{ability} · {ability_power}'
        label(376, f'Сила: {textwrap.shorten(ability, 30)}', 8)
        accent = dead_border if is_dead else ('#d3aa56' if self.dark_theme else '#b4822e')
        canvas.create_line(left + 20, top + 60, left + 240, top + 60,
                           fill=accent, width=2)
        canvas.create_line(left + 20, top + 306, left + 240, top + 306,
                           fill=accent, width=1)
        canvas.create_rectangle(left, top, left + 260, top + 390,
                                outline=accent, width=2)

    def _draw_card_weapon(self, canvas, weapon, hand_x, hand_y, size_factor=1.0):
        weapon = weapon.casefold()
        weapon_files = ('katana', 'axe', 'sword', 'pistol', 'tank', 'portal_cannon')
        weapon_templates = dict(zip((name.casefold() for name in data.weapon_sum[1:]), weapon_files))
        for name, filename in zip(data.weapon_sum[1:], weapon_files):
            try:
                weapon_templates[name.encode('utf-8').decode('cp1251').casefold()] = filename
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
        template_name = weapon_templates.get(weapon)
        if template_name:
            source = self.card_weapon_sources.get(template_name)
            weapon_path = Path(__file__).resolve().parent / 'CardTemplates' / 'weapons' / f'{template_name}.png'
            if source is None and weapon_path.exists():
                try:
                    source = tk.PhotoImage(file=str(weapon_path))
                    self.card_weapon_sources[template_name] = source
                except tk.TclError:
                    source = None
            if source is not None:
                target_size = max(20, round(48 * size_factor))
                scale = max(1, math.ceil(max(source.width() / target_size, source.height() / target_size)))
                cache_key = (template_name, target_size, scale)
                image = self.card_weapon_cache.get(cache_key)
                if image is None:
                    image = source.subsample(scale, scale)
                    self.card_weapon_cache[cache_key] = image
                if template_name == 'tank':
                    x, y = hand_x - image.width() * 0.58, hand_y - image.height() * 0.62
                else:
                    grip_anchors = {
                        'katana': (0.90, 0.91), 'axe': (0.92, 0.93),
                        'sword': (0.90, 0.91), 'pistol': (0.83, 0.76),
                        'portal_cannon': (0.90, 0.90),
                    }
                    grip_x, grip_y = grip_anchors.get(template_name, (0.9, 0.9))
                    x, y = hand_x - image.width() * grip_x, hand_y - image.height() * grip_y
                canvas.create_image(x, y, image=image, anchor='nw')
                return
        if weapon in ('', 'none', 'без оружия'):
            return
        dark = '#392d28'
        metal = '#e5e8ed'
        gold = '#d9aa54'
        if weapon in ('меч', 'катана'):
            canvas.create_line(hand_x + 8, hand_y + 10, hand_x - 31, hand_y - 43,
                               fill=dark, width=7, capstyle='round')
            canvas.create_line(hand_x + 5, hand_y + 7, hand_x - 31, hand_y - 43,
                               fill=metal, width=3 if weapon == 'меч' else 2,
                               capstyle='round')
            canvas.create_line(hand_x - 1, hand_y - 1, hand_x + 13, hand_y + 13,
                               fill=gold, width=4)
        elif weapon == 'топор':
            canvas.create_line(hand_x + 8, hand_y + 9, hand_x - 20, hand_y - 39,
                               fill='#704a32', width=6, capstyle='round')
            canvas.create_polygon(hand_x - 21, hand_y - 36, hand_x - 34, hand_y - 47,
                                  hand_x - 39, hand_y - 29, hand_x - 23, hand_y - 22,
                                  fill=metal, outline=dark, width=2)
        elif weapon == 'пистолет':
            canvas.create_polygon(hand_x - 1, hand_y - 2, hand_x - 38, hand_y - 2,
                                  hand_x - 38, hand_y - 10, hand_x - 9, hand_y - 10,
                                  hand_x - 7, hand_y - 17, hand_x + 2, hand_y - 17,
                                  hand_x + 1, hand_y - 10, hand_x + 7, hand_y - 8,
                                  hand_x + 7, hand_y + 7, hand_x - 2, hand_y + 4,
                                  fill='#535c66', outline=dark, width=2)
            canvas.create_line(hand_x - 22, hand_y - 7, hand_x - 12, hand_y - 7,
                               fill=gold, width=2)
        elif weapon == 'танк':
            canvas.create_oval(hand_x - 35, hand_y - 2, hand_x + 9, hand_y + 14,
                               fill='#394b3c', outline=dark, width=2)
            canvas.create_rectangle(hand_x - 31, hand_y - 13, hand_x + 2, hand_y + 4,
                                    fill='#62724b', outline=dark, width=2)
            canvas.create_rectangle(hand_x - 17, hand_y - 18, hand_x + 1, hand_y - 11,
                                    fill='#78865a', outline=dark, width=1)
            canvas.create_line(hand_x - 1, hand_y - 15, hand_x - 37, hand_y - 20,
                               fill=dark, width=4)
        elif weapon == 'портальная пушка':
            canvas.create_polygon(hand_x + 7, hand_y + 11, hand_x - 9, hand_y - 1,
                                  hand_x - 38, hand_y - 31, hand_x - 30, hand_y - 40,
                                  hand_x - 1, hand_y - 15, hand_x + 17, hand_y + 2,
                                  fill='#4c6670', outline=dark, width=2)
            canvas.create_oval(hand_x - 38, hand_y - 42, hand_x - 25, hand_y - 29,
                               fill='#54d6dc', outline='#c7ffff', width=2)

    def make_text(self, parent):
        input_background = '#30363d' if self.dark_theme else '#ffffff'
        foreground = '#f1f3f5' if self.dark_theme else '#202124'
        text = tk.Text(parent, wrap='word', state='disabled', font=('Segoe UI', 10),
                       background=input_background, foreground=foreground,
                       insertbackground=foreground)
        text.pack(fill='both', expand=True, pady=(8, 0))
        return text

    def _scroll_character_preview(self, event):
        event_number = getattr(event, 'num', None)
        if event_number == 4:
            direction = -1
        elif event_number == 5:
            direction = 1
        else:
            delta = getattr(event, 'delta', 0)
            direction = -1 if delta > 0 else 1
        self.detail.yview_scroll(direction * 3, 'units')
        return 'break'

    def _clear_preview_rows(self):
        self.detail.delete('all')
        self.detail.configure(scrollregion=(0, 0, max(1, self.detail.winfo_width()), 0))
    def set_text(self, widget, value):
        widget.configure(state='normal')
        widget.delete('1.0', 'end')
        widget.insert('1.0', value)
        widget.configure(state='disabled')

    def open_selected(self, _event=None):
        path = getattr(self, 'selected_character_path', None)
        if path is None:
            return
        properties = self._read_character_properties(path)
        pools = {
            'strength': (data.strength_sum, data.strength_weights),
            'speed': (data.speed_sum, data.speed_weights),
            'iq': (data.iq_sum, data.iq_weights),
            'fighting': (data.fighting_sum, data.fighting_weights),
            'weapon_mastery': (data.weapon_mastery_sum, data.weapon_mastery_weights),
            'ability_power': (data.ability_power_sum, data.ability_power_weights),
        }
        try:
            points = int(properties.get('points', '0'))
        except ValueError:
            points = 0
        upgrade_costs = {}
        for stat, (options, weights) in pools.items():
            try:
                next_index = options.index(properties.get(stat, '')) - 1
            except ValueError:
                next_index = -1
            upgrade_costs[stat] = weights[next_index] * 4 if next_index >= 0 else None
        self._clear_preview_rows()
        fields = (
            ('Имя', 'name'), ('Очки', 'points'),
            ('Происхождение', 'substory'),
            ('Раса', 'race'), ('Подраса', 'subrace'),
            ('Рост', 'size'), ('Сила', 'strength'),
            ('Скорость', 'speed'), ('Интеллект', 'iq'),
            ('Боевые навыки', 'fighting'),
            ('Оружие', 'weapon'), ('Владение оружием', 'weapon_mastery'),
            ('Зачарование оружия', 'weapon_enchantment'),
            ('Способность', 'ability'), ('Мощь способности', 'ability_power'),
            ('Хаос', 'chaos'), ('Титул', 'title'),
        )
        canvas_width = max(300, self.detail.winfo_width())
        left, right, gap = 6, canvas_width - 6, 6
        label_font = tkfont.Font(family='Segoe UI', size=11, weight='bold')
        y = 6
        for label, key in fields:
            raw_value = properties.get(key, '').strip()
            if not raw_value or raw_value.casefold() == 'none':
                continue
            value = self._readable_creation_value(raw_value)
            show_upgrade = key in self.stat_upgrade_fields and not getattr(
                self, 'ladder_selection_mode', False
            )
            action_width = 62 if show_upgrade else 0
            label_width = min(165, max(108, label_font.measure(label) + 10))
            value_width = max(50, right - left - label_width - action_width - gap * 3)
            value_chars = max(8, value_width // 8)
            value_lines = max(1, (len(value) + value_chars - 1) // value_chars)
            row_height = max(44, value_lines * 18 + 16)
            bottom = y + row_height
            self.detail.create_rectangle(
                left, y, right, bottom, fill=self.ui_colors['surface'],
                outline=self.ui_colors['border'], width=1,
            )
            self.detail.create_text(
                left + 8, y + row_height / 2, text=label, anchor='w',
                fill=self.ui_colors['muted'], font=label_font,
            )
            value_right = right - action_width - gap - 6
            self.detail.create_text(
                value_right, y + row_height / 2, text=value, anchor='e',
                width=value_width, fill=self.ui_colors['foreground'], font=('Segoe UI', 12),
            )
            if show_upgrade:
                cost = upgrade_costs.get(key)
                can_upgrade = cost is not None and points >= cost
                if key == 'weapon_mastery' and properties.get('weapon', '') == data.weapon_sum[0]:
                    can_upgrade = False
                if key == 'ability_power' and properties.get('ability', '') == data.ability_sum[0]:
                    can_upgrade = False
                action_text = 'MAX' if cost is None else chr(8593) + f' {cost}'
                action_left = right - action_width - 4
                action_right = right - 4
                action_tag = f'upgrade_{key}'
                action_fill = '#f2c94c' if can_upgrade else self.ui_colors['input']
                action_text_fill = '#493700' if can_upgrade else self.ui_colors['muted']
                self.detail.create_rectangle(
                    action_left, y + 7, action_right, bottom - 7,
                    fill=action_fill, outline='#d6a300' if can_upgrade else self.ui_colors['border'],
                    tags=(action_tag,),
                )
                self.detail.create_text(
                    (action_left + action_right) / 2, y + row_height / 2,
                    text=action_text, fill=action_text_fill,
                    font=('Segoe UI', 10, 'bold'), tags=(action_tag,),
                )
                if can_upgrade:
                    self.detail.tag_bind(action_tag, '<Button-1>',
                                         lambda _event, stat=key: self._upgrade_character_stat(stat))
                    self.detail.tag_bind(action_tag, '<Enter>', lambda _event: self.detail.configure(cursor='hand2'))
                    self.detail.tag_bind(action_tag, '<Leave>', lambda _event: self.detail.configure(cursor=''))
            y = bottom + 5
        self.detail.configure(scrollregion=(0, 0, canvas_width, y))
        self.detail.yview_moveto(0)
        self._draw_character_card(properties)


def run():
    root = tk.Tk()
    CharacterApp(root)
    root.mainloop()


if __name__ == '__main__':
    run()

