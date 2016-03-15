function insert_timing_into_file() {
  awk -f insert-timing.awk $1
}

function list_py_files() {
  find . -name '*.py' -not -path ".*/.git/*"
}

function add_timing() {
  list_py_files > all_py_files.tmp
  while read line
  do
    cp $line $line.timing-original
    insert_timing_into_file $line.timing-original > $line
  done < all_py_files.tmp
}

function remove_timing() {
  find . -name '*.py.timing-original' -not -path ".*/.git/*" | sed 's/.timing-original$//' | xargs -n1 -I {} mv {}.timing-original {}
}
case $1 in
  test)
    insert_timing_into_file $2
    ;;
  addall)
    add_timing
    ;;
  removeall)
    remove_timing
    ;;
  *)
    echo "addall or removeall"
esac
