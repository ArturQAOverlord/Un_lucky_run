"""Hero portraits composed from the card templates at full size and scaled down smoothly once."""

import base64
import io
from collections import namedtuple
from functools import lru_cache
from pathlib import Path

import pygame

import data

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

# Layouts are in the pixels of a 1024×1536 background.
BACKGROUND_SIZE = (1024, 1536)
# 'card' is the whole background with its text panels; 'scene' is the painted view between the panels,
# cut to 2:3 for the arena. Figure heights go by size tier; the weapon box grows with the figure.
LAYOUTS = {
    'card': {'box': (0, 0, 1024, 1536), 'center_x': 520, 'feet': 1200,
             'heights': (640, 740, 840, 940), 'weapon': 220},
    # The figure stands right of centre, so the weapon in the right hand stays inside the picture.
    'scene': {'box': (202, 230, 620, 930), 'center_x': 375, 'feet': 920,
              'heights': (560, 640, 715, 780), 'weapon': 190},
}
# Weapons in proportion to each other: a pistol is a hand's length, a tank is a toy-sized joke.
WEAPON_SCALES = {
    'katana': 1.0, 'sword': 0.95, 'axe': 0.85, 'pistol': 0.5, 'tank': 0.8, 'portal_cannon': 0.7,
}
ENCHANTMENT_GLOWS = {
    'Огненное': (255, 110, 30), 'Ледяное': (120, 200, 255), 'Кинетическое': (190, 140, 255),
    'Взрывное': (255, 210, 60), 'Острое': (235, 240, 250),
}
OUTLINE_COLOR = (20, 12, 6)
DEAD_TINT = (235, 190, 185)

# `data` is a base64 PNG for tk.PhotoImage; `hand` is where the hand is in the scaled picture,
# for drawing a weapon whose picture is missing.
Portrait = namedtuple('Portrait', 'data hand weapon_drawn size_factor')


def portrait_key(properties):
    """The fields a portrait depends on, normalised so equal heroes share one cached picture."""
    alive = str(properties.get('live_status', '')).strip().casefold() not in {'false', '0', 'no', 'dead'}
    return tuple(properties.get(field, '').strip().casefold()
                 for field in ('race', 'size', 'weapon')) + (properties.get('weapon_enchantment', ''), alive)


@lru_cache(maxsize=32)
def _load(path):
    return pygame.image.load(str(path))


def _to_png_data(surface):
    buffer = io.BytesIO()
    pygame.image.save(surface, buffer, 'portrait.png')
    return base64.b64encode(buffer.getvalue()).decode('ascii')


def _fit(surface, width=None, height=None):
    scale = min(width / surface.get_width() if width else float('inf'),
                height / surface.get_height() if height else float('inf'))
    size = (max(1, round(surface.get_width() * scale)), max(1, round(surface.get_height() * scale)))
    return pygame.transform.smoothscale(surface, size)


def _dressed_weapon(weapon, enchantment):
    """The weapon with a dark outline that reads on any background and the glow of its enchantment."""
    mask = pygame.mask.from_surface(weapon, 100)
    pad = max(6, weapon.get_width() // 8)
    width, height = weapon.get_width() + 2 * pad, weapon.get_height() + 2 * pad
    dressed = pygame.Surface((width, height), pygame.SRCALPHA)
    glow_color = ENCHANTMENT_GLOWS.get(enchantment)
    if glow_color:
        glow = pygame.Surface((width, height), pygame.SRCALPHA)
        silhouette = mask.to_surface(setcolor=(*glow_color, 255), unsetcolor=(*glow_color, 0))
        # The silhouette is widened into a ring first, then shrinking and growing back blurs it into a halo.
        reach = pad // 2
        for dx, dy in ((0, 0), (-reach, 0), (reach, 0), (0, -reach), (0, reach),
                       (-reach // 2, -reach // 2), (reach // 2, -reach // 2),
                       (-reach // 2, reach // 2), (reach // 2, reach // 2)):
            glow.blit(silhouette, (pad + dx, pad + dy))
        blurred = pygame.transform.smoothscale(glow, (max(1, width // 6), max(1, height // 6)))
        blurred = pygame.transform.smoothscale(blurred, (width, height))
        for _ in range(2):
            dressed.blit(blurred, (0, 0))
    outline = mask.to_surface(setcolor=(*OUTLINE_COLOR, 255), unsetcolor=(*OUTLINE_COLOR, 0))
    thickness = max(2, weapon.get_width() // 70)
    for dx in (-thickness, 0, thickness):
        for dy in (-thickness, 0, thickness):
            if dx or dy:
                dressed.blit(outline, (pad + dx, pad + dy))
    dressed.blit(weapon, (pad, pad))
    return dressed, pad


@lru_cache(maxsize=64)
def render(key, mode, width, height):
    """The hero's portrait scaled to width×height, or None when the race has no template."""
    race, size, weapon_value, enchantment, alive = key
    template = RACE_TEMPLATES.get(race)
    background_path = TEMPLATES_DIR / 'races' / f'{template}.png'
    if not template or not background_path.is_file():
        return None
    layout = LAYOUTS[mode]
    background = _load(background_path)
    if background.get_size() != BACKGROUND_SIZE:
        background = pygame.transform.smoothscale(background, BACKGROUND_SIZE)
    box_left, box_top, box_width, box_height = layout['box']
    canvas = pygame.Surface((box_width, box_height), pygame.SRCALPHA)
    canvas.blit(background, (0, 0), area=layout['box'])

    figure_height = layout['heights'][SIZE_TIERS.get(size, 1)]
    size_factor = figure_height / layout['heights'][1]
    figure_path = TEMPLATES_DIR / 'characters' / f'{template}.png'
    figure = _fit(_load(figure_path), height=figure_height) if figure_path.is_file() else None
    hand = weapon_drawn = None
    if figure is not None:
        left = layout['center_x'] - figure.get_width() // 2
        top = layout['feet'] - figure.get_height()
        hand_offset = figure.get_width() * HAND_FRACTIONS.get(template, 0.16)
        hand_y = layout['feet'] - figure.get_height() * 0.62
        weapon_template = WEAPON_TEMPLATES.get(weapon_value)
        weapon_path = weapon_template and TEMPLATES_DIR / 'weapons' / f'{weapon_template}.png'
        weapon = None
        if weapon_path and weapon_path.is_file():
            box = round(layout['weapon'] * size_factor * WEAPON_SCALES.get(weapon_template, 1.0))
            weapon = _fit(_load(weapon_path), box, box)
            grip_x, grip_y = WEAPON_GRIPS.get(weapon_template, (0.9, 0.9))
            # A weapon sticking out on the left moves the figure right, as far as the picture allows.
            weapon_left = left + hand_offset - weapon.get_width() * grip_x
            left += max(0, min(-weapon_left, box_width - left - figure.get_width()))
        hand = (left + hand_offset, hand_y)
        if weapon is not None:
            dressed, pad = _dressed_weapon(weapon, enchantment)
            # The weapon goes behind the figure, so the hand sits in front of the grip.
            canvas.blit(dressed, (round(hand[0] - weapon.get_width() * grip_x - pad),
                                  round(hand[1] - weapon.get_height() * grip_y - pad)))
            weapon_drawn = True
        canvas.blit(figure, (left, top))

    if not alive:
        canvas = pygame.transform.grayscale(canvas)
        canvas.fill(DEAD_TINT, special_flags=pygame.BLEND_RGB_MULT)
    result = _fit(canvas, width, height)
    scale = result.get_width() / canvas.get_width()
    scaled_hand = hand and (hand[0] * scale, hand[1] * scale)
    return Portrait(_to_png_data(result), scaled_hand, bool(weapon_drawn), size_factor)


@lru_cache(maxsize=8)
def tint(width, height, color, alpha):
    """A see-through sheet of one colour, as base64 PNG: Tk on macOS cannot stipple, so canvases lay this over."""
    sheet = pygame.Surface((width, height), pygame.SRCALPHA)
    sheet.fill((*color, alpha))
    return _to_png_data(sheet)


@lru_cache(maxsize=32)
def fitted_picture(path, width, height):
    """Any picture shrunk smoothly into width×height, as base64 PNG; None when it cannot be read."""
    try:
        return _to_png_data(_fit(_load(path), width, height))
    except (pygame.error, OSError):
        return None
