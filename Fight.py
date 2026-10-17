"""Character comparison and fight simulation."""

import random
from pathlib import Path

import data


def load_character(path):
    character = {}
    with Path(path).open(encoding='utf-8') as file:
        for line in file:
            key, separator, value = line.rstrip('\n').partition(': ')
            if separator:
                character[key] = value
    return character


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


def fight_match(first_path, second_path):
    first_path, second_path = Path(first_path), Path(second_path)
    if first_path.resolve() == second_path.resolve():
        raise ValueError('Выберите двух разных персонажей.')

    first, second = load_character(first_path), load_character(second_path)
    first_score, first_details = _score(first)
    second_score, second_details = _score(second)
    first_luck, second_luck = random.randint(1, 20), random.randint(1, 20)
    first_total, second_total = first_score + first_luck, second_score + second_luck
    first_name = first.get('name', first_path.stem)
    second_name = second.get('name', second_path.stem)

    comparisons = []
    for (attribute, first_points), (_, second_points) in zip(first_details, second_details):
        if first_points == second_points:
            winner = random.choice((first_name, second_name))
        else:
            winner = first_name if first_points > second_points else second_name
        comparisons.append({
            'attribute': attribute,
            'first_points': first_points,
            'second_points': second_points,
            'winner': winner,
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
        winner = random.choice((first_name, second_name))
        report.extend(['', f'Ничья по очкам! Победитель выбран случайно: {winner}.'])
    else:
        winner = first_name if first_total > second_total else second_name
        report.extend(['', f'Победитель: {winner}!'])
    return {
        'report': '\n'.join(report),
        'comparisons': comparisons,
        'winner': winner,
        'first_name': first_name,
        'second_name': second_name,
    }


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
