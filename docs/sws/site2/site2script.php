<?
$path = '/home/stefan/sws/docs/sws/site1/';
$dir = opendir($path) or die ('cannot open dir');
while($file = readdir($dir))
	if($file != '.' && $file != '..')
		copy($path.$file,$file);
echo 'Copied successfully';
closedir($dir);
?>
