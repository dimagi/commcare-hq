hqDefine("m4change/javascripts/main", function () {
    var initialPageData = hqImport("hqwebapp/js/initial_page_data");
    $(function ()
        var OPTIONS = {
            users: initialPageData.get("users"),
            groups: initialPageData.get("groups"),
            receiverUrl: initialPageData.reverse('receiver_secure_post'),
            enddate: initialPageData.get("end_date"),
            webUserID: initialPageData.get("user_id"),
            domain: initialPageData.get("domain"),
        };

        var managementModel = new McctProjectReviewPageManagement(OPTIONS);
        function applyBindings() {
            var $mcctProjectReviewPageManagement = $('#mcct_project_review_page_management');
            var element = $mcctProjectReviewPageManagement[0];
            element.koApplyBindings(managementModel);

            $mcctProjectReviewPageManagement.find('a.select-all').click(function () {
                $mcctProjectReviewPageManagement.find('input.selected-element').prop('checked', true).change();
                return false;
            });

            $mcctProjectReviewPageManagement.find('a.select-none').click(function() {selectNone(); return false;});
            $mcctProjectReviewPageManagement.find('.dataTables_paginate a').mouseup(selectNone);
            $mcctProjectReviewPageManagement.find('.dataTables_length select').change(selectNone);

            function selectNone() {
                $mcctProjectReviewPageManagement.find('input.selected-element:checked').prop('checked', false).change();
            }
        }

        function applyCheckboxListeners() {
             $('input.selected-element', '#mcct_project_review_page_management').on('change', function(event) {
                 managementModel.updateSelection({}, event);
             });
        }

        var keepTrying = setInterval(function () {
            if (window.reportTables !== undefined) {
                clearInterval(keepTrying);
                applyBindings();
                applyCheckboxListeners();
                window.reportTables.fnDrawCallback = applyCheckboxListeners;
            }
        }, 1000);

        $('.hq-help-template').each(function () {
            hqImport("hqwebapp/js/main").transformHelpTemplate($(this), true);
        });
    });
});
