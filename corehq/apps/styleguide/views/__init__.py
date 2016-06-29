from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.views.generic import *
from corehq.apps.styleguide.palette import (
    PaletteColor,
    PaletteColorGroup,
    Palette,
)
from corehq.apps.styleguide.example_forms import BasicCrispyForm


def styleguide_default(request):
    return HttpResponseRedirect(reverse(MainStyleGuideView.urlname))


class MainStyleGuideView(TemplateView):
    template_name = 'styleguide/pages/home.html'
    urlname = 'styleguide_home'


class BaseStyleGuideArticleView(TemplateView):
    template_name = 'styleguide/base_section.html'

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


class ClassBasedViewStyleGuideView(BaseStyleGuideArticleView):
    urlname = 'styleguide_views'
    navigation_name = 'cb_views'

    @property
    def sections(self):
        return [
            'views/intro',
            'views/base_classes',
        ]


class FormsStyleGuideView(BaseStyleGuideArticleView):
    urlname = 'styleguide_forms'
    navigation_name = 'forms'

    @property
    def sections(self):
        return [
            'forms/intro',
            'forms/anatomy',
            'forms/controls',
        ]

    @property
    def page_context(self):
        return {
            'basic_crispy_form': BasicCrispyForm(),
        }


class IconsStyleGuideView(BaseStyleGuideArticleView):
    urlname = 'styleguide_icons'
    navigation_name = 'icons'

    @property
    def sections(self):
        return [
            'icons/overview',
            'icons/sources',
            'icons/new_icons',
        ]


class ColorsStyleGuide(BaseStyleGuideArticleView):
    urlname = 'styleguide_colors'
    navigation_name = 'colors'

    @property
    def sections(self):
        return [
            'colors/overview',
            'colors/palette',
        ]

    @property
    def page_context(self):
        return {
            'palette': self.palette,
        }

    @property
    def palette(self):
        text_color = PaletteColor('181715',)
        bg_color = PaletteColor('f2f2f1',)

        neutrals = PaletteColorGroup(
            "Neutral",
            'neutral',
            PaletteColor('685c53',),
            PaletteColor('d6d6d4', name="Light"),
            PaletteColor('373534', name="Dark"),
        )

        brand = PaletteColorGroup(
            "Brand",
            'brand',
            PaletteColor('004ebc',),
            PaletteColor('bcdeff', name="Light"),
            PaletteColor('002c5f', name="Dark"),
        )

        light_cool_accent = PaletteColorGroup(
            "Light Cool Accent",
            'light-cool-accent',
            PaletteColor('00bdc5',),
            PaletteColor('ccf3f4', name="Light"),
            PaletteColor('00799a', name="Dark"),
        )

        dark_warm_accent = PaletteColorGroup(
            "Dark Warm Accent",
            'dark-warm-accent',
            PaletteColor('ff8400',),
            PaletteColor('ffe3c2', name="Light"),
            PaletteColor('994f00', name="Dark"),
        )

        light_warm_accent = PaletteColorGroup(
            "Light Warm Accent",
            'light-warm-accent',
            PaletteColor('f9c700',),
            PaletteColor('f8ecbd', name="Light"),
            PaletteColor('685300', name="Dark"),
        )

        attention_positive = PaletteColorGroup(
            "Attention Positive",
            'att-pos',
            PaletteColor('47b700',),
            PaletteColor('d5eaca', name="Light"),
            PaletteColor('216f00', name="Dark"),
        )

        attention_negative = PaletteColorGroup(
            "Attention Negative",
            'att-neg',
            PaletteColor('e53e30',),
            PaletteColor('efcfcb', name="Light"),
            PaletteColor('812627', name="Dark"),
        )

        dark_cool_accent = PaletteColorGroup(
            "Dark Cool Accent",
            'dark-cool-accent',
            PaletteColor('9060c8',),
            PaletteColor('d6c5ea', name="Light"),
            PaletteColor('5d3f82', name="Dark"),
        )

        return Palette(
            [
                neutrals,
                brand,
                light_cool_accent,
                dark_warm_accent,
                light_warm_accent,
                attention_positive,
                attention_negative,
                dark_cool_accent,
            ],
            text_color,
            bg_color,
        )
