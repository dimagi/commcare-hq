wget http://ftp.gnu.org/gnu/parallel/parallel-20130222.tar.bz2
tar xjf parallel-20130222.tar.bz2
(cd parallel-20130222 && ./configure && make && sudo make install)

git submodule | cut -c '2-' | cut -d ' ' -f 2 | parallel --ungroup git submodule update --recursive
