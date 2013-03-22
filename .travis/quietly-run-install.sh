LOG=install.log
sh -ex install.sh > $LOG 2>&1 || cat $LOG
