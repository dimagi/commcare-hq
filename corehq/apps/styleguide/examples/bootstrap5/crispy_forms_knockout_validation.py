from django import forms
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy

from corehq.apps.hqwebapp import crispy as hqcrispy


class KnockoutValidationCrispyExampleForm(forms.Form):
    """
    This is an example form that demonstrates the use
    of Crispy Forms in HQ with Knockout Validation
    """
    username = forms.CharField(
        label=gettext_lazy("Username"),
        help_text=gettext_lazy("Hint: 'jon' is taken. Try typing that in to trigger an error."),
    )
    password = forms.CharField(
        label=gettext_lazy("Password"),
        widget=forms.PasswordInput,
    )
    email = forms.CharField(
        label=gettext_lazy("Email"),
        help_text=gettext_lazy("Hint: 'jon@dimagi.com' is taken. Try typing that in to trigger an error."),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = hqcrispy.HQFormHelper()

        self.helper.form_id = "ko-validation-example"
        self.helper.attrs.update({
            "data-bind": "submit: onFormSubmit",
        })

        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Create New User"),
                crispy.Div(
                    crispy.Div(
                        '',
                        css_class="alert alert-info",
                        data_bind="text: alertText",
                    ),
                    data_bind="visible: alertText()"
                ),
                crispy.Div(
                    crispy.Field(
                        "username",
                        # koValidationStateFeedback is a custom binding
                        # handler we created add success messages
                        # and additional options asynchronous validation
                        data_bind="textInput: username,"
                                  "koValidationStateFeedback: { "
                                  "   validator: username,"
                                  "   successMessage: gettext('This username is available.'),"
                                  "   checkingMessage: gettext('Checking if username is available...'),"
                                  "}",
                    ),
                    crispy.Field(
                        "password",
                        autocomplete="off",
                        # FYI textInput is a special binding that updates
                        # the value of the observable on keyUp.
                        data_bind="textInput: password,"
                                  "koValidationStateFeedback: { "
                                  "   validator: password,"
                                  "   successMessage: gettext('Perfect!'),"
                                  "}",
                    ),
                    crispy.Field(
                        "email",
                        autocomplete="off",
                        # This usage of koValidationStateFeedback
                        # demonstrates how to couple standard validators
                        # with a rate-limited async validator
                        # and have all the state messages
                        # appear gracefully in the same place.
                        data_bind="textInput: email,"
                                  "koValidationStateFeedback: { "
                                  "   validator: email,"
                                  "   delayedValidator: emailDelayed,"
                                  "   successMessage: gettext('This email is available.'),"
                                  "   checkingMessage: gettext('Checking if email is available...'),"
                                  "}",
                    ),
                    # We need the wrapper crispy.Div to apply the with
                    # binding to these fields.
                    # Calling newUser().username() works for
                    # the first instance of newUser, but not
                    # after it is re-initialized in _resetForm()
                    data_bind="with: newUser",
                ),
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Create User"),
                    type="submit",
                    css_class="btn btn-primary",
                    data_bind="disable: disableSubmit"
                ),
                twbscrispy.StrictButton(
                    _("Cancel"),
                    css_class="btn btn-outline-primary",
                    data_bind="click: cancelSubmission",
                ),
            ),
        )
