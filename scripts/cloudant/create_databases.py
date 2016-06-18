from manage_cloudant import authenticate_cloudant_instance

if __name__ == '__main__':

    import argparse

    parser = argparse.ArgumentParser(description='Create New Cloudant databases')
    parser.add_argument('--username', dest='username', required=True,
                        help='Cloudant username')
    parser.add_argument('--databases', dest='databases', nargs='+')
    args = parser.parse_args()

    cloudant_instance = authenticate_cloudant_instance(args.username)

    for database in args.databases:
        if not cloudant_instance.database_exists(database):
            cloudant_instance.create_database(database)
