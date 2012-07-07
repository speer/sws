#!/usr/bin/python

import os, pwd, grp
from os import path, sep

class SwsConfiguration:

	MAIN_CONFIG_FILE = 'sws.conf'
	SITES_ENABLED_FOLDER = 'sites-enabled'

	def __init__(self, configFolder):
		self.configFolder = path.abspath(configFolder)
		self.configFile = path.abspath(self.configFolder + sep + SwsConfiguration.MAIN_CONFIG_FILE)
		self.configurations = {
			'listen':80,
			'host':'',
			'pidfile':None,
			'communicationsocketfile':None,
			'user':None,
			'group':None,
			'hostnamelookups':False,
			'defaulttype':None,
			'cgitimeout':30,
			'listenqueuesize':10,
			'socketbuffersize':8192,
			'errordocumentroot':None,
			'errordocument':{
				403:{'msg':'Forbidden','file':None,'defaulttxt':'Status 403 - Forbidden. You are not allowed to access this resource.'},
				404:{'msg':'Not Found','file':None,'defaulttxt':'Status 404 - File Not Found'},
				500:{'msg':'Internal Server Error','file':None,'defaulttxt':'Status 500 - Internal Server Error'}
			}
		}
		self.virtualHosts = {}
		self.defaultVirtualHost = None

	def readConfigFile(self, configFile):
		configLines = ''
		try:
			f = open (configFile,'r')
			line = 'init'
			while line != '':
				line = f.readline()
				if line.strip().startswith('#') or line.strip() == '':
					continue
				configLines = configLines + line
			return (True, configLines)
		except:
			return (False, 'Error: cannot read configuration file '+configFile)

	def initVHost (self, vHost):
		self.virtualHosts[vHost] = {
			'serveradmin':'',
			'servername':None,
			'serveralias':[],
			'documentroot':None,
			'cgiroot':[],
			'directoryindex':[]
		}


	def parseFile(self):

		# parse main config file

		if not os.path.isdir(self.configFolder):
			return (False, 'Error: configuration folder '+self.configFolder+' not found')
		if not os.path.isfile(self.configFile):
			return (False, 'Error: configuration file '+self.configFile+' not found')

		success, configLines = self.readConfigFile(self.configFile)
		if not success:
			return (False,configLines)

		lines = configLines.splitlines()
		for line in lines:
			fields = line.split()

			if len(fields) < 2:
				return (False, 'Error: syntax error in configuration directive: '+line)
			directive = fields[0].lower()
			if directive not in self.configurations.keys():
				return (False, 'Error: unknown configuration directive: '+line)
			if directive in ('errordocument') and len(fields) != 3:
				return (False, 'Error: syntax error in configuration directive: '+line)
			if directive not in ('errordocument') and len(fields) != 2:
				return (False, 'Error: syntax error in configuration directive: '+line)

			# integer directives
			if directive in ('listen','cgitimeout','listenqueuesize','socketbuffersize'):
				try:
					value = int(fields[1])
					self.configurations[directive] = value
					continue
				except:
					return (False, 'Error: type error in configuration directive: '+line)

			# boolean directives
			if directive in ('hostnamelookups'):
				if fields[1].lower() == 'on':
					self.configurations[directive] = True
				elif fields[1].lower() == 'off':
					self.configurations[directive] = False
				else:
					return (False, 'Error: type error in configuration directive: '+line)
				continue

			# errordocument
			if directive in ('errordocument'):
				code = -1
				try:
					code = int(fields[1])
				except:
					return (False, 'Error: type error in code of errordocument directive: '+line)
				if not code in self.configurations[directive].keys():
					return (False, 'Error: error code not supported by server: '+line)
				self.configurations[directive][code]['file'] = fields[2]
				continue

			# file
			if directive in ('communicationsocketfile','pidfile'):
				filepath = os.path.abspath(fields[1])
				pos = filepath.rfind(sep)
				if not os.path.isdir(filepath[:pos]):
					return (False, 'Error: folder does not exist: '+filepath[:pos])

			# directory
			if directive in ('errordocumentroot'):
				if not os.path.isdir(os.path.abspath(fields[1])):
					return (False, 'Error: folder does not exist: '+line)

			# user
			if directive in ('user'):
				try:
					pw = pwd.getpwnam(fields[1])
					self.configurations[directive] = int(pw.pw_uid)
				except:
					try:
						pw = pwd.getpwuid(int(fields[1]))
						self.configurations[directive] = int(pw.pw_uid)
					except:
						return (False, 'Error: user does not exist: '+line)
				continue

			# group
			if directive in ('group'):
				try:
					gr = grp.getgrnam(fields[1])
					self.configurations[directive] = int(gr.gr_gid)
				except:
					try:
						gr = grp.getgrgid(int(fields[1]))
						self.configurations[directive] = int(gr.gr_gid)
					except:
						return (False, 'Error: group does not exist: '+line)
				continue

			# string directive
			self.configurations[directive] = fields[1]

		for directive in self.configurations.keys():
			if self.configurations[directive] == None:
				return (False, 'Error: mandatory directive not specified: '+directive)


		# parse virtualhosts

		# check if sites enabled folder exists
		sitesEnabled = os.path.abspath(self.configFolder + sep + SwsConfiguration.SITES_ENABLED_FOLDER)
		if not os.path.isdir(sitesEnabled):
			return (False, 'Error: folder does not exists: '+sitesEnabled)


		for filename in os.listdir(sitesEnabled):
			vHost = os.path.abspath(sitesEnabled + sep + filename)
			# skip directories
			if not os.path.isfile(vHost) or not vHost.endswith('.conf'):
				continue

			success, configLines = self.readConfigFile(vHost)
			if not success:
				return (False,configLines)

			self.initVHost(vHost)
			lines = configLines.splitlines()
			for line in lines:
				fields = line.split()

				if len(fields) < 1:
					return (False, 'Error: syntax error in configuration directive: '+line)

				directive = fields[0].lower()

				# defaultvirtualhost
				if directive in ('defaultvirtualhost'):
					if self.defaultVirtualHost == None:
						self.defaultVirtualHost = vHost
						continue
					else:
						return (False,'Error: multiple Default VirtualHosts')

				if directive not in self.virtualHosts[vHost].keys():
					return (False, 'Error: unknown configuration directive: '+line)

				if len(fields) < 2:
					return (False, 'Error: syntax error in configuration directive: '+line)

				if directive not in ('directoryindex','serveralias','cgiroot') and len(fields) != 2:
					return (False, 'Error: syntax error in configuration directive: '+line)

				# multiple values
				if directive in ('directoryindex','serveralias','cgiroot'):
					first = False
					for field in fields:
						if not first:
							first = True
							continue
						self.virtualHosts[vHost][directive].append(field)
					continue

				# directory
				if directive in ('documentroot'):
					if not os.path.isdir(os.path.abspath(fields[1])):
						return (False, 'Error: folder does not exist: '+line)
					else:
						self.virtualHosts[vHost][directive] = os.path.abspath(fields[1])
						continue
			
				# string directive
				self.virtualHosts[vHost][directive] = fields[1]


		if len(self.virtualHosts) == 0:
			return (False, 'Error: no VirtualHost specified')

		if self.defaultVirtualHost == None:
			return (False, 'Error: no DefaultVirtualHost specified')

		# check for mandatory directives
		for vHost in self.virtualHosts.keys():
			for directive in self.virtualHosts[vHost].keys():
				if self.virtualHosts[vHost][directive] == None:
					return (False, 'Error: mandatory directive ('+directive+') not specified in VirtualHost: '+vHost)

		return (True,'Parsing OK')


#c = SwsConfiguration ('/home/stefan/sws/config')
#print c.parseFile()[1]
