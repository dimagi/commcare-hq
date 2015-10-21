from django.views.generic.base import TemplateView


class MochaView(TemplateView):
    template_name = 'mocha/base.html'
    urlname = 'mocha_view'

    def dispatch(self, request, *args, **kwargs):
        param = request.GET.get('param', None)
        if param:
            self.template_name = '{}/spec/{}/mocha.html'.format(kwargs['app'], param)
        else:
            self.template_name = '{}/spec/mocha.html'.format(kwargs['app'])
        return super(MochaView, self).dispatch(request, *args, **kwargs)
