#!/usr/bin/python -B

import unittest

from configtestcase import ConfigTestCase
from servertestcase import ServerTestCase

if __name__ == "__main__":
	suite1 = unittest.TestLoader().loadTestsFromTestCase(ConfigTestCase)
	suite2 = unittest.TestLoader().loadTestsFromTestCase(ServerTestCase)
	unittest.main()

