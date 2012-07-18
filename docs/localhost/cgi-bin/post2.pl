#! /usr/bin/perl
use warnings;
use strict;
use CGI qw/ :standard -debug /;
print "Content-type: text/plain\n\n",
      map { $_ . " => " . param($_) . "\n" }
      param;

