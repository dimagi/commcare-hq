/* globals XPATH_CONFIG */
ko.bindingHandlers.xpathValidator = (function () {
    /*
     * usage:
     *
     * <input data-bind="xpathValidator: xpathText" placeholder="My Placeholder"/>
     * where xpathText can be
     * - a string literal, in which case it provides a starting value
     * - null, in which case the input’s @value provides a starting value
     * - a knockout observable, in which case xpathValidator binding
     * behaves like the value binding, in addition to providing xpath validation
     *
     */
    var XPathValidator = function (xpathText, allowCaseHashtags) {
        var self = {};
        if (!ko.isObservable(xpathText)){
            self.xpathText = ko.observable(xpathText);
        } else {
            self.xpathText = xpathText;
        }

        self.allowCaseHashtags = allowCaseHashtags;
        self.error = ko.observable('');
        self.errorTitle = ko.computed(function () {
            var errorLines = self.error().split('\n');
            return errorLines[0];

        });
        self.refreshError = function (value) {
            var error = '';
            if (self.xpathText()) {
                try {
                    XPATH_CONFIG.configureHashtags(self.allowCaseHashtags).parse(value);
                } catch (e) {
                    error = e.message;
                }
            }
            self.error(error);
        };
        self.xpathText.subscribe(self.refreshError);
        self.refreshError(self.xpathText());
        return self;
    };
    return {
        init: function (element, valueAccessor) {
            var value = valueAccessor();
            if (value === null) {
                value = $(element).val();
            }
            var input = $(element).get(0);
            var xpathText, allowCaseHashtags, errorHtml;
            if (value.hasOwnProperty('text')) {
                xpathText = value.text;
                allowCaseHashtags = !!value.allowCaseHashtags;
                errorHtml = value.errorHtml;
            } else {
                xpathText = value;
                allowCaseHashtags = false;
                errorHtml = '';
            }

            ko.renderTemplate('XPathValidator.template', {
                xpathValidator: XPathValidator(xpathText, allowCaseHashtags),
                input: input,
                errorHtml: errorHtml,
            }, {}, element, 'replaceNode');
        },
    };
}());
