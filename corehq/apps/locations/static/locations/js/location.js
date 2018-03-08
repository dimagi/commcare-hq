// for product and user per location selection
hqDefine("locations/js/location", function() {
    var initialPageData = hqImport('hqwebapp/js/initial_page_data');
    var LocationModels = hqImport('locations/js/location_drilldown');
    var insert_new_user = function(user) {
        var $select = $('#id_users-selected_ids');
        $select.multiSelect('addOption', { value: user.user_id, text: user.text });
        $select.multiSelect('select', user.user_id);
    };
    var TEMPLATE_STRINGS = {
        new_user_success: _.template(gettext("User <%= name %> added successfully. " +
                                             "A validation message has been sent to the phone number provided.")),
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
            var alert_user = hqImport("hqwebapp/js/alert_user").alert_user;
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

        // Multiselect widget
        var multiselect_utils = hqImport('hqwebapp/js/multiselect_utils');

        multiselect_utils.createFullMultiselectWidget(
            'id_products-selected_ids',
            gettext("Available Products"),
            gettext("Products at Location"),
            gettext("Search Products...")
        );
    });
    $(function() {

        var location_url = initialPageData.get('api_root');
        var loc_id = initialPageData.get('location.get_id');
        var hierarchy = initialPageData.get('hierarchy');
        var loc_types_with_users = initialPageData.get('loc_types_with_users');

        var model = new LocationModels.LocationSelectViewModel({
            "hierarchy": hierarchy,
            "default_caption": "\u2026",
            "auto_drill": false,
            "loc_filter": function(loc) {
                return loc.uuid() !== loc_id && loc.can_have_children();
            },
            "loc_url": location_url,
        });
        model.editing = ko.observable(false);
        model.allowed_child_types = ko.computed(function() {
            var active_loc = (this.selected_location() || this.root());
            return (active_loc ? active_loc.allowed_child_types() : []);
        }, model);
        model.loc_type = ko.observable();
        model.loc_type.subscribe(function(val) {
            var subforms = $('.custom_subform');
            $.each(subforms, function(i, e) {
                var $e = $(e);
                var loc_type = $e.attr('loctype');
                $e[loc_type === val ? 'show' : 'hide']();
            });
        });

        model.has_user = ko.computed(function() {
            var loc_type = (
                model.allowed_child_types().length === 1 ?
                    model.allowed_child_types()[0] :
                    model.loc_type());
            return loc_types_with_users.indexOf(loc_type) !== -1;
        });

        var locs = initialPageData.get('locations');
        var selected_parent = initialPageData.get('location_parent_get_id');
        model.load(locs, selected_parent);
        model.orig_parent_id = model.selected_locid();

        $("#loc_form :button[type='submit']").click(function() {
            if (this.name === 'update-loc') {
                hqImport('analytix/js/google').track.event('Organization Structure', 'Edit', 'Update Location');
            } else {
                hqImport('analytix/js/google').track.event('Organization Structure', 'Edit', 'Create Child Location');
            }
        });

        hqImport('analytix/js/google').track.click($("#edit_users :button[type='submit']"), 'Organization Structure', 'Edit', 'Update Users at this Location');

        $('#loc_form').koApplyBindings(model);

    });
});
