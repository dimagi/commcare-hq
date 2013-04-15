from __future__ import absolute_import
import pdb
from django.conf import settings
import git
import time
from subprocess import Popen, PIPE
import os
from datetime import datetime
import pytz
import simplejson




def get_project_repo():
    """
    Get the root git repo object for the project's root settings.
    """
    repo = git.Repo(settings.FILEPATH)
    return repo

def sub_git_remote_url(git_dir):
    p = Popen(
        [
            'git',
            '--git-dir',
            git_dir,
            'config',
            '--get',
            "remote.origin.url"
        ],
        stdout=PIPE,
        stderr=PIPE)
    gitout = p.stdout.read().strip()
    return gitout

def sub_git_info(git_dir):
    p = Popen(
        [
            'git',
            '--git-dir',
            git_dir,
            'log',
            '-1',
            "--pretty=format:{%n  \"sha\": \"%H\",%n  \"author\": \"%an <%ae>\",%n  \"date\": \"%ai\",%n  \"subject\": \"%s\"%n, \"message\": \"%b\"%n}"
        ],
        stdout=PIPE,
        stderr=PIPE)
    gitout = p.stdout.read().strip()
    url = sub_git_remote_url(git_dir)

    commit_dict = simplejson.loads(gitout)
    commit_dict['commit_url'] = get_commit_url(url, commit_dict['sha'])
    commit_dict['compare_master'] = get_compare_url(url, commit_dict['sha'], 'master')
    return commit_dict



def sub_git_submodules(git_dir):
    p = Popen(
        [
            'git',
            '--git-dir',
            git_dir,
            'submodule',
            'status'
        ],
        stdout=PIPE,
        stderr=PIPE
    )
    gitout = p.stdout.read().split('\n')

    for x in gitout:
        splits = x.strip().split(' ')
        if len(splits) == 3:
            yield {
                'sha': splits[0].strip(),
                'path': splits[1],
                'branch': splits[2],
            }

def submodule_info_hack(repo, prior_project=None):
    """
    A hacky thing to get at least the submodule commit URL from the submodule info.
    It's a bit of a mess due to how we submodule call, gitpython has issues figuring out what's
    going on.
    """

    ret = {}
    for s in repo.iter_submodules():
        git_dir = os.path.join(settings.FILEPATH, '.git', 'modules', s.name)

        subm = {}
        sub_key = s.url.split('/')[-1].split('.')[0]
        subm['local_name'] = s.name.replace('submodules/', '')
        #p = Popen(['git', '--git-dir', git_dir, 'log', '-1'], stdout=PIPE, stderr=PIPE)
        #http://cfmumbojumbo.com/cf/index.cfm/coding/convert-your-git-log-to-json/
        p = Popen(['git', '--git-dir', git_dir, 'log', '-1', "--pretty=format:{%n  \"sha\": \"%H\",%n  \"author\": \"%an <%ae>\",%n  \"date\": \"%ai\",%n  \"subject\": \"%s\"%n, \"message\": \"%b\"%n}"], stdout=PIPE, stderr=PIPE)
        gitout = p.stdout.read().strip()
        commit_dict = simplejson.loads(gitout)
        commit_dict['commit_url'] = get_commit_url(s.url, s.hexsha)
        commit_dict['compare_master'] = get_compare_url(s.url, s.hexsha, 'master')

        subm['commit'] = commit_dict

        # if prior_project:
        #     prev_submodules = prior_project['submodules']
        #     if sub_key in prev_submodules:
        #         subm['prior_commit'] =

        ret[sub_key] = subm
    return ret


def get_latest_commit_info(repo, commit_limit=5, from_sha=None):
    """
    Snapshot the commit info for current running repo.
    Args:
    commit_limit: basic check for last <int> commits
    from_sha: compare directly via a
    """
    commits = repo.iter_commits()
    commit_count = 0

    if compare_previous:
        # find last commit for given type
        pass


    while True:
        commit = commit_info(commits.next())
        yield commit
        commit_count += 1
        if from_sha is None:
            if commit_count == commit_limit:
                break
        if from_sha == commit['sha']:
            #print "it's equal, break"
            break
        # else:
        #     print "#%s# != #%s#" % (from_sha, commit['sha'])


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


def split_commit_info(commit):
    """
    helper function to get the relevant commit repo url and commit hexsha
    commit is a Gitpython commit object
    """
    return commit.repo.remote().url, commit.hexsha


def commit_info(commit):
    """
    Return json object of relevant info on the commit for the given repo
    """
    ret = {}
    ret['author'] = "%s" % commit.author.name if commit.author.name != "" else commit.author.email
    ret['branch'] = commit.repo.active_branch.name
    ret['date'] = datetime.isoformat(datetime.fromtimestamp(commit.committed_date, tz=pytz.utc))
    ret['message'] = commit.message.strip()
    ret['sha'] = commit.hexsha
    ret['commit_url'] = get_commit_url(*split_commit_info(commit))

    commit_repo_url, commit_hash = split_commit_info(commit)

    ret['compare_master'] = get_compare_url(commit_repo_url, commit_hash, 'master')

    #since last deploy
    #ret['compare_url'] = get_compare_url(*split_commit_info(commit))
    return ret


def get_project_info(commits=5, from_sha=None, compare_previous=False, environment=None):
    repo = get_project_repo()
    return {
        #'repo': repo,
        'project_branch': repo.active_branch.name,

        'last_commits': list(get_latest_commit_info(repo, commits, from_sha=from_sha)),
        'submodules': submodule_info_hack(repo)
    }
