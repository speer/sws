<?
$somepassword = 'thepassword';

$path = '/home/stefan/sws/docs/apache/site2/';
$dir = opendir($path) or die ('cannot open dir');
while($file = readdir($dir))
	if($file != '.' && $file != '..')
		unlink($path.$file);
echo 'Deleted successfully';
closedir($dir);
?>
