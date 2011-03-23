from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
    )
    help = 'Outputs to STDOUT apache config for your project runtime.'
    args = "mkserverinstance [host] [port]"

    def handle(self, *args, **options):
        outstring = """
        <VirtualHost *:80>
            SetEnv SendCL 1 #for chunked encoding
            SetEnv proxy-nokeepalive 1
            ProxyRequests Off
            ProxyPass / http://%(host)s:%(port)s/
            ProxyPassReverse / http://%(host)s:%(port)s/
            ServerName yourproject.com
            <Proxy *>
                AddDefaultCharset off
                Order deny,allow
                Allow from all
            </Proxy>
        </VirtualHost>
        """

        arg_dict = {}
        if len(args) != 2:
            raise CommandError('Usage is %s' % self.args)
        arg_dict['host'] = args[0]
        arg_dict['port'] = args[1]
        print outstring % arg_dict
