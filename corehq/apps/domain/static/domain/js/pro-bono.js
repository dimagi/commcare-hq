hqDefine('domain/js/pro-bono', [
    'jquery',
    'hqwebapp/js/utils/email',
    'select2/dist/js/select2.full.min',
    'commcarehq',
], function (
    $,
    emailUtils
) {

    $(function () {
        $('#id_contact_email').select2({
            tags: true,
            createTag: function (params) {
                var term = params.term,
                    data = this.$element.select2("data");

                // Prevent duplicates
                var matchedData = $(data).filter(function () {
                    return this.text.localeCompare(term) === 0;
                });

                if (matchedData.length === 0 && emailUtils.validateEmail(term)) {
                    return { id: term, text: term };
                }
            },
            multiple: true,
            data: [],
            language: {
                noResults: function () {
                    return gettext("Please enter a valid email.");
                },
            },
        });
    });
});
