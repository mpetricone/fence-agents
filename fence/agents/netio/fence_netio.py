#!/usr/bin/python

import sys, re, pexpect, exceptions
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *

#BEGIN_VERSION_GENERATION
RELEASE_VERSION=""
REDHAT_COPYRIGHT=""
BUILD_DATE=""
#END_VERSION_GENERATION

def get_power_status(conn, options):
	conn.send_eol("port %s" % options["--plug"])
	re_status = re.compile("250 [01imt]")
	conn.log_expect(options, re_status, int(options["--shell-timeout"]))
	status = {
		"0" : "off",
		"1" : "on",
		"i" : "reboot",
		"m" : "manual",
		"t" : "timer"
	}[conn.after.split()[1]]

	return status

def set_power_status(conn, options):
	action = {
		"on" : "1",
		"off" : "0",
		"reboot" : "i"
	}[options["--action"]]

	conn.send_eol("port %s %s" % (options["--plug"], action))
	conn.log_expect(options, "250 OK", int(options["--shell-timeout"]))

def get_outlet_list(conn, options):
	result = {}

	try:
		# the NETIO-230B has 4 ports, counting start at 1
		for plug in ["1", "2", "3", "4"]:
			conn.send_eol("port setup %s" % plug)
			conn.log_expect(options, "250 .+", int(options["--shell-timeout"]))
			# the name is enclosed in "", drop those with [1:-1]
			name = conn.after.split()[1][1:-1]
			result[plug] = (name, "unknown")
	except Exception, exn:
		print str(exn)

	return result

def main():
	device_opt = [ "ipaddr", "login", "passwd", "port" ]

	atexit.register(atexit_handler)

	opt = process_input(device_opt)

	# set default port for telnet only
	if 0 == opt.has_key("--ipport"):
		opt["--ipport"] = "1234"

	opt["eol"] = "\r\n"
	options = check_input(device_opt, opt)

	docs = { }
	docs["shortdesc"] = "I/O Fencing agent for Koukaam NETIO-230B"
	docs["longdesc"] = "fence_netio is an I/O Fencing agent which can be \
used with the Koukaam NETIO-230B Power Distribution Unit. It logs into \
device via telnet and reboots a specified outlet. Lengthy telnet connections \
should be avoided while a GFS cluster is running because the connection will \
block any necessary fencing actions."
	docs["vendorurl"] = "http://www.koukaam.se/"
	show_docs(options, docs)

	##
	## Operate the fencing device
	## We can not use fence_login(), username and passwd are sent on one line
	####
	try:
		conn = fspawn(options, TELNET_PATH)
		conn.send("set binary\n")
		conn.send("open %s -%s\n"%(options["--ip"], options["--ipport"]))

		conn.read_nonblocking(size=100, timeout=int(options["--shell-timeout"]))
		conn.log_expect(options, "100 HELLO .*", int(options["--shell-timeout"]))
		conn.send_eol("login %s %s" % (options["--username"], options["--password"]))
		conn.log_expect(options, "250 OK", int(options["--shell-timeout"]))
	except pexpect.EOF:
		fail(EC_LOGIN_DENIED)
	except pexpect.TIMEOUT:
		fail(EC_LOGIN_DENIED)
	result = fence_action(conn, options, set_power_status, get_power_status, get_outlet_list)

	##
	## Logout from system
	##
	## In some special unspecified cases it is possible that
	## connection will be closed before we run close(). This is not
	## a problem because everything is checked before.
	######
	try:
		conn.send("quit\n")
		conn.log_expect(options, "110 BYE", int(options["--shell-timeout"]))
		conn.close()
	except:
		pass

	sys.exit(result)

if __name__ == "__main__":
	main()
