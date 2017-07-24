function parse_date(date_string) {
        if (!date_string) return new Date(1970,1,1);
        var d = new Date(date_string);
        if (d != "Invalid Date") {
            return d;
        } else  {
            // hat tip: http://stackoverflow.com/questions/2587345/javascript-date-parse
            var parts = date_string.match(/(\d+)/g);
            // new Date(year, month [, date [, hours[, minutes[, seconds[, ms]]]]])
            return new Date(parts[0], parts[1]-1, parts[2], parts[3], parts[4], parts[5]); // months are 0-based
        }
}