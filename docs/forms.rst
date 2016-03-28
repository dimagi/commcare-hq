Forms in HQ
===========

Best practice principles:

- Use as little hardcoded HTML as possible.
- Submit and validate forms asynchronously to your class-based-view's `post` method.
- `Protect forms <making_forms_csrf_safe>`_ against CSRF
- Be consistent with style across HQ. We are currently using `Bootstrap 2.3's
  horizontal forms <bootstrap_forms>`_ across HQ.
- Use `django.forms`.
- Use `crispy forms <http://django-crispy-forms.readthedocs.org/en/latest/>` for field layout.

.. _bootstrap_forms: http://bootstrapdocs.com/v2.3.1/docs/base-css.html#forms
.. _tag_csrf_example: https://github.com/dimagi/commcare-hq/pull/9580/files#diff-b707708b04006cb99be5064dedbc8240R41
.. _ajax_csrf_example: https://github.com/dimagi/commcare-hq/commit/75c4fd0c638c2c79c8a1f765b70b1ac4709b043a#diff-3cfc511ef8ce8d4f15a3b64d1a113d26R125
.. _angular_csrf_example: https://github.com/dimagi/commcare-hq/commit/2a69336776252431413cc2c0bd2ccb3602364fd1#diff-ac9201a9e1f9b2512c8ed46247739179R30
.. _js_csrf_example_1: https://github.com/dimagi/commcare-hq/commit/a3964b2f2f1f2839df1516934b66d11dbc90faaf#diff-8380c7394c4bb525b5a02ebabc97e08fR198
.. _js_csrf_example_2: https://github.com/dimagi/commcare-hq/commit/fadf34936a4fabdf92e2e14503d39f1efb502aa2#diff-88a89488da4f667449d6a54763ab905aR9
.. _inline_csrf_example: https://github.com/dimagi/commcare-hq/commit/b12e0457b8e3b5c3accd5ef9f57a90b3018c7828#diff-597545574657c656fd164ce865186edaR1158
.. _csrf_exempt_example: https://github.com/dimagi/commcare-hq/pull/9736/files#diff-a8527f8793e60d01dedc1bc05c822d76R174
.. _django_csrf: https://docs.djangoproject.com/en/1.8/ref/csrf/

.. _making_forms_csrf_safe:

Making forms CSRF safe
----------------------

HQ is protected against cross site request forgery attacks i.e. if a `POST/PUT/DELETE` request doesn't pass csrf token to corresponding View, the View will reject those requests with a 403 response. All HTML forms and AJAX calls that make such requests should contain a csrf token to succeed. Making a form or AJAX code pass csrf token is easy and the `Django docs <django_csrf>`_ give detailed instructions on how to do so. Here we list out examples of HQ code that does that

1. If crispy form is used to render HTML form, csrf token is included automagically
2. For raw HTML form, use `{% csrf_token %}` tag in the form HTML, see tag_csrf_example_.
3. If request is made via AJAX, it will be automagically protected by `ajax_csrf_setup.js` (which is included in base bootstrap template) as long as your template is inherited from the base template. (`ajax_csrf_setup.js` overrides `$.ajaxSettings.beforeSend` to accomplish this)
4. If an AJAX call needs to override `beforeSend` itself, then the super `$.ajaxSettings.beforeSend` should be explicitly called to pass csrf token. See ajax_csrf_example_
5. If request is made via Angluar JS controller, the angular app needs to be configured to send csrf token. See angular_csrf_example_
6. If HTML form is created in Javascript using raw nodes, csrf-token node should be added to that form. See js_csrf_example_1_ and js_csrf_example_2_
7. If an inline form is generated using outside of `RequestContext` using `render_to_string` or its cousins, use `csrf_inline` custom tag. See inline_csrf_example_
8. If a View needs to be exempted from csrf check (for whatever reason, say for API), use `csrf_exampt` decorator to avoid csrf check. See csrf_exempt_example_
9. For any other special unusual case refer to `Django docs <django_csrf>`_. Essentially, either the HTTP request needs to have a csrf-token or the corresponding View should be exempted from CSRF check.



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
