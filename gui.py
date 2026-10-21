from pathlib import Path
from contextlib import redirect_stdout
from io import StringIO
import ctypes
import ctypes.util
import json
import logging
import math
import os
import random
import re
import sys
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
LOG_PATH = Path(__file__).resolve().parent / 'unlucky_run.log'
LADDER_INDEX_KEY = 'ladder_index'
AUDIO_DEVICE_POLL_MS = 3000
FIGHT_HIT_FLASH_MS = 450
# A lost ladder fight is shown and heard for a moment before the defeat dialog.
LADDER_DEFEAT_PAUSE_MS = 1000
# Borders of the winner and the loser of a fight; the loser colour also marks a lost round.
WINNER_COLOR = '#3f7d3a'
LOSER_COLOR = '#a8322a'
# Mouse wheels report notches of 120; one notch scrolls this many units.
WHEEL_UNITS_PER_NOTCH = 3
# Tk 8.6 on macOS reports wheels and touchpads in lines: one line in pixels.
AQUA_LINE_PIXELS = 20
# Touchpad travel that counts as one wheel notch, e.g. for zoom steps.
NOTCH_PIXELS = 60
# Tk 8.7+ reports macOS touchpads as separate <TouchpadScroll> events with pixel deltas.
TOUCHPAD_EVENTS = tk.TkVersion >= 8.7
# These widgets scroll themselves, so the wheel over them must not scroll the page too.
SELF_SCROLLING_CLASSES = {'Text', 'Treeview', 'Listbox', 'TCombobox'}
# Text width of the ability line in the bottom bar of a collection card (254 px wide).
CARD_ABILITY_WIDTH = 240
# Smallest and largest scale of the tournament bracket, zoomed by hand or fitted to the window.
BRACKET_ZOOM_LIMITS = (0.25, 2.4)
# Width of the value column on an arena stats card, in digits of its font; longer values are cut.
FIGHT_CARD_VALUE_CHARS = 14
# Stats that may take two lines on an arena stats card; they always get both, so rows keep their height.
FIGHT_CARD_TWO_LINE_STATS = {'ability', 'title'}
# Upgradable stats; each pool lists tiers from the best to the worst.
UPGRADE_POOLS = {
    'strength': data.strength_sum,
    'speed': data.speed_sum,
    'iq': data.iq_sum,
    'fighting': data.fighting_sum,
    'weapon_mastery': data.weapon_mastery_sum,
    'ability_power': data.ability_power_sum,
}
UPGRADE_BASE_COST = 5
FONTS_DIR = Path(__file__).resolve().parent / 'fonts'
# Font roles: the bundled fonts first, then serif fonts that most systems have.
FONT_CHOICES = {
    'title': ('Ruslan Display', 'Palatino Linotype', 'Palatino', 'Georgia', 'Times New Roman'),
    'text': ('Kurale', 'Palatino Linotype', 'Palatino', 'Georgia', 'Times New Roman'),
}
# Chosen by resolve_fonts() once Tk is running.
TITLE_FONT = TEXT_FONT = 'Georgia'
TEMPLATES_DIR = Path(__file__).resolve().parent / 'CardTemplates'
# Card pictures for race, weapon and size values, matched case-insensitively.
RACE_TEMPLATES = {race.casefold(): template for race, template in zip(data.race_sum, ('human', 'orc', 'elf'))}
WEAPON_TEMPLATES = {
    weapon.casefold(): template for weapon, template in zip(
        data.weapon_sum[1:], ('katana', 'axe', 'sword', 'pistol', 'tank', 'portal_cannon'))
}
SIZE_TIERS = {size.casefold(): tier for tier, size in enumerate(data.size_sum)}
# Where a figure's right hand is (share of its width) and where each weapon is gripped.
HAND_FRACTIONS = {'human': 0.17, 'orc': 0.12, 'elf': 0.17}
WEAPON_GRIPS = {
    'katana': (0.90, 0.91), 'axe': (0.92, 0.93), 'sword': (0.90, 0.91),
    'pistol': (0.83, 0.76), 'portal_cannon': (0.90, 0.90), 'tank': (0.58, 0.62),
}
# Every theme colour once, as (dark, light); pages look colours up by meaning.
# Dark is a candle-lit hall of old oak and gold; light is a manuscript of parchment and vermilion.
THEME_COLORS = {
    'background': ('#140f0a', '#e8dbbf'),
    'surface': ('#221811', '#f3e9d2'),
    'input': ('#2c2016', '#fbf5e6'),
    'foreground': ('#efe2c2', '#2e2015'),
    'muted': ('#a68f6a', '#76603f'),
    'title': ('#d9b45a', '#7a1f14'),
    'accent': ('#b8862e', '#8e2318'),
    'accent_hover': ('#d4a03f', '#a8301f'),
    'on_accent': ('#1b130c', '#fbf3e0'),
    'border': ('#46351f', '#c4ad84'),
    'frame_border': ('#7a5c2e', '#b08a52'),
    'bevel_light': ('#3a2a1b', '#fffaf0'),
    'bevel_dark': ('#0c0805', '#bfa77b'),
    'hover': ('#8a6a35', '#b08f5c'),
    'skip': ('#b5642a', '#c06a2a'),
    'skip_hover': ('#cf7a36', '#a85a22'),
    'victory_text': ('#a3d28a', '#2f6b2a'),
    'defeat_text': ('#e8806e', '#a12a1f'),
    'win_fill': ('#26391f', '#dbe8c6'),
    'win_text': ('#bfe3a1', '#2b5a24'),
    'lose_fill': ('#401c18', '#f2d3c7'),
    'lose_text': ('#f4a596', '#8f2418'),
    'out_fill': ('#3b1f1a', '#eed5c9'),
    'out_text': ('#eaa797', '#8a2a1e'),
    'champion_fill': ('#3d3216', '#efe0a8'),
    'champion_text': ('#f2d47c', '#5c4410'),
    'eliminated_fill': ('#3a201b', '#efd8cd'),
    'eliminated_text': ('#dca394', '#8a3a2c'),
    'arena_fill': ('#1d1510', '#efe3c8'),
    'arena_text': ('#efe2c2', '#2e2015'),
    'bracket_background': ('#100b07', '#e1d2b0'),
    'bracket_card': ('#2a1f16', '#f8f0dc'),
    'bracket_muted': ('#a68f6a', '#76603f'),
    'fight_card': ('#1f1610', '#fbf3df'),
    'fight_card_border': ('#8a6a32', '#b8955a'),
    'fight_card_text': ('#efe2c2', '#2e2015'),
    'gold_text': ('#d4b06a', '#8a6420'),
    'portrait_text': ('#efe2c2', '#2e2015'),
    'dead_border': ('#c0504a', '#a8322a'),
    'dead_fill': ('#3a1714', '#f3d9d2'),
    'dead_text': ('#f0a49a', '#8f2418'),
    'dead_bar': ('#5a1c18', '#7a2018'),
    'card_accent': ('#d4af37', '#a8822e'),
}
# The chronicle is always written on parchment, whatever the theme.
PARCHMENT = {'paper': '#ecdcb6', 'ink': '#2b1d12', 'rubric': '#7a1f14', 'heading': '#5a3a1a',
             'gilt': '#8a6420', 'faded': '#7a6243', 'code': '#e2cfa3'}
# Gold leaf, dark oak and light text for wooden and painted parts that look the same in both themes.
GILT, WOOD, PARCHMENT_TEXT = '#d4af37', '#2a1d12', '#f6ecd2'
# Heraldic tinctures for the wheel segments, each with the text colour that reads on it:
# gules, azure, vert, purpure, or, argent, tenné, sable, murrey.
TINCTURES = (('#9b1c1c', PARCHMENT_TEXT), ('#1f4e8c', PARCHMENT_TEXT), ('#2f6b3a', PARCHMENT_TEXT),
             ('#5b2f73', PARCHMENT_TEXT), ('#c9a227', WOOD), ('#9aa0a8', WOOD), ('#a8561e', PARCHMENT_TEXT),
             ('#3a3330', PARCHMENT_TEXT), ('#6b1f3a', PARCHMENT_TEXT))

logger = logging.getLogger(__name__)


def hand_position(template, figure, center_x, bottom):
    """Where the right hand of a figure standing on `bottom` is."""
    return (center_x - figure.width() / 2 + figure.width() * HAND_FRACTIONS.get(template, 0.16),
            bottom - figure.height() * 0.62)


def weapon_origin(template, weapon, hand_x, hand_y):
    """Top-left corner that puts the weapon's grip into the hand."""
    grip_x, grip_y = WEAPON_GRIPS.get(template, (0.9, 0.9))
    return hand_x - weapon.width() * grip_x, hand_y - weapon.height() * grip_y


def fit_text(text, font, width):
    """The text, cut short with an ellipsis when it is wider than `width` pixels in `font`."""
    measure = tkfont.Font(font=font).measure
    if measure(text) <= width:
        return text
    while text and measure(text.rstrip() + '…') > width:
        text = text[:-1]
    return text.rstrip() + '…'


def screen_work_area(root):
    """The screen without the taskbar as (left, top, right, bottom); outside Windows, the whole screen."""
    if sys.platform == 'win32':
        area = (ctypes.c_long * 4)()  # RECT
        if ctypes.windll.user32.SystemParametersInfoW(0x30, 0, area, 0):  # SPI_GETWORKAREA
            return tuple(area)
    return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()


def title_bar_height(root):
    """Height of the title bar, which Tk leaves out of the window size; counted on Windows only."""
    if sys.platform != 'win32':
        return 0
    if root.winfo_ismapped():
        return max(0, root.winfo_rooty() - root.winfo_y())
    metric = ctypes.windll.user32.GetSystemMetrics
    return metric(4) + metric(33) + metric(92)  # SM_CYCAPTION, SM_CYSIZEFRAME, SM_CXPADDEDBORDER


def _signed16(value):
    value &= 0xFFFF
    return value - 0x10000 if value >= 0x8000 else value


def _load_library(name):
    path = ctypes.util.find_library(name)
    if path is None:
        raise OSError(f'библиотека {name} не найдена')
    return ctypes.CDLL(path)


def _register_fonts_macos(paths):
    core_text, core_foundation = _load_library('CoreText'), _load_library('CoreFoundation')
    core_foundation.CFURLCreateFromFileSystemRepresentation.restype = ctypes.c_void_p
    core_foundation.CFURLCreateFromFileSystemRepresentation.argtypes = (
        ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_bool)
    core_foundation.CFRelease.argtypes = (ctypes.c_void_p,)
    core_text.CTFontManagerRegisterFontsForURL.restype = ctypes.c_bool
    core_text.CTFontManagerRegisterFontsForURL.argtypes = (ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p)
    for path in paths:
        raw = os.fsencode(path)
        url = core_foundation.CFURLCreateFromFileSystemRepresentation(None, raw, len(raw), False)
        try:
            if not core_text.CTFontManagerRegisterFontsForURL(url, 1, None):  # process scope
                logger.warning('Шрифт не подключён: %s', path.name)
        finally:
            core_foundation.CFRelease(url)


def _register_fonts_fontconfig(paths):
    fontconfig = _load_library('fontconfig')
    fontconfig.FcConfigAppFontAddFile.argtypes = (ctypes.c_void_p, ctypes.c_char_p)
    for path in paths:
        if not fontconfig.FcConfigAppFontAddFile(None, os.fsencode(path)):
            logger.warning('Шрифт не подключён: %s', path.name)


def load_bundled_fonts():
    """Make the fonts from fonts/ available to this process only; call before Tk starts."""
    paths = sorted(FONTS_DIR.glob('*.ttf'))
    try:
        if sys.platform == 'win32':
            for path in paths:
                if not ctypes.windll.gdi32.AddFontResourceExW(str(path), 0x10, 0):  # FR_PRIVATE
                    logger.warning('Шрифт не подключён: %s', path.name)
        elif sys.platform == 'darwin':
            _register_fonts_macos(paths)
        else:
            _register_fonts_fontconfig(paths)
    except (OSError, AttributeError) as error:
        logger.warning('Встроенные шрифты недоступны, будут системные: %s', error)


def resolve_fonts(root):
    """Pick the first installed family for each font role."""
    global TITLE_FONT, TEXT_FONT
    available = set(tkfont.families(root))
    chosen = {role: next((family for family in choices if family in available), choices[-1])
              for role, choices in FONT_CHOICES.items()}
    TITLE_FONT, TEXT_FONT = chosen['title'], chosen['text']
    # Entries, combobox lists and every other widget left on Tk's defaults read in the text font too.
    for name in ('TkDefaultFont', 'TkTextFont', 'TkMenuFont', 'TkHeadingFont', 'TkCaptionFont'):
        tkfont.nametofont(name, root=root).configure(family=TEXT_FONT)
    logger.info('Шрифты: заголовки «%s», текст «%s»', TITLE_FONT, TEXT_FONT)


def upgrade_cost(stat, value):
    """Price of the tier above `value`, or None at the top: every tier costs twice the previous."""
    tiers = UPGRADE_POOLS[stat]
    try:
        index = tiers.index(value)
    except ValueError:
        return None
    if index == 0:
        return None
    upgrades_bought = len(tiers) - 1 - index
    return UPGRADE_BASE_COST * 2 ** upgrades_bought


def creation_sort_key(path, properties, newest_first=True):
    """Order heroes by the `created_at` field; heroes without a valid date always go last."""
    try:
        created = datetime.fromisoformat(properties.get('created_at', '').strip()).timestamp()
    except (ValueError, OverflowError, OSError):
        return (True, 0.0, path.stem.casefold())
    return (False, -created if newest_first else created, path.stem.casefold())


# Collection sort modes in menu order; the first one is the default.
COLLECTION_SORTS = {
    'Сначала новые': lambda path, props: creation_sort_key(path, props),
    'Сначала старые': lambda path, props: creation_sort_key(path, props, newest_first=False),
    'По имени': lambda path, props: path.stem.casefold(),
    'По очкам (по убыванию)': lambda path, props: -Fight.character_points(props),
    'По очкам (по возрастанию)': lambda path, props: Fight.character_points(props),
    'Живые сначала': lambda path, props: (not Fight.is_character_alive(props), creation_sort_key(path, props)),
    'Мёртвые сначала': lambda path, props: (Fight.is_character_alive(props), creation_sort_key(path, props)),
}
ALL_RACES = 'Все расы'


def character_files_by_creation_date(living_only=False):
    if not CHARACTERS_DIR.exists():
        return []
    entries = []
    for path in CHARACTERS_DIR.glob('*.txt'):
        try:
            properties = Fight.load_character(path)
        except (OSError, UnicodeError):
            if living_only:  # an unreadable hero cannot fight
                continue
            properties = {}
        if living_only and not Fight.is_character_alive(properties):
            continue
        entries.append((creation_sort_key(path, properties), path))
    entries.sort(key=lambda entry: entry[0])
    return [path for _key, path in entries]


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
            properties = Fight.load_character(path)
        except (OSError, UnicodeError) as error:
            invalid_files.append(f'{path.name}: не удалось прочитать файл ({error})')
            diagnostics.append(f'{path.name}: ошибка чтения ({error})')
            continue
        raw_index = properties.get(LADDER_INDEX_KEY)
        try:
            index = int(raw_index)
            reason = None if index >= 1 else f'{LADDER_INDEX_KEY} должен быть больше нуля'
        except (TypeError, ValueError):
            reason = f'нет целого индекса {LADDER_INDEX_KEY}' if raw_index is None else (
                f'некорректный индекс {LADDER_INDEX_KEY}: {raw_index!r}'
            )
        if reason is not None:
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
    Fight.write_text_atomic(run_path, json.dumps(record, ensure_ascii=False, indent=2) + '\n')
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
        self.dark_theme = True
        self.sound_enabled = True
        self.sound_volume = 0.7
        self.audio_device = None
        self.settings_path = Path(__file__).resolve().parent / 'settings.json'
        self._load_settings()
        self.audio = audio.AudioManager(
            enabled=self.sound_enabled, volume=self.sound_volume, device=self.audio_device,
        )
        self.audio_poll_id = root.after(AUDIO_DEVICE_POLL_MS, self._poll_audio_devices)
        self._bind_button_sounds()
        root.protocol('WM_DELETE_WINDOW', self.close)
        if self.fullscreen:
            root.attributes('-fullscreen', True)
        elif self.window_resolution:
            root.geometry(self.window_resolution)
        root.bind('<Escape>', self._leave_fullscreen)
        self.style = ttk.Style(root)
        self.image_cache = {}
        resolve_fonts(root)
        self.aqua = root.tk.call('tk', 'windowingsystem') == 'aqua'
        self.scroll_remainders = {}
        self.page_canvases = {}
        for sequence, touchpad in self._wheel_sequences():
            root.bind_all(sequence, lambda event, touchpad=touchpad: self._on_page_wheel(event, touchpad),
                          add='+')
        self._apply_theme()
        self.show_intro()

    def _load_settings(self):
        try:
            settings = json.loads(self.settings_path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            logger.warning('Не удалось прочитать настройки %s: %s', self.settings_path, error)
            return
        if not isinstance(settings, dict):
            logger.warning('Настройки %s должны быть JSON-объектом', self.settings_path)
            return
        self.dark_theme = bool(settings.get('dark_theme', self.dark_theme))
        self.fullscreen = bool(settings.get('fullscreen', self.fullscreen))
        self.sound_enabled = bool(settings.get('sound_enabled', self.sound_enabled))
        try:
            self.sound_volume = max(0.0, min(1.0, float(settings.get('sound_volume', self.sound_volume))))
        except (TypeError, ValueError):
            pass
        audio_device = settings.get('audio_device')
        self.audio_device = audio_device if isinstance(audio_device, str) and audio_device else None
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
            'audio_device': self.audio_device,
        }
        try:
            self.settings_path.write_text(
                json.dumps(settings, ensure_ascii=False, indent=2), encoding='utf-8'
            )
        except OSError as error:
            logger.warning('Не удалось сохранить настройки в %s: %s', self.settings_path, error)

    def _bind_button_sounds(self):
        for binding_tag in ('TButton', 'Button', 'TCheckbutton', 'Checkbutton'):
            self.root.bind_class(
                binding_tag, '<ButtonPress-1>', self._play_button_sound, add='+',
            )

    def _play_button_sound(self, event=None):
        widget = getattr(event, 'widget', None)
        try:
            disabled = (widget.instate(['disabled']) if hasattr(widget, 'instate')
                        else str(widget.cget('state')) == 'disabled')
        except (AttributeError, tk.TclError):
            disabled = False
        if not disabled:
            self.audio.play_effect('button_click')

    def _show_error(self, *args, **kwargs):
        self.audio.play_effect('error')
        return messagebox.showerror(*args, **kwargs)

    def _activate_menu_tile(self, command):
        self.audio.play_effect('button_click')
        command()

    def close(self):
        self.root.after_cancel(self.audio_poll_id)
        self.audio.close()
        self.root.destroy()

    def _cancel_after(self, attribute):
        """Cancel the timer whose id is stored in `attribute`, if there is one."""
        after_id = getattr(self, attribute, None)
        if after_id is not None:
            self.root.after_cancel(after_id)
            setattr(self, attribute, None)

    def clear(self):
        self.generation_active = False
        self.current_spin_finish = None
        for attribute in ('spin_after_id', 'intro_after_id', 'intro_manual_pause_id', 'fight_flash_after_id'):
            self._cancel_after(attribute)
        self.page_canvases.clear()
        self.scroll_remainders.clear()
        for child in self.root.winfo_children():
            child.destroy()
        self.root.after_idle(self._apply_theme)

    def _apply_theme(self):
        if not self.root.winfo_exists():
            return
        if 'clam' in self.style.theme_names():
            self.style.theme_use('clam')
        theme = 0 if self.dark_theme else 1
        colors = {name: pair[theme] for name, pair in THEME_COLORS.items()}
        self.ui_colors = colors
        self.root.configure(background=colors['background'])
        style = self.style
        # Defaults for every ttk widget: warm colours and carved, bevelled edges.
        style.configure('.', background=colors['background'], foreground=colors['foreground'],
                        bordercolor=colors['border'], lightcolor=colors['bevel_light'],
                        darkcolor=colors['bevel_dark'], troughcolor=colors['input'],
                        fieldbackground=colors['input'], selectbackground=colors['accent'],
                        selectforeground=colors['on_accent'], insertcolor=colors['foreground'],
                        arrowcolor=colors['gold_text'])
        style.configure('TFrame', background=colors['background'])
        style.configure('TLabel', background=colors['background'], foreground=colors['foreground'])
        style.configure('TButton', background=colors['surface'], foreground=colors['foreground'],
                        bordercolor=colors['frame_border'], padding=(12, 9), font=(TEXT_FONT, 10))
        style.map('TButton', background=[('disabled', colors['background']), ('pressed', colors['accent']),
                                         ('active', colors['accent_hover'])],
                  foreground=[('disabled', colors['muted']), ('active', colors['on_accent'])])
        for name, background, hover, text in (
            ('Primary.TButton', colors['accent'], colors['accent_hover'], colors['on_accent']),
            ('Skip.TButton', colors['skip'], colors['skip_hover'], colors['on_accent']),
        ):
            style.configure(name, background=background, foreground=text, bordercolor=colors['title'],
                            padding=(16, 10), font=(TEXT_FONT, 10, 'bold'))
            style.map(name, background=[('disabled', colors['surface']), ('pressed', hover), ('active', hover)],
                      foreground=[('disabled', colors['muted']), ('!disabled', text)])
        style.configure('Heading.TLabel', font=(TITLE_FONT, 22), foreground=colors['title'])
        style.configure('Section.TLabel', font=(TITLE_FONT, 12), foreground=colors['title'])
        style.configure('Muted.TLabel', foreground=colors['muted'])
        style.configure('LadderCount.TLabel', background=colors['surface'], foreground=colors['muted'],
                        padding=(12, 10), font=(TEXT_FONT, 10, 'bold'))
        style.configure('Creation.Horizontal.TProgressbar', background=colors['accent'],
                        bordercolor=colors['frame_border'], lightcolor=colors['accent_hover'],
                        darkcolor=colors['accent'], thickness=10)
        style.configure('TEntry', foreground=colors['foreground'], bordercolor=colors['frame_border'], padding=7)
        style.map('TEntry', bordercolor=[('focus', colors['title'])])
        style.configure('TCombobox', foreground=colors['foreground'], background=colors['surface'],
                        bordercolor=colors['frame_border'])
        style.map('TCombobox', fieldbackground=[('readonly', colors['input'])],
                  foreground=[('readonly', colors['foreground'])], background=[('active', colors['hover'])])
        self.root.option_add('*TCombobox*Listbox.background', colors['input'])
        self.root.option_add('*TCombobox*Listbox.foreground', colors['foreground'])
        self.root.option_add('*TCombobox*Listbox.selectBackground', colors['accent'])
        self.root.option_add('*TCombobox*Listbox.selectForeground', colors['on_accent'])
        style.configure('TCheckbutton', background=colors['background'], foreground=colors['foreground'],
                        indicatorbackground=colors['input'], indicatorforeground=colors['title'],
                        upperbordercolor=colors['frame_border'], lowerbordercolor=colors['frame_border'])
        style.map('TCheckbutton', background=[('active', colors['background'])],
                  foreground=[('active', colors['title'])])
        style.configure('Treeview', background=colors['surface'], fieldbackground=colors['surface'],
                        foreground=colors['foreground'], rowheight=32, borderwidth=0, font=(TEXT_FONT, 10))
        style.configure('Treeview.Heading', background=colors['input'], foreground=colors['gold_text'],
                        font=(TEXT_FONT, 10, 'bold'), padding=8)
        style.map('Treeview.Heading', background=[('active', colors['border'])])
        style.map('Treeview', background=[('selected', colors['accent'])],
                  foreground=[('selected', colors['on_accent'])])
        style.configure('TLabelframe', background=colors['background'], bordercolor=colors['frame_border'],
                        relief='solid', borderwidth=1)
        style.configure('TLabelframe.Label', background=colors['background'], foreground=colors['title'],
                        font=(TITLE_FONT, 11))
        style.configure('TNotebook', background=colors['background'], borderwidth=0,
                        bordercolor=colors['frame_border'])
        style.configure('TNotebook.Tab', background=colors['input'], foreground=colors['muted'],
                        bordercolor=colors['frame_border'], padding=(12, 5), font=(TEXT_FONT, 10))
        style.map('TNotebook.Tab', background=[('selected', colors['surface'])],
                  foreground=[('selected', colors['title'])])
        style.configure('TScrollbar', background=colors['border'], troughcolor=colors['background'],
                        bordercolor=colors['frame_border'], gripcount=0)
        style.map('TScrollbar', background=[('active', colors['hover'])])
        style.configure('Horizontal.TScale', background=colors['accent'], troughcolor=colors['input'],
                        bordercolor=colors['frame_border'], lightcolor=colors['accent_hover'],
                        darkcolor=colors['accent'])

        def recolor(widget):
            # Canvases and widgets marked keep_colors (the chronicle's parchment) keep their own colours.
            if isinstance(widget, (tk.Text, tk.Listbox)) and not getattr(widget, 'keep_colors', False):
                widget.configure(bg=colors['input'], fg=colors['foreground'],
                                 selectbackground=colors['accent'], selectforeground=colors['on_accent'],
                                 highlightbackground=colors['background'],
                                 highlightcolor=colors['accent'])
                if isinstance(widget, tk.Text):
                    widget.configure(insertbackground=colors['foreground'])
            for child in widget.winfo_children():
                recolor(child)

        recolor(self.root)

    def _toggle_dark_theme(self):
        self.dark_theme = self.dark_theme_var.get()
        self._apply_theme()
        self._update_audio_status()
        self._save_settings()

    def _set_page_geometry(self, geometry):
        self.page_geometry = geometry
        self._apply_window_geometry()

    def _apply_window_geometry(self):
        if self.fullscreen:
            return
        geometry = self.window_resolution or self.page_geometry
        width, height = (int(value) for value in geometry.split('x'))
        left, top, right, bottom = screen_work_area(self.root)
        # Centre the window, title bar included, on the part of the screen the taskbar leaves free.
        x = max(left, left + (right - left - width) // 2)
        y = max(top, top + (bottom - top - title_bar_height(self.root) - height) // 2)
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

    def _scale_page(self, reference_width, reference_height):
        """Size the window for a page designed at the reference size; return the scale."""
        page_scale = self._automatic_page_scale(reference_width, reference_height)
        self._set_page_geometry(f'{int(reference_width * page_scale)}x{int(reference_height * page_scale)}')
        return page_scale

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
        ttk.Label(parent, text=text, style='Heading.TLabel').pack(anchor='w', pady=(0, 14))

    def _scrollable_page(self, page_scale):
        """The page frame; on small screens it sits in a vertically scrollable canvas."""
        if page_scale >= 0.95:
            frame = ttk.Frame(self.root, padding=18)
            frame.pack(fill='both', expand=True)
            return frame
        page = ttk.Frame(self.root)
        page.pack(fill='both', expand=True)
        page_canvas = tk.Canvas(page, highlightthickness=0, background=self.ui_colors['background'])
        self._attach_scrollbar(page_canvas)
        self.page_canvases[str(page_canvas)] = page_canvas
        frame = ttk.Frame(page_canvas, padding=18)
        page_window = page_canvas.create_window((0, 0), window=frame, anchor='nw')
        frame.bind('<Configure>', lambda _event: page_canvas.configure(
            scrollregion=page_canvas.bbox('all')))
        page_canvas.bind('<Configure>', lambda event: page_canvas.itemconfigure(
            page_window, width=event.width))
        return frame

    @staticmethod
    def _attach_scrollbar(widget):
        """Pack `widget` to fill its parent, with a vertical scrollbar on the right."""
        scrollbar = ttk.Scrollbar(widget.master, orient='vertical', command=widget.yview)
        widget.configure(yscrollcommand=scrollbar.set)
        widget.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

    def _name_table(self, parent, heading, height):
        """A one-column, scrollable list of character names."""
        table = ttk.Treeview(parent, columns=('name',), show='headings', height=height, selectmode='browse')
        table.heading('name', text=heading)
        table.column('name', anchor='w', width=260)
        self._attach_scrollbar(table)
        return table

    @staticmethod
    def _wheel_sequences(modifier=''):
        """Event sequences of mouse wheels and touchpads, each with its 'touchpad' flag."""
        sequences = [(f'<{modifier}{name}>', False) for name in ('MouseWheel', 'Button-4', 'Button-5')]
        if TOUCHPAD_EVENTS:
            sequences.append((f'<{modifier}TouchpadScroll>', True))
        return sequences

    def _bind_mousewheel(self, widgets, handler, modifier=''):
        """Call handler(event, touchpad) for wheel and touchpad scrolling over the widgets."""
        for widget in widgets:
            for sequence, touchpad in self._wheel_sequences(modifier):
                widget.bind(sequence, lambda event, touchpad=touchpad: handler(event, touchpad))

    def _wheel_motion(self, event, touchpad):
        """A wheel or touchpad event as (kind, dx, dy), kind 'units' or 'pixels'; negative is up/left."""
        if touchpad:  # Tk 8.7+: x and y pixel deltas packed into one number
            return 'pixels', -_signed16(event.delta >> 16), -_signed16(event.delta)
        if getattr(event, 'num', None) in (4, 5):  # X11 wheel buttons in Tk 8.6
            return 'units', 0, WHEEL_UNITS_PER_NOTCH if event.num == 5 else -WHEEL_UNITS_PER_NOTCH
        delta = getattr(event, 'delta', 0) or 0
        if self.aqua and delta % 120:  # Tk 8.6 on macOS: lines, from mice and touchpads alike
            kind, amount = 'pixels', -delta * AQUA_LINE_PIXELS
        else:  # notches of 120; Windows precision touchpads send fractions of a notch
            kind, amount = 'units', -delta / 120 * WHEEL_UNITS_PER_NOTCH
        if getattr(event, 'state', 0) & 0x0001:  # Shift: sideways, also for sideways touchpad swipes
            return kind, amount, 0
        return kind, 0, amount

    def _whole_steps(self, key, amount):
        """Add `amount` to the fraction left from earlier events under `key`; return the whole part."""
        remainder = self.scroll_remainders.get(key, 0.0)
        total = amount + (remainder if remainder * amount > 0 else 0.0)
        steps = int(total)
        self.scroll_remainders[key] = total - steps
        return steps

    def _scroll_view(self, widget, kind, amount, axis='y'):
        """Scroll a Text or Canvas by wheel units or pixels; fractions carry over to later events."""
        if not amount:
            return
        if kind == 'pixels' and isinstance(widget, tk.Canvas):  # Tk 8.6 canvases cannot scroll by pixels
            region = widget.cget('scrollregion').split()
            if len(region) == 4:
                x0, y0, x1, y1 = map(float, region)
                size = y1 - y0 if axis == 'y' else x1 - x0
                view, moveto = (widget.yview, widget.yview_moveto) if axis == 'y' else (
                    widget.xview, widget.xview_moveto)
                if size > 0:
                    moveto(view()[0] + amount / size)
            return
        steps = self._whole_steps((str(widget), axis, kind), amount)
        if steps:
            (widget.yview_scroll if axis == 'y' else widget.xview_scroll)(steps, kind)

    def _on_wheel(self, widget, event, touchpad):
        """Vertical wheel or two-finger scrolling of `widget`."""
        kind, _dx, dy = self._wheel_motion(event, touchpad)
        self._scroll_view(widget, kind, dy)
        return 'break'

    def _on_page_wheel(self, event, touchpad):
        """Scroll a compact page when the wheel is used anywhere over its content."""
        widget = event.widget
        if not isinstance(widget, tk.Misc) or widget.winfo_class() in SELF_SCROLLING_CLASSES:
            return None
        while widget is not None:
            canvas = self.page_canvases.get(str(widget))
            if canvas is not None:
                return self._on_wheel(canvas, event, touchpad)
            widget = widget.master
        return None

    def _render_markdown(self, widget, markdown):
        """Render the common Markdown elements of the lore as a page of a parchment chronicle."""
        ink = PARCHMENT
        widget.tag_configure('h1', font=(TITLE_FONT, 28), foreground=ink['rubric'], justify='center',
                             spacing1=12, spacing3=16)
        widget.tag_configure('h2', font=(TITLE_FONT, 19), foreground=ink['heading'],
                             spacing1=14, spacing3=8)
        widget.tag_configure('h3', font=(TEXT_FONT, 15, 'bold'), foreground=ink['gilt'],
                             spacing1=8, spacing3=5)
        widget.tag_configure('paragraph', font=(TEXT_FONT, 13), spacing1=2, spacing3=10,
                             lmargin1=2, lmargin2=2)
        widget.tag_configure('quote', font=(TEXT_FONT, 13, 'italic'),
                             foreground=ink['faded'], lmargin1=24, lmargin2=24,
                             spacing1=4, spacing3=10)
        widget.tag_configure('list', font=(TEXT_FONT, 13), lmargin1=18, lmargin2=38,
                             spacing1=1, spacing3=4)
        widget.tag_configure('code', font=('Consolas', 10), background=ink['code'],
                             lmargin1=14, lmargin2=14, spacing1=4, spacing3=8)
        widget.tag_configure('bold', font=(TEXT_FONT, 13, 'bold'))
        widget.tag_configure('italic', font=(TEXT_FONT, 13, 'italic'))
        widget.tag_configure('strike', overstrike=True)
        widget.tag_configure('inline_code', font=('Consolas', 10), background=ink['code'])
        widget.tag_configure('link', foreground=ink['rubric'], underline=True)
        widget.tag_configure('rule', foreground=ink['gilt'], justify='center', spacing1=5, spacing3=12)

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
                widget.insert('end', '──────────  ❦  ──────────\n', 'rule')
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
        self._scale_page(900, 720)
        frame = ttk.Frame(self.root, padding=(30, 22))
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text=title, font=(TITLE_FONT, 26), foreground=self.ui_colors['title']).pack(anchor='w')
        ttk.Label(frame, text=subtitle,
                  foreground=self.ui_colors['muted'], font=(TEXT_FONT, 11, 'italic')).pack(
                      anchor='w', pady=(2, 14)
                  )

        # The buttons are packed before the chronicle, so a long text can never push them out of the window.
        controls = ttk.Frame(frame)
        controls.pack(side='bottom', fill='x', pady=(14, 0))
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

        text_area = ttk.Frame(frame)
        text_area.pack(fill='both', expand=True)
        text = tk.Text(
            text_area, wrap='word', padx=44, pady=28, relief='flat', borderwidth=0,
            font=(TEXT_FONT, 13), spacing1=2, spacing3=8, takefocus=True,
            background=PARCHMENT['paper'], foreground=PARCHMENT['ink'],
            insertbackground=PARCHMENT['ink'], selectbackground=PARCHMENT['gilt'],
            highlightthickness=3, highlightbackground=PARCHMENT['gilt'], highlightcolor=PARCHMENT['gilt'],
        )
        text.keep_colors = True  # a parchment scroll in both themes
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
            logger.warning('Не удалось прочитать %s: %s', lore_path, error)
            if isinstance(error, FileNotFoundError):
                reason = 'файла нет в папке игры.'
            elif isinstance(error, UnicodeError):
                reason = 'файл сохранён не в кодировке UTF-8. Пересохраните его в UTF-8.'
            else:
                reason = str(error)
            markdown = f'# Летопись недоступна\n\nНе удалось прочитать `{lore_path.name}`: {reason}'
        self._render_markdown(text, markdown)
        text.configure(state='disabled')
        text.yview_moveto(0)

        self._bind_mousewheel((text,), self._on_intro_mousewheel)
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
            self._cancel_after('intro_after_id')
        else:
            self._schedule_intro_scroll()

    def _pause_intro_for_manual_scroll(self):
        if getattr(self, 'intro_user_paused', True):
            return
        self._cancel_after('intro_after_id')
        self._cancel_after('intro_manual_pause_id')
        self.intro_manual_pause_id = self.root.after(2200, self._resume_intro_after_manual_scroll)

    def _resume_intro_after_manual_scroll(self):
        self.intro_manual_pause_id = None
        self._schedule_intro_scroll()

    def _intro_scrollbar_command(self, *arguments):
        self._pause_intro_for_manual_scroll()
        self.intro_text.yview(*arguments)

    def _on_intro_mousewheel(self, event, touchpad=False):
        self._pause_intro_for_manual_scroll()
        return self._on_wheel(self.intro_text, event, touchpad)

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
        frame = ttk.Frame(self.root, padding=(36, 16))
        frame.pack(fill='both', expand=True)
        # The footer is packed first, so the menu above can never push it out of the window.
        footer = ttk.Frame(frame)
        footer.pack(side='bottom', fill='x', pady=(10, 0))
        footer.columnconfigure((0, 1), weight=1, uniform='footer')
        for index, (text, command, state) in enumerate((
            ('📜 Читать лор', self.show_intro, 'normal'),
            ('🏆 Статистика забегов', self.show_ladder_statistics, 'normal' if ladder_run_files() else 'disabled'),
            ('⚙ Настройки', self.show_options, 'normal'),
            ('🚪 Выйти из игры', self.close, 'normal'),
        )):
            row, column = divmod(index, 2)
            ttk.Button(footer, text=text, command=command, state=state).grid(
                row=row, column=column, sticky='ew',
                padx=(0, 4) if column == 0 else (4, 0), pady=(0, 6) if row == 0 else 0)
        ttk.Label(frame, text='Неудачный забег', font=(TITLE_FONT, 30),
                  foreground=colors['title']).pack()
        ttk.Label(frame, text='───────  ⚜  ───────', foreground=colors['frame_border'],
                  font=(TEXT_FONT, 10)).pack()
        ttk.Label(frame, text='Создай героя, собери команду и узнай, кто победит.',
                  foreground=colors['muted'], font=(TEXT_FONT, 11, 'italic')).pack(pady=(0, 10))
        menu = ttk.Frame(frame)
        menu.pack(fill='both', expand=True)
        entries = (
            ('⚒', 'Генератор героев', 'Создай нового персонажа', self.show_create),
            ('⚜', 'Коллекция', 'Просматривай и прокачивай героев', self.show_characters),
            ('⚔', 'Арена', 'Сравни двух бойцов в сражении', self.show_fight),
            ('♛', 'Турнир', 'Собери ростер и проведи чемпионат', self.show_tournament),
        )
        for emblem, title, description, command in entries:
            tile = tk.Frame(menu, bg=colors['surface'], highlightthickness=1,
                            highlightbackground=colors['frame_border'], padx=14, pady=6, cursor='hand2')
            tile.configure(takefocus=True)
            tile.pack(fill='x', pady=3)
            tile.grid_columnconfigure(1, weight=1)
            emblem_label = tk.Label(tile, text=emblem, bg=colors['surface'], fg=colors['gold_text'],
                                    font=(TEXT_FONT, 20), width=2)
            emblem_label.grid(row=0, column=0, rowspan=2, padx=(0, 12))
            title_label = tk.Label(tile, text=title, bg=colors['surface'], fg=colors['title'],
                                   font=(TITLE_FONT, 15), anchor='w')
            title_label.grid(row=0, column=1, sticky='ew')
            description_label = tk.Label(tile, text=description, bg=colors['surface'], fg=colors['muted'],
                                         font=(TEXT_FONT, 10), anchor='w')
            description_label.grid(row=1, column=1, sticky='ew')
            for widget in (tile, emblem_label, title_label, description_label):
                widget.bind('<Button-1>', lambda _event, action=command: self._activate_menu_tile(action))
                widget.bind('<Return>', lambda _event, action=command: self._activate_menu_tile(action))
                widget.bind('<Enter>', lambda _event, card=tile: card.configure(highlightbackground=colors['title']))
                widget.bind('<Leave>', lambda _event, card=tile: card.configure(
                    highlightbackground=colors['frame_border']))
            tile.bind('<FocusIn>', lambda _event, card=tile: card.configure(
                highlightbackground=colors['title'], highlightthickness=2))
            tile.bind('<FocusOut>', lambda _event, card=tile: card.configure(
                highlightbackground=colors['frame_border'], highlightthickness=1))
        ladder_area = ttk.Frame(menu)
        ladder_area.pack(fill='both', expand=True)
        ladder_actions = ttk.Frame(ladder_area)
        ladder_actions.pack(anchor='center', pady=(12, 0))
        ttk.Button(
            ladder_actions, text='⚔ Забег в ладдер', command=self.show_ladder_picker,
            style='Primary.TButton',
        ).pack(side='left')
        ttk.Label(
            ladder_actions, text=f'Запусков: {ladder_run_count()}', style='LadderCount.TLabel',
        ).pack(side='left', padx=(10, 0))

    def show_ladder_statistics(self):
        self.clear()
        self.audio.play_music(None)
        self._scale_page(900, 650)
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
            font=(TEXT_FONT, 11, 'bold'),
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
        self._attach_scrollbar(table)
        table.tag_configure('victory', foreground=self.ui_colors['victory_text'])
        table.tag_configure('defeat', foreground=self.ui_colors['defeat_text'])

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
        except (OSError, UnicodeError, ValueError) as error:
            self._show_error('Не удалось прочитать выбранного героя', str(error))
            return
        self.audio.play_effect('ladder_start')
        self.show_fight(ladder_mode=True)

    def _advance_ladder_fight(self):
        self.ladder_index += 1
        self.show_fight(ladder_mode=True)

    def _mark_ladder_hero_dead(self):
        try:
            Fight.mark_character_dead(self.ladder_hero_path)
        except (OSError, UnicodeError) as error:
            self._show_error(
                'Не удалось сохранить статус персонажа',
                f'Не удалось отметить {self.ladder_hero_path.stem} как мёртвого:\n{error}',
            )

    def _announce_ladder_defeat(self):
        self.spin_after_id = None
        self.audio.play_effect('ladder_run_loss')
        messagebox.showinfo(
            'Поражение',
            f'{self.ladder_hero_path.stem} проиграл бой с {self.ladder_villains[self.ladder_index].stem}.',
        )
        self.show_home()

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
            write_completed_ladder_run_record(record)
        except (OSError, ValueError) as error:
            self._show_error('Не удалось сохранить историю забега', str(error))

    def _leave_ladder(self):
        self.ladder_run_record = None
        self.show_home()

    def show_options(self):
        self.clear()
        self._set_page_geometry('700x500')
        frame = ttk.Frame(self.root, padding=24)
        frame.pack(fill='both', expand=True)
        ttk.Button(frame, text='← Назад', command=self.show_home).pack(
            anchor='w', pady=(0, 18)
        )
        settings = ttk.Frame(frame)
        settings.pack(expand=True)
        ttk.Label(settings, text='Опции', style='Heading.TLabel').pack(pady=(0, 18))
        # Two columns keep the page within 800x600 even with a long audio status.
        general_column = ttk.Frame(settings)
        general_column.pack(side='left', anchor='n', padx=(0, 12))

        appearance = ttk.LabelFrame(general_column, text='Внешний вид', padding=(18, 12))
        appearance.pack(fill='x', pady=(0, 12))
        self.dark_theme_var = tk.BooleanVar(value=self.dark_theme)
        ttk.Checkbutton(appearance, text='Тёмная тема',
                        variable=self.dark_theme_var, command=self._toggle_dark_theme).pack(anchor='w', pady=4)

        sound_settings = ttk.LabelFrame(settings, text='Звук', padding=(18, 12))
        sound_settings.pack(side='left', anchor='n')
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

        device_header = ttk.Frame(sound_settings)
        device_header.pack(fill='x', pady=(10, 4))
        ttk.Label(device_header, text='Устройство вывода').pack(side='left')
        self.audio_test_button = ttk.Button(
            device_header, text='Проверить', command=self._test_audio,
            state='normal' if self.sound_enabled else 'disabled',
        )
        self.audio_test_button.pack(side='right')
        ttk.Button(device_header, text='Обновить', command=self._refresh_audio_devices).pack(
            side='right', padx=(0, 6)
        )
        self.audio_device_var = tk.StringVar()
        self.audio_device_box = ttk.Combobox(
            sound_settings, textvariable=self.audio_device_var, width=44,
            state='readonly' if self.audio.can_choose_device else 'disabled',
        )
        self.audio_device_box.pack(fill='x')
        self.audio_device_box.bind('<<ComboboxSelected>>', self._change_audio_device)
        self.audio_status_label = ttk.Label(sound_settings, wraplength=360, justify='left')
        self.audio_status_label.pack(anchor='w', pady=(6, 0))
        self._fill_audio_devices(self.audio.list_devices())
        self._update_audio_status()

        display = ttk.LabelFrame(general_column, text='Окно', padding=(18, 12))
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
        state = 'normal' if self.sound_enabled else 'disabled'
        self.sound_volume_scale.configure(state=state)
        self.audio_test_button.configure(state=state)
        self._save_settings()
        self._update_audio_status()

    def _change_sound_volume(self, value):
        self.sound_volume = max(0.0, min(1.0, float(value) / 100))
        self.sound_volume_label_var.set(f'{round(self.sound_volume * 100)}%')
        self.audio.set_volume(self.sound_volume)

    def _fill_audio_devices(self, devices):
        choices = {audio.DEFAULT_DEVICE_LABEL: None}
        choices.update((device, device) for device in devices)
        if self.audio_device is not None and self.audio_device not in devices:
            choices[f'{self.audio_device} (не подключено)'] = self.audio_device
        self.audio_device_choices = choices
        self.audio_device_box.configure(values=list(choices))
        self.audio_device_var.set(next(
            label for label, device in choices.items() if device == self.audio_device
        ))

    def _change_audio_device(self, _event=None):
        self.audio_device = self.audio_device_choices.get(self.audio_device_var.get())
        self.audio.set_device(self.audio_device)
        self._save_settings()
        self._fill_audio_devices(self.audio.list_devices())
        self._update_audio_status()

    def _refresh_audio_devices(self):
        self._fill_audio_devices(self.audio.refresh())
        self._update_audio_status()

    def _test_audio(self):
        # refresh() retries a failed device at once instead of waiting for the backoff.
        self._fill_audio_devices(self.audio.refresh())
        self.audio.play_effect('character_created')
        self._update_audio_status()

    def _update_audio_status(self):
        label = getattr(self, 'audio_status_label', None)
        if label is None or not label.winfo_exists():
            return
        text, level = self.audio.status()
        if level == 'error':
            text += f'\nПодробности — в файле {LOG_PATH.name}.'
        color_names = {'ok': 'muted', 'warning': 'gold_text', 'error': 'defeat_text'}
        label.configure(text=text, foreground=self.ui_colors[color_names[level]])

    def _poll_audio_devices(self):
        if self.audio.check_devices():
            box = getattr(self, 'audio_device_box', None)
            if box is not None and box.winfo_exists():
                self._fill_audio_devices(self.audio.list_devices())
        self._update_audio_status()
        self.audio_poll_id = self.root.after(AUDIO_DEVICE_POLL_MS, self._poll_audio_devices)

    def show_tournament(self):
        self.clear()
        self.audio.play_music('tournament')
        page_scale = self._scale_page(900, 760)
        frame = self._scrollable_page(page_scale)
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
        self.available_table = self._name_table(available_frame, 'Персонаж', table_height)
        for index, path in enumerate(files):
            self.available_table.insert('', 'end', iid=str(index), values=(path.stem,))

        controls = ttk.Frame(tables)
        controls.pack(side='left', fill='y', padx=12)
        ttk.Button(controls, text='Добавить →', command=self.add_to_roster).pack(pady=(32, 6))
        ttk.Button(controls, text='← Убрать', command=self.remove_from_roster).pack(pady=6)
        ttk.Button(controls, text='Очистить ростер', command=self.clear_roster).pack(pady=(12, 6))

        self.roster_table = self._name_table(roster_frame, 'Ростер (0/20)', table_height)

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
            table.tag_configure('leader', background=self.ui_colors['win_fill'],
                                foreground=self.ui_colors['win_text'])
            table.tag_configure('eliminated', background=self.ui_colors['out_fill'],
                                foreground=self.ui_colors['out_text'])
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
        for title, colors in (('Победитель', 'champion'), ('Выбыл', 'eliminated')):
            badge = tk.Label(legend, text=title, bg=self.ui_colors[f'{colors}_fill'],
                             fg=self.ui_colors[f'{colors}_text'],
                             font=(TEXT_FONT, 8, 'bold'), padx=8, pady=3)
            badge.pack(side='left', padx=(6, 0))
        self.bracket_canvas = tk.Canvas(bracket_tab, width=1120, height=390,
                                        highlightthickness=2, background=self.ui_colors['surface'],
                                        cursor='fleur', takefocus=True,
                                        highlightbackground=self.ui_colors['frame_border'],
                                        highlightcolor=self.ui_colors['title'])
        self.bracket_canvas.bind(
            '<ButtonPress-1>', lambda event: self.bracket_canvas.scan_mark(event.x, event.y),
        )
        self.bracket_canvas.bind(
            '<B1-Motion>', lambda event: self.bracket_canvas.scan_dragto(event.x, event.y, gain=1),
        )
        self._bind_mousewheel((self.bracket_canvas,), self._on_bracket_wheel)
        self._bind_mousewheel((self.bracket_canvas,), self._on_bracket_zoom_wheel, modifier='Control-')
        for key in ('Left', 'Right', 'Up', 'Down'):
            self.bracket_canvas.bind(f'<{key}>', self._pan_tournament_bracket_key)
        self.bracket_canvas.bind('<Key-0>', lambda _event: self._fit_tournament_bracket())
        bracket_xscroll = ttk.Scrollbar(bracket_tab, orient='horizontal', command=self.bracket_canvas.xview)
        bracket_yscroll = ttk.Scrollbar(bracket_tab, orient='vertical', command=self.bracket_canvas.yview)
        self.bracket_canvas.configure(xscrollcommand=bracket_xscroll.set, yscrollcommand=bracket_yscroll.set)
        bracket_yscroll.pack(side='right', fill='y')
        bracket_xscroll.pack(side='bottom', fill='x')
        self.bracket_canvas.pack(fill='both', expand=True)
        self.bracket_canvas.bind('<Configure>', self._refit_tournament_bracket)
        self.tournament_tabs.bind('<<NotebookTabChanged>>', self._on_tournament_tab_changed)
        self._draw_tournament_bracket(None)
        result_frame = ttk.Frame(report_tab)
        result_frame.pack(fill='both', expand=True)
        self.tournament_result = tk.Text(result_frame, wrap='word', state='disabled', font=('Consolas', 10))
        self._attach_scrollbar(self.tournament_result)

    def _draw_tournament_bracket(self, bracket):
        canvas = self.bracket_canvas
        self.current_bracket = bracket
        self.bracket_zoom = 1.0
        # Full text, font with its size at zoom 1, and room of every text item; see _scale_tournament_bracket.
        self.bracket_texts = {}
        canvas.delete('all')
        colors = self.ui_colors
        foreground, card, muted = colors['arena_text'], colors['bracket_card'], colors['bracket_muted']
        connector = colors['frame_border']
        champion_fill, champion_text = colors['champion_fill'], colors['champion_text']
        eliminated_fill, eliminated_text = colors['eliminated_fill'], colors['eliminated_text']
        canvas.configure(background=colors['bracket_background'])

        qf_y = (42, 129, 216, 303)
        sf_y = (86, 260)
        final_y = 173
        champion_y = 173
        card_width, card_height = 220, 58

        pixels_per_point = canvas.winfo_fpixels('1p')

        def write(x, y, text, font, width, **options):
            family, points, weight = font
            # Sizes in pixels (negative in Tk) let the zoom scale the text in steps finer than a point.
            pixels = round(points * pixels_per_point)
            font = (family, -pixels, weight)
            item = canvas.create_text(x, y, text=fit_text(text, font, width), font=font, **options)
            self.bracket_texts[item] = (text, family, pixels, weight, width)

        columns = ((20, 'Четвертьфиналы'), (310, 'Полуфиналы'),
                   (600, 'Финал'), (890, 'Победитель'))
        for x, title in columns:
            write(x + 110, 18, title, (TITLE_FONT, 12, 'normal'), card_width, anchor='center', fill=colors['title'])

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
                # The score on the right keeps 40 pixels for itself.
                write(x + 10, line_y, name, (TEXT_FONT, 9, 'bold' if is_winner or is_eliminated else 'normal'),
                      card_width - 60, anchor='w',
                      fill=champion_text if is_winner else eliminated_text if is_eliminated else foreground)
                write(x + card_width - 10, line_y, str(score), (TEXT_FONT, 9, 'bold'), 40, anchor='e', fill=muted)

        for y, match in zip(qf_y, quarterfinals):
            draw_match(20, y, match)
        for y, match in zip(sf_y, semifinals):
            draw_match(310, y, match)
        draw_match(600, final_y, bracket['final'] if bracket else None)
        final_match = bracket['final'] if bracket else None
        champion = final_match['winner'] if final_match else 'Победитель турнира'
        canvas.create_rectangle(890, champion_y, 1110, champion_y + card_height,
                                fill=champion_fill, outline=colors['title'], width=2)
        write(1000, champion_y - 16, '♛', (TEXT_FONT, 20, 'normal'), card_width, fill=colors['title'])
        write(1000, champion_y + card_height / 2, champion, (TEXT_FONT, 10, 'bold'), card_width - 20,
              fill=champion_text)
        self._fit_tournament_bracket()

    def _on_tournament_tab_changed(self, _event=None):
        selected_tab = self.tournament_tabs.index('current')
        stage_names = ('Плей-офф', 'Групповой этап', 'Отчёт')
        if hasattr(self, 'tournament_stage_label'):
            self.tournament_stage_label.configure(text=stage_names[selected_tab])
        if selected_tab == 0:
            self.root.after_idle(self._refit_tournament_bracket)

    def _fit_tournament_bracket(self):
        """«Вписать в окно»: fit the bracket to its view and keep it fitted while the window changes size."""
        self.bracket_auto_fit = True
        self._refit_tournament_bracket()

    def _refit_tournament_bracket(self, _event=None):
        """Fit the bracket to its view again, unless the player has zoomed it by hand."""
        if not hasattr(self, 'bracket_canvas') or not self.bracket_canvas.winfo_exists():
            return
        canvas = self.bracket_canvas
        bounds = canvas.bbox('all')
        # Until the page is laid out the canvas is 1x1; its first <Configure> calls this again.
        if not bounds or canvas.winfo_width() <= 1 or self.tournament_tabs.index('current') != 0:
            return
        if not getattr(self, 'bracket_auto_fit', False):
            self._update_bracket_scrollregion()
            return
        view_width, view_height = self._bracket_view_size()
        base_width = (bounds[2] - bounds[0]) / self.bracket_zoom
        base_height = (bounds[3] - bounds[1]) / self.bracket_zoom
        low, high = BRACKET_ZOOM_LIMITS
        target_zoom = max(low, min(high, (view_width - 4) / base_width, (view_height - 4) / base_height))
        self._scale_tournament_bracket(0, 0, target_zoom / self.bracket_zoom)
        canvas.xview_moveto(0)
        canvas.yview_moveto(0)

    def _bracket_view_size(self):
        """Width and height of the visible part of the bracket canvas, inside its border."""
        canvas = self.bracket_canvas
        border = 2 * int(canvas['highlightthickness'])
        return max(1, canvas.winfo_width() - border), max(1, canvas.winfo_height() - border)

    def _update_bracket_scrollregion(self):
        """Let the view scroll over the whole bracket; a bracket smaller than the view sits in its middle."""
        canvas = self.bracket_canvas
        bounds = canvas.bbox('all')
        if not bounds:
            return
        left, top, right, bottom = bounds
        view_width, view_height = self._bracket_view_size()
        spare_x = max(0, view_width - (right - left)) / 2
        spare_y = max(0, view_height - (bottom - top)) / 2
        canvas.configure(scrollregion=(left - spare_x, top - spare_y, right + spare_x, bottom + spare_y))

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
        low, high = BRACKET_ZOOM_LIMITS
        if not low <= self.bracket_zoom * factor <= high:
            return
        self.bracket_auto_fit = False
        canvas = self.bracket_canvas
        anchor_x = canvas.canvasx(max(1, canvas.winfo_width()) / 2)
        anchor_y = canvas.canvasy(max(1, canvas.winfo_height()) / 2)
        self._scale_tournament_bracket(anchor_x, anchor_y, factor)

    def _scale_tournament_bracket(self, x, y, factor):
        """Scale the bracket around (x, y). Tk scales only shapes, so the text is resized here too."""
        canvas = self.bracket_canvas
        canvas.scale('all', x, y, factor, factor)
        self.bracket_zoom *= factor
        for item, (text, family, pixels, weight, width) in self.bracket_texts.items():
            # Rounded down, a text never outgrows its card, so a name that fits once fits at every zoom.
            font = (family, -max(1, math.floor(pixels * self.bracket_zoom + 1e-6)), weight)
            # Tiny fonts still come out wider than their share, so the text is fitted again.
            canvas.itemconfigure(item, font=font, text=fit_text(text, font, width * self.bracket_zoom))
        self._update_bracket_scrollregion()

    def _on_bracket_wheel(self, event, touchpad):
        """The wheel and two-finger scrolling pan the bracket; Shift pans sideways."""
        kind, dx, dy = self._wheel_motion(event, touchpad)
        self._scroll_view(self.bracket_canvas, kind, dx, 'x')
        self._scroll_view(self.bracket_canvas, kind, dy, 'y')
        return 'break'

    def _on_bracket_zoom_wheel(self, event, touchpad):
        """Ctrl + wheel zooms one step per notch; a touchpad zooms one step per notch of travel."""
        kind, _dx, dy = self._wheel_motion(event, touchpad)
        steps = self._whole_steps('zoom', dy / (WHEEL_UNITS_PER_NOTCH if kind == 'units' else NOTCH_PIXELS))
        for _ in range(abs(steps)):
            self._zoom_tournament_bracket(1.12 if steps < 0 else 0.89)
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
        page_scale = self._scale_page(900, 760)
        frame = self._scrollable_page(page_scale)
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
            # The fighters keep the width of their cards; the arena between them takes what is left,
            # so a narrow window shrinks its history table instead of cutting off the second fighter.
            left.grid(row=0, column=0, sticky='ns', padx=(0, 8))
            center.grid(row=0, column=1, sticky='nsew')
            right.grid(row=0, column=2, sticky='ns', padx=(8, 0))
            row.columnconfigure(1, weight=1)
        if ladder_mode:
            fighter_name_style = {
                'background': self.ui_colors['surface'],
                'foreground': self.ui_colors['foreground'],
                'font': (TEXT_FONT, 10, 'bold'),
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
        self.fight_flash_after_id = None
        self.fight_flash_index = None
        self.fight_portrait_canvases = []
        self.fight_stat_labels = []
        self.fight_panels = (left, right)
        self.fight_outcome_labels = []
        for panel in (left, right):
            outcome = tk.Label(panel, text='', font=(TEXT_FONT, 10, 'bold'),
                               background=self.ui_colors['arena_fill'],
                               foreground=self.ui_colors['arena_text'])
            outcome.pack(fill='x', pady=(4, 0))
            outcome.pack_forget()
            self.fight_outcome_labels.append(outcome)
            portrait = tk.Canvas(panel, width=130, height=195, highlightthickness=0,
                                 background=self.ui_colors['background'])
            portrait.pack(pady=(6, 0))
            self.fight_portrait_canvases.append(portrait)
            card = tk.Frame(panel, background=self.ui_colors['fight_card'], highlightthickness=1,
                            highlightbackground=self.ui_colors['fight_card_border'])
            card.pack(fill='x', padx=3, pady=(5, 0), anchor='nw')
            self.fight_stat_labels.append(card)
        if not ladder_mode:
            self.first_fighter.bind('<<ComboboxSelected>>', lambda _event: self._on_fight_selection_changed(0))
            self.second_fighter.bind('<<ComboboxSelected>>', lambda _event: self._on_fight_selection_changed(1))
        wheel_size = int(280 * self._wheel_scale(600, 640))
        # Long announcements wrap to the width of the wheel below.
        self.fight_status = ttk.Label(center, text='', anchor='center', justify='center', wraplength=wheel_size)
        self.fight_status.pack(fill='x', pady=(0, 4))
        self.fight_wheel = tk.Canvas(center, width=wheel_size, height=wheel_size,
                                     highlightthickness=0, background=self.ui_colors['background'])
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
        # Narrow starting widths: a treeview stretches its columns to fill a wider window but never shrinks
        # them below these, so wide ones would be cut off in a narrow window.
        for column, title, width in (
            ('round', 'Раунд', 66), ('attribute', 'Параметр', 170),
            ('score', 'Очки + удача', 120), ('winner', 'Победитель', 150),
        ):
            self.fight_history.heading(column, text=title)
            self.fight_history.column(column, width=width, minwidth=60, anchor='center',
                                      stretch=column in ('attribute', 'winner'))
        self.fight_history.pack(fill='x')
        self.fight_button.pack()
        self.fight_history.tag_configure('first-wins', foreground=self.ui_colors['victory_text'])
        self.fight_history.tag_configure('second-wins', foreground=self.ui_colors['defeat_text'])
        self.fight_history.tag_configure('total', font=(TEXT_FONT, 9, 'bold'))
        self._draw_fight_portrait(0)
        self._draw_fight_portrait(1)

    def _on_fight_selection_changed(self, fighter_index):
        self._reset_fight_panels()
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
        properties = self._read_character_properties(character_path)

        stats_card = self.fight_stat_labels[fighter_index]
        for child in stats_card.winfo_children():
            child.destroy()
        card_bg = self.ui_colors['fight_card']
        main_fg = self.ui_colors['fight_card_text']
        muted_fg = self.ui_colors['gold_text']
        tk.Label(stats_card, text='ХАРАКТЕРИСТИКИ',
                 font=(TITLE_FONT, 10), bg=card_bg, fg=muted_fg,
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
            ('Способность', 'ability'), ('Титул', 'title'),
        )
        # Every fighter gets the same rows, columns and row heights, so changing one never shifts the page.
        label_font, value_font = (TEXT_FONT, 9, 'bold'), (TEXT_FONT, 9)
        label_width = max(tkfont.Font(font=label_font).measure(text) for text, _key in stat_fields) + 6
        value_width = tkfont.Font(font=value_font).measure('0') * FIGHT_CARD_VALUE_CHARS
        for label_text, key in stat_fields:
            value = properties.get(key, '').strip()
            if not value or value.casefold() == 'none':
                value = '—'
            lines = 2 if key in FIGHT_CARD_TWO_LINE_STATS else 1
            row = tk.Frame(
                stats_card, bg=card_bg, padx=7, pady=4, highlightthickness=1,
                highlightbackground=self.ui_colors['border'],
            )
            row.pack(fill='x', padx=3, pady=2)
            row.grid_columnconfigure(0, minsize=label_width)
            row.grid_columnconfigure(1, weight=1, minsize=value_width)
            # No inner padding: a label is exactly as wide as its text, so the columns never stretch.
            tk.Label(row, text=label_text, font=label_font, bd=0, padx=0,
                     bg=card_bg, fg=muted_fg, anchor='w').grid(row=0, column=0, sticky='w')
            tk.Label(row, text=value if lines == 2 else fit_text(value, value_font, value_width),
                     font=value_font, bd=0, padx=0, bg=card_bg, fg=main_fg, justify='right', anchor='e',
                     wraplength=value_width, height=lines).grid(row=0, column=1, sticky='e')

        if self.fight_ladder_mode and fighter_index == 1:
            self._draw_ladder_villain_portrait(canvas, fighter_name, properties)
            return

        template = RACE_TEMPLATES.get(properties.get('race', '').casefold())
        if not template:
            canvas.create_text(65, 97, text=fighter_name, width=120, fill=self.ui_colors['portrait_text'])
            return
        background = self._template_image(TEMPLATES_DIR / 'races' / f'{template}.png', 130, 195)
        if background:
            canvas.create_image(65, 97, image=background, anchor='center')
        target_height = (120, 140, 160, 180)[SIZE_TIERS.get(properties.get('size', '').casefold(), 1)]
        character = self._template_image(TEMPLATES_DIR / 'characters' / f'{template}.png', None, target_height)
        if character:
            self._draw_weapon(canvas, properties, *hand_position(template, character, 65, 189),
                              max(16, round(32 * target_height / 140)))
            canvas.create_image(65, 189, image=character, anchor='s')

    def _draw_weapon(self, canvas, properties, hand_x, hand_y, size):
        """Put the weapon picture into the hand; return False when there is no picture for it."""
        template = WEAPON_TEMPLATES.get(properties.get('weapon', '').casefold())
        weapon = template and self._template_image(TEMPLATES_DIR / 'weapons' / f'{template}.png', size, size)
        if not weapon:
            return False
        canvas.create_image(*weapon_origin(template, weapon, hand_x, hand_y), image=weapon, anchor='nw')
        return True

    def _template_image(self, path, max_width=None, max_height=None):
        """A picture shrunk by a whole factor to fit the box, loaded once per session."""
        key = (path, max_width, max_height)
        if key in self.image_cache:
            return self.image_cache[key]
        if not path.is_file():
            return None
        try:
            source = tk.PhotoImage(file=str(path))
        except tk.TclError as error:
            logger.warning('Не удалось загрузить картинку %s: %s', path, error)
            image = None
        else:
            scale = max(1, math.ceil(max(
                source.width() / max_width if max_width else 0,
                source.height() / max_height if max_height else 0,
            )))
            image = source.subsample(scale, scale)
        self.image_cache[key] = image
        return image

    def _draw_ladder_villain_portrait(self, canvas, fighter_name, properties):
        image_reference = properties.get('image', '').strip()
        foreground = self.ui_colors['portrait_text']
        project_root = Path(__file__).resolve().parent
        image_path = (project_root / image_reference).resolve()
        # Only pictures inside the game folder: a villain file must not point anywhere on disk.
        if (image_reference.casefold() in ('', 'none', 'null') or Path(image_reference).is_absolute()
                or not image_path.is_relative_to(project_root)):
            canvas.create_text(65, 97, text=f'{fighter_name}\n\nНет портрета', width=120, fill=foreground)
            return
        image = self._template_image(image_path, 130, 195)
        if image is None:
            canvas.create_text(
                65, 97, text=f'{fighter_name}\n\nПортрет не найден:\n{image_reference}',
                width=120, fill=foreground, font=(TEXT_FONT, 8),
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
        self.fight_totals = (result['first_total'], result['second_total'])
        self.fight_winner_index = result['winner_index']
        self.fight_winner = self.fight_names[self.fight_winner_index]
        self.fight_round_index = 0
        self.fight_rotation = 0
        if not self.fight_ladder_mode:
            self.fight_names = (self.first_fighter.get(), self.second_fighter.get())
        self.fight_history.delete(*self.fight_history.get_children())
        self.fight_status.configure(style='TLabel')
        self._reset_fight_panels()
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
        second_extent = 360 - first_extent
        # The first fighter's half is azure, the second one's gules.
        (first_fill, first_ink), (second_fill, second_ink) = TINCTURES[1], TINCTURES[0]
        canvas.create_arc(*box, start=rotation, extent=first_extent,
                          fill=first_fill, outline=GILT, width=3)
        canvas.create_arc(*box, start=rotation + first_extent, extent=second_extent,
                          fill=second_fill, outline=GILT, width=3)
        for angle, label, ink in ((rotation + first_extent / 2, first_name, first_ink),
                                  (rotation + first_extent + second_extent / 2, second_name, second_ink)):
            radians = math.radians(angle)
            x = cx + math.cos(radians) * radius * 0.56
            y = cy - math.sin(radians) * radius * 0.56
            canvas.create_text(x, y, text=textwrap.fill(label, 16), width=110,
                              font=(TEXT_FONT, 10, 'bold'), fill=ink, justify='center')
        self._draw_wheel_fittings(canvas, cx, cy, radius)

    def _fight_card_default_colors(self):
        """Background, border and row border of a fighter's stats card at rest."""
        return self.ui_colors['fight_card'], self.ui_colors['fight_card_border'], self.ui_colors['border']

    def _paint_fight_card(self, index, background, border, row_border):
        stats_card = self.fight_stat_labels[index]
        stats_card.configure(background=background, highlightbackground=border)
        for row in stats_card.winfo_children():
            row.configure(background=background)
            if isinstance(row, tk.Frame):
                row.configure(highlightbackground=row_border)
                for label in row.winfo_children():
                    label.configure(background=background)

    def _reset_fight_panels(self):
        for index, (panel, outcome, portrait) in enumerate(zip(
            self.fight_panels, self.fight_outcome_labels, self.fight_portrait_canvases,
        )):
            outcome.pack_forget()
            panel.configure(style='TLabelframe')
            self._paint_fight_card(index, *self._fight_card_default_colors())
            portrait.configure(highlightthickness=0)

    def _flash_round_loser(self, loser_index):
        """Make the round loser's card blush red for a moment, as if they took a hit."""
        self._end_round_flash()
        portrait = self.fight_portrait_canvases[loser_index]
        width, height = int(portrait['width']), int(portrait['height'])
        # Drawn inside the canvas: a highlight border would shift the layout on every hit.
        portrait.create_rectangle(1, 1, width - 1, height - 1, fill=LOSER_COLOR, stipple='gray50',
                                  outline=LOSER_COLOR, width=3, tags=('hit',))
        self._paint_fight_card(loser_index, self.ui_colors['lose_fill'], LOSER_COLOR, LOSER_COLOR)
        self.fight_flash_index = loser_index
        self.fight_flash_after_id = self.root.after(FIGHT_HIT_FLASH_MS, self._end_round_flash)

    def _end_round_flash(self):
        self._cancel_after('fight_flash_after_id')
        index, self.fight_flash_index = self.fight_flash_index, None
        if index is None or not self.fight_portrait_canvases[index].winfo_exists():
            return
        self.fight_portrait_canvases[index].delete('hit')
        self._paint_fight_card(index, *self._fight_card_default_colors())

    @staticmethod
    def _round_score_text(comparison):
        return (f"{comparison['first_points']}+{comparison['first_luck']} : "
                f"{comparison['second_points']}+{comparison['second_luck']}")

    @staticmethod
    def _winner_text(winner, first_total, second_total):
        return f'{winner} (жребий)' if first_total == second_total else winner

    def _spin_fight_round(self):
        if self.fight_round_index >= len(self.fight_rounds):
            self._end_round_flash()
            self._draw_fight_portrait(0)
            self._draw_fight_portrait(1)
            last_comparison = self.fight_rounds[-1]
            self._draw_fight_wheel(
                *self.fight_names,
                self.fight_rotation,
                last_comparison['first_total'],
                last_comparison['second_total'],
            )
            self.fight_status.configure(text='Сражение завершено')
            winner = self.fight_winner
            winner_index = self.fight_winner_index
            first_total, second_total = self.fight_totals
            total_item = self.fight_history.insert(
                '', 'end', tags=('first-wins' if winner_index == 0 else 'second-wins', 'total'),
                values=('Итог', 'Сумма раундов', f'{first_total} : {second_total}',
                        self._winner_text(winner, first_total, second_total)),
            )
            self.fight_history.see(total_item)
            colors = self.ui_colors
            for index, (panel, outcome, portrait) in enumerate(zip(
                self.fight_panels, self.fight_outcome_labels, self.fight_portrait_canvases,
            )):
                is_winner = index == winner_index
                color = WINNER_COLOR if is_winner else LOSER_COLOR
                background = colors['win_fill'] if is_winner else colors['lose_fill']
                foreground = colors['win_text'] if is_winner else colors['lose_text']
                style_name = f'Fight.{"Winner" if is_winner else "Loser"}.TLabelframe'
                self.style.configure(style_name, bordercolor=color, background=background)
                self.style.configure(f'{style_name}.Label', foreground=foreground, background=background)
                panel.configure(style=style_name)
                outcome.configure(
                    text='ПОБЕДИТЕЛЬ' if is_winner else 'ПРОИГРАВШИЙ',
                    background=background, foreground=foreground,
                )
                outcome.pack(fill='x', pady=(4, 0))
                self._paint_fight_card(index, background, color, color)
                portrait.configure(highlightthickness=3, highlightbackground=color)
            self.style.configure('FightWinner.TLabel', background=colors['win_fill'],
                                 foreground=colors['win_text'], font=(TITLE_FONT, 15),
                                 padding=(10, 8))
            self.fight_status.configure(text=f'✦ ПОБЕДИТЕЛЬ: {winner} ✦', style='FightWinner.TLabel')
            if self.fight_ladder_mode:
                if winner_index == 1:
                    # The lost fight is heard at once; the run-level cue comes with the dialog.
                    self.audio.play_effect('ladder_battle_loss')
                    self._mark_ladder_hero_dead()
                    self._save_ladder_run_progress(fight_result='Поражение', final_result='Поражение')
                    self.spin_after_id = self.root.after(LADDER_DEFEAT_PAUSE_MS, self._announce_ladder_defeat)
                    return
                if self.ladder_index + 1 < len(self.ladder_villains):
                    self.audio.play_effect('ladder_battle_win')
                    self._save_ladder_run_progress(fight_result='Победа')
                    next_villain = self.ladder_villains[self.ladder_index + 1].stem
                    self.fight_status.configure(text=f'ПОБЕДА! Следующий соперник: {next_villain}')
                    self.fight_button.configure(
                        text='Следующий бой', command=self._advance_ladder_fight, state='normal',
                    )
                    return
                self.audio.play_effect('ladder_run_win')
                self._save_ladder_run_progress(fight_result='Победа', final_result='Победа')
                messagebox.showinfo(
                    'Поздравляем с победой!',
                    f'{self.ladder_hero_path.stem} одолел всех {len(self.ladder_villains)} '
                    'противников и прошёл ладдер!\n\n'
                    'Теперь откроется последняя глава хроник.',
                )
                self.show_ending_lore()
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
        first_points = max(0, comparison['first_total'])
        second_points = max(0, comparison['second_total'])
        total_points = first_points + second_points
        first_extent = 180 if total_points == 0 else 360 * first_points / total_points
        winner_midpoint = first_extent / 2 if winner_index == 0 else first_extent + (360 - first_extent) / 2
        start_rotation = self.fight_rotation
        target = (90 - winner_midpoint) % 360
        rotation_delta = (target - start_rotation % 360) % 360 + random.randint(4, 6) * 360
        frames = 75
        frame_index = 0
        self.fight_status.configure(
            text=f"{comparison['attribute']}: {self._round_score_text(comparison)}",
        )

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
            winner_text = self._winner_text(
                comparison['winner'], comparison['first_total'], comparison['second_total'],
            )
            self.fight_status.configure(text=f"{comparison['attribute']}: {winner_text}")
            row_tag = 'first-wins' if comparison['winner_index'] == 0 else 'second-wins'
            round_item = self.fight_history.insert('', 'end', tags=(row_tag,), values=(
                self.fight_round_index + 1, comparison['attribute'],
                self._round_score_text(comparison), winner_text,
            ))
            self.fight_history.see(round_item)
            self._flash_round_loser(1 - winner_index)
            self.audio.play_effect('round_win' if winner_index == 0 else 'round_loss')
            self.fight_round_index += 1
            self.spin_after_id = self.root.after(550, self._spin_fight_round)

        animate()

    def show_create(self):
        self.clear()
        self.audio.play_music(None)
        self._scale_page(920, 850)
        # Every hero name is unique in this world; taken ones are read when the page opens.
        self.existing_hero_names = {
            self._hero_name_key(path.stem) for path in CHARACTERS_DIR.glob('*.txt')
        }
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
        self.wheel_selection = ttk.Label(wheel_panel, text='', anchor='center', font=(TEXT_FONT, 11, 'bold'))
        self.wheel_selection.pack(fill='x', pady=(0, 5))
        wheel_size = int(390 * self._wheel_scale(920, 850))
        self.wheel_canvas = tk.Canvas(
            wheel_panel, width=wheel_size, height=wheel_size, highlightthickness=0,
            background=self.ui_colors['background'],
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
            bg=self.ui_colors['surface'], fg=self.ui_colors['title'],
            font=(TITLE_FONT, 13), wraplength=210, anchor='w', justify='left',
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
                     foreground=self.ui_colors['muted'], font=(TEXT_FONT, 9, 'bold')).grid(
                         row=0, column=0, sticky='w', padx=(0, 6))
            value_label = tk.Label(row, text='—', anchor='e', justify='right',
                                   background=self.ui_colors['surface'], foreground=self.ui_colors['foreground'],
                                   font=(TEXT_FONT, 9, 'bold'), wraplength=125)
            value_label.grid(row=0, column=1, sticky='e')
            self.create_summary_rows[key] = value_label
        self.name_entry.focus_set()

    def _update_creation_summary(self):
        hero = self.current_hero
        self.create_summary_name.configure(text=hero.name)
        values = {key: getattr(hero, key, None) for key in self.create_summary_rows}
        values['race_line'] = ' '.join(filter(None, (
            getattr(hero, 'subrace', None), getattr(hero, 'race', None),
        )))
        for key, widget in self.create_summary_rows.items():
            value = values[key]
            widget.configure(text=str(value) if value not in (None, '') else '—')

    def _update_creation_progress(self):
        total = max(1, len(self.wheel_steps))
        completed = min(self.spin_index, total)
        self.create_progress.configure(maximum=total, value=completed)
        if completed >= total:
            text = 'Генерация завершена'
        else:
            text = f'Шаг {completed + 1} из {total}  ·  {self.wheel_steps[self.spin_index][0]}'
        self.create_progress_label.configure(text=text)

    @staticmethod
    def _wheel_step(hero, label, attribute, options, weights, display=str):
        """A wheel step that stores the picked value in the hero's attribute."""
        return (label, options, weights, lambda value: setattr(hero, attribute, value), display)

    def _skip_empty_steps(self):
        # Weapon mastery and ability power only become real steps for some heroes.
        while self.spin_index < len(self.wheel_steps) and self.wheel_steps[self.spin_index] is None:
            self.spin_index += 1

    def _make_wheel_steps(self, hero):
        def simple_step(label, attribute, options, weights):
            return self._wheel_step(hero, label, attribute, options, weights)

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
        steps.append(self._wheel_step(
            hero, 'Влияние хаоса', 'chaos', chaos_options, [no_chaos_weight] + data.chaos_weights,
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
        weights = list(weights) if weights is not None else [1] * len(options)
        total_weight = sum(weights)
        angle_before = 0.0
        for index, (option, weight) in enumerate(zip(options, weights)):
            segment = 360 * weight / total_weight
            start = (rotation + angle_before) % 360
            fill, ink = TINCTURES[index % len(TINCTURES)]
            canvas.create_arc(center_x-radius, center_y-radius, center_x+radius, center_y+radius,
                              start=start, extent=segment, fill=fill, outline=GILT, width=2)
            middle = math.radians(start + segment / 2)
            label_radius = radius * 0.66
            x = center_x + math.cos(middle) * label_radius
            y = center_y - math.sin(middle) * label_radius
            label = textwrap.fill(str(option), width=17)
            canvas.create_text(x, y, text=label, width=105, font=(TEXT_FONT, 8, 'bold'),
                               fill=ink, justify='center')
            angle_before += segment
        self._draw_wheel_fittings(canvas, center_x, center_y, radius)

    @staticmethod
    def _draw_wheel_fittings(canvas, x, y, radius):
        """The oak rim, the hub and the pointer at the top, the same on every wheel."""
        canvas.create_oval(x - radius - 4, y - radius - 4, x + radius + 4, y + radius + 4, outline=WOOD, width=7)
        canvas.create_oval(x - radius - 8, y - radius - 8, x + radius + 8, y + radius + 8, outline=GILT, width=2)
        canvas.create_oval(x - 24, y - 24, x + 24, y + 24, fill=WOOD, outline=GILT, width=3)
        canvas.create_oval(x - 9, y - 9, x + 9, y + 9, fill=GILT, outline='')
        canvas.create_polygon(x - 17, y - radius - 24, x + 17, y - radius - 24, x, y - radius + 6,
                              fill=WOOD, outline=GILT, width=2)
        canvas.create_polygon(x - 10, y - radius - 19, x + 10, y - radius - 19, x, y - radius,
                              fill=GILT, outline='')

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
        self._skip_empty_steps()
        self._update_creation_progress()
        if self.spin_index >= len(self.wheel_steps):
            self._update_creation_summary()
            self.current_hero.created_at = datetime.now().astimezone().isoformat(timespec='seconds')
            try:
                main.file_creation(self.current_hero)
            except OSError as error:
                self._show_error('Ошибка сохранения', str(error))
                self.generation_active = False
                self.generate_button.configure(state='normal')
                return
            self.existing_hero_names.add(self._hero_name_key(self.current_hero.name))
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
        last_pointer_index = self._wheel_index_at_pointer(weights, start_rotation)

        finished = False

        def finish_spin():
            nonlocal finished
            if finished:
                return
            finished = True
            self._cancel_after('spin_after_id')
            self.current_spin_finish = None
            self.skip_spin_button.configure(state='disabled')
            self._draw_wheel(wheel_options, desired_rotation, weights)
            self.wheel_selection.configure(text=f'{label}: {selected_text}')
            assign(selected)
            self._update_creation_summary()
            self.wheel_rotation = desired_rotation
            self.wheel_status.configure(text=f'Выпало: {label} - {selected_text}')
            self.audio.play_effect('wheel_stop')
            hero = self.current_hero
            if self.spin_index == 7 and selected != data.weapon_sum[0]:
                self.wheel_steps[8] = self._wheel_step(
                    hero, 'Владение оружием', 'weapon_mastery',
                    data.weapon_mastery_sum, data.weapon_mastery_weights,
                )
                self.wheel_steps[9] = self._wheel_step(
                    hero, 'Зачарование оружия', 'weapon_enchantment',
                    data.weapon_enchantment_sum, data.weapon_enchantment_weights,
                )
            if self.spin_index == 10 and selected != data.ability_sum[0]:
                self.wheel_steps[11] = self._wheel_step(
                    hero, 'Мощь способности', 'ability_power',
                    data.ability_power_sum, data.ability_power_weights,
                )
            self.spin_index += 1
            self._skip_empty_steps()
            self._update_creation_progress()
            self.spin_after_id = self.root.after(700, self._spin_next)

        self.current_spin_finish = finish_spin

        def animate():
            nonlocal last_pointer_index
            self.spin_after_id = None
            self.spin_frame += 1
            progress = min(self.spin_frame / total_frames, 1.0)
            eased = 1 - (1 - progress) ** 3
            rotation = start_rotation + rotation_delta * eased
            self._draw_wheel(wheel_options, rotation, weights)
            pointer_index = self._wheel_index_at_pointer(weights, rotation)
            if pointer_index != last_pointer_index and progress < 1.0:
                self.audio.play_effect('wheel_tick')
            last_pointer_index = pointer_index
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
    def _hero_name_key(name):
        """Compare names the way people read them: case and repeated spaces do not matter."""
        return ' '.join(name.split()).casefold()

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
                hero = main.character(name)
        except (OSError, ValueError) as error:
            self._show_error('Ошибка', str(error))
            return
        if self._hero_name_key(hero.name) in self.existing_hero_names:
            messagebox.showwarning(
                'Имя занято',
                'Такой герой уже есть, в нашем мире не существует людей '
                'с одним и тем же именем, господин.',
            )
            self.name_entry.focus_set()
            self.name_entry.select_range(0, 'end')
            return
        self.current_hero = hero
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
        self._scale_page(960, 760)
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
        self.character_sort_var = tk.StringVar(value=next(iter(COLLECTION_SORTS)))
        sort_box = ttk.Combobox(controls, state='readonly', textvariable=self.character_sort_var,
                                values=tuple(COLLECTION_SORTS), width=28)
        sort_box.pack(fill='x', pady=(0, 5))
        self.character_status_var = tk.StringVar(value=self._default_status_filter())
        if not ladder_selection:
            status_box = ttk.Combobox(
                controls, state='readonly', textvariable=self.character_status_var,
                values=('Все', 'Живые', 'Мёртвые'),
            )
            status_box.pack(fill='x', pady=(0, 5))
            status_box.bind('<<ComboboxSelected>>', lambda _event: self._refresh_character_gallery())
        races = [ALL_RACES, *data.race_sum]
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
                                        background=colors['background'])
        self._attach_scrollbar(self.gallery_canvas)
        self._bind_mousewheel((self.gallery_canvas, gallery_area),
                              lambda event, touchpad: self._on_wheel(self.gallery_canvas, event, touchpad))
        self.gallery_canvas.bind('<Configure>', self._resize_character_gallery_content)

        preview = ttk.LabelFrame(body, text='Предпросмотр', padding=10)
        preview.pack(side='right', fill='y', padx=(14, 0))
        self.card_canvas = tk.Canvas(preview, width=300, height=450,
                                     highlightthickness=0, background=colors['background'])
        self.card_canvas.pack(pady=(0, 6))
        detail_frame = ttk.Frame(preview)
        detail_frame.pack(fill='both', expand=True)
        self.detail = tk.Canvas(detail_frame, width=300, highlightthickness=0,
                                background=colors['background'])
        self._attach_scrollbar(self.detail)
        if ladder_selection:
            self.ladder_start_button = ttk.Button(
                preview, text='Начать забег', command=self.start_ladder,
                style='Primary.TButton', state='disabled',
            )
            self.ladder_start_button.pack(fill='x', pady=(8, 0))
        self._bind_mousewheel((detail_frame, self.detail),
                              lambda event, touchpad: self._on_wheel(self.detail, event, touchpad))
        self.files = character_files_by_creation_date(living_only=ladder_selection)
        self.visible_files = []
        self.selected_character_path = None
        self.character_search_var.trace_add('write', lambda *_args: self._refresh_character_gallery())
        sort_box.bind('<<ComboboxSelected>>', lambda _event: self._refresh_character_gallery())
        race_box.bind('<<ComboboxSelected>>', lambda _event: self._refresh_character_gallery())
        self._refresh_character_gallery(select_first=True)

    @staticmethod
    def _read_character_properties(path):
        """The hero's fields, or an empty dict when the file cannot be read."""
        try:
            return Fight.load_character(path)
        except (OSError, UnicodeError):
            return {}

    def _draw_gallery_race_icon(self, canvas, x, y, race_value, tag):
        """Draw a compact, theme-friendly race marker for a collection tile."""
        kind = RACE_TEMPLATES.get(race_value.casefold(), 'human')
        palettes = {
            'human': ('#e8c9a6', '#684b39', '#bd8c65'),
            'orc': ('#9dbc88', '#3b5942', '#76976a'),
            'elf': ('#e3cba8', '#75628e', '#ad91c8'),
        }
        skin, hair, accent = palettes[kind]
        canvas.create_oval(x + 2, y + 2, x + 34, y + 34, fill=self.ui_colors['surface'],
                           outline=self.ui_colors['frame_border'], width=1, tags=(tag,))
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
                           fill=WOOD, outline='', tags=(tag,))
        canvas.create_oval(x + 21, y + 17, x + 23, y + 19,
                           fill=WOOD, outline='', tags=(tag,))
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

    def _default_status_filter(self):
        return 'Живые' if self.ladder_selection_mode else 'Все'

    def _reset_character_filters(self):
        self.character_sort_var.set(next(iter(COLLECTION_SORTS)))
        self.character_status_var.set(self._default_status_filter())
        self.character_race_var.set(ALL_RACES)
        self.character_search_var.set('')
        self._refresh_character_gallery()

    def _refresh_character_gallery(self, select_first=False):
        if not hasattr(self, 'gallery_canvas') or not self.gallery_canvas.winfo_exists():
            return
        self.gallery_canvas.delete('all')
        query = self.character_search_var.get().strip().casefold()
        selected_race = self.character_race_var.get()
        selected_status = self.character_status_var.get()
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
            haystack = ' '.join((path.stem, *props.values())).casefold()
            if query and query not in haystack:
                continue
            if selected_race != ALL_RACES and props.get('race', '').casefold() != selected_race.casefold():
                continue
            filtered.append(path)
        sort_key = COLLECTION_SORTS.get(self.character_sort_var.get(), next(iter(COLLECTION_SORTS.values())))
        filtered.sort(key=lambda path: sort_key(path, properties_by_path[path]))
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
            self._set_gallery_tile_hover(tile_path, background_id, False)
        if not same_selection:
            self.open_selected()

    def _tile_outline(self, path, hovering=False):
        """Outline colour and width of a collection tile: dead, selected, hovered or plain."""
        selected = path == self.selected_character_path
        if not Fight.is_character_alive(self.gallery_properties.get(path, {})):
            return self.ui_colors['dead_border'], 2 if selected or hovering else 1
        if selected:
            return self.ui_colors['accent'], 2
        if hovering:
            return self.ui_colors['hover'], 1.5
        return self.ui_colors['border'], 1

    def _set_gallery_tile_hover(self, path, background_id, hovering):
        outline, width = self._tile_outline(path, hovering)
        self.gallery_canvas.itemconfigure(background_id, outline=outline, width=width)

    def _upgrade_character_stat(self, stat):
        if getattr(self, 'ladder_selection_mode', False):
            return
        path = getattr(self, 'selected_character_path', None)
        if path is None or stat not in UPGRADE_POOLS:
            return
        properties = self._read_character_properties(path)
        if not Fight.is_character_alive(properties):
            return
        current = properties.get(stat, '')
        cost = upgrade_cost(stat, current)
        points = Fight.character_points(properties)
        if cost is None or points < cost:
            return
        tiers = UPGRADE_POOLS[stat]
        try:
            Fight.update_character_fields(path, {
                stat: tiers[tiers.index(current) - 1], 'points': points - cost,
            })
        except (OSError, UnicodeError) as error:
            self._show_error('Не удалось улучшить характеристику', str(error))
            return
        self.audio.play_effect('stat_upgrade')
        self.open_selected()
        self._refresh_character_gallery()

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
                fill=self.ui_colors['muted'], font=(TEXT_FONT, 10), anchor='center',
            )
            canvas.configure(scrollregion=(0, 0, canvas_width, 48))
            return

        margin, gap, columns = 6, 8, 2
        tile_width = max(90, (canvas_width - 2 * margin - gap) // columns)
        tile_height = 116
        y = margin
        colors = self.ui_colors
        for row_start in range(0, len(self.visible_files), columns):
            for column in range(columns):
                index = row_start + column
                if index >= len(self.visible_files):
                    break
                path = self.visible_files[index]
                props = self.gallery_properties[path]
                is_dead = not Fight.is_character_alive(props)
                text_color = colors['dead_text'] if is_dead else colors['foreground']
                x = margin + column * (tile_width + gap)
                tag = f'gallery_tile_{index}'
                outline, outline_width = self._tile_outline(path)
                background_id = canvas.create_rectangle(
                    x, y, x + tile_width, y + tile_height,
                    fill=colors['dead_fill'] if is_dead else colors['input'],
                    outline=outline, width=outline_width, tags=(tag,),
                )
                self.gallery_tiles[path] = background_id
                self._draw_gallery_race_icon(canvas, x + 10, y + 8, props.get('race', ''), tag)
                canvas.create_text(
                    x + 54, y + 9, text=path.stem, anchor='nw',
                    width=max(40, tile_width - 64), fill=text_color,
                    font=(TEXT_FONT, 9, 'bold'), tags=(tag,),
                )
                race = ' '.join(filter(None, (props.get('subrace', ''), props.get('race', ''))))
                canvas.create_text(
                    x + 10, y + 52,
                    text='\n'.join(value for value in (race, props.get('size', '')) if value), anchor='nw',
                    width=max(50, tile_width - 20),
                    fill=colors['dead_text'] if is_dead else colors['muted'],
                    font=(TEXT_FONT, 8), tags=(tag,),
                )
                points = props.get('points', '0').strip() or '0'
                badge_width = min(92, tile_width - 16)
                badge_left = x + tile_width - badge_width - 8
                badge_top = y + tile_height - 27
                canvas.create_rectangle(
                    badge_left, badge_top, x + tile_width - 8, y + tile_height - 7,
                    fill=colors['dead_fill'] if is_dead else colors['surface'],
                    outline=colors['dead_border'] if is_dead else colors['accent'],
                    width=1, tags=(tag,),
                )
                canvas.create_text(
                    (badge_left + x + tile_width - 8) / 2, badge_top + 10,
                    text='Мёртв' if is_dead else f'Очки: {points}', fill=text_color,
                    font=(TEXT_FONT, 8, 'bold'), tags=(tag,),
                )
                canvas.tag_bind(
                    tag, '<Button-1>',
                    lambda _event, selected_path=path: self._select_character(selected_path),
                )
                for sequence, hovering in (('<Enter>', True), ('<Leave>', False)):
                    canvas.tag_bind(
                        tag, sequence,
                        lambda _event, selected_path=path, item_id=background_id, hovering=hovering:
                        self._set_gallery_tile_hover(selected_path, item_id, hovering),
                    )
            y += tile_height + gap

        canvas.configure(scrollregion=(0, 0, canvas_width, y))
        if old_top:
            canvas.yview_moveto(old_top)

    def _draw_character_card(self, properties):
        canvas = self.card_canvas
        canvas.delete('all')
        colors = self.ui_colors
        is_dead = not Fight.is_character_alive(properties)
        dead_label = '#ffe8e9'
        canvas.configure(background=colors['dead_fill'] if is_dead else colors['background'])
        template_name = RACE_TEMPLATES.get(properties.get('race', '').casefold())
        photo = template_name and self._template_image(
            TEMPLATES_DIR / 'races' / f'{template_name}.png', 256, 384,
        )
        if photo:
            left = (int(canvas['width']) - photo.width()) // 2
            top = (int(canvas['height']) - photo.height()) // 2
            canvas.create_image(left, top, image=photo, anchor='nw')
        else:
            left, top = 12, 12
            canvas.create_rectangle(left, top, left + 256, top + 384,
                                    fill=WOOD, outline=GILT, width=3)

        target_height = (160, 185, 210, 235)[SIZE_TIERS.get(properties.get('size', '').casefold(), 1)]
        figure = template_name and self._template_image(
            TEMPLATES_DIR / 'characters' / f'{template_name}.png', None, target_height,
        )
        figure_x = left + 130
        figure_bottom = top + 300
        ability = properties.get('ability', '—')

        if figure:
            self._draw_card_weapon(canvas, properties,
                                   *hand_position(template_name, figure, figure_x, figure_bottom),
                                   target_height / 185)
            canvas.create_image(figure_x, figure_bottom, image=figure, anchor='s')

        bar_background = colors['dead_bar'] if is_dead else '#1a120b'
        canvas.create_rectangle(left + 3, top + 4, left + 257, top + 60,
                                fill=bar_background, outline='')
        canvas.create_rectangle(left + 3, top + 306, left + 257, top + 387,
                                fill=bar_background, outline='')

        def label(y, text, size=9, bold=False, width=224, family=TEXT_FONT):
            font = (family, size, 'bold' if bold else 'normal')
            options = dict(text=fit_text(text, font, width), justify='center', font=font)
            canvas.create_text(left + 130, top + y + 1, fill='#0d0906', **options)
            canvas.create_text(left + 129, top + y, fill=dead_label if is_dead else PARCHMENT_TEXT, **options)

        name = properties.get('name', 'Новый персонаж')
        # A long name gets a smaller font before it gets cut.
        name_size = next((size for size in (12, 11, 10)
                          if tkfont.Font(font=(TITLE_FONT, size)).measure(name) <= 224), 9)
        label(17, name, name_size, family=TITLE_FONT)
        race_line = ' '.join(filter(None, (properties.get('subrace'), properties.get('race'))))
        label(39, 'Мёртв' if is_dead else race_line, 8, True)
        label(315, properties.get('title', ''), 8, True)
        label(338, f"Рост: {properties.get('size', '—')}", 8, True)
        label(357, f"Оружие: {properties.get('weapon', '—')}", 8)
        label(376, self._card_ability_line(ability, properties.get('ability_power')), 8,
              width=CARD_ABILITY_WIDTH)
        accent = colors['dead_border'] if is_dead else colors['card_accent']
        canvas.create_line(left + 20, top + 60, left + 240, top + 60,
                           fill=accent, width=2)
        canvas.create_line(left + 20, top + 306, left + 240, top + 306,
                           fill=accent, width=1)
        canvas.create_rectangle(left, top, left + 260, top + 390,
                                outline=accent, width=2)

    @staticmethod
    def _card_ability_line(ability, power):
        """Keep the ability name whole on the card; add its power only when it fits."""
        card_font = (TEXT_FONT, 8)
        text = f'Способность: {ability}'
        with_power = f'{text} · {power}'
        if power and power != 'None' and tkfont.Font(font=card_font).measure(with_power) <= CARD_ABILITY_WIDTH:
            return with_power
        return fit_text(text, card_font, CARD_ABILITY_WIDTH)

    def _draw_card_weapon(self, canvas, properties, hand_x, hand_y, size_factor):
        """The weapon picture, or a simple drawing of it when the picture file is missing."""
        if self._draw_weapon(canvas, properties, hand_x, hand_y, max(20, round(48 * size_factor))):
            return
        weapon = properties.get('weapon', '').casefold()
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
        points = Fight.character_points(properties)
        # The dead keep no progression, so they get no upgrade buttons.
        can_progress = Fight.is_character_alive(properties) and not getattr(
            self, 'ladder_selection_mode', False
        )
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
        label_font = tkfont.Font(family=TEXT_FONT, size=11, weight='bold')
        y = 6
        for label, key in fields:
            raw_value = properties.get(key, '').strip()
            if not raw_value or raw_value.casefold() == 'none':
                continue
            value = raw_value
            show_upgrade = can_progress and key in UPGRADE_POOLS
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
                width=value_width, fill=self.ui_colors['foreground'], font=(TEXT_FONT, 12),
            )
            if show_upgrade:
                cost = upgrade_cost(key, properties.get(key, ''))
                can_upgrade = cost is not None and points >= cost
                if key == 'weapon_mastery' and properties.get('weapon', '') == data.weapon_sum[0]:
                    can_upgrade = False
                if key == 'ability_power' and properties.get('ability', '') == data.ability_sum[0]:
                    can_upgrade = False
                action_text = 'MAX' if cost is None else chr(8593) + f' {cost}'
                action_left = right - action_width - 4
                action_right = right - 4
                action_tag = f'upgrade_{key}'
                action_fill = self.ui_colors['accent'] if can_upgrade else self.ui_colors['input']
                action_text_fill = self.ui_colors['on_accent'] if can_upgrade else self.ui_colors['muted']
                self.detail.create_rectangle(
                    action_left, y + 7, action_right, bottom - 7,
                    fill=action_fill, outline=self.ui_colors['title'] if can_upgrade else self.ui_colors['border'],
                    tags=(action_tag,),
                )
                self.detail.create_text(
                    (action_left + action_right) / 2, y + row_height / 2,
                    text=action_text, fill=action_text_fill,
                    font=(TEXT_FONT, 10, 'bold'), tags=(action_tag,),
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


def configure_logging():
    """Log to the console and to a per-session file so sound problems can be diagnosed."""
    handlers = []
    if sys.stderr is not None:  # pythonw runs without a console
        handlers.append(logging.StreamHandler())
    file_error = None
    try:
        handlers.append(logging.FileHandler(LOG_PATH, mode='w', encoding='utf-8'))
    except OSError as error:
        file_error = error
    logging.basicConfig(
        level=logging.INFO, handlers=handlers,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    )
    if file_error is not None:
        logger.warning('Журнал не записывается в %s: %s', LOG_PATH, file_error)


def run():
    configure_logging()
    load_bundled_fonts()
    root = tk.Tk()
    root.report_callback_exception = lambda *exc_info: logger.error(
        'Необработанная ошибка в интерфейсе', exc_info=exc_info,
    )
    CharacterApp(root)
    root.mainloop()


if __name__ == '__main__':
    run()

