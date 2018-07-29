from __future__ import absolute_import
from __future__ import unicode_literals
from manage_cloudant import authenticate_cloudant_instance, run_ask_runs

if __name__ == '__main__':

    import argparse

    parser = argparse.ArgumentParser(description='Revoke Cloudant API key access to databases')
    parser.add_argument('api_key_to_revoke')
    parser.add_argument('--databases', dest='databases', nargs='+')
    parser.add_argument('--username', dest='username', required=True,
                        help='Cloudant username')
    args = parser.parse_args()

    cloudant_instance = authenticate_cloudant_instance(args.username)

    ask_runs = []
    for database in args.databases:
        ask_runs.append(
            cloudant_instance.get_db(database).revoke_api_key_access(args.api_key_to_revoke))

    run_ask_runs(ask_runs)
