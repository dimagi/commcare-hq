from couchdbkit.ext.django.schema import *
import util


class Review(Document):

    domain = StringProperty()
    title = StringProperty() # for example "Great App"
    rating = IntegerProperty() # for example "4 (out of 5)"
    user = StringProperty() # for example "stank"
    date_published = DateTimeProperty()
    info = StringProperty() # for example "this app has a few bugs, but it works great overall!"
    nickname = StringProperty()

    @classmethod
    def get_by_app(cls, name):
        result = cls.view("appstore/by_app",
            key=name,
            reduce=False,
            include_docs=True).all()
        return result