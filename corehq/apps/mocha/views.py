from django.views.generic.base import TemplateView
from django.shortcuts import render


class MochaView(TemplateView):
    template_name = 'mocha/base.html'
    urlname = 'mocha_view'

    def dispatch(self, request, *args, **kwargs):
        self.template_name = '{}/spec/mocha.html'.format(kwargs['app'])
        return super(MochaView, self).dispatch(request, *args, **kwargs)
