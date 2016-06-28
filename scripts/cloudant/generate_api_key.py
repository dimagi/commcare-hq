from manage_cloudant import authenticate_cloudant_instance

if __name__ == '__main__':

    import argparse

    parser = argparse.ArgumentParser(description='Generate New Cloudant API key')
    parser.add_argument('--username', dest='username', required=True,
                        help='Cloudant username')
    parser.add_argument('--databases', dest='databases', nargs='*')
    args = parser.parse_args()

    cloudant_instance = authenticate_cloudant_instance(args.username)
    api_key, api_password = cloudant_instance.generate_api_key()
    print 'New API key generated.'
    print 'API Key:', api_key
    print 'API Password:', api_password
    for database in args.databases:
        cloudant_instance.get_db(database).grant_api_key_access(api_key)
