import subprocess

DEFAULT_GIT_PATH = "."


def get_commit_command(message, as_string=False, path=None):
    message = message.replace('"', '\'')  # make sure there are no double-quotes
    commit_command = ["git"]
    if path and path != DEFAULT_GIT_PATH:
        commit_command.extend(["-C", path])
    commit_command.extend(["commit", "--no-verify", f"--message=\"Bootstrap 5 Migration - {message}\""])
    if as_string:
        return " ".join(commit_command)
    return commit_command


def get_commit_string(message, path=None):
    return get_commit_command(message, as_string=True, path=path)


def apply_commit(message, path=None):
    path = path or DEFAULT_GIT_PATH
    commit_command = get_commit_command(message, path=path)
    subprocess.call([
        "git", "-C", path, "add", ".",
    ])
    subprocess.call(commit_command)


def has_pending_git_changes(path=None):
    path = path or DEFAULT_GIT_PATH
    status = subprocess.Popen(
        ["git", "-C", path, "status"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    return "nothing to commit" not in str(status.communicate()[0])


def get_working_directory(app_name):
    if app_name == "vellum":
        return "./submodules/formdesigner"
    return None


def ensure_no_pending_changes_before_continuing():
    continue_message = "\nENTER to continue..."
    while True:
        if not has_pending_git_changes():
            break
        input(continue_message)
        continue_message = ("You still have un-committed changes. "
                            "Please commit these changes before continuing."
                            "\nENTER to continue...")
