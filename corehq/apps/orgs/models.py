from couchdbkit.ext.django.schema import *
import util

class Organization(Document):
    name = StringProperty() # for example "worldvision"
    title = StringProperty() # for example "World Vision"

    #metadata
    email = StringProperty()
    url = StringProperty()
    location = StringProperty()


    @classmethod
    def get_by_name(cls, name):
        result = cls.view("orgs/by_name",
            key=name,
            reduce=False,
            include_docs=True).first()
        return result

    @classmethod
    def get_by_title(cls, title):
        result = cls.view("orgs/by_title",
            key=title,
            reduce=False,
            include_docs=True).first()
        return result

