#!/bin/bash
FILENAME=`date '+%Y-%m-%d-%H-%M-%S'`.html
FILE=/home/stefan/sws/docs/site1/$FILENAME
FILE2=/home/stefan/sws/docs/site2/$FILENAME
echo 'this file was created by user' > $FILE
whoami >> $FILE
cp $FILE $FILE2
echo -e 'Content-Type:text/html\n\n<html><head><title>File Copy</title></head><body>'
echo -e 'File created by user '
whoami
echo -e 'at site 1: <a href="'
echo -e $FILENAME
echo -e '">'
echo -e $FILENAME
echo -e '</a>'
if [ -f $FILE2 ]
then
	echo -e '<br/>File copied to site2'
else
	echo -e '<br/>File NOT copied to site2'
fi
