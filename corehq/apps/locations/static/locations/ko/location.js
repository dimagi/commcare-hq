// for product and user per location selection
$(function () {
    $("#id_users-selected_ids").width(800).height(400).multiselect();
    $("#id_products-selected_ids").width(800).height(400).multiselect();
});

var insert_new_user = function(user) {
    $('#id_users-selected_ids').multiselect('addSelected', user.user_id, user.text);
};

$('#new_user').on('show', function() {

    var form_node = $('#add_commcare_account_form');
    var url = form_node.prop('action');

    $.get(url, function(data) {
        form_node.html(data.form_html);
    });

    var handle_submission = function(event) {
        event.preventDefault();
        $.post(url, form_node.serialize(), function(data) {
            if (data.status === 'success') {
                insert_new_user(data.user);
                $('#new_user').modal('hide');
            } else {
                form_node.html(data.form_html);
            }
        });
    };

    form_node.submit(handle_submission);
});
