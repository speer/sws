#!/usr/bin/perl

open(THISFILE, $ARGV[0]);
while(<THISFILE>){
	print $_;
}

close(THISFILE);

while (<STDIN>) {
	print $_;
}

open(THISFILE, $ARGV[1]);
while(<THISFILE>){
	print $_;
}
close(THISFILE);
