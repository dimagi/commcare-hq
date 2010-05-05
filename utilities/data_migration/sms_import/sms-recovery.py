#!/usr/bin/env python
# encoding: utf-8
"""
sms-recovery.py

Created by Brian DeRenzi on 2010-04-27.
Copyright (c) 2010 __MyCompanyName__. All rights reserved.
"""

import sys
import os
import MySQLdb
from datetime import datetime, timedelta

DB_HOST = "localhost"
DB_USER = "changeme"
DB_PASSWORD = "changeme"
DB_NAME = "changeme"

INSERT = "insert into logger_message set connection_id='%s', is_incoming='1', text='%s', date='%s'"

def german_to_est_time(input_string):
	format_string = "%Y-%m-%d %H:%M:%S"
	german_date = datetime.strptime(input_string, format_string)
	delta = timedelta(hours=6)
	est_date = german_date - delta
	output_string = est_date.strftime(format_string)
	print "%s to %s" % (input_string, output_string)
	return output_string

def main():
	# connect to DB
	db = MySQLdb.connect(DB_HOST, DB_USER, DB_PASSWORD, DB_NAME)
	cursor = db.cursor()
	
	counter = 0
	error_count = 0
	fin = open("sms-logs.txt", 'r')
	for line in fin:
		parts = line.partition(":")
		values = parts[2].split("|")

		# hardcode to ignore one we don't care about. this is a one
		# time script, it's ok
		if values[3] == '123':
			continue

		# values are in the format:
		# timestamp, 0(?), dest#, from, message\n
		message = values[4].strip()
		date = german_to_est_time(values[0])
		print "Adding message '%s' to db" % message
		try:
			sql = "select id from reporters_persistantconnection \
				where identity='%s'" % values[3]
			cursor.execute(sql)
			results = cursor.fetchall()
			conn_id = results[0][0] # first row, first column
			
			sql = INSERT % (conn_id, message, date)
			
			# print "    sql: %s" % sql
			cursor.execute(sql)
			counter = counter + 1
		except Exception, e:
			print "    ERROR adding record '%s' to db.\n %s" % (message, unicode(e))
			error_count = error_count + 1
	print "SUMMARY"
	print "%s of 207 incoming messages added" % counter
	print "%s errors logged" % error_count
			
if __name__ == '__main__':
	main()

