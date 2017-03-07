from __future__ import print_function
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Outputs to STDOUT apache config for your project runtime.'

    def add_arguments(self, parser):
        parser.add_argument('host')
        parser.add_argument('port')

    def handle(self, host, port, **options):
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

        print(outstring % {
            'host': host,
            'port': port,
        })
