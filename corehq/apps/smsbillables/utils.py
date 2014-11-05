from corehq.apps.sms.mixin import SMSBackend


def get_global_backends_by_class(backend_class):
    return filter(lambda bk: bk.doc_type == backend_class.__name__,
                  SMSBackend.view(
                      'sms/global_backends',
                      reduce=False,
                      include_docs=True,
                  ))
