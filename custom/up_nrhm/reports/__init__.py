class LangMixin(object):

    @property
    def lang(self):
        lang = self.request.GET.get('lang', 'en')
        return str(lang) if lang else 'en'
