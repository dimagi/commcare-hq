function(keys, values, rereduce) {
    // !code util/pathindia_reduce.js

    var calc = {
            visit_count: 0,
            preg_visit_count: 0
        },
        antenatal = new PathIndiaAntenatalStats(),
        intranatal = new PathIndiaIntranatalStats(),
        postnatal = new PathIndiaPostnatalStats();

    if (rereduce) {
        for (var i in values) {
            var agEntry = values[i];

            antenatal.rereduce(agEntry.antenatal);
            intranatal.rereduce(agEntry.intranatal);
            postnatal.rereduce(agEntry.postnatal);

            calc.visit_count += agEntry.visit_count;
            calc.preg_visit_count += agEntry.preg_visit_count;
        }
    } else {
        for (var j in values) {
            var curEntry = values[j];

            if (curEntry.antenatal)
                antenatal.reduce(curEntry.antenatal);
            if (curEntry.intranatal)
                intranatal.reduce(curEntry.intranatal);
            if (curEntry.postnatal)
                postnatal.reduce(curEntry.postnatal);

            calc.visit_count += curEntry.eligible;
            calc.preg_visit_count += (curEntry.pregnant_visit) ? 1 : 0;
        }
    }

    extend(calc,
        antenatal.getResult(),
        intranatal.getResult(),
        postnatal.getResult()
    );
    return calc;
}