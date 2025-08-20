import "commcarehq";
import $ from "jquery";
import initialPageData from "hqwebapp/js/initial_page_data";
import customDataFields from "users/js/custom_data_fields";
import "locations/js/widgets";

var $customDataFieldsForm = $(".custom-data-fieldset");
if ($customDataFieldsForm.length) {
    $customDataFieldsForm.koApplyBindings(function () {
        return {
            custom_fields: customDataFields.customDataFieldsEditor({
                user_data: initialPageData.get('user_data'),
                profiles: initialPageData.get('custom_fields_profiles'),
                profile_slug: initialPageData.get('custom_fields_profile_slug'),
                slugs: initialPageData.get('custom_fields_slugs'),
                can_edit_original_profile: initialPageData.get('can_edit_original_profile'),
            }),
        };
    });
}
