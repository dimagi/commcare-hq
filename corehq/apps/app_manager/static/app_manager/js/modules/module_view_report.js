hqDefine("app_manager/js/modules/module_view_report", function() {
    $(function () {
        var initial_page_data = hqImport("hqwebapp/js/initial_page_data").get;
        var initNavMenuMedia = hqImport('app_manager/js/app_manager_media').initNavMenuMedia;
        var select2Separator = hqImport('app_manager/js/modules/report_module').select2Separator;
        var ReportModule = hqImport('app_manager/js/modules/report_module').ReportModule;
        var StaticFilterData = hqImport('app_manager/js/modules/report_module').StaticFilterData;
        // Hacky: report modules only deal with one kind of multimedia (the menu image/audio),
        // so assume nav_menu_media_specifics has one element.
        var navMenuMediaItem = initial_page_data("nav_menu_media_specifics")[0];
        var navMenuMedia = initNavMenuMedia(
            "",
            navMenuMediaItem.menu_refs.image,
            navMenuMediaItem.menu_refs.audio,
            initial_page_data("multimedia_object_map"),
            navMenuMediaItem.default_file_name
        );
        var saveURL = hqImport("hqwebapp/js/initial_page_data").reverse("edit_report_module");
        var staticData = new StaticFilterData(initial_page_data('static_data_options'));
        var reportModule = new ReportModule(_.extend({}, initial_page_data("report_module_options"), {
            lang: initial_page_data('lang'),
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
        ]).each(function($element) {
            // never call applyBindings with null as the second arg!
            if ($element.get(0)) {
                $element.koApplyBindings(reportModule);
            }
        });
        navMenuMedia.menuImage.ref.subscribe(function() {
            reportModule.changeSaveButton();
        });
        navMenuMedia.menuAudio.ref.subscribe(function() {
            reportModule.changeSaveButton();
        });

        var select2s = $('.choice_filter');
        for(var i = 0; i < select2s.length; i++) {
            var element = select2s.eq(i);

            var separator = select2Separator;
            var initialValues = element.val() !== "" ? element.val().split(separator) : [];
            element.select2({
                minimumInputLength: 0,
                multiple: true,
                separator: separator,
                allowClear: true,
                // allowClear only respected if there is a non empty placeholder
                placeholder: " ",
                ajax: {
                    // TODO - this is pretty hackish
                    url: (hqImport("hqwebapp/js/initial_page_data").reverse("choice_list_api").split('report_id')[0]
                          + element.parent()[0].lastElementChild.value + "/"),
                    dataType: 'json',
                    quietMillis: 250,
                    data: choiceListUtils.getApiQueryParams,
                    results: choiceListUtils.formatPageForSelect2,
                    cache: true,
                },
            });
            element.select2('data', _.map(initialValues, function(v){
                return {id: v, text: v};
            }));
        }
    });
});
