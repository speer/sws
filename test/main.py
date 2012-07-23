#!/usr/bin/python -B

import unittest

from configtestcase import ConfigTestCase
from servertestcase import ServerTestCase

# Run's both unit test suites, i.e., tests the configuration file parser and the web-server functionalities
if __name__ == "__main__":
	suite1 = unittest.TestLoader().loadTestsFromTestCase(ConfigTestCase)
	suite2 = unittest.TestLoader().loadTestsFromTestCase(ServerTestCase)
	unittest.main()

