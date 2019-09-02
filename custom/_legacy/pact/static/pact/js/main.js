hqDefine("pact/js/main", function () {
    var initialPageData = hqImport("hqwebapp/js/initial_page_data");

    $(function () {
        // Widget initialization
        $("#tbl_issues").tablesorter();
        $("abbr.timeago").timeago();
        $(".timeago").timeago();

        // Edit page
        $("#submit_button").click(function() {
            var form_data = $("#pt_edit_form").serialize();
            var api_url = initialPageData.reverse('pactdata_1') + "?case_id=" + initialPageData.get('patient_id') + "&method=patient_edit";
            console.log(form_data);
            var send_xhr = $.ajax({
                "type": "POST",
                "url":  api_url,
                "data": form_data,
                "success": function(data) {
                    window.location.href = initialPageData.get('pt_root_url') + "&view=info";
                },
                "error": function(data) {
                    if(data.responseText !== undefined) {
                        $("#form_errors").html(data.responseText);
                    }
                }
            });
          });
      });
});
