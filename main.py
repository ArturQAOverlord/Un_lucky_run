import random
import data

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

        self.image = None

def substory_giver(character):
    character.substory = random.choice(data.substory_sum)

    print(f'{character.substory}, вот кем ты был') 

def race_giver(character):
    character.race = random.choice(list(data.race_sum.keys()))
    character.subrace = random.choice(data.race_sum[character.race])

    print(f'Ты - {character.subrace} {character.race} ')

def size_giver(character):
    character.size = random.choice(data.size_sum)
    print(f'Твой рост - {character.size}')

def strength_giver(character):
    character.strength = random.choice(data.strength_sum)
    print(f'Твоя физическая сила - {character.strength}')

def speed_giver(character):
    character.speed = random.choice(data.speed_sum)
    print(f'Твоя скорость - {character.speed}')

def iq_giver(character):
    character.iq = random.choice(data.iq_sum)
    print(f'По-уму ты - {character.iq}')

def fighting_giver(character):
    character.fighting = random.choice(data.fighting_sum)
    print(f'Твое искусство боя - {character.fighting}')

def weapon_giver(character):
    character.weapon = random.choice(data.weapon_sum)
    if character.weapon != 'Без оружия':
        character.weapon_mastery = random.choice(data.weapon_mastery_sum)
        character.weapon_enchantment = random.choice(data.weapon_enchantment_sum)
        print(f'Твое Оружие - {character.weapon}, а владение им - {character.weapon_mastery}')
        print(f'У твоего оружия есть зачарование - {character.weapon_enchantment}' if character.weapon_enchantment != 'Без зачарования' else f'Зачарования на оружии у тебя нет')
    else:
        print(f'Оружия у тебя нет, какая досада...')
        

def ability_giver(character):
    character.ability = random.choice(data.ability_sum)
    if character.ability != 'Без силы':
        character.ability_power = random.choice(data.ability_power_sum)

    print(f'Твоя способность - {character.ability}, и в ней ты - {character.ability_power}' if character.ability != 'Без силы' else f'И родился ты без способностей, экая оказия...')

def chaos_giver(character):
    if random.random() > 0.7:
        character.chaos = random.choice(data.chaos_sum)
        print(f'При рождении ты был тронут высшими силами, ты - {character.chaos}')
    else:
        print(f'При рождении никакие высшие силы тебя не одарили...')

def title_giver(character):
    character.title = random.choice(data.title_sum)

    print(f'Твой титул - {character.title}')

def file_creation(character):
    with open(f'Characters/{character.name}.txt', 'w', encoding='UTF-8') as file:
        for k, v in character.__dict__.items():
            file.write(f'{k}: {v}\n')
    file.close()



print()
current_char = character(input('Как зовут очередного героя? - '))
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
print()
print(current_char.__dict__)
file_creation(current_char)