import multiprocessing
preload_app = True
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = 'gevent'
keepalive = 60
timeout = 900
max_requests = 240
# defaults to 30 sec, setting to 5 minutes to fight `GreenletExit`s
graceful_timeout = 5*60
# cryptically, setting forwarded_allow_ips (to the ip of the hqproxy0)
# gets gunicorn to set https on redirects when appropriate. See:
# http://docs.gunicorn.org/en/latest/configure.html#secure-scheme-headers
# http://docs.gunicorn.org/en/latest/configure.html#forwarded-allow-ips
forwarded_allow_ips = '10.176.162.109'

def post_fork(server, worker):
    # hacky way to address gunicorn gevent requests hitting django too early before urls are loaded
    # see: https://github.com/benoitc/gunicorn/issues/527#issuecomment-19601046
    from django.core.urlresolvers import resolve
    resolve('/')
