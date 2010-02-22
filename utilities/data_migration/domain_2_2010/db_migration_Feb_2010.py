# The following script performs a database-level migration from
# an old server (pre 2/2010) to a new server (post 2/2010).

# This script assumes it is running off an exact copy of the 
# OLD database, e.g. if a mysqldumb was run and used to create
# this database exactly.
#
# The primary change here is the turnkey integration done by ross
# which includes moving domains into their own app, getting rid of
# the ExtUser class, and doing email based domain registration and
# allowing users to belong to more than one domain. 
#

# this script is totally TODO