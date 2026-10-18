from pathlib import Path
from contextlib import redirect_stdout
from io import StringIO
import json
import math
import random
import textwrap
import unicodedata
import tkinter as tk
from tkinter import messagebox, ttk, font as tkfont

import main
import data
import Fight
import Tournament


CHARACTERS_DIR = Path(__file__).resolve().parent / 'Characters'


def character_files_by_creation_date():
    if not CHARACTERS_DIR.exists():
        return []
    return sorted(
        CHARACTERS_DIR.glob('*.txt'),
        key=lambda path: (path.stat().st_ctime, path.name.casefold()),
        reverse=True,
    )


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
        self.settings_path = Path(__file__).resolve().parent / 'settings.json'
        self._load_settings()
        if self.fullscreen:
            root.attributes('-fullscreen', True)
        elif self.window_resolution:
            root.geometry(self.window_resolution)
        root.bind('<Escape>', self._leave_fullscreen)
        style = ttk.Style(root)
        self.style = style
        style.configure('Menu.TButton', font=('Segoe UI', 13, 'bold'), padding=(16, 14))
        self._apply_theme()
        self.show_home()

    def _load_settings(self):
        try:
            settings = json.loads(self.settings_path.read_text(encoding='utf-8'))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return
        if not isinstance(settings, dict):
            return
        self.dark_theme = bool(settings.get('dark_theme', False))
        self.fullscreen = bool(settings.get('fullscreen', False))
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
        }
        try:
            self.settings_path.write_text(
                json.dumps(settings, ensure_ascii=False, indent=2), encoding='utf-8'
            )
        except OSError:
            pass

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
                      'accent_hover': '#568f98', 'border': '#2b3947'}
        else:
            colors = {'background': '#f3f6f8', 'surface': '#ffffff', 'input': '#ffffff',
                      'foreground': '#182530', 'muted': '#657681', 'accent': '#356d78',
                      'accent_hover': '#2c5962', 'border': '#dce4e9'}
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
        self.style.map('Primary.TButton', background=[('active', colors['accent_hover'])],
                       foreground=[('active', '#ffffff')])
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

    def show_home(self):
        self.clear()
        self.root.title('Неудачный забег')
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
            ('Опции', 'Тема и параметры окна', self.show_options),
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
                widget.bind('<Button-1>', lambda _event, action=command: action())
                widget.bind('<Return>', lambda _event, action=command: action())
                widget.bind('<Enter>', lambda _event, card=tile: card.configure(highlightbackground=colors['accent']))
                widget.bind('<Leave>', lambda _event, card=tile: card.configure(highlightbackground=colors['border']))
            tile.bind('<FocusIn>', lambda _event, card=tile: card.configure(
                highlightbackground=colors['accent'], highlightthickness=2))
            tile.bind('<FocusOut>', lambda _event, card=tile: card.configure(
                highlightbackground=colors['border'], highlightthickness=1))
        exit_container = ttk.Frame(frame)
        exit_container.pack(fill='x', pady=(8, 0))
        exit_icon = tk.Canvas(exit_container, width=44, height=44, highlightthickness=0,
                              background=colors['surface'], cursor='hand2')
        exit_icon.pack(side='right', padx=2, pady=2)
        exit_icon.create_rectangle(6, 5, 22, 39, outline=colors['muted'], width=2)
        exit_icon.create_line(17, 7, 17, 37, fill=colors['muted'], width=1)
        exit_icon.create_line(13, 22, 37, 22, fill=colors['muted'], width=3, arrow='last')
        exit_icon.bind('<Button-1>', lambda _event: self.root.destroy())

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

    def show_tournament(self):
        self.clear()
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
        files = character_files_by_creation_date()
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
        if len(selected) < Tournament.MIN_ROSTER_SIZE:
            messagebox.showwarning('Мало участников', 'Для турнира нужно добавить в ростер минимум 20 персонажей.')
            return
        paths = [self.tournament_files[int(index)] for index in selected]
        try:
            result = Tournament.run_tournament(paths)
        except (OSError, ValueError) as error:
            messagebox.showerror('Ошибка турнира', str(error))
            return
        self.set_text(self.tournament_result, result['report'])
        self._draw_tournament_bracket(result['bracket'])
        self.show_group_standings(result['group_standings'])
        self.tournament_tabs.select(1)

    def show_fight(self):
        self.clear()
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
        self.heading(frame, 'Сражение персонажей')
        files = character_files_by_creation_date()
        if len(files) < 2:
            ttk.Label(frame, text='Для сражения нужно сохранить минимум двух персонажей.').pack(anchor='w')
            return
        self.fight_files = files
        names = [file.stem for file in files]
        row = ttk.Frame(frame)
        row.pack(fill='x', pady=(0, 8))
        compact_fight_layout = page_scale < 0.95
        left = ttk.LabelFrame(row, text='Боец 1', padding=8)
        center = ttk.LabelFrame(row, text='Арена', padding=8)
        right = ttk.LabelFrame(row, text='Боец 2', padding=8)
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
            stats_card.configure(
                background='#20242a' if self.dark_theme else '#fffaf0',
                highlightbackground='#c69b4b' if self.dark_theme else '#d6bd88',
            )
            portrait.configure(highlightthickness=0)
        self._draw_fight_portrait(fighter_index)
        self.fight_names = (self.first_fighter.get(), self.second_fighter.get())
        self._draw_fight_wheel(*self.fight_names, getattr(self, 'fight_rotation', 0))

    def _draw_fight_portrait(self, fighter_index):
        if fighter_index not in (0, 1):
            return
        selector = self.first_fighter if fighter_index == 0 else self.second_fighter
        canvas = self.fight_portrait_canvases[fighter_index]
        canvas.delete('all')
        index = selector.current()
        if index < 0:
            return
        try:
            lines = self.fight_files[index].read_text(encoding='utf-8').splitlines()
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
            row = tk.Frame(stats_card, bg=card_bg)
            row.pack(fill='x', padx=5, pady=1)
            tk.Label(row, text=label_text, font=('Segoe UI', 9, 'bold'),
                     bg=card_bg, fg=muted_fg, anchor='nw').pack(anchor='w')
            tk.Label(row, text=readable(value), font=('Segoe UI', 9), bg=card_bg,
                     fg=main_fg, justify='left', anchor='nw', wraplength=170).pack(fill='x', anchor='w')

        templates = dict(zip((race.casefold() for race in data.race_sum), ('human', 'orc', 'elf')))
        aliases = dict(templates)
        for race, template in templates.items():
            try:
                aliases[race.encode('utf-8').decode('cp1251').casefold()] = template
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
        template = aliases.get(properties.get('race', '').casefold())
        if not template:
            canvas.create_text(65, 97, text=selector.get(), width=120,
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

    def start_fight(self):
        first_index = self.first_fighter.current()
        second_index = self.second_fighter.current()
        if first_index < 0 or second_index < 0:
            messagebox.showwarning('Выберите персонажей', 'Нужно выбрать обоих участников.')
            return
        if first_index == second_index:
            messagebox.showwarning('Выберите разных', 'Один персонаж не может сражаться с самим собой.')
            return
        try:
            result = Fight.fight_match(self.fight_files[first_index], self.fight_files[second_index])
        except (OSError, ValueError) as error:
            messagebox.showerror('Ошибка сражения', str(error))
            return
        self.fight_button.configure(state='disabled')
        self.first_fighter.configure(state='disabled')
        self.second_fighter.configure(state='disabled')
        self.fight_rounds = result['comparisons']
        self.fight_report = result['report']
        self.fight_winner_index = 0 if result['winner'] == result['first_name'] else 1
        self.fight_winner = self.fight_names[self.fight_winner_index]
        self.fight_round_index = 0
        self.fight_rotation = 0
        self.fight_names = (self.first_fighter.get(), self.second_fighter.get())
        self.fight_history.delete(*self.fight_history.get_children())
        self.fight_status.configure(style='TLabel', wraplength=0)
        for panel, outcome, stats_card, portrait in zip(
            self.fight_panels, self.fight_outcome_labels,
            self.fight_stat_labels, self.fight_portrait_canvases,
        ):
            outcome.pack_forget()
            panel.configure(style='TLabelframe')
            stats_card.configure(background='#20242a' if self.dark_theme else '#fffaf0')
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
                    text='ПОБЕДИТЕЛЬ' if is_winner else 'ПОРАЖЕНИЕ',
                    background=background, foreground=foreground,
                )
                outcome.pack(fill='x', pady=(4, 0))
                stats_card.configure(background=background, highlightbackground=color)
                for row in stats_card.winfo_children():
                    row.configure(background=background)
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
            self.fight_button.configure(state='normal')
            self.first_fighter.configure(state='readonly')
            self.second_fighter.configure(state='readonly')
            self.first_fighter.selection_clear()
            self.second_fighter.selection_clear()
            self.fight_button.focus_set()
            return

        comparison = self.fight_rounds[self.fight_round_index]
        winner_index = 0 if comparison['winner'] == comparison['first_name'] else 1
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
            row_tag = 'first-wins' if comparison['winner'] == comparison['first_name'] else 'second-wins'
            round_item = self.fight_history.insert('', 'end', tags=(row_tag,), values=(
                self.fight_round_index + 1, comparison['attribute'],
                f"{comparison['first_points']}:{comparison['second_points']}",
                comparison['winner'],
            ))
            self.fight_history.see(round_item)
            self.fight_round_index += 1
            self.spin_after_id = self.root.after(550, self._spin_fight_round)

        animate()

    def show_create(self):
        self.clear()
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
            name_card, text='\u041d\u043e\u0432\u044b\u0439 \u0433\u0435\u0440\u043e\u0439',
            bg=self.ui_colors['surface'], fg=self.ui_colors['foreground'],
            font=('Segoe UI', 12, 'bold'), wraplength=210, anchor='w', justify='left',
        )
        self.create_summary_name.pack(fill='x')
        for label, key in (
            ('\u041f\u0440\u043e\u0438\u0441\u0445\u043e\u0436\u0434\u0435\u043d\u0438\u0435', 'substory'),
            ('\u0420\u0430\u0441\u0430', 'race_line'), ('\u0420\u043e\u0441\u0442', 'size'),
            ('\u0421\u0438\u043b\u0430', 'strength'), ('\u0421\u043a\u043e\u0440\u043e\u0441\u0442\u044c', 'speed'),
            ('\u0423\u043c', 'iq'), ('\u0411\u043e\u0435\u0432\u044b\u0435 \u043d\u0430\u0432\u044b\u043a\u0438', 'fighting'),
            ('\u041e\u0440\u0443\u0436\u0438\u0435', 'weapon'), ('\u0412\u043b\u0430\u0434\u0435\u043d\u0438\u0435', 'weapon_mastery'),
            ('\u0417\u0430\u0447\u0430\u0440\u043e\u0432\u0430\u043d\u0438\u0435', 'weapon_enchantment'),
            ('\u0421\u043f\u043e\u0441\u043e\u0431\u043d\u043e\u0441\u0442\u044c', 'ability'),
            ('\u041c\u043e\u0449\u044c', 'ability_power'), ('\u0425\u0430\u043e\u0441', 'chaos'),
            ('\u0422\u0438\u0442\u0443\u043b', 'title'),
        ):
            row = tk.Frame(summary, background=self.ui_colors['surface'], padx=7, pady=4,
                           highlightthickness=1, highlightbackground=self.ui_colors['border'])
            row.pack(fill='x', pady=2)
            row.grid_columnconfigure(1, weight=1)
            tk.Label(row, text=label, anchor='w', background=self.ui_colors['surface'],
                     foreground=self.ui_colors['muted'], font=('Segoe UI', 9, 'bold')).grid(
                         row=0, column=0, sticky='w', padx=(0, 6))
            value_label = tk.Label(row, text='\u2014', anchor='e', justify='right',
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
                messagebox.showerror('Ошибка сохранения', str(error))
                self.generation_active = False
                self.generate_button.configure(state='normal')
                return
            self.wheel_status.configure(text='Герой создан!')
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
                    '\u0412\u043b\u0430\u0434\u0435\u043d\u0438\u0435 \u043e\u0440\u0443\u0436\u0438\u0435\u043c',
                    data.weapon_mastery_sum, data.weapon_mastery_weights,
                    lambda value: setattr(self.current_hero, 'weapon_mastery', value), str,
                )
                self.wheel_steps[9] = (
                    '\u0417\u0430\u0447\u0430\u0440\u043e\u0432\u0430\u043d\u0438\u0435 \u043e\u0440\u0443\u0436\u0438\u044f',
                    data.weapon_enchantment_sum, data.weapon_enchantment_weights,
                    lambda value: setattr(self.current_hero, 'weapon_enchantment', value), str,
                )
            if self.spin_index == 10 and selected != data.ability_sum[0]:
                self.wheel_steps[11] = (
                    '\u041c\u043e\u0449\u044c \u0441\u043f\u043e\u0441\u043e\u0431\u043d\u043e\u0441\u0442\u0438',
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
            messagebox.showerror('Ошибка', str(error))
            return
        self.generation_active = True
        self.wheel_steps = self._make_wheel_steps(self.current_hero)
        self.spin_index = 0
        self.wheel_rotation = 0
        self._update_creation_summary()
        self._update_creation_progress()
        self.generate_button.configure(state='disabled')
        self._spin_next()

    def show_characters(self):
        self.clear()
        page_scale = self._automatic_page_scale(960, 760)
        self._set_page_geometry(f'{int(960 * page_scale)}x{int(760 * page_scale)}')
        frame = ttk.Frame(self.root, padding=20)
        frame.pack(fill='both', expand=True)
        ttk.Button(frame, text='← На главную', command=self.show_home).pack(anchor='w', pady=(0, 10))
        self.heading(frame, 'Коллекция героев')
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
        self.character_sort_var = tk.StringVar(value='\u0421\u043d\u0430\u0447\u0430\u043b\u0430 \u043d\u043e\u0432\u044b\u0435')
        sort_box = ttk.Combobox(controls, state='readonly', textvariable=self.character_sort_var,
                                values=('\u0421\u043d\u0430\u0447\u0430\u043b\u0430 \u043d\u043e\u0432\u044b\u0435', '\u0421\u043d\u0430\u0447\u0430\u043b\u0430 \u0441\u0442\u0430\u0440\u044b\u0435', '\u041f\u043e \u0438\u043c\u0435\u043d\u0438', '\u041f\u043e \u043e\u0447\u043a\u0430\u043c (\u043f\u043e \u0443\u0431\u044b\u0432\u0430\u043d\u0438\u044e)', '\u041f\u043e \u043e\u0447\u043a\u0430\u043c (\u043f\u043e \u0432\u043e\u0437\u0440\u0430\u0441\u0442\u0430\u043d\u0438\u044e)'), width=28)
        sort_box.pack(fill='x', pady=(0, 5))
        races = ['Все расы'] + [self._readable_creation_value(race) for race in data.race_sum]
        self.character_race_var = tk.StringVar(value=races[0])
        race_box = ttk.Combobox(controls, state='readonly', textvariable=self.character_race_var,
                                values=races)
        race_box.pack(fill='x')
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
        self.files = character_files_by_creation_date()
        self.visible_files = []
        self.selected_character_path = None
        self.character_search_var.trace_add('write', lambda *_args: self._refresh_character_gallery())
        sort_box.bind('<<ComboboxSelected>>', lambda _event: self._refresh_character_gallery())
        race_box.bind('<<ComboboxSelected>>', lambda _event: self._refresh_character_gallery())
        self._refresh_character_gallery(select_first=True)

    def _read_character_properties(self, path):
        try:
            lines = path.read_text(encoding='utf-8').splitlines()
        except OSError:
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

    def _refresh_character_gallery(self, select_first=False):
        if not hasattr(self, 'gallery_canvas') or not self.gallery_canvas.winfo_exists():
            return
        self.gallery_canvas.delete('all')
        query = self.character_search_var.get().strip().casefold()
        selected_race = self.character_race_var.get()
        all_races = 'Все расы'
        filtered = []
        properties_by_path = {}
        for path in self.files:
            props = self._read_character_properties(path)
            properties_by_path[path] = props
            race = self._readable_creation_value(props.get('race', ''))
            haystack = ' '.join((path.stem, *(self._readable_creation_value(value) for value in props.values()))).casefold()
            if query and query not in haystack:
                continue
            if selected_race != all_races and race.casefold() != selected_race.casefold():
                continue
            filtered.append(path)
        sort_mode = self.character_sort_var.get()
        if sort_mode == '\u041f\u043e \u0438\u043c\u0435\u043d\u0438':
            filtered.sort(key=lambda path: path.stem.casefold())
        elif sort_mode == '\u0421\u043d\u0430\u0447\u0430\u043b\u0430 \u0441\u0442\u0430\u0440\u044b\u0435':
            filtered.sort(key=lambda path: path.stat().st_mtime)
        elif sort_mode == '\u041f\u043e \u043e\u0447\u043a\u0430\u043c (\u043f\u043e \u0443\u0431\u044b\u0432\u0430\u043d\u0438\u044e)':
            filtered.sort(key=lambda path: int(properties_by_path[path].get('points', 0) or 0), reverse=True)
        elif sort_mode == '\u041f\u043e \u043e\u0447\u043a\u0430\u043c (\u043f\u043e \u0432\u043e\u0437\u0440\u0430\u0441\u0442\u0430\u043d\u0438\u044e)':
            filtered.sort(key=lambda path: int(properties_by_path[path].get('points', 0) or 0))
        else:
            filtered.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        self.visible_files = filtered
        self.gallery_count.configure(text=f'{len(filtered)} / {len(self.files)}')
        self.gallery_properties = properties_by_path
        self.gallery_tiles = {}
        self._render_character_gallery()
        if not filtered:
            self.selected_character_path = None
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
        for tile_path, background_id in self.gallery_tiles.items():
            selected = tile_path == path
            self.gallery_canvas.itemconfigure(
                background_id,
                outline=self.ui_colors['accent'] if selected else self.ui_colors['border'],
                width=2 if selected else 1,
            )
        if not same_selection:
            self.open_selected()

    def _upgrade_character_stat(self, stat):
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
        path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
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
                canvas_width / 2, 24, text='\u041d\u0438\u0447\u0435\u0433\u043e \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u043e',
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
                x = margin + column * (tile_width + gap)
                tag = f'gallery_tile_{index}'
                selected = path == self.selected_character_path
                background_id = canvas.create_rectangle(
                    x, y, x + tile_width, y + tile_height,
                    fill=self.ui_colors['input'],
                    outline=self.ui_colors['accent'] if selected else self.ui_colors['border'],
                    width=2 if selected else 1, tags=(tag,),
                )
                self.gallery_tiles[path] = background_id
                self._draw_gallery_race_icon(canvas, x + 10, y + 8, props.get('race', ''), tag)
                canvas.create_text(
                    x + 54, y + 9, text=path.stem, anchor='nw',
                    width=max(40, tile_width - 64),
                    fill=self.ui_colors['foreground'], font=('Segoe UI', 9, 'bold'), tags=(tag,),
                )
                race = self._readable_creation_value(' '.join(filter(None, (
                    props.get('subrace', ''), props.get('race', ''),
                ))))
                size = self._readable_creation_value(props.get('size', ''))
                canvas.create_text(
                    x + 10, y + 52,
                    text='\n'.join(value for value in (race, size) if value), anchor='nw',
                    width=max(50, tile_width - 20), fill=self.ui_colors['muted'],
                    font=('Segoe UI', 8), tags=(tag,),
                )
                points = props.get('points', '0').strip() or '0'
                badge_width = min(92, tile_width - 16)
                badge_left = x + tile_width - badge_width - 8
                badge_top = y + tile_height - 27
                canvas.create_rectangle(
                    badge_left, badge_top, x + tile_width - 8, y + tile_height - 7,
                    fill=self.ui_colors['surface'], outline=self.ui_colors['accent'],
                    width=1, tags=(tag,),
                )
                canvas.create_text(
                    (badge_left + x + tile_width - 8) / 2, badge_top + 10,
                    text=f'Очки: {points}', fill=self.ui_colors['foreground'],
                    font=('Segoe UI', 8, 'bold'), tags=(tag,),
                )
                row_items.append((path, tag, background_id))

            for path, tag, _background_id in row_items:
                canvas.tag_bind(
                    tag, '<Button-1>',
                    lambda _event, selected_path=path: self._select_character(selected_path),
                )
            y += tile_height + gap

        canvas.configure(scrollregion=(0, 0, canvas_width, y))
        if old_top:
            canvas.yview_moveto(old_top)

    def _draw_character_card(self, properties):
        canvas = self.card_canvas
        canvas.delete('all')
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

        canvas.create_rectangle(left + 3, top + 4, left + 257, top + 60,
                                fill='#17212b', outline='')
        canvas.create_rectangle(left + 3, top + 306, left + 257, top + 387,
                                fill='#17212b', outline='')

        def label(y, text, size=9, bold=False, width=224):
            options = dict(text=text, width=width, justify='center',
                           font=('Segoe UI', size, 'bold' if bold else 'normal'))
            canvas.create_text(left + 130, top + y + 1, fill='#17191c', **options)
            canvas.create_text(left + 129, top + y, fill='#fff4d6', **options)

        label(17, textwrap.shorten(properties.get('name', 'Новый персонаж'), 26), 12, True)
        race_line = ' '.join(filter(None, (properties.get('subrace'), properties.get('race'))))
        label(39, textwrap.shorten(race_line, 32), 8, True)
        label(315, textwrap.shorten(properties.get('title', ''), 32), 8, True)
        label(338, f"Рост: {properties.get('size', '—')}", 8, True)
        label(357, f"Оружие: {properties.get('weapon', '—')}", 8)
        ability_power = properties.get('ability_power')
        if ability_power and ability_power != 'None':
            ability = f'{ability} · {ability_power}'
        label(376, f'Сила: {textwrap.shorten(ability, 30)}', 8)
        accent = '#d3aa56' if self.dark_theme else '#b4822e'
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
            ('\u0418\u043c\u044f', 'name'), ('\u041e\u0447\u043a\u0438', 'points'),
            ('\u041f\u0440\u043e\u0438\u0441\u0445\u043e\u0436\u0434\u0435\u043d\u0438\u0435', 'substory'),
            ('\u0420\u0430\u0441\u0430', 'race'), ('\u041f\u043e\u0434\u0440\u0430\u0441\u0430', 'subrace'),
            ('\u0420\u043e\u0441\u0442', 'size'), ('\u0421\u0438\u043b\u0430', 'strength'),
            ('\u0421\u043a\u043e\u0440\u043e\u0441\u0442\u044c', 'speed'), ('\u0418\u043d\u0442\u0435\u043b\u043b\u0435\u043a\u0442', 'iq'),
            ('\u0411\u043e\u0435\u0432\u044b\u0435 \u043d\u0430\u0432\u044b\u043a\u0438', 'fighting'),
            ('\u041e\u0440\u0443\u0436\u0438\u0435', 'weapon'), ('\u0412\u043b\u0430\u0434\u0435\u043d\u0438\u0435 \u043e\u0440\u0443\u0436\u0438\u0435\u043c', 'weapon_mastery'),
            ('\u0417\u0430\u0447\u0430\u0440\u043e\u0432\u0430\u043d\u0438\u0435 \u043e\u0440\u0443\u0436\u0438\u044f', 'weapon_enchantment'),
            ('\u0421\u043f\u043e\u0441\u043e\u0431\u043d\u043e\u0441\u0442\u044c', 'ability'), ('\u041c\u043e\u0449\u044c \u0441\u043f\u043e\u0441\u043e\u0431\u043d\u043e\u0441\u0442\u0438', 'ability_power'),
            ('\u0425\u0430\u043e\u0441', 'chaos'), ('\u0422\u0438\u0442\u0443\u043b', 'title'),
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
            action_width = 62 if key in self.stat_upgrade_fields else 0
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
            if key in self.stat_upgrade_fields:
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

