from .localsettings_docker import *

USE_PARTITIONED_DATABASE = True
PARTITION_DATABASE_CONFIG = get_partitioned_database_config(USE_PARTITIONED_DATABASE)
