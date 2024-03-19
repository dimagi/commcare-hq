class Color:
    RED = "91"
    GREEN = "92"
    YELLOW = "93"


def get_break_line(character, break_length):
    return character * int(break_length / len(character))


def get_style_func(color_code):
    return lambda x: f"\033[{color_code}m{x}\033[00m"
