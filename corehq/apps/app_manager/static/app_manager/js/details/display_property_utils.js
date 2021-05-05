/**
 * Contains a few UI utilities for the Display Properties
 * section of case list/detail configuration.
 */
hqDefine("app_manager/js/details/display_property_utils", function () {
    var module = {};

    module.fieldFormatWarningMessage = gettext("Must begin with a letter and contain only letters, numbers, '-', and '_'");

    module.getFieldHtml = function (field) {
        var text = field || '';
        if (module.isAttachmentProperty(text)) {
            text = text.substring(text.indexOf(":") + 1);
        }
        var parts = text.split('/');
        // wrap all parts but the last in a label style
        for (var j = 0; j < parts.length - 1; j++) {
            parts[j] = ('<span class="label label-info">' +
                parts[j] + '</span>');
        }
        if (parts[j][0] === '#') {
            parts[j] = ('<span class="label label-info">' +
                module.toTitleCase(parts[j]) + '</span>');
        } else {
            parts[j] = ('<code style="display: inline-block;">' +
                parts[j] + '</code>');
        }
        return parts.join('<span style="color: #DDD;">/</span>');
    };

    module.isAttachmentProperty = function (value) {
        return value && value.indexOf("attachment:") === 0;
    };

    module.isValidPropertyName = function (name) {
        var word = '[a-zA-Z][\\w_-]*';
        var regex = new RegExp(
            '^(' + word + ':)*(' + word + '\\/)*#?' + word + '$'
        );
        return regex.test(name);
    };

    module.toTitleCase = function (str) {
        return (str
            .replace(/[_\/-]/g, ' ')
            .replace(/#/g, '')
        ).replace(/\w\S*/g, function (txt) {
            return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase();
        });
    };

    /**
     * Enable autocomplete on the given jquery element with the given autocomplete
     * options.
     * @param $elem
     * @param options: Array of strings.
     */
    module.setUpAutocomplete = function ($elem, options) {
        if (!_.contains(options, $elem.value)) {
            options.unshift($elem.value);
        }
        $elem.$edit_view.select2({
            minimumInputLength: 0,
            width: '100%',
            tags: true,
            escapeMarkup: function (m) {
                return DOMPurify.sanitize(m);
            },
            templateResult: function (result) {
                var formatted = result.id;
                if (module.isAttachmentProperty(result.id)) {
                    formatted = (
                        '<i class="fa fa-paperclip"></i> ' +
                        result.id.substring(result.id.indexOf(":") + 1)
                    );
                }
                return DOMPurify.sanitize(formatted);
            },
        }).on('change', function () {
            $elem.val($elem.$edit_view.value);
            $elem.fire('change');
        });
        return $elem;
    };

    return module;
});