/* globals hqDefine */
hqDefine("domain/js/internal_settings", function() {
    var areas = hqImport('hqwebapp/js/initial_page_data').get('areas');

    function update_subareas() {
        var $subarea = $subarea || $('[name="sub_area"]');
        var chosen_sub_area = $subarea.val();
        var area = $('[name="area"]').val();
        var valid_sub_areas = [];
        if (area) {
            valid_sub_areas = areas[area];
        }
        $subarea.empty().append($("<option></option>").attr("value", '').text('---'));
        _.each(valid_sub_areas, function(val) {
            var $opt = $("<option></option>").attr("value", val).text(val);
            if (val == chosen_sub_area) {
                $opt.prop("selected", true);
            }
            $subarea.append($opt);
        });
    }

    function update_workshop_region() {
        var $wr = $wr || $('#id_workshop_region').parent().parent();
        var $workshop_initiative = $workshop_initiative || $('[name="initiative"][value="Workshop"]');
        if ($workshop_initiative.is(":checked")) {
            $wr.show();
        } else {
            $wr.hide();
        }
    }

    $(function() {
        update_subareas();
        update_workshop_region();
        $('[name="area"]').change(function() {
            update_subareas();
        });
        $('[name="initiative"]').change(function() {
            update_workshop_region();
        });

    });

    $(function() {
        $('#id_deployment_date').datepicker({
            changeMonth: true,
            changeYear: true,
            showButtonPanel: true,
            dateFormat: 'yy-mm-dd',
            maxDate: '0',
            numberOfMonths: 2
        });
    });

    var multiselect_utils = hqImport('hqwebapp/js/multiselect_utils');
    multiselect_utils.createFullMultiselectWidget(
        'id_countries',
        django.gettext("Available Countries"),
        django.gettext("Active Countries"),
        django.gettext("Search Countries...")
    );
});