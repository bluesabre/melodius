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

import locale
from locale import gettext as _
locale.textdomain('melodius')

import gi
gi.require_version('Gst', '1.0')
gi.require_version('Gtk', '3.0')

from gi.repository import Gtk, Gdk, Gio, GdkPixbuf, GObject, Gst, Notify # pylint: disable=E0611
import logging
logger = logging.getLogger('melodius')

from melodius_lib import Window
from melodius.AboutMelodiusDialog import AboutMelodiusDialog
from melodius.PreferencesMelodiusDialog import PreferencesMelodiusDialog
from melodius.MelodiusLibrary import MelodiusLibrary

from melodius_lib.sound_menu import SoundMenuControls

import os

import random

import mutagen

GObject.threads_init()
Gst.init(None)

def menu_position(self, menu, data=None, something_else=None):
    """Return the proper position for the application menu."""
    widget = menu.get_attach_widget()
    allocation = widget.get_allocation()
    window_pos = widget.get_window().get_position()
    x = window_pos[0] + allocation.x - menu.get_allocated_width() + widget.get_allocated_width()
    y = window_pos[1] + allocation.y + allocation.height
    return (x, y, True)

def detach_cb(menu, widget):
    """Callback function for detaching the menu."""
    menu.detach()

class History:
    """Simplified history class that maintains previous and next actions."""
    def __init__(self):
        """Initialize the History class."""
        self.history = []
        self.last_accessed = 0

    def __len__(self):
        """Return the size of the history list."""
        return len(self.history)

    def append(self, data):
        """Append a history item to the list."""
        self.history.append(data)

    def insert(self, data):
        """Insert a history item at the current position.  Return the index of
        the new history item."""
        del self.history[self.last_accessed:]
        try:
            if self.history[self.last_accessed-1] == data:
                return self.last_accessed
        except IndexError:
            pass
        self.last_accessed += 1
        self.history.append(data)
        return self.last_accessed

    def previous(self):
        """Return the index of, and the previous history item."""
        if self.last_accessed == 0:
            return (-1, None)
        self.last_accessed -= 1
        if self.last_accessed == 0:
            return (-1, None)
        return (self.last_accessed, self.history[self.last_accessed-1])

    def next(self):
        """Return the index of, and the next history item."""
        if self.last_accessed == len(self.history):
            return (-1, None)
        self.last_accessed += 1
        return (self.last_accessed, self.history[self.last_accessed-1])

    def get_data(self, index):
        """Return the history item at the specified index."""
        self.last_accessed = index
        return self.history[index]

    def get_index(self):
        """Return the current index."""
        return self.last_accessed

# See melodius_lib.Window.py for more details about how this class works
class MelodiusWindow(Window):
    __gtype_name__ = "MelodiusWindow"

    def finish_initializing(self, builder): # pylint: disable=E1002
        """Set up the main window"""
        super(MelodiusWindow, self).finish_initializing(builder)

        self.AboutDialog = AboutMelodiusDialog
        self.PreferencesDialog = PreferencesMelodiusDialog

        # - Begin Toolbar ---------------------------------------------------- #
        self.toolbar = builder.get_object('toolbar')
        context = self.toolbar.get_style_context()
        context.add_class(Gtk.STYLE_CLASS_PRIMARY_TOOLBAR)

        self.prev_button = builder.get_object("toolbutton_prev")
        self.playpause_button = builder.get_object("toolbutton_playpause")
        self.next_button = builder.get_object("toolbutton_next")

        self.box_songinfo = builder.get_object("box_songinfo")
        self.image_artwork = builder.get_object("image_artwork")
        self.label_songinfo = builder.get_object("label_songinfo")

        self.label_progress = builder.get_object("label_progress")
        self.timer_adjustment = builder.get_object("adjustment_timer")
        self.label_length = builder.get_object("label_length")

        # - Begin Song Tooltip ----------------------------------------------- #
        self.tooltip = builder.get_object("tooltip")
        context = self.tooltip.get_style_context()
        context.add_class(Gtk.STYLE_CLASS_TOOLTIP)
        self.tooltip_artwork = builder.get_object("tooltip_artwork")
        self.tooltip_title = builder.get_object("tooltip_title")
        self.tooltip_artist = builder.get_object("tooltip_artist")
        self.tooltip_album = builder.get_object("tooltip_album")
        self.box_songinfo.set_tooltip_window(self.tooltip)
        # - End Song Tooltip - #

        self.repeat_button = builder.get_object("toolbutton_repeat")
        self.shuffle_button = builder.get_object("toolbutton_shuffle")

        self.menu_button = builder.get_object('toolbutton_appmenu')
        self.appmenu = builder.get_object('appmenu')
        self.appmenu.attach_to_widget(self.menu_button, detach_cb)
        # - End Toolbar - #

        # - Begin Infobar ---------------------------------------------------- #
        vbox = builder.get_object("infobar_placeholder")
        self.infobar = Gtk.InfoBar()
        content = self.infobar.get_content_area()
        label = Gtk.Label()
        label.set_markup( "<b>%s</b>" % _("Search") )
        content.pack_start(label, False, False, 0)

        self.search_entry = Gtk.Entry()
        self.search_entry.set_icon_from_stock(Gtk.EntryIconPosition.SECONDARY, "gtk-clear")
        self.search_entry.set_placeholder_text( _("Song title, artist, or album") )
        self.search_entry.connect("changed", self.on_search_entry_changed)
        content.pack_start(self.search_entry, True, True, 0)

        self.infobar.set_message_type(Gtk.MessageType.QUESTION)

        self.infobar.add_button( _("Close"), 1 )
        self.infobar.connect("response", self.on_infobar_response)

        vbox.pack_start(self.infobar, False, False, 0)
        self.infobar.show_all()
        self.infobar.hide()
        # - End Infobar - #

        # - Begin Library Treeview ------------------------------------------- #
        self.library_treeview = builder.get_object('library_treeview')
        for i in range(6):
            column = self.library_treeview.get_column(i)
            cell = Gtk.CellRendererText()
            column.pack_start(cell, True)
            column.add_attribute(cell, 'text', i)

        model = self.library_treeview.get_model()
        self.library_filter = model.filter_new()
        self.library_filter.set_visible_func(self.library_filter_func)
        self.library_treeview.set_model(self.library_filter)
        # - End Library Treeview - #

        # - Load Interface Settings ------------------------------------------ #
        self.settings = Gio.Settings("net.launchpad.melodius")
        self.repeat_button.set_active(self.settings["repeat"])
        self.shuffle_button.set_active(self.settings["shuffle"])

        # - Load GStreamer --------------------------------------------------- #
        self.pipeline = Gst.Pipeline()

        self.audiosrc = Gst.ElementFactory.make("audiotestsrc", None)
        self.pipeline.add(self.audiosrc)

        self.sink = Gst.ElementFactory.make("pulsesink", None)
        self.pipeline.add(self.sink)

        self.audiosrc.link(self.sink)

        self.player = Gst.ElementFactory.make("playbin", None)

        bus = self.player.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.on_message)

        # - Load Sound Menu -------------------------------------------------- #
        self.sound_menu = SoundMenuControls('melodius')
        self.sound_menu._sound_menu_next = self._sound_menu_next
        self.sound_menu._sound_menu_previous = self._sound_menu_previous
        self.sound_menu._sound_menu_is_playing = self._sound_menu_is_playing
        self.sound_menu._sound_menu_play = self._sound_menu_play
        self.sound_menu._sound_menu_pause = self._sound_menu_pause
        self.sound_menu._sound_menu_raise = self._sound_menu_raise

        # - Load Notifications ----------------------------------------------- #
        Notify.init("melodius")
        self.notification = Notify.Notification.new ("Melodius", "Ready to jam!", None)

        # Load library

        self.update_library()


        # - Set Defaults ----------------------------------------------------- #
        self.state = "stopped"
        self.timer_thread = -1

        self.history = History()
        self.now_playing = 0

        path = Gtk.TreePath.new_from_string( str( 0 ) )
        self.library_treeview.set_cursor(path)
        self.load_selected_data()

        self.load_start = False

    def update_library(self, widget=None, data=None):
        model = self.library_treeview.get_model().get_model()
        model.clear()
        self.library = MelodiusLibrary()
        # - Load Library ----------------------------------------------------- #
        for (path, title, artist, album, track, length, rating) in self.library.get_tracks():
            if track == -1:
                track = None
            try:
                model.append([track,
                            title.replace('\\\'', '\'').replace('\\\"', '\"'),
                            artist.replace('\\\'', '\'').replace('\\\"', '\"'),
                            album.replace('\\\'', '\'').replace('\\\"', '\"'),
                            length.replace('\\\'', '\'').replace('\\\"', '\"'),
                            rating,
                            path.replace('\\\'', '\'').replace('\\\"', '\"')])
            except Exception as e:
                print (e)

    def on_melodius_window_delete_event(self, widget, event):
        """Hide the melodius window when closed."""
        #self.hide()
        #return True
        return self.destroy()

    def on_melodius_window_key_press_event(self, widget, event):
        """Catch keypress events."""
        ctrl = event.state & Gdk.ModifierType.CONTROL_MASK
        keyname = Gdk.keyval_name(event.keyval)
        if ctrl:
            if keyname == 'q' or keyname == 'w':
                Gtk.main_quit()
            if keyname == 'f':
                self.infobar.show()
                self.search_entry.grab_focus()
        else:
            if keyname == 'Escape':
                self.infobar.hide()
                self.library_treeview.grab_focus()
                self.search_entry.set_text("")

    def on_toolbutton_playpause_clicked(self, widget):
        """Toggle the playback state using the Play/Pause button."""
        if self.state == "playing":
            self.set_playback_state("paused")
        elif self.state == "paused":
            self.set_playback_state("playing")
        else:
            self.load_selected_data()
            self.set_playback_state("playing")

    def on_toolbutton_prev_clicked(self, widget):
        """Go to the previous song when the Previous button is clicked."""
        self.playlist_prev()

    def on_toolbutton_next_clicked(self, widget):
        """Go to the next song when the Next button is clicked."""
        self.playlist_next()

    def on_toolbutton_repeat_toggled(self, widget):
        """Update the repeat setting in dconf when the setting is changed."""
        self.settings["repeat"] = widget.get_active()

    def on_toolbutton_shuffle_toggled(self, widget):
        """Update the shuffle setting in dconf when the setting is changed."""
        self.settings["shuffle"] = widget.get_active()

    def on_toolbutton_appmenu_toggled(self, widget):
        """Reveal the appmenu when the button is toggled."""
        if widget.get_active():
            self.appmenu.popup(None, None, menu_position,
                                    self.appmenu, 3,
                                    Gtk.get_current_event_time())
        else:
            self.appmenu.hide()

    def on_appmenu_hide(self, widget):
        """Toggle the menu button off when the appmenu is hidden."""
        self.menu_button.set_active(False)

    def on_adjustment_timer_value_changed(self, widget):
        """Update the progress values when the adjustment is changed."""
        progress = sanitize_length(widget.get_value())
        self.label_progress.set_markup( '<small>%s</small>' % progress )

    def on_scale_timer_change_value(self, widget, event, user_data):
        """Update the song position when the scale is manually seeked."""
        seconds = self.timer_adjustment.get_value()
        self.player.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT, seconds * Gst.SECOND)

    def on_infobar_response(self, widget, response):
        """Close the infobar when the button is pressed."""
        self.infobar.hide()
        self.library_treeview.grab_focus()
        self.search_entry.set_text("")

    def on_search_entry_changed(self, widget):
        """Update the search results when the query is changed."""
        self.library_filter.refilter()

    def on_library_treeview_row_activated(self, widget, event, user_data):
        """When a library row is activated, play the selected song."""
        self.load_start = not self.load_start
        if self.load_start:
            self.set_playback_state("stopped")
            self.load_selected_data(True)
            self.set_playback_state("playing")
            self.now_playing += 1

    def get_selected_data(self):
        """Return a dictionary of data collected from the currently selected row."""
        sel = self.library_treeview.get_selection()
        store, path = sel.get_selected_rows()
        try:
            iter = store.get_iter( path[0] )
        except IndexError:
            return None
        data = dict()
        data['track'] = store.get_value(iter, 0)
        data['title'] = store.get_value(iter, 1)
        data['artist'] = store.get_value(iter, 2)
        data['album'] = store.get_value(iter, 3)
        data['length'] = store.get_value(iter, 4)
        data['rating'] = store.get_value(iter, 5)
        data['filename'] = store.get_value(iter, 6)
        data['path'] = path[0]
        return data

    def get_album_artwork(self, filename, size=42):
        """Return a GdkPixbuf.Pixbuf containing the album artwork at the
        specified size."""
        folder = os.path.split(filename)[0]
        for path in os.listdir(folder):
            if path.lower() == 'folder.jpg':
                return GdkPixbuf.Pixbuf.new_from_file_at_size( os.path.join(folder, path), size, size )
        file_data = mutagen.File(filename)
        if file_data.tags.has_key('APIC:'):
            artwork = file_data.tags['APIC:'].data
        else:
            return None
        pixbufLoader = GdkPixbuf.PixbufLoader()
        pixbufLoader.write(artwork)
        pixbufLoader.close()
        pixbuf = pixbufLoader.get_pixbuf()
        return pixbuf.scale_simple(size, size, GdkPixbuf.InterpType.BILINEAR)
        return None

    def load_selected_data(self, insert=False):
        """Load all song-related information from the currently selected row."""
        data = self.get_selected_data()
        if data:
            self.track_title = data['title']
            self.track_album = data['album']
            self.track_artist = data['artist']

            markup_title = text_to_markup(data['title'])
            markup_artist = text_to_markup(data['artist'])
            markup_album = text_to_markup(data['album'])

            self.player.set_property("uri", "file://" + data['filename'])

            artwork = self.get_album_artwork(data['filename'])
            tooltip_artwork = self.get_album_artwork(data['filename'], 128)
            if artwork:
                self.image_artwork.set_from_pixbuf( artwork )
                self.tooltip_artwork.set_from_pixbuf( tooltip_artwork )
            else:
                self.image_artwork.set_from_icon_name("audio-player", 42)
                self.tooltip_artwork.set_from_icon_name("audio-player", 128)

            self.label_songinfo.set_markup(
                                "<big><b>%s</b></big> by <b>%s</b> on <i>%s</i>" %
                                (markup_title, markup_artist, markup_album) )
            self.tooltip_title.set_markup("<big><b>%s</b></big>" % markup_title)
            self.tooltip_artist.set_markup("<b>%s</b>" % markup_artist)
            self.tooltip_album.set_text(self.track_album)

            length_seconds = desanitize_length( data['length'] )
            self.timer_adjustment.set_upper( length_seconds )
            length_string = sanitize_length( length_seconds )
            self.label_length.set_markup("<small>%s</small>" % length_string)

            if insert:
                self.now_playing = self.history.insert(data['path'])

            self.sound_menu.song_changed(   title = self.track_title,
                                            album = self.track_album,
                                            artists = self.track_artist)

            self.show_notification(data)
        else:
            self.label_songinfo.set_markup("<big><b>Melodius</b></big>")
            self.tooltip_title.set_markup("<big><b>Melodius</b></big>")
            self.tooltip_artist.set_text("")
            self.tooltip_album.set_text("")


    def get_library_treeview_path(self):
        """Return the TreeViewPath to the currently selected row."""
        sel = self.library_treeview.get_selection()
        store, path = sel.get_selected_rows()
        return path[0]

    def library_filter_func(self, model, iter, user_data):
        """Filter function rules for the library search."""
        text = self.search_entry.get_text()
        if text.lower() in model[iter][1].lower(): return True
        if text.lower() in model[iter][2].lower(): return True
        if text.lower() in model[iter][3].lower(): return True
        return False

    def playlist_set_path(self, path):
        """Set the playlist selected item to the specified path."""
        state = self.state
        self.set_playback_state("stopped")
        self.library_treeview.set_cursor(path)
        self.load_selected_data()
        if state == "playing":
            self.set_playback_state("playing")

    def playlist_prev(self):
        """Go to the previous song."""
        index, prev = self.history.previous()
        if prev:
            self.now_playing = index
            self.playlist_set_path(prev)

    def playlist_next(self):
        """Go to the next song."""
        index, next = self.history.next()
        if next:
            self.now_playing = index
        else:
            path = self.get_library_treeview_path()
            if self.shuffle_button.get_active():
                val = random.randrange(len(self.library_treeview.get_model()))
                next = Gtk.TreePath.new_from_string( str( val ) )
            else:
                next = Gtk.TreePath.new_from_string( str(int(str(path))+1) )
            self.now_playing = self.history.insert(next)
        self.playlist_set_path(next)


    # - GSTREAMER ------------------------------------------------------------ #
    def update_timer(self):
        """Timer thread callback function."""
        if self.state == "playing":
            val = self.timer_adjustment.get_value()
            self.timer_adjustment.set_value(val+1)
            return True
        elif self.state == "paused":
            return False
        elif self.state == "stopped":
            self.timer_adjustment.set_value(0)
            return False

    def set_playback_state(self, state):
        """Set the current playback state.

        Accepted values are 'playing', 'paused', and 'stopped'."""
        if state == "playing":
            self.playpause_button.set_icon_name("media-playback-pause-symbolic")
            self.player.set_state(Gst.State.PLAYING)
            self.sound_menu.signal_playing()
            if self.timer_thread != -1:
                GObject.source_remove(self.timer_thread)
            self.timer_thread = GObject.timeout_add(1000, self.update_timer)
        elif state == "paused":
            self.playpause_button.set_icon_name("media-playback-start-symbolic")
            self.player.set_state(Gst.State.PAUSED)
            self.sound_menu.signal_paused()
        elif state == "stopped":
            self.playpause_button.set_icon_name("media-playback-start-symbolic")
            self.player.set_state(Gst.State.NULL)
            self.sound_menu.signal_paused()
            self.timer_adjustment.set_value(0)
        self.state = state

    def on_message(self, bus, message):
        """Function for handling gstreamer messages."""
        t = message.type
        if t == Gst.MessageType.EOS:
            self.playlist_next()
        elif t == Gst.MessageType.ERROR:
            self.set_playback_state("stopped")
        elif t == Gst.MessageType.STATE_CHANGED:
            pass
        else:
            pass
            #print "Unknown Message:\n", t
    # - END GSTREAMER -------------------------------------------------------- #

    # Notifications
    def show_notification(self, data):
        """Song track information notification."""
        if self.settings["show-notifications"]:
            primary = self.settings["primary-message"]
            secondary = self.settings["secondary-message"]

            primary = primary.replace("<", "&lt;").replace(">", "&gt;")
            primary = primary.replace("%s", data['title'])
            primary = primary.replace("%a", data['artist'])
            primary = primary.replace("%l", data['album'])

            secondary = secondary.replace("<", "&lt;").replace(">", "&gt;")
            secondary = secondary.replace("%s", data['title'])
            secondary = secondary.replace("%a", data['artist'])
            secondary = secondary.replace("%l", data['album'])

            if self.settings["show-coverart"]:
                artwork = self.get_album_artwork(data['filename'], 48)
                if artwork:
                    self.notification.update(primary, secondary, None)
                    self.notification.set_icon_from_pixbuf(artwork)
                else:
                    self.notification.update(primary, secondary, "audio-player")
            else:
                self.notification.update(primary, secondary, None)
            self.notification.show ()

    # Sound Menu Controls
    def _sound_menu_is_playing(self):
        """return True if the player is currently playing, otherwise, False"""
        return self.state == "playing"

    def _sound_menu_play(self):
        """start playing if ready"""
        self.set_playback_state("playing")

    def _sound_menu_pause(self):
        """pause if playing"""
        self.set_playback_state("paused")

    def _sound_menu_next(self):
        """go to the next song in the list"""
        self.playlist_next()

    def _sound_menu_previous(self):
        """go to the previous song in the list"""
        self.playlist_previous()

    def _sound_menu_raise(self):
        """raise the window to the top of the z-order"""
        self.show()

def sanitize_length(int_seconds):
    """Convert length in seconds into a human-readable time format."""
    length_seconds = int(int_seconds)
    length_minutes = int(length_seconds/60)
    length_seconds = length_seconds - (length_minutes*60)
    length_hours = int(length_minutes/60)
    length_minutes = length_minutes - (length_hours * 60)

    length_seconds = str(length_seconds)
    if len(length_seconds) == 1:
        length_seconds = "0" + length_seconds
    length_minutes = str(length_minutes)
    if len(length_minutes) == 1:
        length_minutes = "0" + length_minutes

    if length_hours > 0:
        length_hours = str(length_hours)
        if len(length_hours) == 1:
            length_hours = "0" + length_hours
        return "%s:%s:%s" % (length_hours, length_minutes, length_seconds)

    else:
        return "%s:%s" % (length_minutes, length_seconds)

def desanitize_length(len_string):
    """Convert length in human-readable format to seconds."""
    split = len_string.split(':')
    if len(split) == 3:
        seconds = int(split[0])*60+int(split[1])*60+int(split[2])
    else:
        seconds = int(split[0])*60+int(split[1])
    return seconds

def text_to_markup(text):
    """Return the string formatted for markup."""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def markup_to_text(markup):
    """Return the string formatted for plain text."""
    return text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')

