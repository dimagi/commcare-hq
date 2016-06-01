from corehq.apps.hqwebapp.views import BaseSectionPageView


class BaseB3SectionPageView(BaseSectionPageView):
    """Subclass of BaseSectionPageView to immediately support Bootstrap3.
    """
    template_name = "style/base_section.html"
