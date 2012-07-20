#!/bin/bash
FILE=/home/stefan/sws/docs/site1/file.txt
echo 'this file was created by user' > $FILE
whoami >> $FILE
cp $FILE /home/stefan/sws/docs/site2/
echo -e 'Content-Type:text/plain\n\nExecuted'
