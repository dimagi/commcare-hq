from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
    )
    help = 'Outputs to STDOUT apache config for your project.'
    args = "mkserverstatic [project_name]"

    nginx_example = """
    location /%%( {
        root %(static_root)s;
        root %(static_root)s;
        expires 30d;
        access_log off;
    }
    """


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
        </VirtualHost>
        """

        arg_dict = {}
        if len(args) != 1:
            raise CommandError('Usage is %s' % self.args)

        arg_dict['project_name'] = args[0]

        static_url_path = settings.STATIC_URL.split('/')
        while static_url_path.count('') > 0:
            static_url_path.remove('')
        arg_dict['static_path'] = '/' + '/'.join([args[0]] + static_url_path) + '/' #include leading and trailing slashes

        media_url_path = settings.MEDIA_URL.split('/')
        while media_url_path.count('') > 0:
            media_url_path.remove('')
        arg_dict['media_path'] = '/' + '/'.join([args[0]] + media_url_path) + '/' #include leading and trailing slashes

        arg_dict['static_root'] = settings.STATIC_ROOT
        arg_dict['media_root'] = settings.MEDIA_ROOT
        print outstring % arg_dict
