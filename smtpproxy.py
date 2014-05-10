# -*- coding: utf-8 -*-

#############################################################################################
### YaBa 2011 - Thanks to: "Dirk Holtwick (INI reader); Lobsang (SMTP Proxy); ActiveState ###
#############################################################################################

from __future__ import print_function
import re, sys, os, socket, threading, signal
from select import select
import pdb
import ConfigParser
import string

_configuracao = {
    "config.endlocal":		"127.0.0.1",
    "config.prtlocal":		25,
    "config.endremoto":		"123.123.123.123",
    "config.prtremoto":		25,
    "srv2clt.msgoriginal":	"AUTH DIGEST-MD5",
	"srv2clt.msgalterada":	"AUTH PLAIN LOGIN",
    "clt2srv.msgoriginal":	"IGNORE",
	"clt2srv.msgalterada":	"IGNORE"
    }

CRLF="\r\n"

################################################################################################################
################################################################################################################

def LoadConfig(file, config={}):
    config = config.copy()
    cp = ConfigParser.ConfigParser()
    cp.read(file)
    for sec in cp.sections():
        name = string.lower(sec)
        for opt in cp.options(sec):
            config[name + "." + string.lower(opt)] = string.strip(cp.get(sec, opt))
    return config

class Server:
    def __init__(self, listen_addr, remote_addr):
        self.local_addr = listen_addr
        self.remote_addr = remote_addr
        self.srv_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.srv_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) 
        self.srv_socket.bind(listen_addr)
        self.srv_socket.setblocking(1)

        self.please_die = False

        self.accepted = {}

    def start(self):
        print("#########################################################################")
        print("# WARNING: STOPPING THIS PROCESS WILL STOP OUTLOOK FROM SENDING MAILS.  #")
        print("#########################################################################")
        print("mycfg actual:")
        print("Local address......: "+mycfg['config.endlocal']+":"+str(mycfg['config.prtlocal']))
        print("Remote address.....: "+mycfg['config.endremoto']+":"+str(mycfg['config.prtremoto']))
        print("#### Server -> Client ####")
        print("Original String....: "+mycfg['srv2clt.msgoriginal'])
        print("Changed String.....: "+mycfg['srv2clt.msgalterada'])
        print("#### Client -> Server ####")
        print("Original String....: "+mycfg['clt2srv.msgoriginal'])
        print("Changed String.....: "+mycfg['clt2srv.msgalterada'])
        print("#########################################################################")
        self.srv_socket.listen(5)
        while not self.please_die:
            try:
                ready_to_read, ready_to_write, in_error = select([self.srv_socket], [], [], 0.1)
            except Exception as err:
                pass
            if len(ready_to_read) > 0:
                try:
                    client_socket, client_addr = self.srv_socket.accept()
                except Exception as err:
                    print("ERRO:", err)
                else:
                    #print("Ligado {0}:{1}".format(client_addr[0], client_addr[1]))
                    tclient = ThreadClient(self, client_socket, self.remote_addr)
                    tclient.start()
                    self.accepted[tclient.getName()] = tclient

    def die(self):
        print("WARNING: You have stopped this daemon. Outlook 2010 will stop sending mails.")
        self.please_die = True
        for tc in self.accepted.values():
            tc.die()
            tc.join()

class ThreadClient(threading.Thread):
    def __init__(self, serv, conn, remote_addr):
        threading.Thread.__init__(self)
        self.server = serv
        self.local = conn
        self.remote_addr = remote_addr
        self.remote = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.please_die = False
        self.mbuffer = []

    def run(self):
        self.remote.connect(self.remote_addr)
        self.remote.setblocking(1)
        while not self.please_die:
            ready_to_read, ready_to_write, in_error = select([self.local], [], [], 0.1)
            if len(ready_to_read) > 0:
                try:
                    msg = self.local.recv(1024)
                except Exception as err:
                    print("ERRO: " + str(self.getName()) + " > " + str(err))
                    break
                else:
                    magiaremote = msg.replace(mycfg['clt2srv.msgoriginal'], mycfg['clt2srv.msgalterada'], 1)
                    self.remote.send(magiaremote)

            # ver se o servidor tem algo a dizer
            ready_to_read, ready_to_write, in_error = select([self.remote], [], [], 0.1)
            if len(ready_to_read) > 0:
                try:
                    msg = self.remote.recv(1024)
                except Exception as err:
                    print("ERRO: " + str(self.getName()) + " > " + str(err))
                    break
                else:
                    magia = msg.replace(mycfg['srv2clt.msgoriginal'],mycfg['srv2clt.msgalterada'], 1)
                    if magia != "":
                        #print("<< {0}".format(repr(msg)))
                        self.local.send(magia)
                    else:
                        break

        self.remote.close()
        self.local.close()
        self.server.accepted.pop(self.getName())

    def die(self):
        self.please_die = True

####### INICIO
if not os.path.exists('config.ini'):
    print("ERROR: Missing CONFIG.INI")
    sys.exit()
mycfg = LoadConfig("config.ini", _configuracao)
srv = Server((mycfg['config.endlocal'], int(mycfg['config.prtlocal'])), (mycfg['config.endremoto'], int(mycfg['config.prtremoto'])))
def die(signum, frame):
    global srv
    srv.die()

signal.signal(signal.SIGINT, die)
signal.signal(signal.SIGTERM, die)
srv.start()