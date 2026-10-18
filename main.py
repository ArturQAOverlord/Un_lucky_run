import random
import data
from pathlib import Path

class character():
    def __init__(self, name):
        self.name = name.title()
        print(f'{name}, значит? Интересно...')

        self.points = 1

        self.substory = None
        self.race = None
        self.subrace = None
        self.size = None

        self.strength = None
        self.speed = None
        self.iq = None
        self.fighting = None

        self.weapon = None
        self.weapon_mastery = None
        self.weapon_enchantment = None
        
        self.ability = None
        self.ability_power = None
        self.chaos = None

        self.title = None
        self.live_status = True


def substory_giver(character):
    character.substory = random.choices(data.substory_sum, weights=data.substory_weights, k=1)[0]

    print(f'{character.substory}, вот кем ты был') 

def race_giver(character):
    character.race = random.choices(list(data.race_sum.keys()), weights=data.race_weights, k=1)[0]
    character.subrace = random.choices(data.race_sum[character.race], weights=data.race_subrace_weights[character.race], k=1)[0]

    print(f'Ты - {character.subrace} {character.race} ')

def size_giver(character):
    character.size = random.choices(data.size_sum, weights=data.size_weights, k=1)[0]
    print(f'Твой рост - {character.size}')

def strength_giver(character):
    character.strength = random.choices(data.strength_sum, weights=data.strength_weights, k=1)[0]
    print(f'Твоя физическая сила - {character.strength}')

def speed_giver(character):
    character.speed = random.choices(data.speed_sum, weights=data.speed_weights, k=1)[0]
    print(f'Твоя скорость - {character.speed}')

def iq_giver(character):
    character.iq = random.choices(data.iq_sum, weights=data.iq_weights, k=1)[0]
    print(f'По-уму ты - {character.iq}')

def fighting_giver(character):
    character.fighting = random.choices(data.fighting_sum, weights=data.fighting_weights, k=1)[0]
    print(f'Твое искусство боя - {character.fighting}')

def weapon_giver(character):
    character.weapon = random.choices(data.weapon_sum, weights=data.weapon_weights, k=1)[0]
    if character.weapon != 'Без оружия':
        character.weapon_mastery = random.choices(data.weapon_mastery_sum, weights=data.weapon_mastery_weights, k=1)[0]
        character.weapon_enchantment = random.choices(data.weapon_enchantment_sum, weights=data.weapon_enchantment_weights, k=1)[0]
        print(f'Твое Оружие - {character.weapon}, а владение им - {character.weapon_mastery}')
        print(f'У твоего оружия есть зачарование - {character.weapon_enchantment}' if character.weapon_enchantment != 'Без зачарования' else f'Зачарования на оружии у тебя нет')
    else:
        print(f'Оружия у тебя нет, какая досада...')
        

def ability_giver(character):
    character.ability = random.choices(data.ability_sum, weights=data.ability_weights, k=1)[0]
    if character.ability != 'Без силы':
        character.ability_power = random.choices(data.ability_power_sum, weights=data.ability_power_weights, k=1)[0]

    print(f'Твоя способность - {character.ability}, и в ней ты - {character.ability_power}' if character.ability != 'Без силы' else f'И родился ты без способностей, экая оказия...')

def chaos_giver(character):
    if random.random() > 0.7:
        character.chaos = random.choices(data.chaos_sum, weights=data.chaos_weights, k=1)[0]
        print(f'При рождении ты был тронут высшими силами, ты - {character.chaos}')
    else:
        print(f'При рождении никакие высшие силы тебя не одарили...')

def title_giver(character):
    character.title = random.choices(data.title_sum, weights=data.title_weights, k=1)[0]

    print(f'Твой титул - {character.title}')

def file_creation(character):
    characters_dir = Path(__file__).resolve().parent / 'Characters'
    characters_dir.mkdir(exist_ok=True)
    with open(characters_dir / f'{character.name}.txt', 'w', encoding='UTF-8') as file:
        for k, v in character.__dict__.items():
            file.write(f'{k}: {v}\n')


def generate_character(name, save=True):
    """Generate a character and return it."""
    current_char = character(name)
    substory_giver(current_char)
    race_giver(current_char)
    size_giver(current_char)
    strength_giver(current_char)
    speed_giver(current_char)
    iq_giver(current_char)
    fighting_giver(current_char)
    weapon_giver(current_char)
    ability_giver(current_char)
    chaos_giver(current_char)
    title_giver(current_char)
    if save:
        file_creation(current_char)
    return current_char


if __name__ == '__main__':
    generate_character(input('Character name: '))
