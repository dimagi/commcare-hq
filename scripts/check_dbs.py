from django.contrib.auth.models import User

from couchforms.models import XFormInstance

def run():
    db = XFormInstance.get_db()
    print db.view("couchforms/by_user", limit=2).all()
    users = User.objects.all()
    print users[0:10]



