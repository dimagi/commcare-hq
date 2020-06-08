hqDefine('userreports/js/constants', function () {
    var COUNT_PER_CHOICE = "Count per Choice";
    var SUM = "Sum";
    var GROUP_BY = "Group By";
    return {
        FORMAT_OPTIONS: ["Choice", "Date"],
        DEFAULT_FILTER_FORMAT_OPTIONS: ["Value", "Date", "Is Empty", "Exists", "Value Not Equal"],
        COUNT_PER_CHOICE: COUNT_PER_CHOICE,
        SUM: SUM,
        GROUP_BY: GROUP_BY,
        DEFAULT_CALCULATION_OPTIONS: [GROUP_BY, COUNT_PER_CHOICE, SUM, "Average"],

        REPORT_TYPE_LIST: "list",
        REPORT_TYPE_TABLE: "table",
    };
});
