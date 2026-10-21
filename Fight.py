"""Character comparison and fight simulation."""

import contextlib
import random
from pathlib import Path

import data


def load_character(path):
    character = {}
    with Path(path).open(encoding='utf-8') as file:
        for line in file:
            key, separator, value = line.rstrip('\n').partition(':')
            if separator:
                character[key.strip()] = value.strip()
    return character


def is_character_alive(character_or_path):
    if isinstance(character_or_path, dict):
        character = character_or_path
    else:
        try:
            character = load_character(character_or_path)
        except (OSError, UnicodeError):
            return False
    raw_status = character.get('live_status')
    if raw_status is None:
        return True
    return str(raw_status).strip().casefold() not in {
        'false', '0', 'no', 'dead',
    }


def write_text_atomic(path, text):
    """Write through a temporary file, so a crash leaves either the old or the new content."""
    path = Path(path)
    temporary_path = path.with_suffix(path.suffix + '.tmp')
    try:
        temporary_path.write_text(text, encoding='utf-8')
        temporary_path.replace(path)
    except OSError:
        with contextlib.suppress(OSError):  # the original error matters more than the cleanup
            temporary_path.unlink()
        raise


def update_character_fields(path, updates):
    """Atomically set `key: value` fields of a character file, keeping the other lines."""
    lines = Path(path).read_text(encoding='utf-8').splitlines()
    pending = {key: str(value) for key, value in updates.items()}
    written = set()
    updated_lines = []
    for line in lines:
        key, separator, _value = line.partition(':')
        key = key.strip()
        if separator and key in pending:
            if key not in written:
                updated_lines.append(f'{key}: {pending[key]}')
                written.add(key)
            continue
        updated_lines.append(line)
    updated_lines.extend(f'{key}: {value}' for key, value in pending.items() if key not in written)
    write_text_atomic(path, '\n'.join(updated_lines) + '\n')


def mark_character_dead(path):
    """A fallen hero keeps nothing: the status and the zeroed points are saved together."""
    update_character_fields(path, {'live_status': False, 'points': 0})


def character_points(character):
    """The points as a number; a missing or broken value counts as zero."""
    try:
        return int(character.get('points', 0))
    except (TypeError, ValueError):
        return 0


def change_points(path, delta, minimum=0):
    """Update and persist a character's points without changing other fields."""
    updated = max(minimum, character_points(load_character(path)) + delta)
    update_character_fields(path, {'points': updated})
    return updated


def _rank(pool, value):
    try:
        return len(pool) - pool.index(value)
    except ValueError:
        return 0


def _score(character):
    score = 0
    details = []
    attributes = (
        ('strength', 'Сила', data.strength_sum, 2),
        ('speed', 'Скорость', data.speed_sum, 2),
        ('iq', 'Интеллект', data.iq_sum, 1),
        ('fighting', 'Боевые навыки', data.fighting_sum, 2),
    )
    for field, label, pool, weight in attributes:
        points = _rank(pool, character.get(field, '')) * weight
        score += points
        details.append((label, points))

    if character.get('weapon', '') != data.weapon_sum[0]:
        points = _rank(data.weapon_mastery_sum, character.get('weapon_mastery', '')) * 2
        score += points
        details.append(('Владение оружием', points))
    else:
        details.append(('Владение оружием', 0))

    if character.get('ability', '') != data.ability_sum[0]:
        points = _rank(data.ability_power_sum, character.get('ability_power', ''))
        score += points
        details.append(('Мощь способности', points))
    else:
        details.append(('Мощь способности', 0))
    return score, details


def _split_luck(luck, rounds):
    """Spread a luck roll over the rounds: every point lands in a random round."""
    shares = [0] * rounds
    for _ in range(luck):
        shares[random.randrange(rounds)] += 1
    return shares


def fight_match(first_path, second_path, award_points=True, check_liveness=(True, True)):
    first_path, second_path = Path(first_path), Path(second_path)
    if first_path.resolve() == second_path.resolve():
        raise ValueError('Выберите двух разных персонажей.')

    first, second = load_character(first_path), load_character(second_path)
    for character, must_be_alive in zip((first, second), check_liveness):
        if must_be_alive and not is_character_alive(character):
            raise ValueError(f"{character.get('name', 'Безымянный')} мёртв и не может сражаться.")
    first_score, first_details = _score(first)
    second_score, second_details = _score(second)
    first_luck, second_luck = random.randint(1, 20), random.randint(1, 20)
    first_total, second_total = first_score + first_luck, second_score + second_luck
    names = (first.get('name', first_path.stem), second.get('name', second_path.stem))

    # Each luck roll is spread over the rounds, so the shown rounds add up to the totals.
    first_shares = _split_luck(first_luck, len(first_details))
    second_shares = _split_luck(second_luck, len(second_details))
    comparisons = []
    for (attribute, first_points), (_, second_points), first_bonus, second_bonus in zip(
        first_details, second_details, first_shares, second_shares,
    ):
        first_round, second_round = first_points + first_bonus, second_points + second_bonus
        if first_round == second_round:
            winner_index = random.randrange(2)
        else:
            winner_index = 0 if first_round > second_round else 1
        comparisons.append({
            'attribute': attribute,
            'first_points': first_points,
            'second_points': second_points,
            'first_luck': first_bonus,
            'second_luck': second_bonus,
            'first_total': first_round,
            'second_total': second_round,
            'winner': names[winner_index],
            'winner_index': winner_index,
        })

    if first_total == second_total:
        winner_index = random.randrange(2)
    else:
        winner_index = 0 if first_total > second_total else 1
    if award_points:
        change_points(first_path, 5 if winner_index == 0 else -4)
        change_points(second_path, 5 if winner_index == 1 else -4)
    return {
        'comparisons': comparisons,
        'winner': names[winner_index],
        'winner_index': winner_index,
        'first_total': first_total,
        'second_total': second_total,
    }


def play(first_path, second_path):
    """A fight without rounds or points, for tournaments."""
    result = fight_match(first_path, second_path, award_points=False)
    return {
        'winner_path': Path((first_path, second_path)[result['winner_index']]),
        'first_total': result['first_total'],
        'second_total': result['second_total'],
    }
