hqDefine("data_interfaces/js/find_by_id", [
    'jquery',
    'underscore',
    'knockout',
    'hqwebapp/js/assert_properties',
    'hqwebapp/js/initial_page_data',
    'analytix/js/kissmetrix',
], function (
    $,
    _,
    ko,
    assertProperties,
    initialPageData,
    kissmetrics
) {
    var findModel = function (options) {
        assertProperties.assert(options, ['errorMessage', 'eventName', 'header', 'help', 'placeholder', 'successMessage']);

        var self = options;
        self.query = ko.observable('');
        self.error = ko.observable('');
        self.link = ko.observable('');
        self.loading = ko.observable(false);

        self.linkMessage = ko.computed(function () {
            if (self.link()) {
                var redirectTemplate = _.template(gettext("<a href='<%- link %>' target='_blank'>View <i class='fa-solid fa-up-right-from-square'></i></a>"));
                return self.successMessage + " " + redirectTemplate({link: self.link()});
            }
            return '';
        });

        self.allowFind = ko.computed(function () {
            return self.query() && !self.loading();
        });

        self.find = function () {
            self.loading(true);
            self.link('');
            self.error('');
            kissmetrics.track.event(options.eventName);
            $.ajax({
                method: 'GET',
                url: initialPageData.reverse('global_quick_find'),
                data: {
                    q: self.query().trim(),
                    redirect: 'false',
                },
                success: function (data) {
                    self.loading(false);
                    self.link(data.link);
                },
                error: function () {
                    self.loading(false);
                    self.error(self.errorMessage);
                },
            });
        };

        return self;
    };

    $(function () {
        kissmetrics.track.event("[Find data by ID] Visited page");

        $("#find-case").koApplyBindings(findModel({
            header: gettext('Find Case'),
            help: _.template(gettext('IDs can be found in a <a href="<%- url %>">case data export</a>'))({
                url: initialPageData.reverse('list_case_exports'),
            }),
            placeholder: gettext('Case ID'),
            successMessage: gettext('Case found!'),
            errorMessage: gettext('Could not find case'),
            eventName: "[Find data by ID] Clicked Find for cases",
        }));

        $("#find-form").koApplyBindings(findModel({
            header: gettext('Find Form Submission'),
            help: _.template(gettext('IDs can be found in a <a href="<%- url %>">form data export</a>'))({
                url: initialPageData.reverse('list_form_exports'),
            }),
            errorMessage: gettext('Could not find form submission'),
            placeholder: gettext('Form Submission ID'),
            successMessage: gettext('Form submission found!'),
            eventName: "[Find data by ID] Clicked Find for forms",
        }));
    });
});
