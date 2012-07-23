#!/usr/bin/perl -w
use strict;


while (<STDIN>) {

$_ =~ s/WORLD/<h1>WORLD<\/h1>/g;
print $_;

}
