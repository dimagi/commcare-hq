(function () {
    function update_button() {
        $('#command-name').text($("#command-select option:selected").text());
    }

    function textToProperHtml(text) {
        var $ele = $('<span>');
        var lines = text.split('\n');
        for (var i = 0; i < lines.length; i++) {
            $ele.append($('<div>').text(lines[i]))
        }
        return $ele.html();
    }

    $(function() {
        var $command_select = $('#command-select');
        $command_select.change(update_button);
        update_button();

        $("#cmd-btn").click(function(){
            var data = {"command": $command_select.val()};
            $.post(hqImport('hqwebapp/js/urllib.js').reverse('run_management_command'), data, function(resp) {
                var alert_cls = resp.success ? "alert-success" : "alert-danger";
                $("#cmd-resp")
                    .removeClass("alert-success alert-danger")
                    .addClass(alert_cls)
                    .removeClass('hide')
                    .html(textToProperHtml(resp.output));
            });
        });
    })
})();
