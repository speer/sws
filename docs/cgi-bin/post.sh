#!/bin/bash
echo -e 'Status: 200 OK\nContent-Type:text/html\n\nThat is a cgi script<br/>'
POST_DATA=$(</dev/stdin)
echo '${POST_DATA}'
