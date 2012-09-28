from corehq.apps.domain.models import Domain



def handle(v, text):

    print Domain.get_by_name(v.domain).__dict__

    # look up domain
    # is it commtrack enabled
    # if not, return false

    # if so, parse and process message


#get_db().view('domain/domains', key='test', include_docs=True, reduce=False).one()['doc']

    return False
