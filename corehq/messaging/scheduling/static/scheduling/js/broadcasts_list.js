hqDefine("scheduling/js/broadcasts_list", function() {
    $(function() {
        var list_broadcasts_url = hqImport("hqwebapp/js/initial_page_data").reverse("new_list_broadcasts"),
            loader_src = hqImport("hqwebapp/js/initial_page_data").get("loader_src");

        $("#scheduled-table").dataTable({
            "lengthChange": false,
            "filter": false,
            "sort": false,
            "displayLength": 5,
            "processing": true,
            "serverSide": true,
            "ajaxSource": list_broadcasts_url,
            "fnServerParams": function(aoData) {
                aoData.push({"name": "action", "value": "list_scheduled"});
            },
            "sDom": "rtp",
            "language": {
                "emptyTable": gettext('There are no messages to display.'),
                "infoEmpty": gettext('There are no messages to display.'),
                "lengthMenu": gettext('Show _MENU_ messages per page'),
                "processing": '<img src="' + loader_src + '" /> ' + gettext('Loading messages...'),
                "info": gettext('Showing _START_ to _END_ of _TOTAL_ broadcasts'),
                "infoFiltered": gettext('(filtered from _MAX_ total broadcasts)'),
            },
            "columnDefs": [
                {
                    "targets": [0],
                    "render": function() {
                        // TODO construct this from ID
                        return 'Delete button';
                    },
                },
                {
                    "targets": [1],
                    "render": function(data, type, row) {
                        var id = row[row.length - 1];
                        var url = hqImport("hqwebapp/js/initial_page_data").reverse('edit_schedule', 'scheduled', id);
                        return "<a href='" + url + "'>" + data + "</a>";
                    },
                },
                {
                    "targets": [3],
                    "render": function(data) {
                        return data ? gettext("Active") : gettext("Inactive");
                    },
                },
                {
                    "targets": [4],
                    "render": function() {
                        // TODO construct this from ID
                        return 'activate or deactivate button';
                    },
                },
            ],
        });

        $("#immediate-table").dataTable({
            "lengthChange": false,
            "filter": false,
            "sort": false,
            "displayLength": 5,
            "processing": true,
            "serverSide": true,
            "ajaxSource": list_broadcasts_url,
            "fnServerParams": function(aoData) {
                aoData.push({"name": "action", "value": "list_immediate"});
            },
            "dom": "rtp",
            "language": {
                "emptyTable": gettext('There are no messages to display.'),
                "infoEmpty": gettext('There are no messages to display.'),
                "lengthMenu": gettext('Show _MENU_ messages per page'),
                "processing": '<img src="' + loader_src + '" /> ' + gettext('Loading Messages...'),
                "info": gettext('Showing _START_ to _END_ of _TOTAL_ messages'),
                "infoFiltered": gettext('(filtered from _MAX_ total messages)'),
            },
            "columnDefs": [
                {
                    "targets": [0],
                    "render": function(data, type, row) {
                        var id = row[row.length - 1];
                        var url = hqImport("hqwebapp/js/initial_page_data").reverse('edit_schedule', 'immediate', id);
                        return "<a href='" + url + "'>" + data + "</a>";
                    },
                },
            ],
        });
    });
});
