from manage_cloudant import authenticate_cloudant_instance

if __name__ == '__main__':

    import argparse

    parser = argparse.ArgumentParser(description='Grant Cloudant API key access to databases')
    parser.add_argument('api_key_to_grant')
    parser.add_argument('--databases', dest='databases', nargs='+')
    parser.add_argument('--username', dest='username', required=True,
                        help='Cloudant username')
    args = parser.parse_args()

    cloudant_instance = authenticate_cloudant_instance(args.username)

    for database in args.databases:
        cloudant_instance.get_db(database).grant_api_key_access(args.api_key_to_grant)
