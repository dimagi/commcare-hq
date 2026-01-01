import "commcarehq";
import "hqwebapp/js/htmx_base";
import initialPageData from "hqwebapp/js/initial_page_data";
import Alpine from "alpinejs";

Alpine.data('initRole', (roleJson) => {
    return {
        role: roleJson,
        isSaving: false,
        roleError: '',
        saveRole() {
            this.isSaving = true;

            $.ajax({
                method: 'POST',
                url: initialPageData.reverse("post_user_role"),
                data: JSON.stringify(this.role, null, 2),
                dataType: 'json',
                success: () => {
                    this.isSaving = false;
                },
                error: (response) => {
                    this.isSaving = false;
                    let message = gettext("An error occurred, please try again.");
                    if (response.responseJSON && response.responseJSON.message) {
                        message = response.responseJSON.message;
                    }
                    this.roleError = message;
                },
            });
        }
    };
});

Alpine.start();
