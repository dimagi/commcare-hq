import re
from collections import defaultdict
from github import Github
from django.template.loader import render_to_string
import requests
from gevent.pool import Pool

LABELS_TO_EXPAND = [
    "product/all-users-all-environments",
    "product/prod-india-all-users",
    "product/feature-flag",
    "product/all-users",
]


def get_deploy_email_message_body(user, compare_url):
    try:
        ref_comparison = compare_url.split('/')[-1]
        last_deploy, current_deploy = ref_comparison.split('...')
    except ValueError:
        # Not a real compare_url
        last_deploy = current_deploy = 'Unavailable'
        pr_infos = []
    else:
        pr_numbers = _get_pr_numbers(last_deploy, current_deploy)
        pool = Pool(5)
        pr_infos = [_f for _f in pool.map(_get_pr_info, pr_numbers) if _f]

    prs_by_label = _get_prs_by_label(pr_infos)

    return render_to_string('hqadmin/partials/project_snapshot.html', {
        'pr_merges': pr_infos,
        'prs_by_label': prs_by_label,
        'last_deploy': last_deploy,
        'current_deploy': current_deploy,
        'user': user,
        'compare_url': compare_url,
    })


def _get_pr_numbers(last_deploy, current_deploy):
    repo = Github().get_organization('dimagi').get_repo('commcare-hq')
    last_deploy_sha = repo.get_commit(last_deploy).sha
    current_deploy_sha = repo.get_commit(current_deploy).sha
    comparison = repo.compare(last_deploy_sha, current_deploy_sha)

    return [
        int(re.search(r'Merge pull request #(\d+)', repo_commit.commit.message).group(1))
        for repo_commit in comparison.commits
        if repo_commit.commit.message.startswith('Merge pull request')
    ]


def _get_pr_info(pr_number):
    url = 'https://api.github.com/repos/dimagi/commcare-hq/pulls/{}'.format(pr_number)
    json_response = requests.get(url).json()
    if not json_response.get('number'):
        # We've probably exceed our rate limit for unauthenticated requests
        return None
    assert pr_number == json_response['number'], (pr_number, json_response['number'])
    additions = json_response['additions']
    deletions = json_response['deletions']

    line_changes = additions + deletions

    labels = _get_pr_labels(pr_number)

    return {
        'number': json_response['number'],
        'title': json_response['title'],
        'body': json_response['body'],
        'opened_by': json_response['user']['login'],
        'url': json_response['html_url'],
        'merge_base': json_response['base']['label'],
        'merge_head': json_response['head']['label'],
        'additions': additions,
        'deletions': deletions,
        'line_changes': line_changes,
        'labels': labels,
    }


def _get_pr_labels(pr_number):
    url = 'https://api.github.com/repos/dimagi/commcare-hq/issues/{}'.format(pr_number)
    json_response = requests.get(url).json()
    if not json_response.get('number'):
        # We've probably exceed our rate limit for unauthenticated requests
        return []
    assert pr_number == json_response['number'], (pr_number, json_response['number'])

    return [
        {'name': label['name'], 'color': label['color']}
        for label in json_response['labels']
    ]


def _get_prs_by_label(pr_infos):
    prs_by_label = defaultdict(list)
    for pr in pr_infos:
        for label in pr['labels']:
            if label['name'] in LABELS_TO_EXPAND:
                prs_by_label[label['name']].append(pr)
    return dict(prs_by_label)


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
        print(get_deploy_email_message_body(*sys.argv[3:5]).encode('utf-8'))
