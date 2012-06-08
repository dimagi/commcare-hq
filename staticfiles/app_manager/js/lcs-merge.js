function lcsMerge(X, Y, isEqual) {
    'use strict';
    isEqual = isEqual || function (a, b) {
        return a === b;
    };
    function recLcsMerge(X, Y, i, j) {
        var val, val1, val2, recur = recLcsMerge;

        if (i === 0 && j === 0) {
            val = {
                lcs: [],
                merge: []
            };
        } else if (i === 0) {
            val = recur(X, Y, i, j - 1);
            val.merge.push({x: false, y: true, token: Y[j - 1]});
        } else if (j === 0) {
            val = recur(X, Y, i - 1, j);
            val.merge.push({x: true, y: false, token: X[i - 1]});
        } else if (isEqual(X[i - 1], Y[j - 1])) {
            val = recur(X, Y, i - 1, j - 1);
            val.lcs.push(X[i - 1]);
            val.merge.push({x: true, y: true, token: X[i - 1]});
        } else {
            val1 = recur(X, Y, i, j - 1);
            val2 = recur(X, Y, i - 1, j);
            if (val2.lcs.length > val1.lcs.length) {
                val = val2;
                val.merge.push({x: true, y: false, token: X[i - 1]});
            } else {
                val = val1;
                val.merge.push({x: false, y: true, token: Y[j - 1]});
            }
        }
        return val;
    }

    return recLcsMerge(X, Y, X.length, Y.length);
}