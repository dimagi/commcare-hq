import django
# Compatability mode for older django versioning for hash management


if django.get_version() < '1.4':
    from django.contrib.auth.models import get_hexdigest
    def make_password(password, salt=None):
        import random
        algo = 'sha1'
        if not salt:
            salt = get_hexdigest(algo, str(random.random()), str(random.random()))[:5]
        hsh = get_hexdigest(algo, salt, password)
        return '%s$%s$%s' % (algo, salt, hsh)
else:
    from django.contrib.auth.hashers import make_password
