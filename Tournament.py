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
                characters[path].get('name', path.stem).casefold(),
            ),
            reverse=True,
        )
        group_table = []
        report.extend(['', f'Группа {group_name} - таблица:'])
        for rank, path in enumerate(ranked, start=1):
            stats = table[path]
            name = characters[path].get('name', path.stem)
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

    report.extend(['', 'СЕТКА ПЛЕЙ-ОФФ'])
    quarterfinal_pairs = (
        (qualifiers[0], qualifiers[3]),
        (qualifiers[2], qualifiers[1]),
        (qualifiers[4], qualifiers[7]),
        (qualifiers[6], qualifiers[5]),
    )
    quarter_winners = []
    quarterfinals = []
    report.append('Четвертьфинал:')
    for index, (first, second) in enumerate(quarterfinal_pairs, start=1):
        result = Fight.play(first, second)
        winner = result['winner_path']
        quarter_winners.append(winner)
        quarterfinals.append({
            'first': characters[first].get('name', first.stem),
            'second': characters[second].get('name', second.stem),
            'winner': characters[winner].get('name', winner.stem),
            'first_score': result['first_total'],
            'second_score': result['second_total'],
        })
        report.append(
            f'  ЧФ{index}: {characters[first].get("name", first.stem)} '
            f'против {characters[second].get("name", second.stem)} '
            f'-> {characters[winner].get("name", winner.stem)} '
            f'({result["first_total"]}:{result["second_total"]})'
        )

    semifinal_pairs = ((quarter_winners[0], quarter_winners[1]), (quarter_winners[2], quarter_winners[3]))
    semifinal_winners = []
    semifinals = []
    report.append('Полуфинал:')
    for index, (first, second) in enumerate(semifinal_pairs, start=1):
        result = Fight.play(first, second)
        winner = result['winner_path']
        semifinal_winners.append(winner)
        semifinals.append({
            'first': characters[first].get('name', first.stem),
            'second': characters[second].get('name', second.stem),
            'winner': characters[winner].get('name', winner.stem),
            'first_score': result['first_total'],
            'second_score': result['second_total'],
        })
        report.append(
            f'  ПФ{index}: {characters[first].get("name", first.stem)} '
            f'против {characters[second].get("name", second.stem)} '
            f'-> {characters[winner].get("name", winner.stem)} '
            f'({result["first_total"]}:{result["second_total"]})'
        )

    first, second = semifinal_winners
    final_result = Fight.play(first, second)
    champion = final_result['winner_path']
    champion_points = Fight.change_points(champion, 50)
    final = {
        'first': characters[first].get('name', first.stem),
        'second': characters[second].get('name', second.stem),
        'winner': characters[champion].get('name', champion.stem),
        'first_score': final_result['first_total'],
        'second_score': final_result['second_total'],
    }
    report.extend([
        'Финал:',
        f'  {characters[first].get("name", first.stem)} '
        f'против {characters[second].get("name", second.stem)} '
        f'-> {characters[champion].get("name", champion.stem)} '
        f'({final_result["first_total"]}:{final_result["second_total"]})',
        '',
        f'ПОБЕДИТЕЛЬ: {characters[champion].get("name", champion.stem)}',
        '',
        'Формат: 4 группы, по 2 лучших из каждой выходят в четвертьфинал.',
    ])
    return {
        'winner': characters[champion].get('name', champion.stem),
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
