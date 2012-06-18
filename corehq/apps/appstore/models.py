from couchdbkit.ext.django.schema import *
import util


class Review(Document):
    title = StringProperty() # for example "Great App"
    rating = IntegerProperty() # for example "4 (out of 5)"
    user = StringProperty() # for example "stank"
    date_published = DateTimeProperty()
    info = StringProperty() # for example "this app has a few bugs, but it works great overall!"
