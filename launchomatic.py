#!/usr/bin/python
import ConfigParser
import time

from gi.repository import Gtk, Wnck
from gi.repository.Gtk import IconTheme
from gi.repository.GdkPixbuf import Pixbuf

import threading
import json
import os
from os.path import expanduser
from subprocess import Popen, PIPE
import sys
from Xlib import display, X



class LauncherList(list):

    def __init__(self, commands):

        self.add_window_list()
        self.add_commands(commands)

        class LazyLoader(threading.Thread):

            def run(thread):
                self.add_launchers()

        lazy_loader = LazyLoader()
        lazy_loader.start()

        self.sort(key=lambda x: (x['type'], x['keyword']))

    def add_window_list(self):

        self.window_list = []
        self.filter = None

        screen = Wnck.Screen.get_default()
        screen.force_update()  # recommended per Wnck documentation

        # loop all windows
        for window in screen.get_windows():
            application = window.get_application()

            if window.get_class_group_name() == None:
                continue

            self.append({ "id": window.get_xid(),
                          "name": "%s - %s" % (window.get_class_group_name(),
                                               window.get_name()),
                          "keyword": window.get_class_group_name(),
                          "icon": window.get_mini_icon(),
                          "type": "app" })

    def add_commands(self, commands):

        command_icon = Pixbuf.new_from_file_at_size("{base_path}/res/command.svg".format(
            base_path = os.path.dirname(os.path.realpath(__file__))
        ), 16, 16)

        for name, command in commands.items():
            self.append({
                "type": "command",
                "name": name,
                "keyword": command,
                "command": command,
                "icon": command_icon
            })

    def add_launchers(self):

        command_icon = Pixbuf.new_from_file_at_size("{base_path}/res/command.svg".format(
            base_path = os.path.dirname(os.path.realpath(__file__))
        ), 16, 16)

        theme = IconTheme()

        for launcher_directory in ["/home/wouter/.local/share/applications",
                                   "/usr/share/applications"]:

            for launcher in os.listdir(launcher_directory):

                try:
                    config = ConfigParser.ConfigParser()
                    config.read("%s/%s" % (launcher_directory, launcher))

                    if not config.has_section("Desktop Entry"):
                        continue

                    if not config.get("Desktop Entry", "type") == "Application":
                        continue

                    icon_name = config.get("Desktop Entry", "icon")

                    icon = command_icon

                    if icon_name != "eclipse.png":
                        print icon_name
                        try:
                            icon = theme.load_icon(icon_name, 20, 0)
                        except:
                            pass

                    self.append({
                        "type": "command",
                        "name": config.get("Desktop Entry", "name"),
                        "keyword": "",
                        "command": config.get("Desktop Entry", "exec"),
                        "icon": icon
                    })

                except ConfigParser.Error:
                    pass

    def get_matches(self, filter):
        matches = []
        for item in self:
            match = True

            if filter:

                for term in filter.split():

                    name = item['name'].lower()
                    keyword = item['keyword'].lower()
                    filter = term.lower()

                    if name.find(filter) == -1 and keyword.find(filter) == -1:
                        match = False

            if match:
                matches.append(item)

        return matches

    def get_by_name(self, name):
        for item in self:
            if item['name'] == name:
                return item
        return None




class MyWindow(Gtk.Window):

    def __init__(self):

        Gtk.Window.__init__(self, title="Launch-o-matic")

        self.selected_item = None
        self.filter = None
        self.config = {}

        self.load_config()
        self.launcher_list = LauncherList(self.config.get('commands', {}))

        self.setup_ui()
        self.update_result_list()


    def load_config(self):
        home = expanduser("~")
        try:
            with open("%s/.launchomatic.json" % home, "r") as config_source:
                self.config = json.load(config_source)
        except IOError:
            print "Warning: config file '%s' not found" % ("%s/.switchomatic.json" % home)
            pass

    def setup_ui(self):

        self.set_resizable(False)
        self.set_modal(True)
        self.set_decorated(True)
        self.set_position(3)

        self.connect("focus-out-event", self.focus_lost)

        self.virt_layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add(self.virt_layout)

        self.filter_entry = Gtk.Entry()
        self.filter_entry.connect("changed", self.filter_changed)
        self.filter_entry.connect("key-release-event", self.filter_key_pressed)
        self.virt_layout.add(self.filter_entry)

        self.result_store = Gtk.ListStore(Pixbuf, str)
        self.result_list = Gtk.TreeView(self.result_store)
        self.result_list.set_property
        self.result_list.set_property("headers-visible", False)
        self.result_list.connect("key-release-event", self.result_list_key_pressed)
        self.result_list.connect("button-release-event", self.result_list_mouse_pressed)
        self.result_list.get_selection().connect("changed", self.result_list_item_selected)

        renderer_pixbuf = Gtk.CellRendererPixbuf()

        column_pixbuf = Gtk.TreeViewColumn("Image", renderer_pixbuf, pixbuf=0)
        self.result_list.append_column(column_pixbuf)

        renderer_text = Gtk.CellRendererText()
        column_text = Gtk.TreeViewColumn("Text", renderer_text, text=1)
        self.result_list.append_column(column_text)

        self.virt_layout.add(self.result_list)

    def focus_lost(self, event, window):
        self.close()

    def filter_changed(self, entry):
        self.filter = entry.get_text()
        self.update_result_list()
        self.set_position(3)

    def close(self):
        Gtk.main_quit()

    def filter_key_pressed(self, entry, event):
#        print event.keyval

        if event.keyval == 65307:
            self.close()

        if event.keyval == 65293:
            self.activate_first_match()

    def result_list_key_pressed(self, entry, event):

        if event.keyval == 65307:
            self.close()

        if event.keyval == 65293 and self.selected_item:
            self.activate(self.selected_item)

    def result_list_mouse_pressed(self, entry, event):
        self.activate(self.selected_item)

    def result_list_item_selected(self, selection):
        model, treeiter = selection.get_selected()
        if treeiter != None:

            self.selected_item = model[treeiter][1]

    def update_result_list(self):
        self.result_store.clear()
        for window in self.launcher_list.get_matches(self.filter)[:15]:
            icon = window.get('icon')
            self.result_store.append([icon, window['name']])


    def activate_first_match(self):

        matches = self.launcher_list.get_matches(self.filter)

        if len(matches) == 0:
            return

        self.activate(matches[0]['name'])

    def activate(self, name):

        launcher = self.launcher_list.get_by_name(name)

        if not launcher:
            print "Could not find ", launcher
            return


        if launcher["type"] == "app":
            print "Activating '{}'".format(name)

            screen = Wnck.Screen.get_default()
            screen.force_update()  # recommended per Wnck documentation

            # loop all windows
            for window in screen.get_windows():
                if window.get_xid() != launcher['id']:
                    continue

                window.activate(time.time())

        if launcher["type"] == "command":
            print "Running command '{}'".format(name)
            Popen([launcher["command"]],
                   shell=True,
                   close_fds=True)

        Gtk.main_quit()


win = MyWindow()
win.connect("delete-event", Gtk.main_quit)
win.show_all()
Gtk.main()
