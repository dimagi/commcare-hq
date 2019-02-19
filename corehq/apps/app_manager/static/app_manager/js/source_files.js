/* globals hqDefine */
hqDefine('app_manager/js/source_files',[
    'jquery',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'select2/dist/js/select2.full.min',
], function ($, _, initialPageData) {
    $(function () {
        $('.toggle-next').click(function (e) {
            e.preventDefault();
            $(this).parents('tr').next('tr').toggleClass("hide");
        });

        var currentVersion = initialPageData.get('current_version'),
            $form = $("#compare-form"),
            $select = $form.find("select");

        $select.select2({
            ajax: {
                url: initialPageData.reverse('paginate_releases'),
                dataType: 'json',
                data: function (params) {
                    return {
                        limit: 10,
                        query: params.term,
                        page: params.page,
                    };
                },
                processResults: function (data) {
                    return {
                        results: _.map(data.apps, function (build) {
                            return {
                                id: build.id,
                                text: build.version + ": " + (build.build_comment || gettext("no comment")),
                            };
                        }),
                        pagination: data.pagination,
                    };
                },
            },
            width: '200px',
        });

        $form.find("button").click(function () {
            var version = $select.val();
            if (!version) {
                alert(gettext("Please enter a version to compare"));
                return;
            }
            window.location = initialPageData.reverse('diff', version);
        });
    });
});
