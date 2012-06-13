from couchdbkit.ext.django.schema import *
import util
from django import forms
from django.db import models


class Organization(Document):
    name = StringProperty() # for example "worldvision"
    title = StringProperty() # for example "World Vision"

    #metadata
    email = StringProperty()
    url = StringProperty()
    location = StringProperty()
    logo_filename = StringProperty()

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

    def get_logo(self):
        if self.logo_filename:
            return (self.fetch_attachment(self.logo_filename), self._attachments[self.logo_filename]['content_type'])
        else:
            return None
