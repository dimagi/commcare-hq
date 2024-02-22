hqDefine("reports/js/edit_scheduled_report", [
    "jquery",
    "underscore",
    "analytix/js/google",
    "hqwebapp/js/initial_page_data",
    "hqwebapp/js/toggles",
    "hqwebapp/js/multiselect_utils",
    "hqwebapp/js/bootstrap3/widgets",  // autocomplete widget for email recipient list
    "jquery-ui/ui/widgets/datepicker",
    'hqwebapp/js/bootstrap3/components.ko',    // select toggle widget
], function (
    $,
    _,
    googleAnalytics,
    initialPageData,
    toggles,
    multiselectUtils
) {
    var addOptionsToSelect = function ($select, optList, selectedVal) {
        for (var i = 0; i < optList.length; i++) {
            var $opt = $('<option />').val(optList[i][0]).text(optList[i][1]);
            if (optList[i][0] === selectedVal) {
                $opt.prop("selected", true);
            }
            $select.append($opt);
        }
        return $select;
    };

    var updateIntervalAuxInput = function (weeklyOptions, monthlyOptions, dayValue) {
        var $interval = $interval || $('[name="interval"]');
        $('#div_id_day').remove();
        if ($interval.val() !== 'hourly' && $interval.val() !== 'daily') {
            var opts = $interval.val() === 'weekly' ? weeklyOptions : monthlyOptions;
            var $daySelect = $('<select id="id_day" class="select form-control" name="day" />');
            $daySelect = addOptionsToSelect($daySelect, opts, dayValue);
            var $dayControlGroup = $('<div id="div_id_day" class="form-group" />')
                .append($('<label for="id_day" class="control-label col-sm-3 col-md-2 requiredField">Day<span class="asteriskField">*</span></label>'))
                .append($('<div class="controls col-sm-9 col-md-8 col-lg-6" />').append($daySelect));
            $interval.closest('.form-group').after($dayControlGroup);
        }

        $('#div_id_stop_hour').hide();
        if ($interval.val() === 'hourly') {
            $("label[for='id_hour']").text(gettext('From Time') + "*");
            $('#div_id_stop_hour').show();
        } else {
            $("label[for='id_hour']").text(gettext('Time') + "*");
        }
    };

    var ScheduledReportFormHelper = function (options) {
        var self = this;
        self.weekly_options = options.weekly_options;
        self.monthly_options = options.monthly_options;
        self.day_value = options.day_value;

        self.init = function () {
            $(function () {
                _.delay(function () {
                    // Delay initialization so that widget is created by the time this code is called
                    updateIntervalAuxInput(self.weekly_options, self.monthly_options, self.day_value);
                });
                $(document).on('change', '[name="interval"]', function () {
                    updateIntervalAuxInput(self.weekly_options, self.monthly_options);
                });
                $("#id_start_date").datepicker({
                    dateFormat: "yy-mm-dd",
                    minDate: 0,
                });
            });
        };
    };

    var isConfigurableMap = initialPageData.get('is_configurable_map');
    var supportsTranslations = initialPageData.get('supports_translations');
    var languagesMap = initialPageData.get('languages_map');
    var languagesForSelect = initialPageData.get('languages_for_select');
    var isOwner = initialPageData.get('is_owner');

    var updateUcrElements = function (selectedConfigs) {
        var showUcrElements = _.any(
            selectedConfigs, function (i) {return isConfigurableMap[i] === true;}
        );
        var showTranslation = showUcrElements || _.any(
            selectedConfigs, function (i) {return supportsTranslations[i] === true;}
        );

        if (showTranslation) {
            if (showUcrElements) {
                $("#ucr-privacy-warning").show();
            }
            // Figure out which options to show in the select2
            var languageLists = _.map(selectedConfigs, function (i) {return languagesMap[i];});
            var languageSet = _.reduce(languageLists, function (memo, list) {
                _.map(list, function (e) {
                    memo[e] = true;
                });
                return memo;
            }, {});
            var currentLanguageOptions = Object.keys(languageSet).sort();
            var $idLanguage = $('#id_language');

            if (currentLanguageOptions.length === 1 && currentLanguageOptions[0] === 'en') {
                $idLanguage.val('en');
                $('#div_id_language').hide();
            } else {
                // Update the options of the select2
                var current = $idLanguage.val();
                $idLanguage.empty();

                // Populate the select2
                _.map(currentLanguageOptions, function (l) {
                    $idLanguage.append(
                        $("<option></option>").attr("value", l).text(languagesForSelect[l][1])
                    );
                });
                $idLanguage.val(current);
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
    $("#id_config_ids").change(function () {
        updateUcrElements($(this).val());
    });
    if (!isOwner) {
        $('#id_config_ids').hide().after(
            $('#id_config_ids').children().map(function () {
                return $("<div>").text($(this).text()).get(0);
            })
        );
    } else {
        multiselectUtils.createFullMultiselectWidget('id_config_ids', {
            selectableHeaderTitle: gettext("Available Reports"),
            selectedHeaderTitle: gettext("Included Reports"),
            searchItemTitle: gettext("Search Reports..."),
        });
    }
    updateUcrElements($("#id_config_ids").val());

    var helper = new ScheduledReportFormHelper({
        weekly_options: initialPageData.get('weekly_day_options'),
        monthly_options: initialPageData.get('monthly_day_options'),
        day_value: initialPageData.get('day_value'),
    });
    helper.init();

    $('#id-scheduledReportForm').submit(function () {
        googleAnalytics.track.event('Scheduled Reports', 'Create a scheduled report', '-', "", {}, function () {
            document.getElementById('id-scheduledReportForm').submit();
        });
        return false;
    });
});
