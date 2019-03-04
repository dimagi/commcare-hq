hqDefine("scheduling/js/conditional_alert_list", [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/assert_properties',
    'hqwebapp/js/initial_page_data',
    'datatables',
    'datatables.bootstrap',
], function (
    $,
    ko,
    _,
    assertProperties,
    initialPageData
) {
    var table = null;

    var rule = function (options) {
        var self = ko.mapping.fromJS(options);

        self.editUrl = ko.computed(function () {
            return initialPageData.reverse("edit_conditional_alert", self.id());
        });

        self.remove = function () {
            if (confirm(gettext("Are you sure you want to remove this conditional message?"))) {
                alertAction('delete', self.id());
            }
        };

        self.toggleStatus = function () {
            var action = self.active() ? "deactivate" : "activate";
            alertAction(action, self.id());
        };

        self.restart = function () {
            var prompt = null;
            if (initialPageData.get("limit_rule_restarts")) {
                prompt = gettext(
                    "A rule should only be restarted when you believe it is stuck and is not progressing. " +
                    "You will only be able to restart this rule once every two hours. Restart this rule?"
                );
            } else {
                prompt = gettext(
                    "A rule should only be restarted when you believe it is stuck and is not progressing. " +
                    "Your user is able to restart as many times as you like, but restarting too many times without " +
                    "finishing can place a burden on the system. Restart this rule?"
                );
            }
            if (confirm(prompt)) {
                alertAction('restart', self.id());
            }
        };

        self.projectName = ko.observable('');
        self.copy = function () {
            if (self.projectName() === '') {
                alert(gettext("Please enter a project name first."));
                return;
            }

            if (confirm(interpolate(gettext("Copy this alert to project %s?"), [self.projectName()]))) {
                alertAction('copy', self.id(), self.projectName());
            }
        };

        return self;
    };

    var ruleList = function (options) {
        assertProperties.assert(options, ['listUrl']);
        var self = {};

        self.rules = ko.observableArray();

        self.goToPage = function (page) {
            $.ajax({
                url: options.listUrl,
                data: {
                    action: 'list_conditional_alerts',
                    page: page,
                    limit: 10,  // TODO
                },
                success: function (data) {
                    self.rules(_.map(data.rules, function (r) { return rule(r); }));
                },
            });
        };

        self.goToPage(1);

        return self;
    };

    $(function () {
        $("#conditional-alert-list").koApplyBindings(ruleList({
            listUrl: initialPageData.reverse("conditional_alert_list"),
        }));

        /*var conditonalAlterListUrl = initialPageData.reverse("conditional_alert_list");

        table = $("#conditional-alert-list").dataTable({
            "lengthChange": false,
            "filter": false,
            "sort": false,
            "displayLength": 10,
            "processing": false,
            "serverSide": true,
            "ajaxSource": conditonalAlterListUrl,
            "fnServerParams": function (aoData) {
                aoData.push({"name": "action", "value": "list_conditional_alerts"});
            },
            "sDom": "rtp",
            "language": {
                "emptyTable": gettext('There are no alerts to display.'),
                "infoEmpty": gettext('There are no alerts to display.'),
                "info": gettext('Showing _START_ to _END_ of _TOTAL_ alerts'),
            },
            "columns": [
                {"data": ""},
                {"data": "name"},
                {"data": "case_type"},
                {"data": "active"},
                {"data": ""},
            ],
        });

        function reloadTable() {
            // Don't redraw the table if someone is typing a project name in the copy input
            var canDraw = true;
            $('.copy-project-name').each(function () {
                if ($(this).val()) {
                    canDraw = false;
                }
            });

            if (canDraw) {
                table.fnDraw(false);
            }

            setTimeout(reloadTable, 10000);
        }

        setTimeout(reloadTable, 10000);*/
    });

    function alertAction(action, rule_id, projectName) {
        var activateButton = $('#activate-button-for-' + rule_id);
        var deleteButton = $('#delete-button-for-' + rule_id);
        var copyButton = $('#copy-button-for-' + rule_id);
        if (action === 'delete') {
            deleteButton.disableButton();
            activateButton.prop('disabled', true);
            copyButton.prop('disabled', true);
        } else if (action === 'activate' || action === 'deactivate') {
            activateButton.disableButton();
            deleteButton.prop('disabled', true);
            copyButton.prop('disabled', true);
        } else if (action === 'copy') {
            copyButton.disableButton();
            deleteButton.prop('disabled', true);
            activateButton.prop('disabled', true);
        }

        var payload = {
            action: action,
            rule_id: rule_id,
        };

        if (action === 'copy') {
            payload['project'] = projectName;
        }

        $.ajax({
            url: '',
            type: 'post',
            dataType: 'json',
            data: payload,
        })
            .done(function (result) {
                if (action === 'restart') {
                    if (result.status === 'success') {
                        alert(gettext("This rule has been restarted."));
                    } else if (result.status === 'error') {
                        var text = gettext(
                            "Unable to restart rule. Rules can only be started every two hours and there are " +
                            "%s minute(s) remaining before this rule can be started again."
                        );
                        text = interpolate(text, [result.minutes_remaining]);
                        alert(text);
                    }
                } else if (action === 'copy') {
                    if (result.status === 'success') {
                        alert(gettext("Copy successful."));
                    } else if (result.status === 'error') {
                        alert(interpolate(gettext("Error: %s"), [result.error_msg]));
                    }
                }
            })
            .always(function () {
                table.fnDraw(false);
            });
    }
});
