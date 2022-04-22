
SIZE_LIMIT = 1000000

# this is what ES's maxClauseCount is currently set to, can change this config
# value if we want to support querying over more domains
MAX_CLAUSE_COUNT = 1024

# Default scroll parameters (same values hard-coded in elasticsearch-py's
# `scan()` helper).
SCROLL_KEEPALIVE = '5m'
SCROLL_SIZE = 1000

# index settings
INDEX_CONF_REINDEX = {
    "index.refresh_interval": "1800s",
    "index.max_result_window": SIZE_LIMIT,
}

INDEX_CONF_STANDARD = {
    "index.refresh_interval": "5s",
    "index.max_result_window": SIZE_LIMIT,
}
