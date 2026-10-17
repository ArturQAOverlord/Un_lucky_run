from pathlib import Path
from contextlib import redirect_stdout
from io import StringIO
import math
import random
import textwrap
import tkinter as tk
from tkinter import messagebox, ttk

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
        root.bind('<Escape>', self._leave_fullscreen)
        style = ttk.Style(root)
        self.style = style
        self.dark_theme = False
        style.configure('Menu.TButton', font=('Segoe UI', 13, 'bold'), padding=(16, 14))
        self.show_home()

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
            colors = {'background': '#17191c', 'surface': '#22262b', 'input': '#30363d',
                      'foreground': '#f1f3f5', 'accent': '#3979a8'}
        else:
            colors = {'background': '#f0f0f0', 'surface': '#ffffff', 'input': '#ffffff',
                      'foreground': '#202124', 'accent': '#d9eaf7'}
        self.style.configure('.', background=colors['background'], foreground=colors['foreground'])
        self.style.configure('TFrame', background=colors['background'])
        self.style.configure('TLabel', background=colors['background'], foreground=colors['foreground'])
        self.style.configure('TButton', background=colors['surface'], foreground=colors['foreground'])
        self.style.map('TButton', background=[('active', colors['accent'])])
        self.style.configure('Menu.TButton', font=('Segoe UI', 13, 'bold'), padding=(16, 14))
        self.style.configure('TEntry', fieldbackground=colors['input'], foreground=colors['foreground'])
        self.style.configure('TCombobox', fieldbackground=colors['input'], foreground=colors['foreground'])
        self.style.map('TCombobox', fieldbackground=[('readonly', colors['input'])],
                       foreground=[('readonly', colors['foreground'])])
        self.style.configure('TCheckbutton', background=colors['background'], foreground=colors['foreground'])
        self.style.configure('Treeview', background=colors['input'], fieldbackground=colors['input'],
                             foreground=colors['foreground'], rowheight=26)
        self.style.configure('Treeview.Heading', background=colors['surface'], foreground=colors['foreground'])
        self.style.map('Treeview', background=[('selected', colors['accent'])],
                       foreground=[('selected', colors['foreground'])])
        self.style.configure('TLabelframe', background=colors['background'])
        self.style.configure('TLabelframe.Label', background=colors['background'],
                             foreground=colors['foreground'])
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
                widget.configure(background=colors['background'])
            for child in widget.winfo_children():
                recolor(child)

        recolor(self.root)

    def _toggle_dark_theme(self):
        self.dark_theme = self.dark_theme_var.get()
        self._apply_theme()

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
        if self.window_resolution or self.fullscreen:
            return 1.0
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

    def _toggle_fullscreen(self):
        self.fullscreen = self.fullscreen_var.get()
        self.root.attributes('-fullscreen', self.fullscreen)
        self._apply_window_geometry()

    def _leave_fullscreen(self, _event=None):
        if self.fullscreen:
            self.fullscreen = False
            self.root.attributes('-fullscreen', False)
            if hasattr(self, 'fullscreen_var'):
                self.fullscreen_var.set(False)
            self._apply_window_geometry()

    def heading(self, parent, text):
        ttk.Label(parent, text=text, font=('Segoe UI', 16, 'bold')).pack(anchor='w', pady=(0, 16))

    def show_home(self):
        self.clear()
        self.root.title('Неудачный забег')
        self._set_page_geometry('600x640')
        frame = ttk.Frame(self.root, padding=(36, 30))
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Неудачный забег', font=('Segoe UI', 24, 'bold')).pack(pady=(18, 4))
        ttk.Label(frame, text='Главное меню', font=('Segoe UI', 12)).pack(pady=(0, 24))
        menu = ttk.Frame(frame)
        menu.pack(fill='both', expand=True, pady=(0, 8))
        entries = (
            ('Создать персонажа', self.show_create),
            ('Готовые персонажи', self.show_characters),
            ('Сражение', self.show_fight),
            ('Турнир', self.show_tournament),
            ('\u041e\u043f\u0446\u0438\u0438', self.show_options),
        )
        for text, command in entries:
            ttk.Button(menu, text=text, command=command, style='Menu.TButton').pack(
                fill='both', expand=True, pady=7
            )

    def show_options(self):
        self.clear()
        frame = ttk.Frame(self.root, padding=24)
        frame.pack(fill='both', expand=True)
        ttk.Button(frame, text='Назад', command=self.show_home).pack(anchor='w', pady=(0, 18))
        settings = ttk.Frame(frame)
        settings.pack(expand=True)
        ttk.Label(settings, text='Опции', font=('Segoe UI', 16, 'bold')).pack(pady=(0, 16))
        self.dark_theme_var = tk.BooleanVar(value=self.dark_theme)
        ttk.Checkbutton(settings, text='Тёмная тема', variable=self.dark_theme_var,
                        command=self._toggle_dark_theme).pack(pady=8)
        self.fullscreen_var = tk.BooleanVar(value=self.fullscreen)
        ttk.Checkbutton(settings, text='Полноэкранный режим', variable=self.fullscreen_var,
                        command=self._toggle_fullscreen).pack(pady=8)
        ttk.Label(settings, text='Разрешение окна:').pack(pady=(12, 4))
        self.resolution_var = tk.StringVar(value=self.window_resolution or 'Авто')
        resolution_box = ttk.Combobox(
            settings, textvariable=self.resolution_var, state='readonly',
            values=self._resolution_options(), width=18,
        )
        resolution_box.pack()
        resolution_box.bind('<<ComboboxSelected>>', self._change_resolution)

    def show_tournament(self):
        self.clear()
        self._set_page_geometry('900x760')
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
        roster_frame = ttk.Frame(tables)
        roster_frame.pack(side='right', fill='both', expand=True, padx=(12, 0))

        self.available_table = ttk.Treeview(available_frame, columns=('name',), show='headings', height=9, selectmode='browse')
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

        self.roster_table = ttk.Treeview(roster_frame, columns=('name',), show='headings', height=9, selectmode='browse')
        self.roster_table.heading('name', text='Ростер (0/20)')
        self.roster_table.column('name', anchor='w', width=260)
        self.roster_table.pack(side='left', fill='both', expand=True)
        roster_scroll = ttk.Scrollbar(roster_frame, orient='vertical', command=self.roster_table.yview)
        roster_scroll.pack(side='right', fill='y')
        self.roster_table.configure(yscrollcommand=roster_scroll.set)

        self.roster_count = ttk.Label(frame, text='Выбрано: 0 / 20')
        self.roster_count.pack(anchor='w', pady=(0, 6))
        actions = ttk.Frame(frame)
        actions.pack(anchor='w', pady=(0, 8))
        ttk.Button(actions, text='Автозаполнить: первые 20',
                   command=self.auto_fill_roster).pack(side='left', padx=(0, 8))
        ttk.Button(actions, text='Провести турнир', command=self.start_tournament).pack(side='left')
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
            for column, title, width, anchor in (
                ('rank', '№', 32, 'center'), ('name', 'Персонаж', 145, 'w'),
                ('wins', 'Победы', 62, 'center'), ('score', 'Очки', 72, 'center'),
            ):
                table.heading(column, text=title)
                table.column(column, width=width, anchor=anchor, stretch=column == 'name')
            table.pack(fill='both', expand=True)
            self.group_tables[group_name] = table
        self.bracket_canvas = tk.Canvas(bracket_tab, width=1120, height=390,
                                        highlightthickness=0, background='white', cursor='hand2')
        self.bracket_canvas.bind(
            '<ButtonPress-1>',
            lambda event: self.bracket_canvas.scan_mark(event.x, event.y),
        )
        self.bracket_canvas.bind(
            '<B1-Motion>',
            lambda event: self.bracket_canvas.scan_dragto(event.x, event.y, gain=1),
        )
        bracket_xscroll = ttk.Scrollbar(bracket_tab, orient='horizontal',
                                        command=self.bracket_canvas.xview)
        self.bracket_canvas.configure(xscrollcommand=bracket_xscroll.set,
                                      scrollregion=(0, 0, 1120, 390))
        self.bracket_canvas.pack(fill='both', expand=True)
        bracket_xscroll.pack(fill='x')
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
        canvas.delete('all')
        foreground = '#e9edf2' if self.dark_theme else '#263448'
        card = '#252b33' if self.dark_theme else '#ffffff'
        muted = '#aab4c0' if self.dark_theme else '#667085'
        connector = '#64748b'
        champion_fill = '#d8f3dc' if not self.dark_theme else '#254b39'
        champion_text = '#205c38' if not self.dark_theme else '#d7f5df'
        canvas.configure(background='#17191c' if self.dark_theme else '#f0f0f0')
        columns = ((20, 'Четвертьфиналы'), (310, 'Полуфиналы'),
                   (600, 'Финал'), (890, 'Победитель'))
        for x, title in columns:
            canvas.create_text(x, 18, text=title, anchor='w', fill=foreground,
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
                line_y = y + 18 + row * 25
                if is_winner:
                    canvas.create_rectangle(x + 1, line_y - 11, x + card_width - 1,
                                            line_y + 11, fill=champion_fill, outline='')
                canvas.create_text(x + 10, line_y, text=textwrap.shorten(name, 24),
                                   anchor='w', fill=champion_text if is_winner else foreground,
                                   font=('Segoe UI', 9, 'bold' if is_winner else 'normal'))
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
                table.insert('', 'end', values=(
                    player['rank'], player['name'], player['wins'],
                    f"{player['for']}:{player['against']}",
                ))

    def remove_from_roster(self):
        selection = self.roster_table.selection()
        if not selection:
            return
        self.roster_table.delete(selection[0])
        self.update_roster_count()

    def update_roster_count(self):
        count = len(self.roster_table.get_children())
        self.roster_table.heading('name', text=f'Ростер ({count}/20)')
        self.roster_count.configure(text=f'Выбрано: {count} / 20')

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
        page_scale = self._automatic_page_scale(600, 640)
        self._set_page_geometry(f'{int(600 * page_scale)}x{int(640 * page_scale)}')
        frame = ttk.Frame(self.root, padding=18)
        frame.pack(fill='both', expand=True)
        ttk.Button(frame, text='\u2190 \u041d\u0430 \u0433\u043b\u0430\u0432\u043d\u0443\u044e', command=self.show_home).pack(anchor='w', pady=(0, 12))
        self.heading(frame, '\u0421\u0440\u0430\u0436\u0435\u043d\u0438\u0435 \u043f\u0435\u0440\u0441\u043e\u043d\u0430\u0436\u0435\u0439')
        files = character_files_by_creation_date()
        if len(files) < 2:
            ttk.Label(frame, text='\u0414\u043b\u044f \u0441\u0440\u0430\u0436\u0435\u043d\u0438\u044f \u043d\u0443\u0436\u043d\u043e \u0441\u043e\u0445\u0440\u0430\u043d\u0438\u0442\u044c \u043c\u0438\u043d\u0438\u043c\u0443\u043c \u0434\u0432\u0443\u0445 \u043f\u0435\u0440\u0441\u043e\u043d\u0430\u0436\u0435\u0439.').pack(anchor='w')
            return
        self.fight_files = files
        names = [file.stem for file in files]
        row = ttk.Frame(frame)
        row.pack(fill='x', pady=(0, 8))
        left = ttk.Frame(row, width=125)
        left.pack(side='left', fill='y', expand=True)
        center = ttk.Frame(row, width=270)
        center.pack(side='left', fill='y')
        right = ttk.Frame(row, width=125)
        right.pack(side='left', fill='y', expand=True)
        ttk.Label(left, text='\u041f\u0435\u0440\u0432\u044b\u0439 \u0431\u043e\u0435\u0446', anchor='center').pack(fill='x', pady=(0, 4))
        self.first_fighter = ttk.Combobox(left, state='readonly', values=names)
        self.first_fighter.pack(fill='x', padx=3)
        ttk.Label(right, text='\u0412\u0442\u043e\u0440\u043e\u0439 \u0431\u043e\u0435\u0446', anchor='center').pack(fill='x', pady=(0, 4))
        self.second_fighter = ttk.Combobox(right, state='readonly', values=names)
        self.second_fighter.pack(fill='x', padx=3)
        self.first_fighter.current(0)
        self.second_fighter.current(1)
        self.fight_portrait_canvases = []
        for panel in (left, right):
            portrait = tk.Canvas(panel, width=115, height=172, highlightthickness=0,
                                 background='#20242a' if self.dark_theme else '#e8e2d8')
            portrait.pack(pady=(6, 0))
            self.fight_portrait_canvases.append(portrait)
        self.fight_portrait_sources = {}
        self.first_fighter.bind('<<ComboboxSelected>>', lambda _event: self._draw_fight_portrait(0))
        self.second_fighter.bind('<<ComboboxSelected>>', lambda _event: self._draw_fight_portrait(1))
        self.fight_status = ttk.Label(center, text='', anchor='center')
        self.fight_status.pack(fill='x', pady=(0, 4))
        wheel_scale = self._wheel_scale(600, 640)
        self.fight_wheel = tk.Canvas(center, width=int(270 * wheel_scale), height=int(220 * wheel_scale),
                                     highlightthickness=0, background='#20242a' if self.dark_theme else '#f0f0f0')
        self.fight_wheel.pack(pady=(0, 6))
        self._draw_fight_wheel(names[0], names[1], 0)
        self.fight_button = ttk.Button(center, text='\u041d\u0430\u0447\u0430\u0442\u044c \u0441\u0440\u0430\u0436\u0435\u043d\u0438\u0435', command=self.start_fight)
        self.fight_button.pack()
        self._draw_fight_portrait(0)
        self._draw_fight_portrait(1)
        self.fight_result = self.make_text(frame)

    def _draw_fight_portrait(self, fighter_index):
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

        templates = dict(zip((race.casefold() for race in data.race_sum), ('human', 'orc', 'elf')))
        aliases = dict(templates)
        for race, template in templates.items():
            try:
                aliases[race.encode('utf-8').decode('cp1251').casefold()] = template
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
        template = aliases.get(properties.get('race', '').casefold())
        if not template:
            canvas.create_text(57, 86, text=selector.get(), width=105,
                               fill='#f1f3f5' if self.dark_theme else '#202124')
            return

        root = Path(__file__).resolve().parent / 'CardTemplates'
        for kind in ('races', 'characters'):
            key = (kind, template)
            if key in self.fight_portrait_sources:
                continue
            image_path = root / kind / f'{template}.png'
            if not image_path.exists():
                continue
            try:
                image = tk.PhotoImage(file=str(image_path))
                scale = max(1, math.ceil(max(image.width() / 115, image.height() / 172)))
                self.fight_portrait_sources[key] = image.subsample(scale, scale)
            except tk.TclError:
                pass
        background = self.fight_portrait_sources.get(('races', template))
        character = self.fight_portrait_sources.get(('characters', template))
        if background:
            canvas.create_image(57, 86, image=background, anchor='center')
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
                weapon_key = ('weapons', weapon_template)
                if weapon_key not in self.fight_portrait_sources:
                    weapon_path = root / 'weapons' / f'{weapon_template}.png'
                    if weapon_path.exists():
                        try:
                            source = tk.PhotoImage(file=str(weapon_path))
                            scale = max(1, math.ceil(max(source.width() / 58, source.height() / 58)))
                            self.fight_portrait_sources[weapon_key] = source.subsample(scale, scale)
                        except tk.TclError:
                            pass
                weapon = self.fight_portrait_sources.get(weapon_key)
                if weapon:
                    hand_x = 57 - character.width() / 2 + character.width() * 0.16
                    hand_y = 166 - character.height() * 0.62
                    if weapon_template == 'tank':
                        x, y = hand_x - weapon.width() * 0.58, hand_y - weapon.height() * 0.62
                    else:
                        x, y = hand_x - weapon.width() * 0.78, hand_y - weapon.height() * 0.78
                    canvas.create_image(x, y, image=weapon, anchor='nw')
            canvas.create_image(57, 166, image=character, anchor='s')

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
        self.set_text(self.fight_result, '')
        self.fight_rounds = result['comparisons']
        self.fight_report = result['report']
        self.fight_round_index = 0
        self.fight_rotation = 0
        self.fight_names = (self.first_fighter.get(), self.second_fighter.get())
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
            last_comparison = self.fight_rounds[-1]
            self._draw_fight_wheel(
                *self.fight_names,
                self.fight_rotation,
                last_comparison['first_points'],
                last_comparison['second_points'],
            )
            self.fight_status.configure(text='Сражение завершено')
            self.set_text(self.fight_result, self.fight_report)
            self.fight_button.configure(state='normal')
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
            self.fight_round_index += 1
            self.spin_after_id = self.root.after(550, self._spin_fight_round)

        animate()

    def show_create(self):
        self.clear()
        page_scale = self._automatic_page_scale(760, 850)
        self._set_page_geometry(f'{int(760 * page_scale)}x{int(850 * page_scale)}')
        frame = ttk.Frame(self.root, padding=18)
        frame.pack(fill='both', expand=True)
        ttk.Button(frame, text='← На главную', command=self.show_home).pack(anchor='w', pady=(0, 10))
        self.heading(frame, 'Создание персонажа')
        ttk.Label(frame, text='Имя героя:').pack(anchor='w', pady=(0, 4))
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(frame, textvariable=self.name_var)
        self.name_entry.pack(fill='x')
        self.name_entry.bind('<Return>', lambda _event: self.generate())
        self.generate_button = ttk.Button(frame, text='Начать генерацию', command=self.generate)
        self.generate_button.pack(anchor='w', pady=8)
        self.wheel_status = ttk.Label(frame, text='Каждый атрибут будет выбираться 10 секунд.')
        self.wheel_status.pack(anchor='w', pady=(0, 2))
        self.wheel_selection = ttk.Label(frame, text='')
        self.wheel_selection.pack(anchor='w', pady=(0, 4))
        self.skip_spin_button = ttk.Button(
            frame, text='Пропустить прокрутку', command=self._skip_current_spin,
            state='disabled',
        )
        self.skip_spin_button.pack(anchor='w', pady=(0, 4))
        wheel_size = int(430 * self._wheel_scale(760, 850))
        self.wheel_canvas = tk.Canvas(
            frame, width=wheel_size, height=wheel_size, highlightthickness=1,
            highlightbackground='#777777', background='white',
        )
        self.wheel_canvas.pack(pady=4)
        self._draw_wheel(data.substory_sum, 0)
        self.result = tk.Text(frame, wrap='word', state='disabled', font=('Segoe UI', 9), height=6)
        self.result.pack(fill='both', expand=True, pady=(4, 0))
        self.name_entry.focus_set()

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
            simple_step('Способность', 'ability', data.ability_sum, data.ability_weights),
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
        if self.spin_index >= len(self.wheel_steps):
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
        total_frames = 333
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
            self.wheel_rotation = desired_rotation
            self.wheel_status.configure(text=f'Выпало: {label} - {selected_text}')
            self.result.configure(state='normal')
            self.result.insert('end', f'{label}: {selected_text}\n')
            self.result.see('end')
            self.result.configure(state='disabled')

            next_steps = []
            if label == 'Оружие' and selected != data.weapon_sum[0]:
                next_steps.extend([
                    ('Владение оружием', data.weapon_mastery_sum, data.weapon_mastery_weights,
                     lambda value: setattr(self.current_hero, 'weapon_mastery', value), str),
                    ('Зачарование оружия', data.weapon_enchantment_sum, data.weapon_enchantment_weights,
                     lambda value: setattr(self.current_hero, 'weapon_enchantment', value), str),
                ])
            if label == 'Способность' and selected != data.ability_sum[0]:
                next_steps.append((
                    'Мощь способности', data.ability_power_sum, data.ability_power_weights,
                    lambda value: setattr(self.current_hero, 'ability_power', value), str,
                ))
            if next_steps:
                self.wheel_steps[self.spin_index + 1:self.spin_index + 1] = next_steps
            self.spin_index += 1
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
        if finish_spin is not None:
            finish_spin()

    def generate(self):
        if getattr(self, 'generation_active', False):
            return
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning('Нужно имя', 'Введите имя персонажа.')
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
        self.generate_button.configure(state='disabled')
        self.set_text(self.result, '')
        self._spin_next()

    def show_characters(self):
        self.clear()
        frame = ttk.Frame(self.root, padding=18)
        frame.pack(fill='both', expand=True)
        ttk.Button(frame, text='← На главную', command=self.show_home).pack(anchor='w', pady=(0, 12))
        self.heading(frame, 'Готовые персонажи')
        body = ttk.Frame(frame)
        body.pack(fill='both', expand=True)
        input_background = '#30363d' if self.dark_theme else '#ffffff'
        foreground = '#f1f3f5' if self.dark_theme else '#202124'
        selection_background = '#3979a8' if self.dark_theme else '#d9eaf7'
        self.character_list = tk.Listbox(
            body, width=24, exportselection=False,
            background=input_background, foreground=foreground,
            selectbackground=selection_background, selectforeground=foreground,
        )
        self.character_list.pack(side='left', fill='y')
        self.character_list.bind('<<ListboxSelect>>', self.open_selected)
        scrollbar = ttk.Scrollbar(body, orient='vertical', command=self.character_list.yview)
        scrollbar.pack(side='left', fill='y')
        self.character_list.configure(yscrollcommand=scrollbar.set)
        preview = ttk.Frame(body)
        preview.pack(side='left', fill='both', expand=True, padx=(12, 0))
        self.card_canvas = tk.Canvas(preview, width=280, height=420,
                                     highlightthickness=0, background='white')
        self.card_canvas.pack(pady=(0, 4))
        self.detail = tk.Text(preview, wrap='word', state='disabled',
                              font=('Segoe UI', 8), height=5)
        detail_scroll = ttk.Scrollbar(preview, orient='vertical', command=self.detail.yview)
        self.detail.configure(yscrollcommand=detail_scroll.set)
        self.detail.pack(side='left', fill='both', expand=True)
        detail_scroll.pack(side='right', fill='y')
        self.card_template_cache = {}
        self.card_character_sources = {}
        self.card_character_cache = {}
        self.card_weapon_sources = {}
        self.card_weapon_cache = {}
        self.files = character_files_by_creation_date()
        for path in self.files:
            self.character_list.insert('end', path.stem)
        if not self.files:
            self.set_text(self.detail, 'Пока нет сохранённых персонажей.')
            self._draw_character_card({})
        else:
            self.character_list.selection_set(0)
            self.open_selected()

    def _draw_character_card(self, properties):
        canvas = self.card_canvas
        canvas.delete('all')
        race = properties.get('race', '').casefold()
        race_template_names = dict(zip((race.casefold() for race in data.race_sum), ('human', 'orc', 'elf')))
        template_name = race_template_names.get(race)
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
        target_heights = dict(zip((size.casefold() for size in data.size_sum), (190, 225, 265, 305)))
        target_height = target_heights.get(size_name, 225)
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
                scale = max(1, round(source.height() / target_height))
                figure = source.subsample(scale, scale)
                self.card_character_cache[figure_key] = figure
            except tk.TclError:
                figure = None

        figure_x = left + 130
        figure_bottom = top + 330
        ability = properties.get('ability', '—')

        if figure is not None:
            hand_fractions = {'human': 0.17, 'orc': 0.12, 'elf': 0.17}
            hand_x = figure_x - figure.width() / 2 + figure.width() * hand_fractions.get(template_name, 0.16)
            hand_y = figure_bottom - figure.height() * 0.62
            self._draw_card_weapon(canvas, properties.get('weapon', ''), hand_x, hand_y)
            canvas.create_image(figure_x, figure_bottom, image=figure, anchor='s')

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

    def _draw_card_weapon(self, canvas, weapon, hand_x, hand_y):
        weapon = weapon.casefold()
        weapon_templates = {
            '\u043a\u0430\u0442\u0430\u043d\u0430': 'katana', '\u0442\u043e\u043f\u043e\u0440': 'axe', '\u043c\u0435\u0447': 'sword',
            '\u043f\u0438\u0441\u0442\u043e\u043b\u0435\u0442': 'pistol', '\u0442\u0430\u043d\u043a': 'tank',
            '\u043f\u043e\u0440\u0442\u0430\u043b\u044c\u043d\u0430\u044f \u043f\u0443\u0448\u043a\u0430': 'portal_cannon',
        }
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
                scale = max(1, math.ceil(max(source.width() / 88, source.height() / 88)))
                cache_key = (template_name, scale)
                image = self.card_weapon_cache.get(cache_key)
                if image is None:
                    image = source.subsample(scale, scale)
                    self.card_weapon_cache[cache_key] = image
                if template_name == 'tank':
                    x, y = hand_x - image.width() * 0.58, hand_y - image.height() * 0.62
                else:
                    x, y = hand_x - image.width() * 0.78, hand_y - image.height() * 0.78
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

    def set_text(self, widget, value):
        widget.configure(state='normal')
        widget.delete('1.0', 'end')
        widget.insert('1.0', value)
        widget.configure(state='disabled')

    def open_selected(self, _event=None):
        selection = self.character_list.curselection()
        if not selection:
            return
        path = self.files[selection[0]]
        try:
            content = path.read_text(encoding='utf-8')
        except OSError as error:
            messagebox.showerror('Ошибка чтения', str(error))
            return
        self.set_text(self.detail, content)
        properties = {}
        for line in content.splitlines():
            key, separator, value = line.partition(':')
            if separator:
                properties[key.strip()] = value.strip()
        self._draw_character_card(properties)


def run():
    root = tk.Tk()
    CharacterApp(root)
    root.mainloop()


if __name__ == '__main__':
    run()
