from requests.auth import HTTPBasicAuth


def _apply_updates(doc, update_dict):
    # updates the doc with items from the dict
    # returns whether or not any updates were made
    should_save = False
    for key, value in update_dict.items():
        if getattr(doc, key, None) != value:
            setattr(doc, key, value)
            should_save = True
    return should_save


class EndpointMixin(object):
    @classmethod
    def from_config(cls, config):
        return cls(config.url, config.username, config.password)

    def _auth(self):
        return HTTPBasicAuth(self.username, self.password)

    def _urlcombine(self, base, target):
        return '{base}{target}'.format(base=base, target=target)