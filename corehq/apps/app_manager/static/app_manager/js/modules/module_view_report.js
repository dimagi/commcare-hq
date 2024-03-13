hqDefine("app_manager/js/modules/module_view_report", function () {
    $(function () {
        var initialPageData = hqImport("hqwebapp/js/initial_page_data");
        var initNavMenuMedia = hqImport('app_manager/js/app_manager_media').initNavMenuMedia;
        var reportModuleModel = hqImport('app_manager/js/modules/report_module').reportModuleModel;
        var staticFilterDataModel = hqImport('app_manager/js/modules/report_module').staticFilterDataModel;
        var choiceListUtils = hqImport('reports_core/js/choice_list_utils');

        // Hacky: report modules only deal with one kind of multimedia (the menu image/audio),
        // so assume nav_menu_media_specifics has one element.
        var navMenuMediaItem = initialPageData.get("nav_menu_media_specifics")[0];
        var navMenuMedia = initNavMenuMedia(
            "",
            navMenuMediaItem.menu_refs.image,
            navMenuMediaItem.menu_refs.audio,
            initialPageData.get("multimedia_object_map"),
            navMenuMediaItem.default_file_name
        );

        var saveURL = hqImport("hqwebapp/js/initial_page_data").reverse("edit_report_module");
        var staticData = staticFilterDataModel(initialPageData.get('static_data_options'));
        var reportModule = reportModuleModel(_.extend({}, initialPageData.get("report_module_options"), {
            lang: initialPageData.get('lang'),
            staticFilterData: staticData,
            saveURL: saveURL,
            menuImage: navMenuMedia.menuImage,
            menuAudio: navMenuMedia.menuAudio,
            containerId: "#settings",
        }));

        _([
            $('#save-button'),
            $('#module-name'),
            $('#module-filter'),
            $('#report-list'),
            $('#add-report-btn'),
            $('#report-context-tile'),
        ]).each(function ($element) {
            // never call applyBindings with null as the second arg!
            if ($element.get(0)) {
                $element.koApplyBindings(reportModule);
            }
        });
        navMenuMedia.menuImage.ref.subscribe(function () {
            reportModule.changeSaveButton();
        });
        navMenuMedia.menuAudio.ref.subscribe(function () {
            reportModule.changeSaveButton();
        });

        var select2s = $('.choice_filter');
        for (var i = 0; i < select2s.length; i++) {
            var element = select2s.eq(i);
            var initialValues = element.data('initial');

            // Any initially-selected values need to be appended to the <select> as options
            // This needs to happen before the .select2() call, otherwise it'd need a
            // change event to take effect
            if (initialValues) {
                if (!_.isArray(initialValues)) {
                    initialValues = [initialValues];
                }
                _.each(initialValues, function (value) {
                    element.append(new Option(value, value));
                });
                element.val(initialValues);
            }

            element.select2({
                minimumInputLength: 0,
                multiple: true,
                allowClear: true,
                placeholder: " ",   // allowClear only respected if there is a non empty placeholder
                ajax: {
                    url: (hqImport("hqwebapp/js/initial_page_data").reverse("choice_list_api").split('report_id')[0]
                          + element.data("filter-name") + "/"),
                    dataType: 'json',
                    delay: 250,
                    data: choiceListUtils.getApiQueryParams,
                    processResults: choiceListUtils.formatPageForSelect2,
                    cache: true,
                },
            });
        }
    });
});
