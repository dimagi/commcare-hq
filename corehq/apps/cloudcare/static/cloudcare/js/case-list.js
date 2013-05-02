var CaseList = (function () {
    var CaseList = function (o) {
            var that = this;
            that.user_id = o.user_id;
            that.$caseTable = $('<table/>').appendTo(o.home);

            $.ajax({
                url: o.casesUrl,
                data: {
                    user_id: that.user_id
                },
                dataType: 'json',
                success: function (data) {
                    that.setCases(data);
                }
            });
        };
    CaseList.init = function (o) {
        return new CaseList(o);
    };
    CaseList.prototype = {
        setCases: function (cases) {
            var that = this,
                i;
            for (i = 0; i < cases.length; i += 1) {
                $('<tr/>').append(
                    $('<td/>').append(
                        $('<a/>').attr({href: '#'}).text(cases[i].properties.case_name || '(Untitled Case)')
                    )
                ).appendTo(that.$caseTable);
            }

        }
    };
    return CaseList;
}());