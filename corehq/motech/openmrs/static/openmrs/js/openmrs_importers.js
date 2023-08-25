hqDefine('openmrs/js/openmrs_importers', [
    'jquery',
    'underscore',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/bootstrap3/alert_user',
    'hqwebapp/js/base_ace',
], function (
    $,
    _,
    ko,
    initialPageData,
    alertUser,
    baseAce
) {

    var openmrsImporter = function (properties) {
        var self = {};

        self.server_url = ko.observable(properties["server_url"]);
        // We are using snake_case for property names so that they
        // match Django form field names. That way we can iterate the
        // fields of an unbound Django form in
        // openmrs_importer_template.html and bind to these properties
        // using the Django form field names.
        self.username = ko.observable(properties["username"]);
        self.password = ko.observable(properties["password"]);
        self.notify_addresses_str = ko.observable(properties["notify_addresses_str"]);
        self.location_id = ko.observable(properties["location_id"]);
        self.import_frequency = ko.observable(properties["import_frequency"]);
        self.log_level = ko.observable(properties["log_level"]);
        self.timezone = ko.observable(properties["timezone"]);
        self.report_uuid = ko.observable(properties["report_uuid"]);
        self.report_params = ko.observable(properties["report_params"]);
        self.case_type = ko.observable(properties["case_type"]);
        self.owner_id = ko.observable(properties["owner_id"]);
        self.location_type_name = ko.observable(properties["location_type_name"]);
        self.external_id_column = ko.observable(properties["external_id_column"]);
        self.name_columns = ko.observable(properties["name_columns"]);
        self.column_map = ko.observable(properties["column_map"]);

        self.import_frequency_options = [
            {"value": "daily", "text": gettext("Daily")},
            {"value": "weekly", "text": gettext("Weekly")},
            {"value": "monthly", "text": gettext("Monthly")},
        ];
        self.log_level_options = [
            {"value": 99, "text": gettext("Disable logging")},
            {"value": 40, "text": "Error"},  // Don't translate the names of log levels
            {"value": 20, "text": "Info"},
        ];

        self.serialize = function () {
            return {
                "server_url": self.server_url(),
                "username": self.username(),
                "password": self.password(),
                "notify_addresses_str": self.notify_addresses_str(),
                "location_id": self.location_id(),
                "import_frequency": self.import_frequency(),
                "log_level": self.log_level(),
                "timezone": self.timezone(),
                "report_uuid": self.report_uuid(),
                "report_params": self.report_params(),
                "case_type": self.case_type(),
                "owner_id": self.owner_id(),
                "location_type_name": self.location_type_name(),
                "external_id_column": self.external_id_column(),
                "name_columns": self.name_columns(),
                "column_map": self.column_map(),
            };
        };

        return self;
    };

    var openmrsImporters = function (openmrsImporters, importNowUrl) {
        var self = {};

        self.openmrsImporters = ko.observableArray();

        self.init = function () {
            if (openmrsImporters.length > 0) {
                for (var i = 0; i < openmrsImporters.length; i++) {
                    self.openmrsImporters.push(openmrsImporter(openmrsImporters[i]));
                }
            } else {
                self.addOpenmrsImporter();
            }
        };

        self.addOpenmrsImporter = function () {
            self.openmrsImporters.push(openmrsImporter({}));
        };

        self.initOpenmrsImporterTemplate = function (elements) {
            _.each(elements, function (element) {
                _.each($(element).find('.jsonwidget'), baseAce.initObservableJsonWidget);
            });
        };

        self.removeOpenmrsImporter = function (openmrsImporter) {
            self.openmrsImporters.remove(openmrsImporter);
        };

        self.submit = function (form) {
            var openmrsImporters = [];
            for (var i = 0; i < self.openmrsImporters().length; i++) {
                var openmrsImporter = self.openmrsImporters()[i];
                openmrsImporters.push(openmrsImporter.serialize());
            }
            $.post(
                form.action,
                {'openmrs_importers': JSON.stringify(openmrsImporters)},
                function (data) { alertUser.alert_user(data['message'], 'success', true); }
            ).fail(function () { alertUser.alert_user(gettext('Unable to save OpenMRS Importers'), 'danger'); });
        };

        self.importNow = function () {
            $.post(importNowUrl, {}, function () {
                alertUser.alert_user(gettext("Importing from OpenMRS will begin shortly."), "success");
            }).fail(function () {
                alertUser.alert_user(gettext("Failed to schedule task to import from OpenMRS."), "danger");
            });
        };

        return self;
    };

    $(function () {
        var viewModel = openmrsImporters(
            initialPageData.get('openmrs_importers'),
            initialPageData.reverse('openmrs_import_now')
        );
        viewModel.init();
        $('#openmrs-importers').koApplyBindings(viewModel);
    });
});
