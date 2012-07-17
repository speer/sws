#!/usr/bin/perl
print "Status:200 OK\n\n";
foreach $key (keys %ENV) {
print "$key --> $ENV{$key}<br>";
}

