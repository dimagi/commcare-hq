from __future__ import absolute_import
from django.conf import settings
import git
import time
from subprocess import Popen, PIPE
import os
from datetime import datetime
import pytz

def get_project_info(commits=5):
    repo = get_project_repo()
    return {'repo': repo,
           'last_commits': get_latest_commit_info(repo, commits),
           'submodules': submodule_info_hack(repo)
           }



def get_project_repo():
    """
    Get the root git repo object for the project's root settings.
    """
    repo = git.Repo(settings.FILEPATH)
    return repo

def submodule_info_hack(repo):
    """
    A hacky thing to get at least the submodule commit URL from the submodule info.
    It's a bit of a mess due to how we submodule call, gitpython has issues figuring out what's
    going on.
    """

    ret = []
    for s in repo.iter_submodules():
        git_dir = os.path.join(settings.FILEPATH, '.git', 'modules', s.name)

        subm = {}
        subm['sha'] = s.hexsha
        subm['commit_url'] = get_commit_url(s.url, s.hexsha)
        subm['compare_url'] = get_compare_url(s.url, s.hexsha)
        subm['name'] = s.name.replace('submodules/', '')
        p = Popen(['git', '--git-dir', git_dir, 'log', '-1'], stdout=PIPE, stderr=PIPE)
        gitout = p.stdout.read().strip()
        subm['info'] = gitout
        ret.append(subm)
    return ret

def get_latest_commit_info(repo, num):
    commits = repo.iter_commits()
    for x in range(num):
        yield commit_info(commits.next())

def split_repo_url(repo_url):
    if repo_url.startswith('git://') or repo_url.startswith("https://"):
        chunks = repo_url.split("/")[-2:]
    elif repo_url.startswith("git@"):
        chunks = repo_url.split(':')[-1].split('/')
    return chunks

def get_commit_url(repo_url, hexsha, compare=False):
    chunks = split_repo_url(repo_url)
    url = "https://github.com/%s/%s/commit/%s" % (chunks[0], chunks[1].replace('.git',''), hexsha)
    return url
def get_compare_url(repo_url, hexsha):
    chunks = split_repo_url(repo_url)
    url = "https://github.com/%s/%s/compare/%s...master" % (chunks[0], chunks[1].replace('.git',''), hexsha)
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
    ret['date'] = datetime.fromtimestamp(commit.committed_date, tz=pytz.utc)
    ret['message'] = commit.message.strip()
    ret['sha'] = commit.hexsha
    ret['commit_url'] = get_commit_url(*split_commit_info(commit))
    ret['compare_url'] = get_compare_url(*split_commit_info(commit))
    return ret
