import re

def name_to_url(name):
    return re.sub(r'[^0-9a-z]+', '-', name.strip().lower())
