from couchdbkit.ext.django.schema import Document, StringProperty, StringListProperty


class MobileIndicatorSet(Document):
    domain = StringProperty(required=True)
    indicator_set_name = StringProperty(required=True)
    indicator_set = StringProperty(required=True)
    columns = StringListProperty(required=True)

    @classmethod
    def by_domain(cls, domain):
        key = [domain, 'MobileIndicatorSet']
        sets = MobileIndicatorSet.view('domain/docs',
                                       startkey=key,
                                       endkey=key + [{}],
                                       reduce=False,
                                       include_docs=True).all()

        return sets


class MobileIndicatorOwner(Document):
    domain = StringProperty()
    indicator_set_id = StringProperty()
    owner_id = StringProperty()
    owner_type = StringProperty(choices=['user', 'group'])

    @classmethod
    def by_indicator_set_owner_type(cls, domain, indicator_set_id, owner_type):
        ownerships = MobileIndicatorOwner.view('indicator_fixtures/ownership',
                                               key=[domain, 'by_indicator_set_owner_type',
                                                    owner_type, indicator_set_id],
                                               include_docs=True,
                                               reduce=False).all()

        return ownerships

    @classmethod
    def by_owner(cls, owner_id, domain):
        ownerships = MobileIndicatorOwner.view('indicator_fixtures/ownership',
                                               keys=[domain, 'by_owner', owner_id],
                                               include_docs=True,
                                               reduce=False).all()

        return ownerships
