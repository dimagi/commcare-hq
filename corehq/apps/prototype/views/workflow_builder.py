from django.views.generic import TemplateView


class WorflowBuilderView(TemplateView):
    urlname = 'workflow_builder_home'
    template_name = "prototype/workflow_builder/home.html"
