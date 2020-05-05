hqDefine("userreports/js/configurable_reports_home", [
    'jquery',
    'underscore',
    'DOMPurify/dist/purify.min',
    'select2/dist/js/select2.full.min',
], function (
    $,
    _,
    DOMPurify
) {
    var $select = $("#select2-navigation");

    $select.on('select2:select', function () {
        document.location = $select.val();
    });

    $select.select2({
        placeholder: gettext("Edit a report or data source"),
        templateResult: function (item) {
            var text = item.text.trim();
            if (!item.element) {
                return text;
            }
            var options = $(item.element).data();
            return _.template("<%= static_label %> <%= deactivated_label %> <i class='<%= icon %>'></i> <%= text %> <script>alert('stuff')</script>")({
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
