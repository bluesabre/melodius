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

# This is your preferences dialog.
#
# Define your preferences in
# data/glib-2.0/schemas/net.launchpad.melodius.gschema.xml
# See http://developer.gnome.org/gio/stable/GSettings.html for more info.

from gi.repository import GObject, Gio, Gtk, Notify # pylint: disable=E0611

import locale
from locale import gettext as _
locale.textdomain('melodius')

import logging
logger = logging.getLogger('melodius')

from melodius_lib.PreferencesDialog import PreferencesDialog

from . import MelodiusLibrary

class PreferencesMelodiusDialog(PreferencesDialog):
    __gtype_name__ = "PreferencesMelodiusDialog"
    __gsignals__ = {
        'library_updated': (GObject.SIGNAL_RUN_FIRST, None,
                           (bool,)),
        'show_preview_notification': (GObject.SIGNAL_RUN_FIRST, None,
                           (bool,))
        }

    def finish_initializing(self, builder): # pylint: disable=E1002
        """Set up the preferences dialog"""
        super(PreferencesMelodiusDialog, self).finish_initializing(builder)
        
        # Library Settings
        self.library_treeview = self.builder.get_object('library_treeview')
        column = self.library_treeview.get_column(0)
        self.library_treeview.append_column( column)
        cell = Gtk.CellRendererText()
        column.pack_start(cell, True)
        column.add_attribute(cell, 'text', 0)
        
        self.library_toolbar = self.builder.get_object('library_toolbar')
        context = self.library_toolbar.get_style_context()
        context.add_class("inline-toolbar")
        
        self.library_stats = self.builder.get_object('library_stats')
        
        # Notification Settings
        self.show_notifications = self.builder.get_object("checkbutton_show_notifications")
        
        self.preview_image = self.builder.get_object("preview_image")
        self.preview_primary_message = self.builder.get_object("preview_primary_message")
        self.preview_secondary_message = self.builder.get_object("preview_secondary_message")
        
        self.notification_settings = self.builder.get_object("box_notification_settings")
        self.notifications_coverart = self.builder.get_object("notifications_coverart")
        self.notifications_primary = self.builder.get_object("notifications_primary")
        self.notifications_secondary = self.builder.get_object("notifications_secondary")

        # Bind each preference widget to gsettings
        self.settings = Gio.Settings("net.launchpad.melodius")
        
        model = self.library_treeview.get_model()
        for folder in self.settings['folders']:
            model.append([folder])
        self.library = MelodiusLibrary.MelodiusLibrary()
        
        self.show_notifications.set_active( self.settings["show-notifications"] )
        self.notifications_coverart.set_active( self.settings["show-coverart"] )
        self.notifications_primary.set_text( self.settings["primary-message"] )
        self.notifications_secondary.set_text( self.settings["secondary-message"] )
        
        #widget = self.builder.get_object('example_entry')
        #settings.bind("example", widget, "text", Gio.SettingsBindFlags.DEFAULT)
        
        # Initialize notification previews
        Notify.init("melodius-preview")

    def on_toolbutton_library_add_clicked(self, widget):
        dialog = Gtk.FileChooserDialog(title=_("Add a folder to the library"), parent=self, action=Gtk.FileChooserAction.SELECT_FOLDER, buttons=(Gtk.STOCK_CANCEL,Gtk.ResponseType.CANCEL,Gtk.STOCK_ADD,Gtk.ResponseType.OK))
        dialog.set_select_multiple(True)
        dialog.show()
        response = dialog.run()
        dialog.hide()
        if response == Gtk.ResponseType.OK:
            model = self.library_treeview.get_model()
            existing = []
            iter = model.get_iter_first()
            while iter:
                existing.append( model.get_value(iter, 0) )
                iter = model.iter_next(iter)
            for folder in dialog.get_filenames():
                if folder not in existing:
                    model.append([folder])
                    self.library.add_folder(folder)
        self.on_prefs_library_updated()
        
    def on_toolbutton_library_remove_clicked(self, widget):
        sel = self.library_treeview.get_selection()
        store, path = sel.get_selected_rows()
        folder = store[path][0]
        iter = store.get_iter( path[0] )
        store.remove(iter)
        self.library.remove_folder(folder)
        self.on_prefs_library_updated()
        
    def on_prefs_library_updated(self):
        model = self.library_treeview.get_model()
        folders = []
        iter = model.get_iter_first()
        while iter:
            folders.append( model.get_value(iter, 0) )
            iter = model.iter_next(iter)
        folders.sort()
        model.clear()
        for folder in folders:
            model.append([folder])
        self.settings['folders'] = folders
        self.library = MelodiusLibrary.MelodiusLibrary()
        self.library_stats.set_label(_('<i>%i songs in library.  %s total playtime.</i>') % (len(self.library), '0:00:00'))
        self.emit("library_updated", len(self.library))
        
    def on_checkbutton_show_notifications_toggled(self, widget):
        """Toggle the notification settings editable"""
        self.settings["show-notifications"] = widget.get_active()
        self.notification_settings.set_sensitive(widget.get_active())
        
    def on_notifications_coverart_toggled(self, widget):
        self.preview_image.set_visible(widget.get_active())
        self.settings["show-coverart"] = widget.get_active()
        
    def on_notifications_primary_changed(self, widget):
        """Update the primary message preview"""
        text = widget.get_text()
        self.settings["primary-message"] = text
        text = text.replace("<", "&lt;").replace(">", "&gt;")
        text = text.replace("%s", _("Song Title"))
        text = text.replace("%a", _("Song Artist"))
        text = text.replace("%l", _("Song Album"))
        self.preview_primary_message.set_markup("<b>%s</b>" % text)

    def on_notifications_secondary_changed(self, widget):
        """Update the secondary message preview"""
        text = widget.get_text()
        self.settings["secondary-message"] = text
        text = text.replace("%s", _("Song Title"))
        text = text.replace("%a", _("Song Artist"))
        text = text.replace("%l", _("Song Album"))
        self.preview_secondary_message.set_markup(text)

    def on_button_preview_clicked(self, widget):
        """Show a notification preview"""
        primary = self.notifications_primary.get_text()
        primary = primary.replace("<", "&lt;").replace(">", "&gt;")
        primary = primary.replace("%s", _("Song Title"))
        primary = primary.replace("%a", _("Song Artist"))
        primary = primary.replace("%l", _("Song Album"))
        
        secondary = self.notifications_secondary.get_text()
        secondary = secondary.replace("<", "&lt;").replace(">", "&gt;")
        secondary = secondary.replace("%s", _("Song Title"))
        secondary = secondary.replace("%a", _("Song Artist"))
        secondary = secondary.replace("%l", _("Song Album"))
        
        if self.notifications_coverart.get_active():
            notification = Notify.Notification.new (primary,secondary,"audio-player")
        else:
            notification = Notify.Notification.new (primary,secondary,None)
        notification.show ()
        
    def on_notifications_revert_clicked(self, widget):
        """Revert notification settings to defaults."""
        self.notifications_coverart.set_active(True)
        self.notifications_primary.set_text("%s")
        self.notifications_secondary.set_text("by %a on %l")
        
