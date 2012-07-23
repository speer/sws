#!/bin/bash

# this script tries to access files from another documentroot, which might contain confidential information
FILE=/home/stefan/sws/docs/site2/mysql.sh
echo -e 'Content-Type:text/plain\n\nFile content:'
cat $FILE
