#!/usr/bin/python3
# vim: set fileencoding=utf-8 :
# Alexander Grothe 2012

from gi.repository import GObject
import logging
import socket
import string
from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)

class lircConnection():
    def __init__(self, main):
        self.main = main
        self.socket_path = self.main.settings.get_setting('Frontend',
                                                          'lirc_socket',
                                                          None)
        logging.debug("lirc_socket is {0}".format(self.socket_path))
        if self.socket_path is None:
            return
        self.try_connection()
        self.callback = None
        logging.debug("lirc_toggle = {0}".format(
            self.main.settings.get_setting("Frontend", "lirc_toggle", None)))
        logging.debug("lirc_switch = {0}".format(
            self.main.settings.get_setting("Frontend", "lirc_switch", None)))
        logging.debug("lirc_power = {0}".format(
            self.main.settings.get_setting("Frontend", "lirc_power", None)))

    def connect_lircd(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.socket_path)
        self.callback = GObject.io_add_watch(self.sock, GObject.IO_IN, self.handler)

    def try_connection(self):
        try:
            self.connect_lircd()
            logging.info(u"conntected to Lirc-Socket on %s"%(self.socket_path))
            return False
        except:
            GObject.timeout_add(1000, self.try_connection)
            try:
                if self.callback:
                    GObject.source_remove(self.callback)
            except:
                logging.exception(
                  "vdr-frontend could not connect to lircd socket")
                pass
            return False

    def handler(self, sock, *args):
        '''callback function for activity on lircd socket'''
        try:
            buf = sock.recv(1024)
            if not buf:
                self.sock.close()
                try:
                    if self.callback:
                        GObject.source_remove(self.callback)
                except:
                    pass
                logging.error("Error reading from lircd socket")
                self.try_connection()
                return False
        except:
            sock.close()
            try:
                GObject.source_remove(self.callback)
            except: pass
            logging.exception('retry lirc connection')
            self.try_connection()
            return True
        lines = buf.decode().split("    n")
        for line in lines:
            try:
                code,count,cmd,device = line.split(" ")[:4]
                if count != "0":
                    #logging.debug('repeated keypress')
                    return True
                else:
                   try:
                       gobject.source_remove(self.main.timer)
                   except: pass
            except:
                logging.exception(line)
                return True
            logging.debug('Key press: %s',cmd)
            logging.debug(self.main.current)
            if self.main.current == 'vdr':
                if cmd == self.main.settings.get_setting("Frontend", "lirc_toggle", None):
                    if self.main.status() == 1:
                        self.main.detach()
                    else:
                        self.main.frontends[self.main.current].resume()
                elif cmd == self.main.settings.get_setting("Frontend", 'lirc_switch', None):
                    self.main.switchFrontend()
                    return True

                elif cmd == self.main.settings.get_setting("Frontend", 'lirc_power', None):
                    if self.main.status() == 1:
                        self.main.timer = GObject.timeout_add(
                                                15000,self.main.soft_detach)
                    else:
                        self.main.send_shutdown()
                else:
                    self.main.resume()
            elif self.main.current == 'xbmc':
                logging.debug("keypress for xbmc")
                if cmd == self.main.settings.get_setting("Frontend",
                                                         'lirc_switch',
                                                         None):
                    logging.info('stop XBMC via remote lirc_xbmc')
                    self.main.switchFrontend()
                    return True
                elif cmd == self.main.settings.get_setting("Frontend",
                                                       'lirc_power',
                                                       None):
                    if self.main.status() == 1:
                        self.main.wants_shutdown = True
                        self.main.timer = GObject.timeout_add(
                                                15000,self.main.soft_detach)
        return True
