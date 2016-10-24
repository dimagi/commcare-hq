from django.views.generic import TemplateView


class WorflowBuilderView(TemplateView):
    urlname = 'workflow_builder_home'
    template_name = "prototype/workflow_builder/home.html"


class PromptView(TemplateView):
    urlname = 'workflow_builder_prompt'
    template_name = "prototype/workflow_builder/prompt.html"
