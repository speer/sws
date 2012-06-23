#!/usr/bin/perl
print "Content-type: text/html\nStatus:200 OK\n\n";
foreach $key (keys %ENV) {
print "$key --> $ENV{$key}<br>";
}

