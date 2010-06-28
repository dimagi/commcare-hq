from django_digest.testsettings import *

DATABASE_ENGINE = 'mysql' 
DATABASE_STORAGE_ENGINE = 'InnoDB'
DATABASE_HOST = 'localhost'
DATABASE_PORT = 3306
DATABASE_NAME = 'django_digest'
DATABASE_USER = 'root'
DATABASE_PASSWORD = ''

try:
    from django_digest.developer_settings import *
except ImportError:
    pass
