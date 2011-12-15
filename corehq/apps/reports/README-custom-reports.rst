Custom Reports HOWTO
--------------------

Here is how to create a class-based custom report in HQ.

1. Create a class (in a submodule, usually) that subclasses corehq.apps.reports.custom.HQReport.
   See corehq.apps.reports.custom for examples, which are reproduced below.

2. In that class, set the name, slug, and description as appropriate::

       class SampleHQReport(HQReport):
           name = "Sample Report"
           slug = "sample"
           description = "A sample report demonstrating the HQ reports system."

   The name is what you see at the top of the page and in the report selector dropdown.  The slug will form part of the
   URL.  The description will appear when the user mouses over the entry in the report selector dropdown.

3. Set up any custom fields you need.  Month and Year fields are already created, but if you need a custom field,
   define it like this::

       class ExampleInputField(ReportField):
           slug = "example-input"
           template = "reports/partials/example-input-select.html"

           def update_context(self):
               self.context['example_input_default'] = "Some Example Text"

   Create the partial template for the field::

        <label for="example-input">Example Text Input:</label>
        <input type="text" id="example-input" name="example-input" value="{{ example_input_default }}" />

   Add a reference to it to the "fields" property of your new class::

        class SampleHQReport(HQReport):
            name = "Sample Report"
            slug = "sample"
            description = "A sample report demonstrating the HQ reports system."
            fields = ['corehq.apps.reports.custom.ExampleInputField']

4. Create a calc() function in your new class.  This function should set one or more attributes of self.context for
   display in the report template, like so::

       def calc(self):
           self.context['now_date'] = datetime.now()
           self.context['the_answer'] = 42

           text = self.request.GET.get("example-input", None)

           if text:
               self.context['text'] = text
           else:
               self.context['text'] = "You didn't type anything!"

   You have access to the request object as self.request.  Selector options will be passed in self.request.GET.

5. Create a template for your new report::

       {% extends "reports/report_base.html" %}
       {% load i18n %}

       {% block reportcontent %}
           <h2>This is a sample report!</h2>

           <div>Today is {{ now_date }}.  The answer is {{ answer }}.</div>

           <div>Some text: [{{ text }}]</div>
       {% endblock %}

   Make sure that all template variables in the report are populated, either in your calc() function or elsewhere.

   Set the template_name property in your report class::

        class SampleHQReport(HQReport):
            name = "Sample Report"
            slug = "sample"
            description = "A sample report demonstrating the HQ reports system."
            template_name = "reports/sample-report.html"
            fields = ['corehq.apps.reports.custom.ExampleInputField']

   The template_name should be a valid reference to a template inheriting from "reports/report_base.html" (so as to
   properly build out the selector form.)

6. If you need to do anything else, such as adding Couch views, do that now.

7. Finally, for each domain in which you want to use this report, add an entry to CUSTOM_REPORT_MAP in settings.py::

        CUSTOM_REPORT_MAP = {
            "mydomain": ['corehq.apps.reports.custom.SampleHQReport',
                        ]
        }

   You can add the same report to multiple domains.

   You should now be able to access your new report through the "Select Report" dropdown in the "Reports" tab
   in your domain.  No URL setup is required -- the reports_dispatcher function in views.py will take care of it.
