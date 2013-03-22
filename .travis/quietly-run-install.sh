LOG=install.log
(bash -ex install.sh > $LOG 2>&1) || (cat $LOG; exit 1)
