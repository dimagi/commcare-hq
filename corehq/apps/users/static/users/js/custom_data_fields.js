/**
 *  This file defines a model for editing custom data fields while creating or editing a mobile user.
 */
hqDefine("users/js/custom_data_fields", [
    'knockout',
    'underscore',
    'hqwebapp/js/assert_properties',
], function (
    ko,
    _,
    assertProperties
) {
    var fieldModel = function (value) {
        return {
            value: ko.observable(value),
            previousValue: ko.observable(value),    // save user-entered value
            disable: ko.observable(false),
        };
    };

    var customDataFieldsEditor = function (options) {
        assertProperties.assertRequired(options, ['profiles', 'slugs']);
        var self = {};

        self.profiles = _.indexBy(options.profiles, 'id');
        self.slugs = options.slugs;
        _.each(self.slugs, function (slug) {
            self[slug] = fieldModel('');    // TODO: populate with original value, inc. for disabled
        });

        self.serialize = function () {
            var data = {
                commcare_profile: self.commcare_profile.value(),
            };
            _.each(self.slugs, function (slug) {
                data[slug] = self[slug].value();
            });
            return data;
        };

        // TODO: get PROFILE_SLUG from initial page data
        self.commcare_profile = fieldModel('');   // TODO: populate with original value
        self.commcare_profile.value.subscribe(function (newValue) {
            if (!newValue) {
                return;
            }
            var profile = self.profiles[newValue];
            _.each(self.slugs, function (slug) {
                var field = self[slug];
                if (slug in profile.fields) {
                    if (!field.disable()) {
                        field.previousValue(field.value());
                    }
                    field.value(profile.fields[slug]);
                    field.disable(true);
                } else {
                    if (field.disable()) {
                        field.value(field.previousValue());
                    }
                    field.disable(false);
                }
            });
        });

        return self;
    };

    return {
        customDataFieldsEditor: customDataFieldsEditor,
    };
});
