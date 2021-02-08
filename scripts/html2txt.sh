cat $1 | sed -E 's:</?[^>]*/?>::g' | sed 's:^ *::g' | cat -s
