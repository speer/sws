#!/usr/bin/perl -w
use strict;

while (<STDIN>) {

$_ =~ s/Gug/Hallo/g;
print $_;

}
