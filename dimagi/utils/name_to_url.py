import re

def name_to_url(name, default=""):
    url = re.sub(r'[^0-9a-z]+', '-', name.strip().lower())
    if re.search('^[0-9\-]*$', url) and default:
        url = "{}-{}".format(default, url)
    url = url.strip("-")
    return url
