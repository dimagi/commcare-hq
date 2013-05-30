def prime_views(pool_size):
    """
    Prime the views so that a very large import doesn't cause the index
    to get too far behind
    """

    # These have to be included here or ./manage.py runserver explodes on
    # all pages of the app with single thread related errors
    from gevent.pool import Pool
    from dimagi.utils.management.commands import prime_views

    prime_pool = Pool(pool_size)
    prime_all = prime_views.Command()
    prime_all.prime_everything(prime_pool, verbose=True)
    prime_pool.join()
