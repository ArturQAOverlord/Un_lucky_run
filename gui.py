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


class CharacterApp:
    def __init__(self, root):
        self.root = root
        root.title('Неудачный забег')
        root.geometry('600x640')
        root.minsize(480, 420)
        style = ttk.Style(root)
        self.style = style
        self.dark_theme = False
        style.configure('Menu.TButton', font=('Segoe UI', 13, 'bold'), padding=(16, 14))
        self.show_home()

    def clear(self):
        self.generation_active = False
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

        def recolor(widget):
            if isinstance(widget, (tk.Text, tk.Listbox)):
                widget.configure(bg=colors['input'], fg=colors['foreground'],
                                 insertbackground=colors['foreground'], selectbackground=colors['accent'])
            elif isinstance(widget, tk.Canvas):
                widget.configure(background=colors['background'])
            for child in widget.winfo_children():
                recolor(child)

        recolor(self.root)

    def _toggle_dark_theme(self):
        self.dark_theme = self.dark_theme_var.get()
        self._apply_theme()

    def heading(self, parent, text):
        ttk.Label(parent, text=text, font=('Segoe UI', 16, 'bold')).pack(anchor='w', pady=(0, 16))

    def show_home(self):
        self.clear()
        self.root.title('Неудачный забег')
        self.root.geometry('600x640')
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
        self.heading(frame, 'Опции')
        self.dark_theme_var = tk.BooleanVar(value=self.dark_theme)
        ttk.Checkbutton(frame, text='Тёмная тема', variable=self.dark_theme_var,
                        command=self._toggle_dark_theme).pack(anchor='w', pady=8)

    def show_tournament(self):
        self.clear()
        self.root.geometry('900x760')
        frame = ttk.Frame(self.root, padding=18)
        frame.pack(fill='both', expand=True)
        ttk.Button(frame, text='← На главную', command=self.show_home).pack(anchor='w', pady=(0, 12))
        self.heading(frame, 'Турнир')
        files = sorted(CHARACTERS_DIR.glob('*.txt'), key=lambda path: path.name.casefold()) if CHARACTERS_DIR.exists() else []
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
        ttk.Button(frame, text='Провести турнир', command=self.start_tournament).pack(anchor='w', pady=(0, 8))
        result_frame = ttk.Frame(frame)
        result_frame.pack(fill='both', expand=True)
        self.tournament_result = tk.Text(result_frame, wrap='word', state='disabled', font=('Consolas', 10))
        self.tournament_result.pack(side='left', fill='both', expand=True)
        result_scroll = ttk.Scrollbar(result_frame, orient='vertical', command=self.tournament_result.yview)
        result_scroll.pack(side='right', fill='y')
        self.tournament_result.configure(yscrollcommand=result_scroll.set)

    def add_to_roster(self):
        selection = self.available_table.selection()
        if not selection:
            return
        item_id = selection[0]
        if self.roster_table.exists(item_id):
            return
        self.roster_table.insert('', 'end', iid=item_id, values=self.available_table.item(item_id, 'values'))
        self.update_roster_count()

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

    def show_fight(self):
        self.clear()
        frame = ttk.Frame(self.root, padding=18)
        frame.pack(fill='both', expand=True)
        ttk.Button(frame, text='← На главную', command=self.show_home).pack(anchor='w', pady=(0, 12))
        self.heading(frame, 'Сражение персонажей')
        files = sorted(CHARACTERS_DIR.glob('*.txt'), key=lambda path: path.name.casefold()) if CHARACTERS_DIR.exists() else []
        if len(files) < 2:
            ttk.Label(frame, text='Для сражения нужно сохранить минимум двух персонажей.').pack(anchor='w')
            return
        self.fight_files = files
        names = [path.stem for path in files]
        ttk.Label(frame, text='Первый персонаж:').pack(anchor='w', pady=(0, 4))
        self.first_fighter = ttk.Combobox(frame, state='readonly', values=names)
        self.first_fighter.pack(fill='x', pady=(0, 12))
        ttk.Label(frame, text='Второй персонаж:').pack(anchor='w', pady=(0, 4))
        self.second_fighter = ttk.Combobox(frame, state='readonly', values=names)
        self.second_fighter.pack(fill='x', pady=(0, 12))
        self.first_fighter.current(0)
        self.second_fighter.current(1)
        self.fight_button = ttk.Button(frame, text='Начать сражение', command=self.start_fight)
        self.fight_button.pack(anchor='w', pady=(0, 8))
        self.fight_status = ttk.Label(frame, text='')
        self.fight_status.pack(anchor='w', pady=(0, 4))
        self.fight_wheel = tk.Canvas(frame, width=380, height=300, highlightthickness=0, background='white')
        self.fight_wheel.pack(pady=(0, 4))
        self._draw_fight_wheel(names[0], names[1], 0)
        self.fight_result = self.make_text(frame)

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

    def _draw_fight_wheel(self, first_name, second_name, rotation):
        canvas = self.fight_wheel
        canvas.delete('all')
        width, height = int(canvas['width']), int(canvas['height'])
        cx, cy = width / 2, height / 2 + 8
        radius = min(width, height) / 2 - 28
        box = (cx - radius, cy - radius, cx + radius, cy + radius)
        canvas.create_arc(*box, start=rotation, extent=180, fill='#58a6d6', outline='white', width=3)
        canvas.create_arc(*box, start=rotation + 180, extent=180, fill='#e88962', outline='white', width=3)
        for angle, label in ((rotation + 90, first_name), (rotation + 270, second_name)):
            radians = math.radians(angle)
            x = cx + math.cos(radians) * radius * 0.56
            y = cy - math.sin(radians) * radius * 0.56
            canvas.create_text(x, y, text=textwrap.fill(label, 16), width=110,
                              font=('Segoe UI', 10, 'bold'), justify='center')
        canvas.create_oval(cx-18, cy-18, cx+18, cy+18, fill='white', outline='#333333', width=2)
        canvas.create_polygon(cx-12, cy-radius-18, cx+12, cy-radius-18, cx, cy-radius+8,
                              fill='#d00000', outline='#700000')

    def _spin_fight_round(self):
        if self.fight_round_index >= len(self.fight_rounds):
            self._draw_fight_wheel(*self.fight_names, self.fight_rotation)
            self.fight_status.configure(text='Сражение завершено')
            self.set_text(self.fight_result, self.fight_report)
            self.fight_button.configure(state='normal')
            return

        comparison = self.fight_rounds[self.fight_round_index]
        winner_index = 0 if comparison['winner'] == comparison['first_name'] else 1
        start_rotation = self.fight_rotation
        target = 0 if winner_index == 0 else 180
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
            self._draw_fight_wheel(*self.fight_names, rotation)
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
        self.root.geometry('760x850')
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
        self.wheel_canvas = tk.Canvas(frame, width=430, height=430, highlightthickness=1, highlightbackground='#777777', background='white')
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
        radius = min(width, height) / 2 - 24
        colors = ('#f4a261', '#2a9d8f', '#e9c46a', '#e76f51', '#8ecae6', '#a8dadc', '#cdb4db', '#ffafcc', '#b7e4c7')
        weights = list(weights) if weights is not None else [1] * len(options)
        total_weight = sum(weights)
        angle_before = 0.0
        for index, (option, weight) in enumerate(zip(options, weights)):
            segment = 360 * weight / total_weight
            start = (rotation + angle_before) % 360
            canvas.create_arc(center_x-radius, center_y-radius, center_x+radius, center_y+radius,
                              start=start, extent=segment, fill=colors[index % len(colors)], outline='white', width=2)
            middle = math.radians(start + segment / 2)
            label_radius = radius * 0.64
            x = center_x + math.cos(middle) * label_radius
            y = center_y - math.sin(middle) * label_radius
            label = textwrap.fill(str(option), width=17)
            canvas.create_text(x, y, text=label, width=105, font=('Segoe UI', 8), justify='center')
            angle_before += segment
        canvas.create_oval(center_x-22, center_y-22, center_x+22, center_y+22, fill='white', outline='#333333', width=2)
        needle_angle = math.radians(rotation % 360)
        canvas.create_line(
            center_x, center_y,
            center_x + math.cos(needle_angle) * radius * 0.28,
            center_y - math.sin(needle_angle) * radius * 0.28,
            fill='#222222', width=5, arrow='last',
        )
        canvas.create_polygon(center_x-12, center_y-radius-17, center_x+12, center_y-radius-17,
                              center_x, center_y-radius+8, fill='#d00000', outline='#700000')

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
            return

        label, options, weights, assign, display = self.wheel_steps[self.spin_index]
        selected = random.choices(options, weights=weights, k=1)[0]
        selected_text = display(selected)
        wheel_options = [display(option) for option in options]
        selected_index = options.index(selected)
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

        def animate():
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
                    ('Владение оружием', data.weapon_mastery_sum, data.weapon_mastery_weights, lambda value: setattr(self.current_hero, 'weapon_mastery', value), str),
                    ('Зачарование оружия', data.weapon_enchantment_sum, data.weapon_enchantment_weights, lambda value: setattr(self.current_hero, 'weapon_enchantment', value), str),
                ])
            if label == 'Способность' and selected != data.ability_sum[0]:
                next_steps.append((
                    'Мощь способности',
                    data.ability_power_sum,
                    data.ability_power_weights,
                    lambda value: setattr(self.current_hero, 'ability_power', value),
                    str,
                ))
            if next_steps:
                self.wheel_steps[self.spin_index + 1:self.spin_index + 1] = next_steps
            self.spin_index += 1
            self.spin_after_id = self.root.after(700, self._spin_next)

        animate()

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
        self.character_list = tk.Listbox(body, width=24, exportselection=False)
        self.character_list.pack(side='left', fill='y')
        self.character_list.bind('<<ListboxSelect>>', self.open_selected)
        scrollbar = ttk.Scrollbar(body, orient='vertical', command=self.character_list.yview)
        scrollbar.pack(side='left', fill='y')
        self.character_list.configure(yscrollcommand=scrollbar.set)
        self.detail = self.make_text(body)
        self.files = sorted(CHARACTERS_DIR.glob('*.txt'), key=lambda path: path.name.casefold()) if CHARACTERS_DIR.exists() else []
        for path in self.files:
            self.character_list.insert('end', path.stem)
        if not self.files:
            self.set_text(self.detail, 'Пока нет сохранённых персонажей.')

    def make_text(self, parent):
        text = tk.Text(parent, wrap='word', state='disabled', font=('Segoe UI', 10))
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


def run():
    root = tk.Tk()
    CharacterApp(root)
    root.mainloop()


if __name__ == '__main__':
    run()
