"""
Generate apache conf for static content
NOTE that this should go before the conf for dynamic content

"""

from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = "Outputs apache config for your project to STDOUT"
    args = "mkapacheconf [django_port]"

    def handle(self, *args, **options):
        outstring = """
        <VirtualHost *:80>
                Alias %(media_path)s %(media_root)s/
                Alias %(static_path)s %(static_root)s/

                <Directory %(static_root)s>
                    Order deny,allow
                    Allow from all
                </Directory>

                <Directory %(media_root)s>
                    Order deny,allow
                    Allow from all
                </Directory>

                ProxyPass %(media_path)s !
                ProxyPass %(static_path)s !

                ProxyPass / http://localhost:%(django_port)s/
                ProxyPassReverse / http://localhost:%(django_port)s/
        </VirtualHost>
        """

        arg_dict = {}
        try:
            arg_dict['django_port'] = str(args[0])
        except IndexError:
            arg_dict['django_port'] = '8000'
        arg_dict['static_root'] = settings.STATIC_ROOT
        arg_dict['media_root'] = settings.MEDIA_ROOT
        arg_dict['static_path'] = settings.STATIC_URL
        arg_dict['media_path'] = settings.MEDIA_URL

        print outstring % arg_dict


