from __future__ import absolute_import
import os
from subprocess import Popen, PIPE
import simplejson


def git_file_deltas(git_dir, commit, compare=None):
    #source: http://stackoverflow.com/a/2713363
    pass


def sub_git_remote_url(git_dir):
    args = ['config', '--get', "remote.origin.url"]
    p = sub_git_cmd(git_dir, args)
    gitout = p.stdout.read().strip()
    return gitout

def sub_git_cmd(git_dir, args):
    """
    run git command
    args are the full command with args

    git_dir, the actual full path of the .git/ repo directory to run commands against

    returns popen object for access to stdout+stderr
    """
    git_dir_to_use = None
    if os.path.exists(os.path.join(git_dir, '.git')):
        #ok file exists
        git_dir_to_use = os.path.join(git_dir, '.git')
    elif os.path.isfile(os.path.join(git_dir, '.git')):
        #it's a submodule, dereference the actual git info
        git_dir_to_use = os.path.join(git_dir, '.git')

    p = Popen(
        [
            'git',
            '--git-dir',
            git_dir_to_use,
        ] + args,
        stdout=PIPE, stderr=PIPE
    )
    # else:
    #     raise Exception("Error, the .git location for %s doesn't exists" % git_dir)
    return p


def sub_get_current_branch(git_dir):
    #HT: http://stackoverflow.com/a/12142066
    args = [
        'rev-parse',
        '--abbrev-ref',
        'HEAD'
    ]
    p = sub_git_cmd(git_dir, args)
    return p.stdout.read().strip()


def get_project_snapshot(git_dir, submodules=False, log_count=1, submodule_count=1):
    root_info = sub_git_info(git_dir, log_count=log_count)
    root_info['current_branch'] = sub_get_current_branch(git_dir)
    if submodules:
        root_info['submodules'] = list(sub_git_submodules(git_dir, log_count=submodule_count))
    return root_info

def sub_git_info(git_dir, log_count=1):
    info_dict = {}

    args = ['log',
            '-%s' % log_count,
            """--pretty=format:{ \"sha\": \"%H\",  \"author\": \"%an <%ae>\", \"date\": \"%ai\", \"subject\": \"%s\", \"message\": \"%b\"}"""
        ]
    p = sub_git_cmd(git_dir, args)
    gitout = p.stdout.read().strip()
    revs = gitout.split('\n')
    url = sub_git_remote_url(git_dir)
    revsstring = '[%s]' % ','.join(revs)

    commit_list = simplejson.loads(revsstring.replace('\t', '\u0009'))
    for commit in commit_list:
        commit['commit_url'] = get_commit_url(url, commit['sha'])
        commit['compare_master'] = get_compare_url(url, commit['sha'], 'master')

    info_dict['commits'] = commit_list
    return info_dict


def get_git_sub_info(git_dir, sub_path, log_count=1):
    full_sub_path = os.path.join(git_dir, sub_path)
    sub_info = sub_git_info(full_sub_path, log_count=log_count)
    return sub_info

def sub_git_submodules(git_dir, log_count=1):
    """
    Using shell, get the active submodule info
    """
    args =['submodule', 'status' ]
    p = sub_git_cmd(git_dir, args)
    gitout = p.stdout.read().split('\n')

    for x in gitout:
        splits = x.strip().split(' ')
        if len(splits) == 3:
            sub_sha = splits[0].strip()
            sub_path = splits[1]
            sub_log = get_git_sub_info(git_dir, sub_path, log_count=log_count)
            sub_log['path'] = sub_path
            sub_log['branch'] = splits[2]
            sub_log['sha_sha'] = sub_sha
            yield sub_log

def split_repo_url(repo_url):
    """
    Repo url splits to [git_account, git_repo]
    even if it's git://, or git@

    """
    if repo_url.startswith('git://') or repo_url.startswith("https://"):
        chunks = repo_url.split("/")[-2:]
    elif repo_url.startswith("git@"):
        chunks = repo_url.split(':')[-1].split('/')
    return chunks


def get_commit_url(repo_url, hexsha, compare=False):
    chunks = split_repo_url(repo_url)
    url = "https://github.com/%s/%s/commit/%s" % (chunks[0], chunks[1].replace('.git', ''), hexsha)
    return url


def get_compare_url(repo_url, start_cmp, end_cmp):
    chunks = split_repo_url(repo_url)
    url = "https://github.com/%(account)s/%(repo)s/compare/%(start_cmp)s...%(end_cmp)s" % {
        "account": chunks[0],
        "repo": chunks[1].replace('.git', ''),
        "start_cmp": start_cmp,
        "end_cmp": end_cmp
    }
    return url

