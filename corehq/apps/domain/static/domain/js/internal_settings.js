hqDefine("domain/js/internal_settings", [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/multiselect_utils',
    'jquery-ui/ui/widgets/datepicker',
    'commcarehq',
], function (
    $,
    ko,
    _,
    initialPageData,
    multiselectUtils
) {
    var areas = initialPageData.get('areas');

    var internalSettingsViewModel = function (initialValues) {
        var self = {};
        self.use_custom_auto_case_update_hour = ko.observable(initialValues.use_custom_auto_case_update_hour);
        self.use_custom_auto_case_update_limit = ko.observable(initialValues.use_custom_auto_case_update_limit);
        self.use_custom_odata_feed_limit = ko.observable(initialValues.use_custom_odata_feed_limit);
        return self;
    };

    function updateSubareas() {
        var $subarea = $subarea || $('[name="sub_area"]');
        var chosenSubArea = $subarea.val();
        var area = $('[name="area"]').val();
        var validSubAreas = [];
        if (area) {
            validSubAreas = areas[area];
        }
        $subarea.empty().append($("<option></option>").attr("value", '').text('---'));
        _.each(validSubAreas, function (val) {
            var $opt = $("<option></option>").attr("value", val).text(val);
            if (val === chosenSubArea) {
                $opt.prop("selected", true);
            }
            $subarea.append($opt);
        });
    }

    function updateWorkshopRegion() {
        var $wr = $wr || $('#id_workshop_region').parent().parent();
        var $workshopInitiative = $workshopInitiative || $('[name="initiative"][value="Workshop"]');
        if ($workshopInitiative.is(":checked")) {
            $wr.removeClass("d-none");
        } else {
            $wr.addClass("d-none");
        }
    }

    $(function () {
        updateSubareas();
        updateWorkshopRegion();
        $('[name="area"]').change(function () {
            updateSubareas();
        });
        $('[name="initiative"]').change(function () {
            updateWorkshopRegion();
        });

        var internalSettingsView = internalSettingsViewModel(
            initialPageData.get("current_values")
        );
        $('#update-project-info').koApplyBindings(internalSettingsView);

        $('#id_deployment_date').datepicker({
            changeMonth: true,
            changeYear: true,
            showButtonPanel: true,
            dateFormat: 'yy-mm-dd',
            maxDate: '0',
            numberOfMonths: 2,
        });

        multiselectUtils.createFullMultiselectWidget('id_countries', {
            selectableHeaderTitle: gettext("Available Countries"),
            selectedHeaderTitle: gettext("Active Countries"),
            searchItemTitle: gettext("Search Countries..."),
        });
        multiselectUtils.createFullMultiselectWidget('id_active_ucr_expressions', {
            selectableHeaderTitle: gettext("Inactive Expressions"),
            selectedHeaderTitle: gettext("Active Expressions"),
            searchItemTitle: gettext("Search Expressions"),
        });
    });
});
