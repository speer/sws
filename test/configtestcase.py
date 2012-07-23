#!/usr/bin/python -B

import unittest
import sys
sys.path.append('../code')
import config
import httplib

class ConfigTestCase (unittest.TestCase):

	CONFIG_FOLDER = '/home/stefan/sws/test/config'
	
	def testConfigFolderNotFound(self):
		testfolder = self.CONFIG_FOLDER + '/t0'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 10

	def testConfigMainFileNotFound(self):
		testfolder = self.CONFIG_FOLDER + '/t1'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 11

	def testConfigMainSyntaxError1(self):
		testfolder = self.CONFIG_FOLDER + '/t2'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 13

	def testConfigMainSyntaxError2(self):
		testfolder = self.CONFIG_FOLDER + '/t3'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 14

	def testConfigMainSyntaxError3(self):
		testfolder = self.CONFIG_FOLDER + '/t4'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 15

	def testConfigMainSyntaxError4(self):
		testfolder = self.CONFIG_FOLDER + '/t5'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 16

	def testConfigMainSyntaxError5(self):
		testfolder = self.CONFIG_FOLDER + '/t6'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 17

	def testConfigMainSyntaxError6(self):
		testfolder = self.CONFIG_FOLDER + '/t7'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 18

	def testConfigMainSyntaxError7(self):
		testfolder = self.CONFIG_FOLDER + '/t8'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 19

	def testConfigMainInvalidErrorCode(self):
		testfolder = self.CONFIG_FOLDER + '/t9'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 20

	def testConfigMainFolderNotFound1(self):
		testfolder = self.CONFIG_FOLDER + '/t10'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 21

	def testConfigMainFolderNotFound2(self):
		testfolder = self.CONFIG_FOLDER + '/t11'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 22

	def testConfigMainUserGroup1(self):
		testfolder = self.CONFIG_FOLDER + '/t12'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 23

	def testConfigMainUserGroup2(self):
		testfolder = self.CONFIG_FOLDER + '/t13'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 23

	def testConfigMainUserGroup3(self):
		testfolder = self.CONFIG_FOLDER + '/t14'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 24

	def testConfigMainUserGroup4(self):
		testfolder = self.CONFIG_FOLDER + '/t15'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 24

	def testConfigMainMandatoryMissing(self):
		testfolder = self.CONFIG_FOLDER + '/t16'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 25

	def testConfigSitesEnabledNotFound(self):
		testfolder = self.CONFIG_FOLDER + '/t17'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 26

	def testConfigNoVirtualHostsFound(self):
		testfolder = self.CONFIG_FOLDER + '/t18'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 41

	def testConfigNoDefaultVirtualHostFound(self):
		testfolder = self.CONFIG_FOLDER + '/t19'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 42

	def testConfigVHMandatoryDirectiveNotFound(self):
		testfolder = self.CONFIG_FOLDER + '/t20'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 43

	def testConfigVHDirectoryBeforeDocumentroot(self):
		testfolder = self.CONFIG_FOLDER + '/t21'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 27

	def testConfigVHDirectoryNesting(self):
		testfolder = self.CONFIG_FOLDER + '/t22'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 28

	def testConfigVHDirectiveNotAllowed(self):
		testfolder = self.CONFIG_FOLDER + '/t23'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 30

	def testConfigVHMultipleDefaultVirtualHosts(self):
		testfolder = self.CONFIG_FOLDER + '/t24'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 31

	def testConfigVHUnknownDirective(self):
		testfolder = self.CONFIG_FOLDER + '/t25'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 32

	def testConfigVHSyntaxError1(self):
		testfolder = self.CONFIG_FOLDER + '/t26'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 33

	def testConfigVHSyntaxError2(self):
		testfolder = self.CONFIG_FOLDER + '/t27'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 34

	def testConfigVHSyntaxError3(self):
		testfolder = self.CONFIG_FOLDER + '/t28'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 35

	def testConfigVHDirectoryNotFound(self):
		testfolder = self.CONFIG_FOLDER + '/t29'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 36

	def testConfigVHSyntaxError4(self):
		testfolder = self.CONFIG_FOLDER + '/t30'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 37

	def testConfigVHSyntaxError5(self):
		testfolder = self.CONFIG_FOLDER + '/t31'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 38

	def testConfigVHSyntaxError6(self):
		testfolder = self.CONFIG_FOLDER + '/t32'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 39

	def testConfigVHSyntaxError7(self):
		testfolder = self.CONFIG_FOLDER + '/t33'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 40

	def testConfigMainNegativeValueError7(self):
		testfolder = self.CONFIG_FOLDER + '/t34'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 43

	def testConfigVHWrongHandler(self):
		testfolder = self.CONFIG_FOLDER + '/t35'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 44

	def testConfigVHWrongExecutor(self):
		testfolder = self.CONFIG_FOLDER + '/t36'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 45

	def testConfigVHWrongExecutor2(self):
		testfolder = self.CONFIG_FOLDER + '/t37'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 46

	def testConfigVHWrongExecutor3(self):
		testfolder = self.CONFIG_FOLDER + '/t38'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 47

	def testConfigVHWrongAddType(self):
		testfolder = self.CONFIG_FOLDER + '/t39'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 49

	def testConfigMainWrongAddType(self):
		testfolder = self.CONFIG_FOLDER + '/t40'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 48

	def testConfigVHWrongFilter1(self):
		testfolder = self.CONFIG_FOLDER + '/t41'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 50

	def testConfigVHWrongFilter2(self):
		testfolder = self.CONFIG_FOLDER + '/t42'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 51

	def testConfigVHWrongFilter3(self):
		testfolder = self.CONFIG_FOLDER + '/t43'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 52

	def testConfigVHWrongFilter4(self):
		testfolder = self.CONFIG_FOLDER + '/t44'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 53

	def testConfigVHWrongHeader(self):
		testfolder = self.CONFIG_FOLDER + '/t45'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 54

	def testConfigVHWrongStopInheritation(self):
		testfolder = self.CONFIG_FOLDER + '/t46'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 55

	def testConfigFileOK(self):
		testfolder = self.CONFIG_FOLDER + '/t50'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 0

	def testConfigMainFile(self):
		testfolder = self.CONFIG_FOLDER + '/t51'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[0] == True
		assert c.configurations['listen'] == 8080
		assert c.configurations['host'] == '127.0.0.1'
		assert c.configurations['user'] == 1000
		assert c.configurations['group'] == 33
		assert c.configurations['hostnamelookups'] == True
		assert c.configurations['defaulttype'] == 'text/plain'
		assert c.configurations['cgitimeout'] == 23
		assert c.configurations['cgirecursionlimit'] == 15
		assert c.configurations['listenqueuesize'] == 9
		assert c.configurations['socketbuffersize'] == 4096
		assert c.configurations['communicationsocketfile'] == '/tmp/sws.peerweb.it'
		assert c.configurations['errorlogfile'] == '/home/stefan/sws/log/error.log'
		assert c.configurations['accesslogfile'] == '/home/stefan/sws/log/access.log'
		assert c.configurations['errordocumentroot'] == '/home/stefan/sws/errordocs'
		assert c.configurations['communicationsocketfile'] == '/tmp/sws.peerweb.it'
		assert len(c.configurations['errordocument']) == 3
		assert c.configurations['errordocument'][403]['file'] == '403.html'
		assert c.configurations['errordocument'][404]['file'] == '404.html'
		assert c.configurations['errordocument'][500]['file'] == '500.html'


	def testConfigVHFiles(self):
		testfolder = self.CONFIG_FOLDER + '/t52'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[0] == True
		assert len(c.virtualHosts) == 2
		vH1 = testfolder + '/sites-enabled/127.0.0.1.conf'
		vH2 = testfolder + '/sites-enabled/watten.conf'
		assert c.virtualHosts.keys()[0] == vH1
		assert c.virtualHosts.keys()[1] == vH2
		# test VH1
		assert c.virtualHosts[vH1]['serveradmin'] == 'stefan@127.0.0.1'
		assert c.virtualHosts[vH1]['servername'] == '127.0.0.1'
		assert len(c.virtualHosts[vH1]['serveralias']) == 3
		assert c.virtualHosts[vH1]['serveralias'][0] == 'www.watten.org'
		assert c.virtualHosts[vH1]['serveralias'][1] == 'www.wattn.org'
		assert c.virtualHosts[vH1]['serveralias'][2] == 'wattn.org'
		assert c.virtualHosts[vH1]['documentroot'] == '/home/stefan/sws'
		assert len(c.virtualHosts[vH1]['directory']['/']['directoryindex']) == 3
		assert c.virtualHosts[vH1]['directory']['/']['directoryindex'][0] == 'index.html'
		assert c.virtualHosts[vH1]['directory']['/']['directoryindex'][1] == 'index.htm'
		assert c.virtualHosts[vH1]['directory']['/']['directoryindex'][2] == 'index2.html'
		assert c.virtualHosts[vH1]['errorlogfile'] == '/home/stefan/sws/log/a_error.log'
		assert c.virtualHosts[vH1]['accesslogfile'] == '/home/stefan/sws/log/a_access.log'
		assert c.virtualHosts[vH1]['errordocumentroot'] == '/tmp'
		assert c.virtualHosts[vH1]['errordocument'][404] == 'tmp404.html'
		assert c.virtualHosts[vH1]['errordocument'][500] == '500.html'
		assert len(c.virtualHosts[vH1]['directory']) == 4
		assert len(c.virtualHosts[vH1]['directory']['/']['cgihandler']) == 1
		assert c.virtualHosts[vH1]['directory']['/']['cgihandler'][0]['extension'] == '.asp'
		assert len(c.virtualHosts[vH1]['directory']) == 4
		assert c.virtualHosts[vH1]['directory']['/docs/cgi-bin/sh']['cgihandler'][2]['extension'] == '.sh3'
		assert c.virtualHosts[vH1]['directory']['/docs/cgi-bin/sh']['cgihandler'][2]['executor'] == '/bin/bash'
		assert len(c.virtualHosts[vH1]['directory']['/']['addtype']) == 2
		assert c.virtualHosts[vH1]['directory']['/']['addtype']['.css'] == 'text/css'
		assert c.virtualHosts[vH1]['directory']['/']['addtype']['.html'] == 'text/html'
		assert len(c.virtualHosts[vH1]['extfilterdefine']) == 2
		assert c.virtualHosts[vH1]['extfilterdefine']['test1'][0] == '/bin/test1'
		assert c.virtualHosts[vH1]['extfilterdefine']['test1'][1] == 'param'
		assert c.virtualHosts[vH1]['extfilterdefine']['test2'][0] == '/bin/test2'
		assert len(c.virtualHosts[vH1]['directory']['/docs/cgi-bin']['setoutputfilter']) == 3
		assert c.virtualHosts[vH1]['directory']['/docs/cgi-bin']['setoutputfilter'][0] == 'test1'
		assert c.virtualHosts[vH1]['directory']['/docs/cgi-bin']['setoutputfilter'][1] == 'test2'
		assert c.virtualHosts[vH1]['directory']['/docs/cgi-bin']['setoutputfilter'][2] == 'test1' 
		assert len(c.virtualHosts[vH1]['directory']['/docs/cgi-bin']['addheader']) == 2
		assert c.virtualHosts[vH1]['directory']['/docs/cgi-bin']['addheader']['content-encoding'] == 'none'
		assert c.virtualHosts[vH1]['directory']['/docs/cgi-bin']['addheader']['content-type'] == 'text/html'
		assert c.virtualHosts[vH1]['directory']['/docs/cgi-bin']['stopinheritation']['directoryindex'] == True
		assert c.virtualHosts[vH1]['directory']['/docs/cgi-bin']['stopinheritation']['cgihandler'] == True
		assert c.virtualHosts[vH1]['directory']['/docs/cgi-bin']['stopinheritation']['setoutputfilter'] == True
		assert c.virtualHosts[vH1]['directory']['/docs/cgi-bin']['stopinheritation']['addheader'] == True
		assert c.virtualHosts[vH1]['directory']['/docs/cgi-bin']['stopinheritation']['addtype'] == True
		
		# test VH2
		assert c.virtualHosts[vH2]['serveradmin'] == ''
		assert c.virtualHosts[vH2]['servername'] == 'watten.org'
		assert len(c.virtualHosts[vH2]['serveralias']) == 0
		assert c.virtualHosts[vH2]['documentroot'] == '/home/stefan/sws/docs'
		assert len(c.virtualHosts[vH2]['directory']) == 1
		assert len(c.virtualHosts[vH2]['directory']['/']['directoryindex']) == 0
		assert len(c.virtualHosts[vH2]['directory']['/']['cgihandler']) == 0
		assert c.virtualHosts[vH2]['errorlogfile'] == c.configurations['errorlogfile']
		assert c.virtualHosts[vH2]['accesslogfile'] == c.configurations['accesslogfile']
		assert c.virtualHosts[vH2]['errordocumentroot'] == c.configurations['errordocumentroot']
		assert c.defaultVirtualHost == vH2

if __name__ == "__main__":
	unittest.main()
