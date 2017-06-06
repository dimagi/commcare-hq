hqDefine("app_manager/js/form_view.js", function() {
    function formFilterMatches(filter, pattern_matches, substring_matches) {
        if (typeof(filter) != 'string') {
            return false;
        }

        var result = false;
        $.each(pattern_matches, function(index, pattern) {
            result = result || filter.match(pattern);
        });

        $.each(substring_matches, function(index, sub) {
            result = result || filter.indexOf(sub) != -1;
        });

        return result;
    }

    function FormFilter() {
        var self = this;
        var patterns = initial_page_data('form_filter_patterns');

        self.formFilter = ko.observable(initial_page_data('form_filter'));

        self.caseReferenceNotAllowed = ko.computed(function() {
            var moduleUsesCase = initial_page_data('all_other_forms_require_a_case') && initial_page_data('form_requires') === 'case';
            if (!moduleUsesCase || initial_page_data('put_in_root')) {
                // We want to determine here if the filter expression references
                // any case but the user case.
                var filter = self.formFilter();
                if (typeof(filter) !== 'string') {
                    return true;
                }

                $.each(patterns.usercase_substring, function(index, sub) {
                    filter = filter.replace(sub, '');
                });

                if (formFilterMatches(filter, patterns.case, patterns.case_substring)) {
                    return true;
                }
            }
            return false;
        });

        self.userCaseReferenceNotAllowed = ko.computed(function() {
            return !initial_page_data('is_usercase_in_use') && formFilterMatches(
                self.formFilter(), patterns.usercase, patterns.usercase_substring
            );
        });

        self.allowed = ko.computed(function () {
            return !self.formFilter() || !self.caseReferenceNotAllowed() && !self.userCaseReferenceNotAllowed();
        });
    }

    var initial_page_data = hqImport("hqwebapp/js/initial_page_data.js").get;
    $(function (){
        // Validation for build
        var setupValidation = hqImport('app_manager/js/app_manager.js').setupValidation;
        setupValidation(hqImport("hqwebapp/js/urllib.js").reverse("validate_form_for_build"));

        // Settings > Display Condition
        var $formFilter = $('#form-filter');
        if ($formFilter.length && initial_page_data('allow_form_filtering')) {
            $('#form-filter').koApplyBindings(new FormFilter());
        }

        // Settings > Custom Instances
        if (COMMCAREHQ.toggleEnabled('CUSTOM_INSTANCES')) {
            var customInstances = hqImport('app_manager/js/custom_intances.js').wrap({
                customInstances: initial_page_data('custom_instances'),
            });
            $('#custom-instances').koApplyBindings(customInstances);
        }

        // Case Management > Data dictionary descriptions for case properties
        $('.property-description').popover();

        // Advanced > XForm > Upload
        (function(){
            $("#xform_file_input").change(function(){
                if ($(this).val()) {
                    $("#xform_file_submit").show();
                } else {
                    $("#xform_file_submit").hide();
                }
            }).trigger('change');
        }());

        // Advanced > XForm > View
        $("#xform-source-opener").click(function(evt){
            if (evt.shiftKey) {
                // Shift+click: edit form source
                $(".source-readonly").hide();
                $(".source-edit").show();
                $.get($(this).data('href'), function (data) {
                    $("#xform-source-edit").text(data).blur();
                }, 'json');
            } else {
                // Plain click: view form source
                $(".source-edit").hide();
                $(".source-readonly").show();
                $("#xform-source").text("Loading...");
                $.get($(this).data('href'), function (data) {
                    var brush = new SyntaxHighlighter.brushes.Xml();
                    brush.init({ toolbar: false });
                    // brush.getDiv seems to escape inconsistently, so I'm helping it out
                    data = data.replace(/&/g, '&amp;');
                    $("#xform-source").html(brush.getDiv(data));
                }, 'json');
            }
            $(".xml-source").modal();
        });
    });
});
