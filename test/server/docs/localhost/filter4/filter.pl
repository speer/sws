#!/usr/bin/perl -w
use strict;

while (<STDIN>) {

$_ =~ s/filter/filtered/g;
print $_;

}
