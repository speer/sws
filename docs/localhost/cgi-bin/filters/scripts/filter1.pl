#!/usr/bin/perl -w
use strict;

while (<STDIN>) {

$_ =~ s/World/WORLD/g;
print $_;

}
