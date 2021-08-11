#! /usr/bin/env python
import sys
import sh


def main():
    domain = get_domain()
    while domain:
        act = prompt(ACTIONS, domain)
        if act is None:
            break
        try:
            act(domain)
        except MigrationFinished:
            domain = get_domain()


def get_domain():
    return input("Domain name: ")


def migrate_finish(domain):
    py("manage.py", "migrate_domain_from_couch_to_sql", domain, "MIGRATE", "--finish")


def migrate_patch(domain):
    py("manage.py", "migrate_domain_from_couch_to_sql", domain, "MIGRATE", "--patch")


def commit_migration(domain):
    py("manage.py", "migrate_domain_from_couch_to_sql", domain, "COMMIT", "--no-input")
    raise MigrationFinished


def recommit_migration(domain):
    print("This is meant be used when a previous COMMIT failed with the error:")
    print(f"could not set use_sql_backend for domain {domain} (try again)")
    answer = input("Type 'commit' to continue: ")
    if answer != "commit":
        print("Abort.")
        return
    import_statement = "from corehq.apps.couch_sql_migration.progress import set_couch_sql_migration_complete"
    py(
        "manage.py", "shell", "-c",
        f'{import_statement}; set_couch_sql_migration_complete("{domain}")',
    )
    raise MigrationFinished


def show_stats(domain):
    py("manage.py", "migrate_domain_from_couch_to_sql", domain, "stats")


def show_diffs(domain):
    args = prompt(DIFF_ARGS, domain)
    if not args:
        return
    sh.less(
        sh.python("manage.py", "couch_sql_diff", domain, "show", *args.split(), _piped=True),
        _in=sys.stdin,
        _out=sys.stdout,
        _err=sys.stderr,
    )


def prompt(choices, domain):
    print(f"\nOptions for {domain} migration:")
    for opt in choices:
        print(f"  {opt}")
    while True:
        answer = input("Your choice: ").strip()
        if not answer:
            return None
        opts = {key[:len(answer)]: val for key, val in choices.items()}
        if len(choices) != len(opts):
            print("Non-unique choice: ", answer)
            continue
        try:
            return opts[answer]
        except KeyError:
            print("Invalid choice: ", answer)


def py(*args, **kw):
    try:
        sh.python(*args, _in=sys.stdin, _out=sys.stdout, _err=sys.stderr, **kw)
    except sh.ErrorReturnCode as err:
        print(f"ERROR {err.full_cmd} -> {err.exit_code}")


class MigrationFinished(Exception):
    pass


ACTIONS = {
    "finish": migrate_finish,
    "patch": migrate_patch,
    "commit": commit_migration,
    "redo commit": recommit_migration,
    "diff": show_diffs,
    "stats": show_stats,
    "quit": None,
}


DIFF_ARGS = {
    "1: --select=CommCareCase": "--select=CommCareCase",
    "2: --select=CommCareCase --changes": "--select=CommCareCase --changes",
    "3: --select=XFormInstance": "--select=XFormInstance",
    "abort": None,
}


if __name__ == "__main__":
    main()
