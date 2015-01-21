

def get_server_url(http_method, server_root, username, password):
    if username and password:
        return '%(http_method)s://%(user)s:%(pass)s@%(server)s' % {
            'http_method': http_method,
            'user': username,
            'pass': password,
            'server': server_root,
        }
    else:
        return '%(http_method)s://%(server)s' % {
            'http_method': http_method,
            'server': server_root,
        }


def get_dynamic_db_settings(server_root, username, password, dbname,
                            use_https=False):
    """
    Get dynamic database settings.
    Other apps can use this if they want to change settings

    """

    http_method = 'https' if use_https else 'http'
    server_url = get_server_url(http_method, server_root, username, password)
    database = '%(server)s/%(database)s' % {
        'server': server_url,
        'database': dbname,
    }
    return {
        'COUCH_SERVER':  server_url,
        'COUCH_DATABASE': database,
    }


def _make_couchdb_tuple(row, couch_database_url):

    if isinstance(row, basestring):
        app_label = row
        return app_label, couch_database_url
    else:
        app_label, postfix = row
        return app_label, '%s__%s' % (couch_database_url, postfix)


def make_couchdb_tuples(config, couch_database_url):
    """
    Helper function to generate couchdb tuples
    for mapping app name to couch database URL.

    """
    return [_make_couchdb_tuple(row, couch_database_url) for row in config]


def get_extra_couchdbs(config, couch_database_url):
    """
    Create a mapping from database prefix to database url

    :param config:              list of database strings or tuples
    :param couch_database_url:  main database url
    """
    extra_dbs = {}
    for row in config:
        if isinstance(row, tuple):
            _, postfix = row
            extra_dbs[postfix] = '%s__%s' % (couch_database_url, postfix)

    return extra_dbs


def celery_failure_handler(task, exc, task_id, args, kwargs, einfo):
    from redis.exceptions import ConnectionError
    from redis_cache.exceptions import ConnectionInterrumped
    if isinstance(exc, (ConnectionInterrumped, ConnectionError)):
        task.retry(exc, max_retries=3, countdown=60 * 5)
