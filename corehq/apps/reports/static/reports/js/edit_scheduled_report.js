hqDefine("reports/js/edit_scheduled_report.js", function() {
    var initial_page_data = hqImport("hqwebapp/js/initial_page_data.js").get;
    var isConfigurableMap = initial_page_data('is_configurable_map');
    var languagesMap = initial_page_data('languages_map');
    var languagesForSelect = initial_page_data('languages_for_select');

    var updateUcrElements = function(selectedConfigs){
        var showUcrElements = _.any(
            selectedConfigs, function(i){return isConfigurableMap[i] === true;}
        );
        var currentLanguageOptions = [];

        if (showUcrElements){
            $("#ucr-privacy-warning").show();

            // Figure out which options to show in the select2
            var languageLists = _.map(selectedConfigs, function(i){return languagesMap[i];});
            var languageSet = _.reduce(languageLists, function(memo, list){
                _.map(list, function(e){
                    memo[e] = true;
                });
                return memo;
            }, {});
            var currentLanguageOptions = Object.keys(languageSet).sort();
            var $id_language = $('#id_language');

            if (currentLanguageOptions.length === 1 && currentLanguageOptions[0] === 'en') {
                $id_language.val('en');
                $('#div_id_language').hide();
            } else {
                // Update the options of the select2
                var current = $id_language.val();
                $id_language.empty();

                // Populate the select2
                _.map(currentLanguageOptions, function (l) {
                    $id_language.append(
                        $("<option></option>").attr("value", l).text(languagesForSelect[l][1])
                    );
                });
                $id_language.val(current);
                $("#div_id_language").show();
            }
        } else {
            $("#div_id_language").hide();
            $("#ucr-privacy-warning").hide();
        }
    };

    $("#id_config_ids").change(function(){
        updateUcrElements($(this).val());
    });
    var multiselect_utils = hqImport('style/js/multiselect_utils');
    multiselect_utils.createFullMultiselectWidget(
        'id_config_ids',
        django.gettext("Available Reports"),
        django.gettext("Included Reports"),
        django.gettext("Search Reports...")
    );
    updateUcrElements($("#id_config_ids").val());

    var scheduled_report_form_helper = new ScheduledReportFormHelper({
        weekly_options: initial_page_data('weekly_day_options'),
        monthly_options: initial_page_data('monthly_day_options'),
        day_value: initial_page_data('day_value'),
    });
    scheduled_report_form_helper.init();

    $('#id-scheduledReportForm').submit(function() {
        ga_track_event('Scheduled Reports', 'Create a scheduled report', '-', {
            'hitCallback': function () {
                document.getElementById('id-scheduledReportForm').submit();
            }
        });
        return false;
    });
});
