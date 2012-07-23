#!/bin/bash

# this is a script that executes a MYSQL query, has 700 privileges and is owned by www-data, so that just apache can access it
#mysql -h localhost -u root -ppassword db -e "SELECT * FROM table;"
echo -e "Content-Type:text/plain\n\n"
