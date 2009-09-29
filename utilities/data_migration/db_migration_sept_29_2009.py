# The following script performs a database-level migration from
# an old server (pre 9/29/2009) to a new server (post 9/29/2009).
#
# add authenticated_to to receiver.models.Submission
# adds unsalted_password to hq.models.ExtUser

from django.db import connection
from receiver.models import Submission
from hq.models import ExtUser

def run():
    print "starting update"
    _perform_table_migration()
    print "finished update"
    
def _perform_table_migration():
    cursor = connection.cursor()
    
    cursor.execute("ALTER TABLE `receiver_submission` ADD COLUMN `authenticated_to_id` INT(11) DEFAULT NULL AFTER `raw_post`;")
    cursor.execute("ALTER TABLE `receiver_submission` ADD KEY `receiver_submission_authenticated_to_id` (`authenticated_to_id`);")
    cursor.execute("ALTER TABLE `hq_extuser` ADD COLUMN `unsalted_password` varchar(128) DEFAULT NULL AFTER `reporter_id`;")
    
    submits = Submission.objects.all()[0:20]
    print "checking 20 submits"
    for submit in submits:
        if submit.authenticated_to != None:
            print "%s submission has strange authenticated value %s" % (submit.id, submit.authenticated_to)
        else:
            print "%s submission updated correctly" % submit.id

    users = ExtUser.objects.all()
    print "checking all extusers"
    for user in users:
        if user.unsalted_password != None:
            print "%s extuser has strange password value %s" % (user.id, user.unsalted_password)
        else:
            print "%s extuser updated correctly" % user.id
