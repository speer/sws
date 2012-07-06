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

	def parseFile(self):
		if not os.path.isdir(self.configFolder):
			return (False, 'Error: configuration folder '+self.configFolder+' not found')
		if not os.path.isfile(self.configFile):
			return (False, 'Error: configuration file '+self.configFile+' not found')
		configLines = ''
		try:
			f = open (self.configFile,'r')
			line = 'init'
			while line != '':
				line = f.readline()
				if line.strip().startswith('#') or line.strip() == '':
					continue
				configLines = configLines + line
		except:
			return (False, 'Error: cannot read configuration file '+self.configFile)
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

		return (True,'Parsing OK')


#c = SwsConfiguration ('/home/stefan/sws/config')
#print c.parseFile()[1]
