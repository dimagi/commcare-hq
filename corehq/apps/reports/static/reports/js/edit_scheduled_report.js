/* globals django */
hqDefine("reports/js/edit_scheduled_report", function() {
    var add_options_to_select = function($select, opt_list, selected_val) {
        for (var i = 0; i < opt_list.length; i++) {
            var $opt = $('<option />').val(opt_list[i][0]).text(opt_list[i][1]);
            if (opt_list[i][0] === selected_val) {
                $opt.prop("selected", true);
            }
            $select.append($opt);
        }
        return $select;
    };

    var update_day_input = function(weekly_options, monthly_options, day_value) {
        var $interval = $interval || $('[name="interval"]');
        $('#div_id_day').remove();
        if ($interval.val() !== 'daily') {
            var opts = $interval.val() === 'weekly' ? weekly_options : monthly_options;
            var $day_select = $('<select id="id_day" class="select form-control" name="day" />');
            $day_select = add_options_to_select($day_select, opts, day_value);
            var $day_control_group = $('<div id="div_id_day" class="form-group" />')
                .append($('<label for="id_day" class="control-label col-sm-3 col-md-2 requiredField">Day<span class="asteriskField">*</span></label>'))
                .append($('<div class="controls col-sm-9 col-md-8 col-lg-6" />').append($day_select));
            $interval.closest('.form-group').after($day_control_group);
        }
    };

    var ScheduledReportFormHelper = function(options) {
        var self = this;
        self.weekly_options = options.weekly_options;
        self.monthly_options = options.monthly_options;
        self.day_value = options.day_value;

        self.init = function() {
            $(function() {
                update_day_input(self.weekly_options, self.monthly_options, self.day_value);
                $('[name="interval"]').change(function() {
                    update_day_input(self.weekly_options, self.monthly_options);
                });
            });
        };
    };

    var initial_page_data = hqImport("hqwebapp/js/initial_page_data").get;
    var isConfigurableMap = initial_page_data('is_configurable_map');
    var languagesMap = initial_page_data('languages_map');
    var languagesForSelect = initial_page_data('languages_for_select');
    var isOwner = initial_page_data('is_owner');

    var updateUcrElements = function(selectedConfigs){
        var showUcrElements = _.any(
            selectedConfigs, function(i){return isConfigurableMap[i] === true;}
        );

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

    $('#id_language').select2({
        placeholder: gettext("Select a language..."),
    });
    $("#id_config_ids").change(function(){
        updateUcrElements($(this).val());
    });
    if (!isOwner) {
        $('#id_config_ids').hide().after(
            $('#id_config_ids').children().map(function () {
                return $("<div>").text($(this).text()).get(0);
            })
        );
    }
    else {
        var multiselect_utils = hqImport('hqwebapp/js/multiselect_utils');
        multiselect_utils.createFullMultiselectWidget(
            'id_config_ids',
            django.gettext("Available Reports"),
            django.gettext("Included Reports"),
            django.gettext("Search Reports...")
        );
    }
    updateUcrElements($("#id_config_ids").val());

    var scheduled_report_form_helper = new ScheduledReportFormHelper({
        weekly_options: initial_page_data('weekly_day_options'),
        monthly_options: initial_page_data('monthly_day_options'),
        day_value: initial_page_data('day_value'),
    });
    scheduled_report_form_helper.init();

    $('#id-scheduledReportForm').submit(function() {
        hqImport('analytix/js/google').track.event('Scheduled Reports', 'Create a scheduled report', '-', "", {}, function () {
            document.getElementById('id-scheduledReportForm').submit();
        });
        return false;
    });
});
