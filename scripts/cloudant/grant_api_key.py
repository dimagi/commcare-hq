from __future__ import absolute_import
from __future__ import unicode_literals
from manage_cloudant import authenticate_cloudant_instance, run_ask_runs

if __name__ == '__main__':

    import argparse

    parser = argparse.ArgumentParser(description='Grant Cloudant API key access to databases')
    parser.add_argument('api_key_to_grant')
    parser.add_argument('--databases', dest='databases', nargs='+')
    parser.add_argument('--username', dest='username', required=True,
                        help='Cloudant username')
    parser.add_argument('--admin', dest='admin', nargs='?', const=True, default=False)
    args = parser.parse_args()

    cloudant_instance = authenticate_cloudant_instance(args.username)

    ask_runs = []

    for database in args.databases:
        ask_runs.append(cloudant_instance.get_db(database)
                        .grant_api_key_access(args.api_key_to_grant, admin=args.admin))

    run_ask_runs(ask_runs)
