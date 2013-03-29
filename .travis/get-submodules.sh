git submodule | cut -c '2-' | cut -d ' ' -f 2 | parallel --ungroup git submodule update --recursive
