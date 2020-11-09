#!/bin/bash
# Build a commit frequency list.

git log --name-status --after=2018-01-01 $*  | \
    grep -E '^[A-Z]\s+'                      | \
    grep -v "django.po"                      | \
    grep -v "requirements/"                  | \
    grep -v "requirements-python3/"          | \
    grep -v "custom/"                        | \
    cut -c3-500                              | \
    sort                                     | \
    uniq -c                                  | \
    grep -vE '^ {6}1 '                       | \
    sort -n                                  | \
    tail -n 20
