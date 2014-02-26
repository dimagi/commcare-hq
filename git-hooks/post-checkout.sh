#!/bin/sh

# do this in the background so your prompt doesn't hang
find . -name '*.pyc' -delete &
