def strip_location(profile_url, location):
    base = '/'.join(profile_url.split('/')[:-1]) + '/'

    def strip_left(prefix):
        string = location
        if string.startswith(prefix):
            return string[len(prefix):]

    return strip_left('./') or strip_left(base) or strip_left('jr://resource/') or location
