from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.views.generic import *


def styleguide_default(request):
    return HttpResponseRedirect(reverse(MainStyleGuideView.urlname))


class MainStyleGuideView(TemplateView):
    template_name = 'styleguide/pages/home.html'
    urlname = 'styleguide_home'


class BaseStyleGuideArticleView(TemplateView):
    template_name = 'styleguide/base_section.html'

    def dispatch(self, request, *args, **kwargs):
        # todo remove after bootstrap 3 migration is over
        request.preview_bootstrap3 = True
        return super(BaseStyleGuideArticleView, self).dispatch(request, *args, **kwargs)

    @property
    def sections(self):
        """This will be inserted into the page context's sections variable
        as a list of strings following the format
        'styleguide/_includes/<section>.html'
        Make sure you create the corresponding template in the styleguide app.

        :return: List of the sections in order. Usually organized by
        <article>/<section_name>
        """
        raise NotImplementedError("please implement 'sections'")

    @property
    def navigation_name(self):
        """This will be inserted into the page context under
        styleguide/_includes/nav/<navigation_name>.html. Make sure
        you create the corresponding template in the styleguide app
        when you add this.
        :return: a string that is the name of the navigation section
        """
        raise NotImplementedError("please implement 'navigation_name'")

    @property
    def section_context(self):
        return {
            'sections': ['styleguide/_includes/%s.html' % s
                         for s in self.sections],
            'navigation': ('styleguide/_includes/nav/%s.html'
                           % self.navigation_name),
        }

    @property
    def page_context(self):
        """It's intended that you override this method when necessary to provide
        any additional content that's relevant to the view specifically.
        :return: a dict
        """
        return {}

    def render_to_response(self, context, **response_kwargs):
        context.update(self.section_context)
        context.update(self.page_context)
        return super(BaseStyleGuideArticleView, self).render_to_response(
            context, **response_kwargs)


class FormsStyleGuideView(BaseStyleGuideArticleView):
    urlname = 'styleguide_forms'
    navigation_name = 'forms'

    @property
    def sections(self):
        return [
            'forms/anatomy',
        ]
