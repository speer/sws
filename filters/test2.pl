#!/usr/bin/perl -w
use strict;


while (<STDIN>) {

$_ =~ s/Hallou/Gruesse/g;
print $_;

}
