from __future__ import absolute_import
from __future__ import unicode_literals
from manage_cloudant import authenticate_cloudant_instance, run_ask_runs

if __name__ == '__main__':

    import argparse

    parser = argparse.ArgumentParser(description='Create New Cloudant databases')
    parser.add_argument('--username', dest='username', required=True,
                        help='Cloudant username')
    parser.add_argument('--databases', dest='databases', nargs='+')
    args = parser.parse_args()

    cloudant_instance = authenticate_cloudant_instance(args.username)

    ask_runs = []

    for database in args.databases:
        if not cloudant_instance.database_exists(database):
            ask_runs.append(cloudant_instance.create_database(database))

    run_ask_runs(ask_runs)
