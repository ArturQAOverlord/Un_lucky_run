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


# Bonuses a fighter's build adds to the rounds, by round label.
RACE_BONUSES = {
    'Человек': {'Интеллект': 2},
    'Орк': {'Сила': 2},
    'Эльф': {'Скорость': 2},
}
SIZE_BONUSES = {
    'Мелкий': {'Скорость': 2, 'Сила': -1},
    'Крупный': {'Сила': 2, 'Скорость': -1},
    'Гигантский': {'Сила': 4, 'Скорость': -2},
}
WEAPON_BONUSES = {
    'Без оружия': {'Боевые навыки': 2},
    'Катана': {'Владение оружием': 2, 'Скорость': 1},
    'Топор': {'Владение оружием': 2, 'Сила': 2},
    'Меч': {'Владение оружием': 2, 'Боевые навыки': 1},
    'Пистолет': {'Владение оружием': 4},
    'Танк': {'Владение оружием': 7, 'Скорость': -3},
    'Портальная пушка': {'Владение оружием': 2, 'Интеллект': 3},
}
# Each enchantment overpowers the next one: fire melts ice, ice stops kinetic force, kinetic force
# throws an explosion back, an explosion shatters a sharp edge and a sharp edge cuts the flame.
ENCHANTMENT_CYCLE = ('Огненное', 'Ледяное', 'Кинетическое', 'Взрывное', 'Острое')
ENCHANTMENT_BONUS = 1
ENCHANTMENT_ADVANTAGE = 3
CHOSEN_LUCK_BONUS = 3
CHAOS_CONDUCTOR_CHANCE = 0.4
DEVIL_CHANCE = 0.5
DEVIL_THEFT = 5
NULLIFIER = 'Нулификатор-пария'
# A rerolled die in one round shows 0 to this many points of luck.
REROLL_FACES = 6


def _signed(amount):
    return f'{amount:+d}'.replace('-', '−')


class _Fighter:
    """A fighter's state while a fight is resolved: points, luck shares and bonuses per round."""

    def __init__(self, character):
        self.character = character
        _, details = _score(character)
        self.points = dict(details)
        self.luck = 0
        self.luck_shares = dict.fromkeys(self.points, 0)
        self.bonus = dict.fromkeys(self.points, 0)
        ability = character.get('ability', '')
        self.ability = ability if ability in data.ability_sum[1:] else None
        self.ability_rank = (
            max(1, _rank(data.ability_power_sum, character.get('ability_power', ''))) if self.ability else 0
        )
        chaos = character.get('chaos', '')
        self.chaos = chaos if chaos in data.chaos_sum else None
        enchantment = character.get('weapon_enchantment', '')
        armed = character.get('weapon', '') != data.weapon_sum[0]
        self.enchantment = enchantment if armed and enchantment in ENCHANTMENT_CYCLE else None

    def total(self, label):
        return self.points[label] + self.luck_shares[label] + self.bonus[label]

    def grand_total(self):
        return sum(self.total(label) for label in self.points)

    def strongest_round(self):
        return max(self.points, key=self.total)

    def weakest_round(self):
        return min(self.points, key=self.total)

    def keep_rounds_non_negative(self):
        for label in self.points:
            self.bonus[label] -= min(0, self.total(label))


def _logger(events, owner):
    def log(round_label, text, detail=''):
        events.append({'owner': owner, 'round': round_label, 'text': text, 'detail': detail})
    return log


def _nullify(fighters, events):
    """A nullifier pariah silences the opponent's ability and chaos, base ability power included."""
    silenced = [opponent.chaos == NULLIFIER for opponent in reversed(fighters)]
    for index, (fighter, is_silenced) in enumerate(zip(fighters, silenced)):
        if not is_silenced or not (fighter.ability or fighter.chaos):
            continue
        fighter.ability = fighter.chaos = None
        fighter.ability_rank = 0
        fighter.bonus['Мощь способности'] -= fighter.points['Мощь способности']
        _logger(events, 1 - index)(None, 'Нулификатор гасит силы', 'соперник пуст')


def _roll_luck(fighter, log):
    luck = random.randint(1, 20)
    if fighter.ability == 'Удачливый сукин сын':
        rolls = [luck] + [random.randint(1, 20) for _ in range(2 if fighter.ability_rank >= 4 else 1)]
        luck = max(rolls)
        log(None, 'Удачливый сукин сын', f"{'/'.join(map(str, rolls))} → {luck}")
    elif fighter.ability == 'Провидец' and luck < 9 + fighter.ability_rank:
        reroll = max(luck, random.randint(1, 20))
        log(None, 'Провидец перебрасывает', f'{luck} → {reroll}')
        luck = reroll
    if fighter.chaos == 'Избран богами':
        luck += CHOSEN_LUCK_BONUS
        log(None, 'Избран богами', f'удача {_signed(CHOSEN_LUCK_BONUS)}')
    return luck


def _build_bonuses(fighter, opponent, log):
    """Race, size and weapon shape the rounds a little; an enchantment strengthens the weapon."""
    for label in fighter.points:
        sources, amount = [], 0
        for table, field in ((RACE_BONUSES, 'race'), (SIZE_BONUSES, 'size'), (WEAPON_BONUSES, 'weapon')):
            value = fighter.character.get(field, '')
            if label in table.get(value, {}):
                sources.append(value)
                amount += table[value][label]
        if amount:
            fighter.bonus[label] += amount
            log(label, ' · '.join(sources), _signed(amount))

    if fighter.enchantment:
        amount, text = ENCHANTMENT_BONUS, f'{fighter.enchantment} зачарование'
        position = ENCHANTMENT_CYCLE.index(fighter.enchantment)
        beaten = ENCHANTMENT_CYCLE[(position + 1) % len(ENCHANTMENT_CYCLE)]
        if opponent.enchantment == beaten:
            amount += ENCHANTMENT_ADVANTAGE
            text = f'{fighter.enchantment} бьёт {beaten.lower()}'
        fighter.bonus['Владение оружием'] += amount
        log('Владение оружием', text, _signed(amount))


def _telepath(fighter, opponent, log):
    insight = fighter.ability_rank
    fighter.bonus['Интеллект'] += insight
    log('Интеллект', 'Телепат читает мысли', _signed(insight))
    copied = min(opponent.points['Боевые навыки'] - fighter.points['Боевые навыки'], fighter.ability_rank * 2)
    if copied > 0:
        fighter.bonus['Боевые навыки'] += copied
        log('Боевые навыки', 'Телепат перенимает приёмы', _signed(copied))


def _fire_breath(fighter, opponent, log):
    smoke = (fighter.ability_rank + 1) // 2
    fighter.bonus['Сила'] += fighter.ability_rank
    opponent.bonus['Скорость'] -= smoke
    log('Сила', 'Дыхание огнём', _signed(fighter.ability_rank))
    log('Скорость', 'Соперник в дыму', f'{_signed(-smoke)} сопернику')


def _nuclear_farts(fighter, opponent, log):
    stench, tears = fighter.ability_rank, (fighter.ability_rank + 1) // 2
    opponent.bonus['Интеллект'] -= stench
    fighter.bonus['Интеллект'] -= 1
    opponent.bonus['Скорость'] -= tears
    log('Интеллект', 'Ядерные пуки: дышать нечем', f'{_signed(-stench)} / −1 себе')
    log('Скорость', 'Ядерные пуки: глаза слезятся', f'{_signed(-tears)} сопернику')


def _energy_manipulator(fighter, opponent, log):
    """Drains the opponent's ability power, or the charge of their weapon when there is none."""
    for source, text in (('Мощь способности', 'Поглощает энергию'), ('Владение оружием', 'Высасывает заряд оружия')):
        drained = min(fighter.ability_rank + 2, opponent.total(source))
        if drained > 0:
            opponent.bonus[source] -= drained
            fighter.bonus['Мощь способности'] += drained
            log('Мощь способности', text, _signed(drained))
            return


def _teleporter(fighter, opponent, log):
    target = opponent.strongest_round()
    dodged = min(fighter.ability_rank + 1, opponent.total(target))
    if dodged > 0:
        opponent.bonus[target] -= dodged
        log(target, 'Телепорт: уклонение', f'{_signed(-dodged)} сопернику')


def _endurance(fighter, opponent, log):
    target = fighter.weakest_round()
    fighter.bonus[target] += fighter.ability_rank + 2
    log(target, 'Сверхвыносливость', _signed(fighter.ability_rank + 2))


def _touched_by_chaos(fighter, opponent, log):
    target = random.choice(list(fighter.points))
    surge = random.randint(-2, 6)
    fighter.bonus[target] += surge
    log(target, 'Всплеск хаоса', _signed(surge))


def _chaos_conductor(fighter, opponent, log):
    """With some luck, swaps the scores of the round the conductor loses the worst."""
    losing = [label for label in fighter.points if fighter.total(label) < opponent.total(label)]
    if not losing or random.random() >= CHAOS_CONDUCTOR_CHANCE:
        return
    target = max(losing, key=lambda label: opponent.total(label) - fighter.total(label))
    gap = opponent.total(target) - fighter.total(target)
    fighter.bonus[target] += gap
    opponent.bonus[target] -= gap
    log(target, 'Хаос меняет счёт местами', f'±{gap}')


def _devils_favourite(fighter, opponent, log):
    if fighter.grand_total() >= opponent.grand_total() or random.random() >= DEVIL_CHANCE:
        return
    target = opponent.strongest_round()
    stolen = min(DEVIL_THEFT, opponent.total(target))
    opponent.bonus[target] -= stolen
    fighter.bonus[target] += stolen
    log(target, 'Дьявол подыгрывает', f'{_signed(stolen)} у соперника')


# Abilities adding points act first; the ones reacting to the resulting scores act after them.
DIRECT_ABILITIES = {
    'Телепат': _telepath,
    'Дыхание огнем': _fire_breath,
    'Ядерные пуки': _nuclear_farts,
    'Энергетический манипулятор': _energy_manipulator,
}
REACTIVE_ABILITIES = {
    'Телепортатор': _teleporter,
    'Сверхвыносливость': _endurance,
}
CHAOS_EFFECTS = {
    'Тронут хаосом': _touched_by_chaos,
    'Проводник хаоса': _chaos_conductor,
}
# The devil only helps someone who is still losing once everything else has happened.
LAST_CHANCE_EFFECTS = {
    'Любимец дьявола': _devils_favourite,
}


def _apply_effects(fighters, events, pick_effect):
    for index, (fighter, opponent) in enumerate((fighters, fighters[::-1])):
        effect = pick_effect(fighter)
        if effect:
            effect(fighter, opponent, _logger(events, index))
    for fighter in fighters:
        fighter.keep_rounds_non_negative()


def fight_match(first_path, second_path, award_points=True, check_liveness=(True, True)):
    first_path, second_path = Path(first_path), Path(second_path)
    if first_path.resolve() == second_path.resolve():
        raise ValueError('Выберите двух разных персонажей.')

    first, second = load_character(first_path), load_character(second_path)
    for character, must_be_alive in zip((first, second), check_liveness):
        if must_be_alive and not is_character_alive(character):
            raise ValueError(f"{character.get('name', 'Безымянный')} мёртв и не может сражаться.")
    names = (first.get('name', first_path.stem), second.get('name', second_path.stem))

    fighters = (_Fighter(first), _Fighter(second))
    events = []
    _nullify(fighters, events)
    # Each luck roll is spread over the rounds, so the shown rounds add up to the totals.
    for index, fighter in enumerate(fighters):
        fighter.luck = _roll_luck(fighter, _logger(events, index))
        fighter.luck_shares = dict(zip(fighter.points, _split_luck(fighter.luck, len(fighter.points))))
    _apply_effects(fighters, events, lambda fighter: _build_bonuses)
    for attribute, effects in (
        ('ability', DIRECT_ABILITIES), ('ability', REACTIVE_ABILITIES),
        ('chaos', CHAOS_EFFECTS), ('chaos', LAST_CHANCE_EFFECTS),
    ):
        _apply_effects(fighters, events, lambda fighter: effects.get(getattr(fighter, attribute)))

    first_fighter, second_fighter = fighters
    comparisons = []
    for attribute in first_fighter.points:
        first_round, second_round = first_fighter.total(attribute), second_fighter.total(attribute)
        if first_round == second_round:
            winner_index = random.randrange(2)
        else:
            winner_index = 0 if first_round > second_round else 1
        comparisons.append({
            'attribute': attribute,
            'first_points': first_fighter.points[attribute],
            'second_points': second_fighter.points[attribute],
            'first_luck': first_fighter.luck_shares[attribute],
            'second_luck': second_fighter.luck_shares[attribute],
            'first_bonus': first_fighter.bonus[attribute],
            'second_bonus': second_fighter.bonus[attribute],
            'first_total': first_round,
            'second_total': second_round,
            'winner': names[winner_index],
            'winner_index': winner_index,
            'events': [event for event in events if event['round'] == attribute],
        })

    first_total, second_total = first_fighter.grand_total(), second_fighter.grand_total()
    if first_total == second_total:
        winner_index = random.randrange(2)
    else:
        winner_index = 0 if first_total > second_total else 1
    if award_points:
        award_fight_points(first_path, second_path, winner_index)
    return {
        'names': names,
        'comparisons': comparisons,
        'effects': [event for event in events if event['round'] is None],
        'winner': names[winner_index],
        'winner_index': winner_index,
        'first_total': first_total,
        'second_total': second_total,
    }


def award_fight_points(first_path, second_path, winner_index):
    change_points(first_path, 5 if winner_index == 0 else -4)
    change_points(second_path, 5 if winner_index == 1 else -4)


def _pick_winner(first_total, second_total):
    if first_total == second_total:
        return random.randrange(2)
    return 0 if first_total > second_total else 1


def reroll_round_luck(result, round_index, fighter_index):
    """A fate token: the fighter's luck in one round is thrown again and the new throw stands,
    even when it is worse. The round, the totals and the fight's winner are settled anew."""
    comparison = result['comparisons'][round_index]
    side = ('first', 'second')[fighter_index]
    old_luck, new_luck = comparison[f'{side}_luck'], random.randint(0, REROLL_FACES)
    comparison[f'{side}_luck'] = new_luck
    total = comparison[f'{side}_total'] + new_luck - old_luck
    # Effects never push a round below zero, whatever the dice say.
    comparison[f'{side}_bonus'] -= min(0, total)
    comparison[f'{side}_total'] = max(0, total)

    winner_index = _pick_winner(comparison['first_total'], comparison['second_total'])
    comparison.update(winner=result['names'][winner_index], winner_index=winner_index)
    result['first_total'] = sum(round_['first_total'] for round_ in result['comparisons'])
    result['second_total'] = sum(round_['second_total'] for round_ in result['comparisons'])
    # A tie keeps the coin already tossed for the fight.
    if result['first_total'] != result['second_total']:
        result['winner_index'] = _pick_winner(result['first_total'], result['second_total'])
    result['winner'] = result['names'][result['winner_index']]
    return old_luck, new_luck


def play(first_path, second_path):
    """A fight without rounds or points, for tournaments."""
    result = fight_match(first_path, second_path, award_points=False)
    return {
        'winner_path': Path((first_path, second_path)[result['winner_index']]),
        'first_total': result['first_total'],
        'second_total': result['second_total'],
    }
