#!/usr/bin/python -B

import unittest
import sys
sys.path.append('../code')
import config

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

	def testConfigFileOK(self):
		testfolder = self.CONFIG_FOLDER + '/t50'
		c = config.SwsConfiguration(testfolder)
		assert c.parseFile()[2] == 0

if __name__ == "__main__":
	unittest.main()

