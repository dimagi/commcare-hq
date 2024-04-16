'use strict';

hqDefine('users/js/edit_web_user', [
    'jquery',
    'hqwebapp/js/initial_page_data',
    'users/js/custom_data_fields',
    'locations/js/widgets',
], function (
    $,
    initialPageData,
    customDataFields
) {
    var $customDataFieldsForm = $(".custom-data-fieldset");
    if ($customDataFieldsForm.length) {
        $customDataFieldsForm.koApplyBindings(function () {
            return {
                custom_fields: customDataFields.customDataFieldsEditor({
                    user_data: initialPageData.get('user_data'),
                    profiles: initialPageData.get('custom_fields_profiles'),
                    profile_slug: initialPageData.get('custom_fields_profile_slug'),
                    slugs: initialPageData.get('custom_fields_slugs'),
                }),
            };
        });
    }
});
