import subprocess


def get_commit_command(message, as_string=False):
    message = message.replace('"', '\'')  # make sure there are no double-quotes
    commit_command = ["git", "commit", "--no-verify", f"--message=\"Bootstrap 5 Migration - {message}\""]
    if as_string:
        return " ".join(commit_command)
    return commit_command


def get_commit_string(message):
    return get_commit_command(message, as_string=True)


def apply_commit(message):
    commit_command = get_commit_command(message)
    subprocess.call([
        "git", "add", ".",
    ])
    subprocess.call(commit_command)


def has_no_pending_git_changes():
    status = subprocess.Popen(
        ["git", "status"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    return "nothing to commit" in str(status.communicate()[0])
