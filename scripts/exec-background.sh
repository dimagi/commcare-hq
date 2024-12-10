#!/bin/bash

# Spawn 10 background jobs
for i in {1..10}; do
  # Create 0 users and 10,000 cases in the `test` domain
  ./manage.py create_test_data test 0 10000 &
done

# Wait for all background jobs to finish
wait
