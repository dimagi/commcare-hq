/* globals alert_user, TEMPLATE_STRINGS */
// for product and user per location selection

var insert_new_user = function(user) {
    var $select = $('#id_users-selected_ids');
    $select.multiSelect('addOption', { value: user.user_id, text: user.text });
    $select.multiSelect('select', user.user_id);
};

$(function() {
    var form_node = $('#add_commcare_account_form');
    var url = form_node.prop('action');

    $('#new_user').on('show.bs.modal', function() {
        form_node.html('<i class="fa fa-refresh fa-spin"></i>');
        $.get(url, function(data) {
            form_node.html(data.form_html);
        });
    });

    form_node.submit(function(event) {
        event.preventDefault();
        $.ajax({
            type: 'POST',
            url: url,
            data: form_node.serialize(),
            success: function(data) {
                if (data.status === 'success') {
                    insert_new_user(data.user);
                    alert_user(
                        TEMPLATE_STRINGS.new_user_success({name: data.user.text}),
                        'success'
                    );
                    $('#new_user').modal('hide');
                } else {
                    form_node.html(data.form_html);
                }
            },
            error: function() {
                alert_user(gettext('Error saving user', 'danger'));
            },
        });
    });
});
