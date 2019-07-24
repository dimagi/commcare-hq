from __future__ import absolute_import
from __future__ import unicode_literals
import os
import re
from subprocess import Popen, PIPE


def git_file_deltas(git_dir, commit, compare=None):
    #source: http://stackoverflow.com/a/2713363
    pass


def sub_git_remote_url(git_dir):
    args = ['config', '--get', "remote.origin.url"]
    with sub_git_cmd(git_dir, args) as p:
        gitout = p.stdout.read().decode('utf-8').strip()
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
    # else:
    #     raise Exception("Error, the .git location for %s doesn't exists" % git_dir)

    try:
        p = Popen(
            [
                'git',
                '--git-dir',
                git_dir_to_use,
            ] + args,
            stdout=PIPE, stderr=PIPE
        )
    except OSError as e:
        # Is git missing ?
        if e.errno == 2:
            e.strerror += ": git"
        raise(e)

    return p


def sub_get_current_branch(git_dir):
    #HT: http://stackoverflow.com/a/12142066
    args = [
        'rev-parse',
        '--abbrev-ref',
        'HEAD'
    ]
    with sub_git_cmd(git_dir, args) as p:
        gitout = p.stdout.read().decode('utf-8').strip()
    return gitout


def get_project_snapshot(git_dir, submodules=False, log_count=1, submodule_count=1):
    root_info = sub_git_info(git_dir, log_count=log_count)
    root_info['current_branch'] = sub_get_current_branch(git_dir)
    if submodules:
        root_info['submodules'] = list(sub_git_submodules(git_dir, log_count=submodule_count))
    return root_info


def sub_git_info(git_dir, log_count=1):
    """
    Given a git dir and log count, return a json formatted representation
    """
    return_dict = {}
    kv_line_format = {
        'sha': '%H',
        'author': '%an <%ae>',
        'date': '%ai',
        'subject': '%s',
        'message': '%b'
    }

    KV_DELIMITER = ':~@#$~:'
    LINE_DELIMITER = '@#\n#@'

    # construct an output of git log that is essentially a:
    # key=value
    # key=value, etc
    # but a sing a custom Key=Value delimiter, and a custom Line delimiter since
    # there might be newlines in messages and subjects
    # the git log -z format delimits the entire log by null, but we need separation of each property

    line_by_line_format = LINE_DELIMITER.join(['%s%s%s' % (k, KV_DELIMITER, v) for k, v in kv_line_format.items()])

    args = ['log',
            '-%s' % log_count,
            '-z',
            '--pretty=format:%s' % line_by_line_format
    ]
    with sub_git_cmd(git_dir, args) as p:
        gitout = p.stdout.read().decode('utf-8').strip()
    url = sub_git_remote_url(git_dir)
    all_raw_revs = gitout.split('\0')

    def parse_rev_block(block_text):
        ret = {}
        for prop in block_text.split(LINE_DELIMITER):
            if len(prop) == 0:
                continue
            try:
                k, v = prop.split(KV_DELIMITER)
            except ValueError:
                k = "GitParseError"
                v = prop
            ret[k] = v
        return ret
    commit_list = [parse_rev_block(s) for s in all_raw_revs]

    for commit in commit_list:
        commit['commit_url'] = get_commit_url(url, commit['sha'])
        commit['compare_master'] = get_compare_url(url, commit['sha'], 'master')

    return_dict['commits'] = commit_list
    return return_dict


def get_git_sub_info(git_dir, sub_path, log_count=1):
    full_sub_path = os.path.join(git_dir, sub_path)
    sub_info = sub_git_info(full_sub_path, log_count=log_count)
    return sub_info


def sub_git_submodules(git_dir, log_count=1):
    """
    Using shell, get the active submodule info
    """
    args =['submodule', 'status' ]
    with sub_git_cmd(git_dir, args) as p:
        gitout = p.stdout.read().decode('utf-8').strip()

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
    if re.search(r'^\w+://', repo_url):
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

