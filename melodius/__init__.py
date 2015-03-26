# -*- Mode: Python; coding: utf-8; indent-tabs-mode: nil; tab-width: 4 -*-
### BEGIN LICENSE
# Copyright (C) 2012 Sean Davis <smd.seandavis@gmail.com>
# This program is free software: you can redistribute it and/or modify it 
# under the terms of the GNU General Public License version 3, as published 
# by the Free Software Foundation.
# 
# This program is distributed in the hope that it will be useful, but 
# WITHOUT ANY WARRANTY; without even the implied warranties of 
# MERCHANTABILITY, SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR 
# PURPOSE.  See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along 
# with this program.  If not, see <http://www.gnu.org/licenses/>.
### END LICENSE

import optparse

import locale
from locale import gettext as _
locale.textdomain('melodius')

from gi.repository import Gtk, Gdk, GObject # pylint: disable=E0611

from melodius import MelodiusWindow

from melodius_lib import set_up_logging, get_version

import os, sqlite3

def parse_options():
    """Support for command line options"""
    parser = optparse.OptionParser(version="%%prog %s" % get_version())
    parser.add_option(
        "-v", "--verbose", action="count", dest="verbose",
        help=_("Show debug messages (-vv debugs melodius_lib also)"))
    (options, args) = parser.parse_args()

    set_up_logging(options)

def main():
    'constructor for your class instances'
    parse_options()
    
    if not os.path.isdir( os.path.join( os.getenv("HOME"), ".melodius" ) ):
        os.mkdir( os.path.join( os.getenv("HOME"), ".melodius" ) )
    if not os.path.isfile( os.path.join( os.getenv("HOME"), ".melodius", "library.db" ) ):
        conn = sqlite3.connect(os.path.join( os.getenv("HOME"), ".melodius", "library.db" ))
        c = conn.cursor()
        c.execute('''CREATE TABLE library
             (path text, title text, artist text, album text, track int, length text, rating int)''')
        conn.commit()
        c.close()
        conn.close()
        
    #turn on the dbus mainloop
    from dbus.mainloop.glib import DBusGMainLoop
    DBusGMainLoop(set_as_default=True)

    #GObject.threads_init()
    Gdk.threads_init()
    # Run the application.    
    window = MelodiusWindow.MelodiusWindow()
    window.show()
    Gtk.main()
