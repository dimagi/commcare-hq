from corehq.apps.es import UserES
from corehq.toggles import all_toggles


def find_static_toggle(slug):
    for toggle in all_toggles():
        if toggle.slug == slug:
            return toggle


def get_dimagi_users(domain):
    res = (
        UserES()
        .web_users()
        .domain(domain)
        .term('username', 'dimagi.com')
        .size(10)
        .source('username')
        .run()
    )
    usernames = [r['username'] for r in res.hits]
    if res.total > 10:
        usernames.append('...')
    return ', '.join(usernames)
