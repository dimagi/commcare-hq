/*
 * Main module for non-report ilsgateway pages
 */
hqDefine("ilsgateway/js/main", function() {
    var _post = function (elem, url, options) {
        var options = options || {};
        var success = options.success || "{% trans "Sync Successful" %}";
        var error = options.error || "{% trans "Error!" %}";
        $(elem).prop('disabled', true).html("{% trans "Syncing..." %}");

        $.ajax({
            type: 'POST',
            url: url,
            success: function() {
                $(elem).html(success);
            },
            error: function() {
                $(elem).html(error).addClass("btn-danger");
            }
        });
    };

    $(function() {
        // Config page
        $("#run_reports").click(function() {
            var url = '{% url 'run_reports' domain %}';
            var successMessage = "{% trans "Sync started" %}";
            _post(this, url, {success: successMessage});
        });

        // Supervision Docs page
        $('.delete').click(function() {
            $(this).parent().find('.modal').modal();
        });

        // Pending Recalculations page
        var $recalculations = $('#recalculations');
        if ($recalculations.length) {
            $recalculations.dataTable();
        }

        // Edit Location page
        var $editLocations = $('#edit_locations');
        if ($editLocations.length) {
            var multiselect_utils = hqImport('hqwebapp/js/multiselect_utils');
            multiselect_utils.createFullMultiselectWidget(
                'id_selected_ids',
                gettext("Available Locations"),
                gettext("Locations in Program"),
                gettext("Search Locations...")
            );

            var LocationModelView = function() {
                this.isPilot = ko.observable($('#id_is_pilot').get(0).checked);
            };
            ko.applyBindings(new LocationModelView(), $editLocations.get(0));
        }
    });
});
