from django.utils.decorators import method_decorator
from corehq.apps.hqwebapp.views import BaseSectionPageView
from corehq.apps.style.decorators import use_bootstrap3


class BaseB3SectionPageView(BaseSectionPageView):
    """Subclass of BaseSectionPageView to immediately support Bootstrap3.
    """
    template_name = "style/bootstrap3/base_section.html"

    @use_bootstrap3
    def dispatch(self, request, *args, **kwargs):
        return super(BaseB3SectionPageView, self).dispatch(request, *args, **kwargs)
