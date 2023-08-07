# zip the contents a directory as a ccz using the name of the current ccz in the directory
pccz () {
  ccz=`ls *.ccz | sed -n 1p`
  rm -i *.ccz
  zip -r $ccz *
}

# move a ccz file to a temp directory and unzip it there
occz () {
   if [ -f $1 ] ; then
     dir=`mktemp -d`
     echo $dir
     mv $1 $dir
     cd $dir
     unzip *.ccz
   else
       echo "'$1' is not a valid file"
   fi
}
