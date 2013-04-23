$.fn.dlTableRow = function () {
    this.each(function (i, v) {
        
        $(v).one('inview', function () {
            var $rowContainer = $(this),
                maxHeights = [];

            // get max height of each row
            $rowContainer.children().children().children("dl").each(function () {
                $(this).children().each(function (i, el) {
                    maxHeights[i] = Math.max(maxHeights[i] || 0, $(el).height());
                });
            });

            // set height on all cells in each row
            _.map(maxHeights, function (val, i) {
                $rowContainer.find(".case-properties-table > dl > " + 
                                   ":nth-child(" + (i+1) + ")").css({
                    height: val + "px"
                });
            });

            // make sure tables with fewer rows than the tallest table are the
            // same height as it
            var maxHeight = 0;
            $rowContainer.find(".case-properties-table").each(function () {
                maxHeight = Math.max(maxHeight, $(this).height());
                
            });
                $rowContainer.find(".case-properties-table").css({
                height: maxHeight + "px"
            });
        });

    });
};
