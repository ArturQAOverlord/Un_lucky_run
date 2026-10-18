"""Character comparison and fight simulation."""

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


def set_character_live_status(path, is_alive):
    path = Path(path)
    lines = path.read_text(encoding='utf-8').splitlines()
    status_value = str(bool(is_alive))
    status_found = False
    updated_lines = []
    for line in lines:
        key, separator, _value = line.partition(':')
        if separator and key.strip() == 'live_status':
            if not status_found:
                updated_lines.append(f'{key.strip()}: {status_value}')
                status_found = True
            continue
        updated_lines.append(line)
    if not status_found:
        updated_lines.append(f'live_status: {status_value}')

    temporary_path = path.with_suffix(path.suffix + '.tmp')
    try:
        temporary_path.write_text('\n'.join(updated_lines) + '\n', encoding='utf-8')
        temporary_path.replace(path)
    except OSError:
        try:
            temporary_path.unlink()
        except OSError:
            pass
        raise


def change_points(path, delta, minimum=0):
    """Update and persist a character's points without changing other fields."""
    path = Path(path)
    lines = path.read_text(encoding='utf-8').splitlines()
    points_index = None
    current = 0
    for index, line in enumerate(lines):
        key, separator, value = line.partition(':')
        if separator and key.strip() == 'points':
            points_index = index
            try:
                current = int(value.strip())
            except ValueError:
                current = 0
            break

    updated = max(minimum, current + delta)
    if points_index is None:
        lines.append(f'points: {updated}')
    else:
        lines[points_index] = f'{lines[points_index].partition(":")[0]}: {updated}'
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
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


def fight_match(first_path, second_path, award_points=True, check_liveness=(True, True)):
    first_path, second_path = Path(first_path), Path(second_path)
    if first_path.resolve() == second_path.resolve():
        raise ValueError('Выберите двух разных персонажей.')

    first, second = load_character(first_path), load_character(second_path)
    for character, must_be_alive in zip((first, second), check_liveness):
        if must_be_alive and not is_character_alive(character):
            raise ValueError(f"Character {character.get('name', 'Unknown')} is dead and cannot fight.")
    first_score, first_details = _score(first)
    second_score, second_details = _score(second)
    first_luck, second_luck = random.randint(1, 20), random.randint(1, 20)
    first_total, second_total = first_score + first_luck, second_score + second_luck
    first_name = first.get('name', first_path.stem)
    second_name = second.get('name', second_path.stem)

    comparisons = []
    for (attribute, first_points), (_, second_points) in zip(first_details, second_details):
        if first_points == second_points:
            winner_index = random.randrange(2)
        else:
            winner_index = 0 if first_points > second_points else 1
        winner = (first_name, second_name)[winner_index]
        comparisons.append({
            'attribute': attribute,
            'first_points': first_points,
            'second_points': second_points,
            'winner': winner,
            'winner_index': winner_index,
            'first_name': first_name,
            'second_name': second_name,
        })

    report = [
        f'{first_name}: характеристики {first_score} + удача {first_luck} = {first_total}',
        f'{second_name}: характеристики {second_score} + удача {second_luck} = {second_total}',
        '',
        f'{first_name}, вклад характеристик: ' + ', '.join(f'{key} +{points}' for key, points in first_details),
        f'{second_name}, вклад характеристик: ' + ', '.join(f'{key} +{points}' for key, points in second_details),
        '',
        'Сравниваются сила, скорость, интеллект, боевые навыки, владение оружием и мощь способности. Каждый участник также получает случайный бонус удачи от 1 до 20.',
    ]
    if first_total == second_total:
        winner_index = random.randrange(2)
    else:
        winner_index = 0 if first_total > second_total else 1
    winner = (first_name, second_name)[winner_index]
    if first_total == second_total:
        report.extend(['', f'Ничья по очкам! Победитель выбран случайно: {winner}.'])
    else:
        report.extend(['', f'Победитель: {winner}!'])
    if award_points and winner_index == 0:
        first_points = change_points(first_path, 5)
        second_points = change_points(second_path, -4)
    elif award_points:
        first_points = change_points(first_path, -4)
        second_points = change_points(second_path, 5)
    else:
        first_points = _character_points(first)
        second_points = _character_points(second)
    if award_points:
        report.extend(['', f'Очки: {first_name} — {first_points}, {second_name} — {second_points}.'])
    return {
        'report': '\n'.join(report),
        'comparisons': comparisons,
        'winner': winner,
        'winner_index': winner_index,
        'first_name': first_name,
        'second_name': second_name,
        'first_points_total': first_points,
        'second_points_total': second_points,
    }


def _character_points(character):
    try:
        return int(character.get('points', 0))
    except (TypeError, ValueError):
        return 0


def fight(first_path, second_path):
    """Return the text report for a fight (backwards-compatible API)."""
    return fight_match(first_path, second_path)['report']


def play(first_path, second_path):
    """Return the winner and final scores for use in tournaments."""
    first_path, second_path = Path(first_path), Path(second_path)
    if first_path.resolve() == second_path.resolve():
        raise ValueError('Choose two different characters.')

    first = load_character(first_path)
    second = load_character(second_path)
    for character in (first, second):
        if not is_character_alive(character):
            raise ValueError(f"Character {character.get('name', 'Unknown')} is dead and cannot fight.")
    first_score, _ = _score(first)
    second_score, _ = _score(second)
    first_total = first_score + random.randint(1, 20)
    second_total = second_score + random.randint(1, 20)
    if first_total == second_total:
        winner_path = random.choice((first_path, second_path))
    else:
        winner_path = first_path if first_total > second_total else second_path
    winner_data = first if winner_path.resolve() == first_path.resolve() else second
    return {
        'winner_path': winner_path,
        'winner_name': winner_data.get('name', winner_path.stem),
        'first_total': first_total,
        'second_total': second_total,
    }
