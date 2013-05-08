
# TODO: make this a legit command line tool?

import os
import sys
import json
import requests

upload_url = sys.argv[1]

token = os.environ['GH_TOKEN']
commit = os.environ['TRAVIS_COMMIT']
repo_slug = os.environ['TRAVIS_REPO_SLUG']

requests.post('https://api.github.com/repos/%s/statuses/%s' % (repo_slug, commit),
    headers = { 'Authorization: token %s' % token },
    data = json.dumps({
        'state': 'success',
        'description': 'The Travis CI build passed. See coverage report.',
        'target_url': upload_url
    }),
)
