from couchdbkit.ext.django.schema import *
import util


class Review(Document):

    domain = StringProperty()
    original_doc = StringProperty()
    title = StringProperty() # for example "Great App"
    rating = IntegerProperty() # for example "4 (out of 5)"
    user = StringProperty() # for example "stank"
    date_published = DateTimeProperty()
    info = StringProperty() # for example "this app has a few bugs, but it works great overall!"
    nickname = StringProperty()

    @classmethod
    def get_by_app(cls, app_name):
        result = cls.view("appstore/by_app",
            key=app_name,
            reduce=False,
            include_docs=True).all()
        return result

    @classmethod
    def get_by_version(cls, version_name):
        result = cls.view("appstore/by_app",
            groups=True,
            group_level=2,
            key=version_name,
            reduce=False,
            include_docs=True).all()
        return result

    @classmethod
    def get_average_rating_by_app(cls, app_name):
        result = cls.get_db().view("appstore/by_app",
            key=app_name,
            reduce=True,
            include_docs=False)
        if result:
            assert len(result) == 1
            row = result.one()
            return row['value']['sum'] / row['value']['count']
        return result



    @classmethod
    def get_average_rating_by_version(cls, version_name):
        result = cls.view("appstore/by_app",
            key=version_name,
            reduce=True,
            include_docs=False,
            groups=True,
            group_level=2)
        return result['sum'] / result['count']

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
        return result