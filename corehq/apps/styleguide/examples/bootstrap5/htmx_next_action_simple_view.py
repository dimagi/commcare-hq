from django.urls import reverse
from django.utils.decorators import method_decorator

from corehq.apps.domain.decorators import login_required
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.hqwebapp.views import BasePageView
from corehq.apps.styleguide.examples.bootstrap5.htmx_next_action_simple_forms import (
    ChooseFruitForm,
    ConfirmFruitChoiceForm,
)
from corehq.util.htmx_action import HqHtmxActionMixin, hq_hx_action


@method_decorator(login_required, name='dispatch')
@method_decorator(use_bootstrap5, name='dispatch')
class SimpleNextActionDemoView(HqHtmxActionMixin, BasePageView):
    """
    A minimal example of a multi-step flow using the `next_action` pattern.

    Step 1: Choose a fruit.
    Step 2: Confirm the choice or go back to change it.
    """

    urlname = 'sg_htmx_next_action_demo'
    template_name = 'styleguide/htmx_next_action_simple/main.html'
    form_template = 'styleguide/htmx_next_action_simple/next_step_with_message.html'
    container_id = 'simple-next-action'

    @property
    def page_url(self):
        return reverse(self.urlname)

    @property
    def page_context(self):
        # The initial full-page render (non-HTMX) doesn’t need the form;
        # the container will fetch it via HTMX on load.
        return {
            'container_id': self.container_id,
        }

    def _step_context(self, form=None, next_action=None, message=None):
        """
        Shared context for all steps.
        """
        return {
            'form': form or ChooseFruitForm(),
            'container_id': self.container_id,
            'next_action': next_action or 'validate_choice',
            'message': message,
        }

    @hq_hx_action('get')
    def load_first_step(self, request, *args, **kwargs):
        """
        HTMX action: load the initial "choose fruit" form.
        """
        return self.render_htmx_partial_response(
            request,
            self.form_template,
            self._step_context(),
        )

    @hq_hx_action('post')
    def validate_choice(self, request, *args, **kwargs):
        """
        HTMX action: validate the chosen fruit.

        - If invalid: re-render the same step with errors.
        - If valid: move to the "confirm or change" step.
        """
        form = ChooseFruitForm(request.POST)
        if not form.is_valid():
            return self.render_htmx_partial_response(
                request,
                self.form_template,
                self._step_context(form=form, next_action='validate_choice'),
            )

        fruit = form.cleaned_data['fruit']
        confirm_form = ConfirmFruitChoiceForm(initial={'fruit': fruit})
        return self.render_htmx_partial_response(
            request,
            self.form_template,
            self._step_context(
                form=confirm_form,
                next_action='confirm_or_change',
            ),
        )

    @hq_hx_action('post')
    def confirm_or_change(self, request, *args, **kwargs):
        """
        HTMX action: either finish the flow or go back to step 1.
        """
        form = ConfirmFruitChoiceForm(request.POST)
        if not form.is_valid():
            # Stay on confirm step and show errors
            return self.render_htmx_partial_response(
                request,
                self.form_template,
                self._step_context(form=form, next_action='confirm_or_change'),
            )

        fruit = form.cleaned_data['fruit']
        next_step = form.cleaned_data['next_step']

        if next_step == 'change':
            # Go back to step 1, optionally pre-filling the previous choice
            choose_form = ChooseFruitForm(initial={'fruit': fruit})
            return self.render_htmx_partial_response(
                request,
                self.form_template,
                self._step_context(
                    form=choose_form,
                    next_action='validate_choice',
                ),
            )

        # next_step == "confirm": show a simple success message and reset to step 1
        message = f'Saved your choice: {fruit}'
        return self.render_htmx_partial_response(
            request,
            self.form_template,
            self._step_context(
                form=ChooseFruitForm(),
                next_action='validate_choice',
                message=message,
            ),
        )
