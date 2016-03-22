from __future__ import print_function
import re
from django.template.loader import render_to_string
import requests
from gevent.pool import Pool


def get_deploy_email_message_body(environment, user, compare_url):
    import sh
    git = sh.git.bake(_tty_out=False)
    current_deploy, last_deploy = _get_last_two_deploys(environment)
    pr_merges = git(
        'log', '{}...{}'.format(last_deploy, current_deploy),
        oneline=True, grep='Merge pull request #'
    ).strip().split('\n')
    pr_numbers = [int(re.search(r'Merge pull request #(\d+)', line).group(1))
                  for line in pr_merges if line]
    pool = Pool(5)
    pr_infos = pool.map(_get_pr_info, pr_numbers)

    return render_to_string('hqadmin/partials/project_snapshot.html', {
        'pr_merges': pr_infos,
        'last_deploy': last_deploy,
        'current_deploy': current_deploy,
        'user': user,
        'compare_url': ('https://github.com/dimagi/commcare-hq/compare/{}...{}'
                        .format(last_deploy, current_deploy)),
        'compare_url_check': compare_url,
    })


def _get_last_two_deploys(environment):
    import sh
    git = sh.git.bake(_tty_out=False)
    pipe = git('tag')
    pipe = sh.grep(pipe, environment)
    pipe = sh.sort(pipe, '-rn')
    pipe = sh.head(pipe, '-n2')
    return pipe.strip().split('\n')


def _get_pr_info(pr_number):
    url = 'https://api.github.com/repos/dimagi/commcare-hq/pulls/{}'.format(pr_number)
    json_response = requests.get(url).json()
    assert pr_number == json_response['number'], (pr_number, json_response['number'])
    additions = json_response['additions']
    deletions = json_response['deletions']

    line_changes = additions + deletions

    return {
        'number': json_response['number'],
        'title': json_response['title'],
        'opened_by': json_response['user']['login'],
        'url': json_response['html_url'],
        'merge_base': json_response['base']['label'],
        'merge_head': json_response['head']['label'],
        'additions': additions,
        'deletions': deletions,
        'line_changes': line_changes,
    }

if __name__ == '__main__':
    def setup_fake_django():
        from django.conf import settings
        import os
        settings.configure(
            TEMPLATE_LOADERS=('django.template.loaders.filesystem.Loader',),
            TEMPLATE_DIRS=(os.path.join(os.path.dirname(__file__), '..', 'templates'),),
        )
    import sys
    if sys.argv[1] == 'get_deploy_email_message_body':
        setup_fake_django()
        print(get_deploy_email_message_body(*sys.argv[2:5]).encode('utf-8'))
