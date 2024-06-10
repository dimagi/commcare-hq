'use strict';
hqDefine("reports/js/bootstrap3/application_status", function () {
    const initialPageData = hqImport("hqwebapp/js/initial_page_data");

    $(function () {
        $('#report-content').on('click', '.view-assigned-locations-btn', function () {
            const userId = $(this).data().userId;

            // Clear out previous locations row, if it exists
            $(`#${userId}.assigned-locations-error`).remove();

            let $locationTable = $(`#${userId}.location-row`);
            if ($locationTable.length) {
                // There should be only one row per user
                $($locationTable[0]).toggle();
                return;
            }

            const $row = $(this).closest('tr');
            $.get({
                url: initialPageData.reverse('get_assigned_location_names_for_user'),
                data: { user_id: userId },
                success: function (data) {
                    // User might have clicked view button while previous fetch is busy,
                    // so skip if one already exists
                    $locationTable = $(`#${userId}.location-row`);
                    if (!$locationTable.length) {
                        const locationNamesStr = data.assigned_location_names_html;
                        $row.after(
                            `<tr id=${userId} class="location-row">
                                <td colspan="10">
                                    <div class="well" style="font-family:monospace">
                                        ${locationNamesStr}
                                    </div>
                                </td>
                            </tr>`
                        );
                    }
                },
                error: function () {
                    const errorText = gettext('Failed to fetch assigned locations');
                    $row.after(
                        `<tr id=${userId} class="assigned-locations-error">
                            <td colspan="10">
                                <div class="alert alert-danger">${errorText}</div>
                            </td>
                        </tr>
                        `
                    );
                },
            });
        });
    });
});