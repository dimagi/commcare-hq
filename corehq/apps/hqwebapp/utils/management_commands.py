class Color:
    RED = "91"
    GREEN = "92"
    YELLOW = "93"


def get_break_line(character, break_length):
    return character * int(break_length / len(character))


def get_style_func(color_code):
    return lambda x: f"\033[{color_code}m{x}\033[00m"


def select_option_from_prompt(prompt, options, default=None):
    if default:
        formatted_options = '/'.join([f'[{o}]' if o == default else o
                                      for o in options])
    else:
        formatted_options = '/'.join(options)
    prompt_with_options = f"{prompt} ({formatted_options}) "
    while True:
        option = input(prompt_with_options).lower()
        if option == "" and default:
            return default
        if option in options:
            break
        else:
            prompt_with_options = f'Sorry, "{option}" is not an option. ' \
                                  f'Please choose from [{formatted_options}]: '
    return option


def get_confirmation(prompt, default=None):
    option = select_option_from_prompt(prompt, ['y', 'n'], default=default)
    return option == 'y'
