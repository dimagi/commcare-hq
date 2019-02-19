hqDefine('domain/js/pro-bono', [
    'jquery',
    'select2/dist/js/select2.full.min',
], function (
    $
) {
    var _validateEmail = function (email) {
        // from http://stackoverflow.com/questions/46155/validate-email-address-in-javascript
        var re = /^(([^<>()[\]\\.,;:\s@\"]+(\.[^<>()[\]\\.,;:\s@\"]+)*)|(\".+\"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/; // eslint-disable-line no-useless-escape
        return re.test(email);
    };

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

                if (matchedData.length === 0 && _validateEmail(term)) {
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
