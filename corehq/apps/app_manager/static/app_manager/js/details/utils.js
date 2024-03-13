/* globals DOMPurify */
/**
 * Contains a few UI utilities for the Display Properties
 * section of case list/detail configuration.
 *
 * Depends on `add_ons` being available in initial page data
 */
hqDefine("app_manager/js/details/utils", function () {
    var module = {};

    module.fieldFormatWarningMessage = gettext("Must begin with a letter and contain only letters, numbers, '-', and '_'");

    module.getFieldFormats = function () {
        var formats = [{
            value: "plain",
            label: gettext('Plain'),
        }, {
            value: "date",
            label: gettext('Date'),
        }, {
            value: "time-ago",
            label: gettext('Time Since or Until Date'),
        }, {
            value: "phone",
            label: gettext('Phone Number'),
        }, {
            value: "enum",
            label: gettext('ID Mapping'),
        }, {
            value: "late-flag",
            label: gettext('Late Flag'),
        }, {
            value: "invisible",
            label: gettext('Search Only'),
        }, {
            value: "address",
            label: gettext('Address'),
        }, {
            value: "distance",
            label: gettext('Distance from current location'),
        }, {
            value: "markdown",
            label: gettext('Markdown'),
        }];

        if (hqImport('hqwebapp/js/toggles').toggleEnabled('CASE_LIST_MAP')) {
            formats.push({
                value: "address-popup",
                label: gettext('Address Popup (Web Apps only)'),
            });
        }

        if (hqImport('hqwebapp/js/toggles').toggleEnabled('CASE_LIST_CLICKABLE_ICON')) {
            formats.push({
                value: "clickable-icon",
                label: gettext('Clickable Icon (Web Apps only)'),
            });
        }

        if (hqImport('hqwebapp/js/toggles').toggleEnabled('MM_CASE_PROPERTIES')) {
            formats.push({
                value: "picture",
                label: gettext('Picture'),
            }, {
                value: "audio",
                label: gettext('Audio'),
            });
        }

        var addOns = hqImport("hqwebapp/js/initial_page_data").get("add_ons");
        if (addOns.enum_image) {
            formats.push({
                value: "enum-image",
                label: gettext('Icon'),
            });
        }
        if (addOns.conditional_enum) {
            formats.push({
                value: "conditional-enum",
                label: gettext('Conditional ID Mapping'),
            });
        }

        return formats;
    };

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

    module.TIME_AGO = {
        year: 365.25,
        month: 365.25 / 12,
        week: 7,
        day: 1,
    };

    module.toTitleCase = function (str) {
        return (str
            .replace(/[_/-]/g, ' ')
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
                var formatted = result.text;
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
