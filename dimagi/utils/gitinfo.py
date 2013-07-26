from __future__ import absolute_import
from subprocess import Popen, PIPE
import simplejson

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
    p = Popen(
        [
            'git',
            '--git-dir',
            git_dir
        ] + args,
        stdout=PIPE, stderr=PIPE
    )
    return p


def sub_get_current_branch(git_dir):
    args = [
        'rev-parse',
        '--abbrev-ref',
        'HEAD'
    ]
    p = sub_git_cmd(git_dir, args)
    return p.stdout.read().strip()


def get_project_snapshot(git_dir, submodules=False):
    root_info = sub_git_info(git_dir)
    root_info['current_branch'] = sub_get_current_branch(git_dir)
    if submodules:
        root_info['submodules'] = list(sub_git_submodules(git_dir))
    return root_info



def sub_git_info(git_dir, ref_count=1):
    info_dict = {}

    args = ['log',
            '-%s' % ref_count,
            #"""--pretty=format:{%n \"sha\": \"%H\",%n  \"author\": \"%an <%ae>\",%n \"date\": \"%ai\",%n \"subject\": \"%s\",%n \"message\": \"%b\"%n}"""
            """--pretty=format:{ \"sha\": \"%H\",  \"author\": \"%an <%ae>\", \"date\": \"%ai\", \"subject\": \"%s\", \"message\": \"%b\"}"""
        ]
    p = sub_git_cmd(git_dir, args)
    gitout = p.stdout.read().strip()
    revs = gitout.split('\n')
    url = sub_git_remote_url(git_dir)
    revsstring = '[%s]' % ','.join(revs)

    commit_list = simplejson.loads(revsstring)
    info_dict['commits'] = commit_list
    info_dict['commit_url'] = get_commit_url(url, commit_list[0]['sha'])
    info_dict['compare_master'] = get_compare_url(url, commit_list[0]['sha'], 'master')
    return info_dict



def sub_git_submodules(git_dir):
    """
    Using shell, get the active submodule info
    """
    args =['submodule', 'status' ]
    p = sub_git_cmd(git_dir, args)
    gitout = p.stdout.read().split('\n')

    for x in gitout:
        splits = x.strip().split(' ')
        if len(splits) == 3:
            yield {
                'sha': splits[0].strip(),
                'path': splits[1],
                'branch': splits[2],
            }


######
# bad gitypython stuff
# def get_project_repo():
#     """
#     Get the root git repo object for the project's root settings.
#     """
#     repo = git.Repo(settings.FILEPATH)
#     return repo


# def submodule_info_hack(repo, prior_project=None):
#     """
#     A hacky thing to get at least the submodule commit URL from the submodule info.
#     It's a bit of a mess due to how we submodule call, gitpython has issues figuring out what's
#     going on.
#     """
#
#     ret = {}
#     for s in repo.iter_submodules():
#         git_dir = os.path.join(settings.FILEPATH, '.git', 'modules', s.name)
#
#         subm = {}
#         sub_key = s.url.split('/')[-1].split('.')[0]
#         subm['local_name'] = s.name.replace('submodules/', '')
#         #p = Popen(['git', '--git-dir', git_dir, 'log', '-1'], stdout=PIPE, stderr=PIPE)
#         #http://cfmumbojumbo.com/cf/index.cfm/coding/convert-your-git-log-to-json/
#         p = Popen(['git', '--git-dir', git_dir, 'log', '-1', "--pretty=format:{%n  \"sha\": \"%H\",%n  \"author\": \"%an <%ae>\",%n  \"date\": \"%ai\",%n  \"subject\": \"%s\"%n, \"message\": \"%b\"%n}"], stdout=PIPE, stderr=PIPE)
#         gitout = p.stdout.read().strip()
#         commit_dict = simplejson.loads(gitout)
#         commit_dict['commit_url'] = get_commit_url(s.url, s.hexsha)
#         commit_dict['compare_master'] = get_compare_url(s.url, s.hexsha, 'master')
#
#         subm['commit'] = commit_dict
#
#         # if prior_project:
#         #     prev_submodules = prior_project['submodules']
#         #     if sub_key in prev_submodules:
#         #         subm['prior_commit'] =
#
#         ret[sub_key] = subm
#     return ret


# def get_latest_commit_info(repo, commit_limit=5, from_sha=None):
#     """
#     Snapshot the commit info for current running repo.
#     Args:
#     commit_limit: basic check for last <int> commits
#     from_sha: compare directly via a
#     """
#     commits = repo.iter_commits()
#     commit_count = 0
#
#     if from_sha:
#         # find last commit for given type
#         pass
#
#
#     while True:
#         commit = commit_info(commits.next())
#         yield commit
#         commit_count += 1
#         if from_sha is None:
#             if commit_count == commit_limit:
#                 break
#         if from_sha == commit['sha']:
#             #print "it's equal, break"
#             break
#         # else:
#         #     print "#%s# != #%s#" % (from_sha, commit['sha'])


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

