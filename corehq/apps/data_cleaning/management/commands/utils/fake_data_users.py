import random

DATA_EDITING_TEST_USER_PREFIX = 'dc.plantcare'


def get_first_name():
    return random.choice(
        (
            'Alice',
            'Bob',
            'Charlie',
            'David',
            'Eve',
            'Frank',
            'Grace',
            'Hannah',
            'Isaac',
            'Jane',
            'Kevin',
            'Linda',
            'Michael',
            'Nancy',
            'Oscar',
            'Pamela',
            'Quincy',
            'Rachel',
            'Steve',
            'Tina',
            'Ulysses',
            'Vivian',
            'Walter',
            'Xavier',
            'Yvonne',
            'Zach',
        )
    )


def get_last_name():
    return random.choice(
        (
            'Rodriguez',
            'Lewis',
            'Lee',
            'Walker',
            'Hall',
            'Allen',
            'Young',
            'Hernandez',
            'King',
            'Wright',
            'Lopez',
            'Smith',
            'Johnson',
            'Williams',
            'Jones',
            'Brown',
            'Davis',
            'Miller',
            'Wilson',
            'Moore',
            'Taylor',
            'Thomas',
            'Jackson',
            'White',
            'Harris',
            'Martin',
            'Thompson',
            'Garcia',
            'Martinez',
            'Robinson',
            'Clark',
        )
    )
