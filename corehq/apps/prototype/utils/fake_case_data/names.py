import random


def get_dutch_name():
    first = random.choice((
        "Guusje", "Riny", "Noortje", "Fenne", "Eva", "Suze", "Anita",
        "Emmy", "Jana", "Hendrina", "Diede", "Rianne", "Heintje", "Elke", "Isabeau",
        "Else",
    ))
    last = random.choice((
        "Bakker", "Jansen", "Aadrens", "Aalbers", "De Jong", "De Vries",
        "Claasen", "Achterberg", "Van den Berg", "Visser",
    ))
    return first, last


def get_english_name():
    first = random.choice((
        "Brittney", "Wambdi", "Maple", "Aubrielle", "Breanna", "Chelsea", "Kori",
        "Susi", "Faye", "Chanelle", "Melanie", "Yolotli", "Lacie", "Dinah", "Darlene",
        "Iola", "Katy"
    ))
    last = random.choice((
        "Jones", "Thomas", "Evans", "Johnson", "Davis", "Miller", "Williams", "Garcia",
        "Brown", "Smith", "Rodriguez", "Taylor", "Jackson",
    ))
    return first, last


def get_spanish_name():
    first = random.choice((
        "Catalina", "Lucy", "Lizbeth", "Nadia", "Yamile", "Emmie", "Javiera", "Marisol",
        "Annalee", "Graciela", "Wilda", "Janella", "Twyla", "Cherice", "Glenda", "Elfleda",
        "Lauryn", "Genoveva",
    ))
    last = random.choice((
        "Rodriguez", "Garcia", "Hernandez", "Martinez", "Gomez", "Gonzalez", "Delgado",
        "Cano", "Flores", "Ruiz", "Ortiz", "Ramirez", "Torres",
    ))
    return first, last
