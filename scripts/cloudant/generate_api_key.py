from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from manage_cloudant import authenticate_cloudant_instance, run_ask_runs

if __name__ == '__main__':

    import argparse

    parser = argparse.ArgumentParser(description='Generate New Cloudant API key')
    parser.add_argument('--username', dest='username', required=True,
                        help='Cloudant username')
    parser.add_argument('--databases', dest='databases', nargs='*')
    parser.add_argument('--admin', dest='admin', nargs='?', const=True, default=False)
    args = parser.parse_args()

    cloudant_instance = authenticate_cloudant_instance(args.username)
    api_key, api_password = cloudant_instance.generate_api_key().ask_and_run()
    print('New API key generated.')
    print('API Key:', api_key)
    print('API Password:', api_password)

    ask_runs = []

    for database in args.databases:
        ask_runs.append(cloudant_instance.get_db(database)
                        .grant_api_key_access(api_key, admin=args.admin))

    run_ask_runs(ask_runs)
