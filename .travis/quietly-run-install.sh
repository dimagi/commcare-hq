LOG=install.log

echo Running install.sh
sh -ex ../install.sh > $LOG 2>&1 || cat $LOG
