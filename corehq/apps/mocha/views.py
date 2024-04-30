from django.views.generic.base import TemplateView


class MochaView(TemplateView):
    template_name = 'mocha/base.html'
    urlname = 'mocha_view'

    def dispatch(self, request, *args, **kwargs):
        app = kwargs.get('app', None)
        config = kwargs.get('config', None)
        bootstrap_version = kwargs.get('bootstrap_version', None)

        template_name = "mocha.html"
        if bootstrap_version:
            template_name = f"{bootstrap_version}/{template_name}"
        if config:
            template_name = f"{config}/{template_name}"
        template_name = f"{app}/spec/{template_name}"

        self.template_name = template_name
        return super(MochaView, self).dispatch(request, *args, **kwargs)
