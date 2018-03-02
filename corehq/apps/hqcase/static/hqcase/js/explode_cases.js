hqDefine('hqcase/js/explode_cases', function() {
    $(function(){
        $('#explode').koApplyBindings({
            factor: ko.observable(''),
            user_id: ko.observable(''),
        });
        $('#explode-user_id').select2({
            ajax: {
                url: "{% url 'users_select2_options' domain %}",
                type: 'POST',
                datatype: 'json',
                quietMills: 250,
                data: function (term, page) {
                    return {
                        q: term,
                        page: page,
                    };
                },
                results: function (data, page) {
                    if (data.success) {
                        var limit = data.limit;
                        var hasMore = (page * limit) < data.total;
                        return {
                            results: data.items,
                            more: hasMore,
                        };
                    }
                },
            },
        });
    });
});
