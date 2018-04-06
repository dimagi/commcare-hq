from __future__ import absolute_import
from __future__ import unicode_literals
from django.views.generic.base import TemplateView


class MochaView(TemplateView):
    template_name = 'mocha/base.html'
    urlname = 'mocha_view'

    def dispatch(self, request, *args, **kwargs):
        config = kwargs.get('config', None)
        if config:
            self.template_name = '{}/spec/{}/mocha.html'.format(kwargs['app'], config)
        else:
            self.template_name = '{}/spec/mocha.html'.format(kwargs['app'])
        return super(MochaView, self).dispatch(request, *args, **kwargs)
