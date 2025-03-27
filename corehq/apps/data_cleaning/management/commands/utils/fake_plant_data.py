import datetime
import random
import uuid

from corehq.apps.data_cleaning.management.commands.utils import issues


def get_plant_name():
    name = random.choice((
        "Aloe Vera", "Spider Plant", "Snake Plant", "Pothos", "Peace Lily",
        "Rubber Plant", "ZZ Plant", "Monstera", "Fiddle Leaf Fig", "Philodendron",
        "Parlor Palm", "Calathea", "Succulent", "Cactus", "Bamboo Palm",
        "Bird of Paradise", "Dracaena", "English Ivy", "Fern", "Palm",
        "Orchid", "Begonia", "Coleus", "Dumb Cane", "Jade Plant",
        "Moth Orchid", "Ponytail Palm", "Prayer Plant", "Rattlesnake Plant",
        "Swiss Cheese Plant", "Umbrella Plant", "Wax Plant", "Yucca",
        "African Violet", "Air Plant", "Asparagus Fern", "Boston Fern",
        "Cast Iron Plant", "Chinese Evergreen", "Croton", "Dieffenbachia",
        "Dragon Tree", "Elephant Ear", "Fiddle Leaf Fig", "Ficus",
        "Flamingo Flower", "Flamingo Lily", "Flamingo Plant", "Flamingo Flower",
        "Flamingo Lily", "Flamingo Plant", "Flamingo Flower", "Flamingo Lily",
    ))
    # add whitespace issues
    spaces = issues.get_random_spaces()
    if issues.is_mostly_false():
        # throw in a return characer for funsies
        spaces = spaces + '\n'
    return name.replace(" ", spaces)


def get_plant_submission_dates():
    time_start = datetime.datetime.now() - datetime.timedelta(random.choice(range(1, 365)))
    tz = datetime.timezone(datetime.timedelta(hours=1))
    time_start = time_start.astimezone(tz)

    # Format time_start with milliseconds and timezone offset (e.g., "2025-03-26T16:56:11.256+01")
    time_start_str = time_start.isoformat(timespec='milliseconds')

    # time_end: random time between 1 and 5 minutes after time_start
    delta_seconds = random.randint(60, 300)  # 60 to 300 seconds
    time_end = time_start + datetime.timedelta(seconds=delta_seconds)
    time_end_str = time_end.isoformat(timespec='milliseconds')

    # last_watered_on: random date within 14 days before time_start
    days_offset_watered = random.randint(0, 13)
    last_watered_date = (time_start - datetime.timedelta(days=days_offset_watered)).date()
    last_watered_on = last_watered_date.isoformat()  # Format: "YYYY-MM-DD"

    # last_watered_time: seconds value from time_start.
    # Here we calculate seconds since midnight (including fractions of a second)
    last_watered_time_val = (
        time_start.hour * 3600 + time_start.minute * 60 + time_start.second + time_start.microsecond / 1e6
    )
    last_watered_time = str(last_watered_time_val)

    # last_watered_datetime: same date as last_watered_on, but with a random time on that day.
    random_hour = random.randint(0, 23)
    random_minute = random.randint(0, 59)
    random_second = random.randint(0, 59)
    last_watered_datetime = datetime.datetime.combine(
        last_watered_date, datetime.time(random_hour, random_minute, random_second)
    )
    last_watered_datetime_str = last_watered_datetime.strftime("%Y-%m-%d %H:%M:%S")

    # last_repotted: random date up to 2 years (730 days) before time_start
    days_offset_repotted = random.randint(0, 730)
    last_repotted_date = (time_start - datetime.timedelta(days=days_offset_repotted)).date()
    last_repotted = last_repotted_date.isoformat()  # Format: "YYYY-MM-DD"

    # for simulating bad values where dates are expected in user input fields
    def _not_a_date():
        return random.choice((
            'x', 'not a date', 'no', 'nope',
        ))

    return {
        "time_start": time_start_str,
        "time_end": time_end_str,
        "last_watered_on": (
            issues.simulate_missing_value_issues(last_watered_on)
            or issues.simulate_missing_value_issues(_not_a_date())
        ),
        "last_watered_time": (
            issues.simulate_missing_value_issues(last_watered_time)
            or issues.simulate_missing_value_issues(_not_a_date())
        ),
        "last_watered_datetime": (
            issues.simulate_missing_value_issues(last_watered_datetime_str)
            or issues.simulate_missing_value_issues(_not_a_date())
        ),
        "last_repotted": (
            issues.simulate_missing_value_issues(last_repotted)
            or issues.simulate_missing_value_issues(_not_a_date())
        ),
    }


def get_plant_nickname():
    return random.choice((
        "Green Giant", "Leafy Beauty", "Eco Elegance", "Green Machine", "Leafy Wonder",
        "Eco Warrior", "Green Goddess", "Leafy Dream", "Eco Queen", "Green Thumb",
        "Leafy Queen", "Eco King", "Green King", "Leafy King", "Eco Prince",
        "Green Prince", "Leafy Prince", "Eco Princess", "Green Princess", "Leafy Princess",
        "Eco Empress", "Green Empress", "Leafy Empress", "Eco Emperor", "Green Emperor",
        "Leafy Emperor", "Eco Knight", "Green Knight", "Leafy Knight", "Eco Lady",
        "Foliage Friend", "Eco Friend", "Green Friend", "Leafy Friend", "Eco Buddy",
        "Green Buddy", "Leafy Buddy", "Eco Pal", "Green Pal", "Leafy Pal", "Eco Companion",
        "Green Companion", "Leafy Companion", "Eco Partner", "Green Partner", "Leafy Partner",
        "Sprout Star", "Eco Star", "Green Star", "Leafy Star", "Eco Hero", "Green Hero",
        "Leafy Hero", "Eco Legend", "Green Legend", "Leafy Legend", "Eco Myth", "Green Myth",
        "Leafy Myth", "Eco Magic", "Green Magic", "Leafy Magic", "Eco Miracle", "Green Miracle",
        "Leafy Miracle", "Eco Marvel", "Green Marvel", "Leafy Marvel", "Eco Wonder",
        "Lush Legacy", "Eco Legacy", "Green Legacy", "Leafy Legacy", "Eco Dynasty",
        "Green Dynasty", "Leafy Dynasty", "Eco Realm", "Green Realm", "Leafy Realm",
        "Eco Domain", "Green Domain", "Leafy Domain", "Eco Haven", "Green Haven",
        "Leafy Haven", "Eco Oasis", "Green Oasis", "Leafy Oasis", "Eco Retreat",
        "Serene Sprout", "Eco Serenity", "Green Serenity", "Leafy Serenity", "Eco Zen",
        "Green Zen", "Leafy Zen", "Eco Harmony", "Green Harmony", "Leafy Harmony",
        "Eco Balance", "Green Balance", "Leafy Balance", "Eco Peace", "Green Peace",
        "Leafy Peace", "Eco Tranquility", "Green Tranquility", "Leafy Tranquility",
        "Eco Calm", "Green Calm", "Leafy Calm", "Eco Bliss", "Green Bliss", "Leafy Bliss",
        "Eco Joy", "Green Joy", "Leafy Joy", "Eco Happiness", "Green Happiness",
        "Leafy Happiness", "Eco Cheer", "Green Cheer", "Leafy Cheer", "Eco Delight",
    ))


def get_plant_description():
    return random.choice((
        "Thrives in bright, indirect sunlight and adds a fresh vibe to indoor spaces.",
        "A low-maintenance plant that's perfect for beginners and busy plant parents.",
        "Known for its air-purifying properties and ability to remove toxins from the air.",
        "A popular choice for offices and homes due to its hardiness and adaptability.",
        "A versatile plant that can grow in a variety of conditions and light levels.",
        "A great choice for plant lovers who want to add a touch of green to their space.",
        "A beautiful plant that adds a touch of elegance and style to any room.",
        "A classic plant that's easy to care for and looks great in any setting.",
        "A striking plant with unique foliage that makes a statement in any room.",
        "A timeless addition that transforms rooms into lush, vibrant sanctuaries.",
        "A plant that's perfect for creating a calming, peaceful atmosphere in your home.",
        "A plant that's sure to brighten your day and bring a smile to your face.",
        "A plant that's as beautiful as it is easy to care for and maintain.",
        "A plant that's perfect for creating a cozy, inviting atmosphere in your home.",
        "A plant that's perfect for adding a touch of nature to your indoor spaces.",
        "Quick-growing and vibrant, creating a mini indoor jungle.",
        "A plant that's perfect for adding a pop of color to your home or office.",
        "A plant that's perfect for creating a relaxing, stress-free environment.",
        "A plant that's perfect for adding a touch of nature to your home or office.",
        "Known for its resilience, adapting well to various humidity levels.",
        "Glossy leaves not only beautify the room but also help purify the air.",
        "A plant that's perfect for adding a touch of green to your home or office.",
        "A plant that's perfect for adding a touch of nature to your living space.",
        "A plant that's perfect for creating a peaceful, serene environment.",
        "A plant that's perfect for creating a calming, tranquil atmosphere.",
        "A plant that's perfect for adding a touch of green to your living space.",
        "Brings a splash of nature with its robust and thriving greenery.",
        "A hardy houseplant perfect for low maintenance and beginner care.",
        "A plant that's perfect for creating a cozy, inviting atmosphere.",
        "A plant that's perfect for adding a touch of green to your living space.",
        "A plant that's perfect for creating a calming, tranquil atmosphere.",
    ))


def get_health_indicators():
    # this includes values that aren't part of the form (simulating a removed option)
    options = [
        'yellow_leaves', 'pests', 'fungus', 'root_rot', 'underwatered',
    ]
    count = random.randint(1, len(options))
    selected_options = random.sample(options, count)
    return " ".join(selected_options)


def get_pot_type():
    # this includes values that aren't part of the form (simulating a removed option)
    return random.choice((
        'ceramic', 'terra_cotta', 'plastic', 'metal', 'wooden',
    ))


def get_user_details(commcare_users):
    user = random.choice(commcare_users)
    return user.username, user.get_id


def get_plant_case_data_with_issues(commcare_users):
    """
    Returns the following:
        - plant_name
        - nickname
        - description
        - height_cm
        - num_leaves
        - last_watered_on
        - last_watered_time
        - last_watered_datetime
        - last_repotted
        - health_indicators
        - pot_type
        - case_id
        - time_start
        - time_end
        - user_id
        - form_id
    """
    plant_name = get_plant_name()
    dates_data = get_plant_submission_dates()
    nickname = get_plant_nickname()
    description = get_plant_description()
    health_idindicators = get_health_indicators()
    pot_type = get_pot_type()
    username, user_id = get_user_details(commcare_users)
    height = round(random.uniform(1, 500), 1)
    height_cm = issues.simulate_missing_value_issues(height)
    num_leaves = random.randint(1, 1000)
    return {
        "plant_name": issues.simulate_free_input_issues(plant_name, is_missing=False),
        "nickname": issues.simulate_free_input_issues(nickname),
        "description": issues.simulate_free_input_issues(description),
        "height_cm": height_cm,
        "height": height if height_cm is None else None,  # simulate a renamed property
        "num_leaves": issues.simulate_missing_value_issues(num_leaves),
        "health_indicators": issues.simulate_missing_value_issues(health_idindicators),
        "pot_type": issues.simulate_missing_value_issues(pot_type),
        "user_id": user_id,
        "username": username,
        "case_id": uuid.uuid4(),
        "form_id": uuid.uuid4(),
        **dates_data
    }
