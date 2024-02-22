hqDefine("app_manager/js/modules/case_list_setting", function () {
    function getLabel(slug) { return $('.case-list-setting-label[data-slug="' + slug + '"]'); }
    function getShow(slug) { return $('.case-list-setting-show[data-slug="' + slug + '"]'); }
    function getMedia(slug) { return $('.case-list-setting-media[data-slug="' + slug + '"]'); }

    function updateCaseListLabelError(slug) {
        var labelText = getLabel(slug).find('input').val();
        var show = getShow(slug).val() === 'true';
        if (!labelText.length && show) {
            getLabel(slug).closest('.form-group').addClass('has-error');
            $('#case_list_label_error').removeClass("hide");
        } else {
            getLabel(slug).closest('.form-group').removeClass('has-error');
            $('#case_list_label_error').addClass("hide");
        }
    }

    function updateCaseListLabel(slug, show) {
        getLabel(slug)[show ? 'show' : 'hide']();
        getMedia(slug)[show ? 'show' : 'hide']();
        updateCaseListLabelError(slug);
    }

    $(function () {
        _.each($(".case-list-setting-label"), function (el) {
            var $el = $(el),
                slug = $el.data("slug");
            $el.find("input").attr("name", slug + "-label");
            $el.find("input").on('textchange', function () {
                updateCaseListLabelError(slug);
            });
        });

        _.each($(".case-list-setting-show"), function (el) {
            var $el = $(el),
                slug = $el.data("slug");
            updateCaseListLabel(slug, $el.val() === 'true');
            $el.change(function () {
                updateCaseListLabel(slug, $el.val() === 'true');
            });
        });
    });
});
