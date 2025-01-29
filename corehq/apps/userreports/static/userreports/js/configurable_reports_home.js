hqDefine("userreports/js/configurable_reports_home", [
    'jquery',
    'underscore',
    'DOMPurify/dist/purify.min',
    'hqwebapp/js/initial_page_data',
    'select2/dist/js/select2.full.min',
    'commcarehq',
], function (
    $,
    _,
    DOMPurify,
    initialPageData,
) {
    var $select = $("#select2-navigation");
    $select.on('select2:select', function () {
        document.location = $select.val();
    });
    var selectTextHeading = '';
    if (initialPageData.get('useUpdatedUcrNaming')) {
        selectTextHeading = gettext("Edit a custom web report or custom web report source");
    } else {
        selectTextHeading = gettext("Edit a report or data source");
    }
    $select.select2({
        placeholder: selectTextHeading,
        templateResult: function (item) {
            var text = item.text.trim();
            if (!item.element) {
                return text;
            }
            var options = $(item.element).data();
            // static_label and deactivated_label are sanitized from backend
            return _.template("<%= static_label %> <%= deactivated_label %> <i class='<%- icon %>'></i> <%- text %>")({
                icon: options.label === "report" ? "fcc fcc-reports" : "fa fa-database",
                static_label: options.isStatic ? "<span class='label label-default'>" + gettext("static") + "</span>" : "",
                deactivated_label: options.isDeactivated ? "<span class='label label-default'>" + gettext("deactivated") + "</span>" : "",
                text: text,
            });
        },
        escapeMarkup: function (m) {
            return DOMPurify.sanitize(m);
        },
    });
});
