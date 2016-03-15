BEGIN {
  line="import time; print('{} {}'.format(__file__, time.time()))";
  begun=0;
  multiline_comment = "";
}
begun { print }
!begun {
  skip_because_of_multiline_comment = 0;
  if (multiline_comment) {
    if (multiline_comment == "\"\"\"" && $0 ~ /"""/) {
      multiline_comment = "";
    }
    if (multiline_comment == "'''" && $0 ~ /'''/) {
      multiline_comment = "";
    }
    skip_because_of_multiline_comment = 1;
  } else {
    if ($0 ~ /^\s*"""/) {
      if ($0 !~ /""".*"""/) {
        multiline_comment = "\"\"\""
      }
      skip_because_of_multiline_comment = 1;
    } else if ($0 ~ /^\s*'''/) {
      if ($0 !~ /'''.*'''/) {
        multiline_comment = "'''"
      }
      skip_because_of_multiline_comment = 1;
    }
  }

  if ($0 ~ /^#/ || $0 ~ /^from __future/ || $0 ~ /^\s*$/ || multiline_comment || skip_because_of_multiline_comment) {
    print
  } else {
    print line
    print
    begun = 1;
  }
}
END {
    if (!begun) {
        print line
    }
    print line
}
