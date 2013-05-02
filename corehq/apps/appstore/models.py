from couchdbkit.ext.django.schema import *
from dimagi.utils.decorators.memoized import memoized

class SnapshotMixin(DocumentSchema):
    copy_history = StringListProperty()

    @property
    def is_copy(self):
        return True if self.copy_history else False

    @property
    @memoized
    def copied_from(self):
        doc_id = self.copy_history[-1] if self.is_copy else None
        if doc_id:
            doc = self.get(doc_id)
            return doc
        return None

    def get_updated_history(self):
        return self.copy_history + [self._id]

class Review(Document):

    domain = StringProperty()
    project_id = StringProperty() #the id of the project this rates
    title = StringProperty() # for example "Great App"
    rating = IntegerProperty() # for example "4 (out of 5)"
    user = StringProperty() # for example "stank"
    date_published = DateTimeProperty()
    info = StringProperty() # for example "this app has a few bugs, but it works great overall!"

    @classmethod
    def get_by_app(cls, app_name):
        result = cls.view("appstore/by_app",
            key=app_name,
            reduce=False,
            include_docs=True).all()
        return result

    @classmethod
    def get_by_version(cls, version_name):
        result = cls.view("appstore/by_version",
            startkey=[version_name],
            endkey=[version_name, {}],
            reduce=False,
            include_docs=True).all()
        return result

    @classmethod
    def get_by_version_and_user(cls, version_name, user):
        result = cls.view("appstore/by_version",
            key=[version_name, user],
            reduce=False,
            include_docs=True).all()
        return result

    @classmethod
    def get_average_rating_by_app(cls, app_id):
        result = cls.get_db().view("appstore/by_app",
            key=app_id,
            reduce=True,
            include_docs=False)

        if result:
            assert len(result) == 1
            row = result.one()
            return row['value']['sum'] / row['value']['count']
        return None

    @classmethod
    def get_average_rating_by_version(cls, version_name):
        result = cls.get_db().view("appstore/by_version",
            startkey=[version_name],
            endkey=[version_name, {}],
            reduce=True,
            include_docs=False)

        if result:
            assert len(result) == 1
            row = result.one()
            return row['value']['sum'] / row['value']['count']
        return None

    @classmethod
    def get_num_ratings_by_app(cls, app_name):
        result = cls.get_db().view("appstore/by_app",
            key=app_name,
            reduce=True,
            include_docs=False)
        if result:
            assert len(result) == 1
            row = result.one()
            return row['value']['count']
        return 0

    @classmethod
    def get_num_ratings_by_version(cls, version_name):
        result = cls.get_db().view("appstore/by_version",
            startkey=[version_name],
            endkey=[version_name, {}],
            reduce=True,
            include_docs=False)
        if result:
            assert len(result) == 1
            row = result.one()
            return row['value']['count']
        return 0
