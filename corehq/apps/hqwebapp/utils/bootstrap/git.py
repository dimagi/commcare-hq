import subprocess

from corehq.apps.hqwebapp.utils.bootstrap.paths import get_git_path


def get_commit_command(message, as_string=False):
    message = message.replace('"', '\'')  # make sure there are no double-quotes
    commit_command = ["git", "commit", "--no-verify", f"--message=\"Bootstrap 5 Migration - {message}\""]
    if as_string:
        return " ".join(commit_command)
    return commit_command


def get_commit_string(message):
    return get_commit_command(message, as_string=True)


def apply_commit(message, renames=None):
    commit_command = get_commit_command(message)
    if renames is not None:
        for old_path, new_path in renames.items():
            subprocess.call([
                "git",
                "mv",
                get_git_path(old_path),
                get_git_path(new_path),
            ])
    subprocess.call([
        "git", "add", ".",
    ])
    subprocess.call(commit_command)


def has_pending_git_changes():
    status = subprocess.Popen(
        ["git", "status"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    return "nothing to commit" not in str(status.communicate()[0])


def ensure_no_pending_changes_before_continuing():
    continue_message = "\nENTER to continue..."
    while True:
        if not has_pending_git_changes():
            break
        input(continue_message)
        continue_message = ("You still have un-committed changes. "
                            "Please commit these changes before continuing."
                            "\nENTER to continue...")
