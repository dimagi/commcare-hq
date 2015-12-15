Forms in HQ
===========

Best practice principles:

- Use as little hardcoded HTML as possible.
- Submit and validate forms asynchronously to your class-based-view's `post` method.
- Be consistent with style across HQ. We are currently using `Bootstrap 2.3's
  horizontal forms <bootstrap_forms>`_ across HQ.
- Use `django.forms`.
- Use `crispy forms <http://django-crispy-forms.readthedocs.org/en/latest/>` for field layout.

.. _bootstrap_forms: http://bootstrapdocs.com/v2.3.1/docs/base-css.html#forms

.. _async_form_example:

An Example Complex Asynchronous Form With Partial Fields
--------------------------------------------------------

We create the following base form, subclassing `django.forms.Form`:

.. code-block:: python

    from django import forms
    from crispy_forms.helper import FormHelper
    from crispy_forms import layout as crispy

    class PersonForm(forms.Form):
        first_name = forms.CharField()
        last_name = forms.CharField()
        pets = forms.CharField(widget=forms.HiddenInput)

        def __init__(self, *args, **kwargs):
            super(PersonForm, self).__init__(*args, **kwargs)

            self.helper = FormHelper()
            self.helper.layout = crispy.Layout(
                # all kwargs passed to crispy.Field turn into that tag's attributes and underscores
                # become hyphens. so data_bind="value: name" gets inserted as data-bind="value: name"
                crispy.Field('first_name', data_bind="value: first_name"),
                crispy.Field('last_name', data_bind="value: last_name"),
                crispy.Div(
                    data_bind="template: {name: 'pet-form-template', foreach: pets}, "
                              "visible: isPetVisible"
                ),
                # form actions creates the gray box around the submit / cancel buttons
                FormActions(
                    StrictButton(
                        _("Update Information"),
                        css_class="btn-primary",
                        type="submit",
                    ),
                    # todo: add a cancel 'button' class!
                    crispy.HTML('<a href="%s" class="btn">Cancel</a>' % cancel_url),
                    # alternatively, the following works if you capture the name="cancel"'s event in js:
                    Button('cancel', 'Cancel'),
                ),
            )

        @property
        def current_values(self):
            values = dict([(name, self.person_form[name].value()) for name in self.person_form.keys()])
            # here's where you would make sure events outputs the right thing
            # in this case, a list so it gets converted an ObservableArray for the knockout model
            return values

        def clean_first_name(self):
            first_name = self.cleaned_data['first_name']
            # validate
            return first_name

        def clean_last_name(self):
            last_name = self.cleaned_data['last_name']
            # validate
            return last_name

        def clean_pets(self):
            # since we could have any number of pets we tell knockout to store it as json in a hidden field
            pets = json.loads(self.cleaned_data['pets'])
            # validate pets
            # suggestion:
            errors = []
            for pet in pets:
                pet_form = PetForm(pet)
                pet_form.is_valid()
                errors.append(pet_form.errors)
            # raise errors as necessary
            return pets


    class PetForm(forms.Form):
        nickname = CharField()

        def __init__(self, *args, **kwargs):
            super(PetForm, self).__init__(*args, **kwargs)

            self.helper = FormHelper()
            # since we're using this form to 'nest' inside of PersonForm, we want to prevent
            # crispy forms from auto-including a form tag:
            self.helper.form_tag = False

            self.helper.layout = crispy.Layout(
                Field('nickname', data_bind="value: nickname"),
            )


The view will look something like:

.. code-block:: python

    class PersonFormView(BaseSectionPageView):
        # see documentation on ClassBasedViews for use of BaseSectionPageView
        template_name = 'people/person_form.html'
        allowed_post_actions = [
            'person_update',
            'select2_field_update',  # an example of another action you might consider
        ]

        @property
        @memoized
        def person_form(self):
            initial = {}
            if self.request.method == 'POST':
                return PersonForm(self.request.POST, initial={})
            return PersonForm(initial={})

        @property
        def page_context(self):
            return {
                'form': self.person_form,
                'pet_form': PetForm(),
            }

        @property
        def post_action:
            return self.request.POST.get('action')

        def post(self, *args, **kwargs):
            if self.post_action in self.allowed_post_actions:
                return HttpResponse(json.dumps(getattr(self, '%s_response' % self.action)))
            # NOTE: doing the entire form asynchronously means that you have to explicitly handle the display of
            # errors for each field. Ideally we should subclass crispy.Field to something like KnockoutField
            # where we'd add something in the template for errors.
            raise Http404()

        @property
        def person_update_response(self):
            if self.person_form.is_valid():
                return {
                    'data': self.person_form.current_values,
                }
            return {
                'errors': self.person_form.errors.as_json(),
                # note errors looks like:
                # {'field_name': [{'message': "msg", 'code': "invalid"}, {'message': "msg", 'code': "required"}]}
            }


The template `people/person_form.html`:

.. code-block:: html

    {% extends 'people/base_template.html' %}
    {% load hq_shared_tags %}
    {% load i18n %}
    {% load crispy_forms_tags %}

    {% block js %}{{ block.super }}
        <script src="{% static 'people/ko/form.person.js' %}"></script>
    {% endblock %}

    {% block js-inline %}{{ block.super }}
        <script>
            var personFormModel = new PersonFormModel(
                {{ form.current_values|JSON }},
            );
            $('#person-form').koApplyBindings(personFormModel);
            personFormModel.init();
        </script>
    {% endblock %}

    {% block main_column %}
    <div id="manage-reminders-form">
        <form class="form form-horizontal" method="post">
            {% crispy form %}
        </form>
    </div>

    <script type="text/html" id="pet-form-template">
        {% crispy pet_form %}
    </script>
    {% endblock %}

Your knockout code in `form.person.js`:

.. code-block:: javascript

    var PersonFormModel = function (initial) {
        'use strict';
        var self = this;

        self.first_name = ko.observable(initial.first_name);
        self.last_name = ko.observable(initial.last_name);

        self.petObjects = ko.observableArray();
        self.pets = ko.computed(function () {
            return JSON.stringify(_.map(self.petObjects(), function (pet) {
                return pet.asJSON();
            }));
        });

        self.init = function () {
            var pets = $.parseJSON(initial.pets || '[]');
            self.petObjects(_.map(pets, function (initial_data) {
                return new Pet(initial_data);
            }));
        };

    };

    var Pet = function (initial) {
        'use strict';
        var self = this;

        self.nickname = ko.observable(initial.nickname);

        self.asJSON = ko.computed(function () {
            return {
                nickname: self.nickname()
            }
        });
    };

That should hopefully get you 90% there. For an example on HQ see
`corehq.apps.reminders.views.CreateScheduledReminderView <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/reminders/views.py#L486>`
