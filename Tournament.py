"""Group tournament followed by an eight-person knockout bracket."""

from itertools import combinations
from pathlib import Path

import Fight


MIN_ROSTER_SIZE = 20
GROUP_COUNT = 4
ADVANCE_PER_GROUP = 2


def run_tournament(character_paths):
    paths = [Path(path) for path in character_paths]
    unique_paths = {path.resolve() for path in paths}
    if len(paths) < MIN_ROSTER_SIZE:
        raise ValueError(f'Нужно минимум {MIN_ROSTER_SIZE} персонажей.')
    if len(unique_paths) != len(paths):
        raise ValueError('В ростере есть повторяющиеся персонажи.')

    characters = {path: Fight.load_character(path) for path in paths}

    def name_of(path):
        return characters[path].get('name', path.stem)

    def play_match(first, second):
        result = Fight.play(first, second)
        winner = result['winner_path']
        return winner, {
            'first': name_of(first),
            'second': name_of(second),
            'winner': name_of(winner),
            'first_score': result['first_total'],
            'second_score': result['second_total'],
        }

    def match_line(match):
        return (f"{match['first']} против {match['second']} -> {match['winner']} "
                f"({match['first_score']}:{match['second_score']})")

    groups = [[] for _ in range(GROUP_COUNT)]
    # Deal players across groups evenly while preserving the selected roster order.
    for index, path in enumerate(paths):
        groups[index % GROUP_COUNT].append(path)

    report = ['ГРУППОВОЙ ЭТАП']
    qualifiers = []
    group_standings = []
    for group_index, group in enumerate(groups):
        group_name = chr(ord('A') + group_index)
        table = {
            path: {'wins': 0, 'for': 0, 'against': 0}
            for path in group
        }
        for first, second in combinations(group, 2):
            result = Fight.play(first, second)
            first_total = result['first_total']
            second_total = result['second_total']
            table[first]['for'] += first_total
            table[first]['against'] += second_total
            table[second]['for'] += second_total
            table[second]['against'] += first_total
            winner = result['winner_path']
            table[winner]['wins'] += 1

        ranked = sorted(
            group,
            key=lambda path: (
                table[path]['wins'],
                table[path]['for'] - table[path]['against'],
                table[path]['for'],
                name_of(path).casefold(),
            ),
            reverse=True,
        )
        group_table = []
        report.extend(['', f'Группа {group_name} - таблица:'])
        for rank, path in enumerate(ranked, start=1):
            stats = table[path]
            name = name_of(path)
            group_table.append({
                'rank': rank,
                'name': name,
                'wins': stats['wins'],
                'for': stats['for'],
                'against': stats['against'],
            })
            report.append(
                f'{rank}. {name} - побед: {stats["wins"]}, '
                f'очки: {stats["for"]}:{stats["against"]}'
            )
        group_standings.append({'name': group_name, 'standings': group_table})
        qualifiers.extend(ranked[:ADVANCE_PER_GROUP])

    def play_round(title, label, pairs):
        report.append(title)
        winners, matches = [], []
        for index, (first, second) in enumerate(pairs, start=1):
            winner, match = play_match(first, second)
            winners.append(winner)
            matches.append(match)
            report.append(f'  {label}{index}: {match_line(match)}')
        return winners, matches

    report.extend(['', 'СЕТКА ПЛЕЙ-ОФФ'])
    quarter_winners, quarterfinals = play_round('Четвертьфинал:', 'ЧФ', (
        (qualifiers[0], qualifiers[3]),
        (qualifiers[2], qualifiers[1]),
        (qualifiers[4], qualifiers[7]),
        (qualifiers[6], qualifiers[5]),
    ))
    semifinal_winners, semifinals = play_round('Полуфинал:', 'ПФ', (
        (quarter_winners[0], quarter_winners[1]), (quarter_winners[2], quarter_winners[3]),
    ))
    champion, final = play_match(*semifinal_winners)
    champion_points = Fight.change_points(champion, 50)
    report.extend([
        'Финал:',
        f'  {match_line(final)}',
        '',
        f'ПОБЕДИТЕЛЬ: {final["winner"]}',
        '',
        'Формат: 4 группы, по 2 лучших из каждой выходят в четвертьфинал.',
    ])
    return {
        'winner': final['winner'],
        'report': '\n'.join(report),
        'groups': groups,
        'champion_path': champion,
        'champion_points': champion_points,
        'bracket': {
            'quarterfinals': quarterfinals,
            'semifinals': semifinals,
            'final': final,
        },
        'group_standings': group_standings,
    }
