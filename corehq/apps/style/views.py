from corehq.apps.hqwebapp.views import BaseSectionPageView


class BaseB3SectionPageView(BaseSectionPageView):
    """Subclass of BaseSectionPageView to immediately support Bootstrap3.
    """

    def dispatch(self, request, *args, **kwargs):
        # todo remove after bootstrap 3 migration is over
        request.preview_bootstrap3 = True
        return super(BaseB3SectionPageView, self).dispatch(request, *args, **kwargs)
