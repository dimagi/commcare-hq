hqDefine('domain/js/pro-bono', [
    'jquery',
    'select2-3.5.2-legacy/select2',
], function(
    $
) {
    var _validateEmail = function (email) {
        // from http://stackoverflow.com/questions/46155/validate-email-address-in-javascript
        var re = /^(([^<>()[\]\\.,;:\s@\"]+(\.[^<>()[\]\\.,;:\s@\"]+)*)|(\".+\"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;
        return re.test(email);
    };

    $(function () {
        $('#id_contact_email').select2({
            createSearchChoice: function (term, data) {
                var matchedData = $(data).filter(function() {
                    return this.text.localeCompare(term) === 0;
                });

                var isEmailValid = _validateEmail(term);

                if (matchedData.length === 0 && isEmailValid) {
                    return { id: term, text: term };
                }
            },
            multiple: true,
            data: [],
            formatNoMatches: function () {
                return gettext("Please enter a valid email.");
            },
        });
    });
});
