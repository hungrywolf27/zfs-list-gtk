#!/usr/bin/env python3

import os
import sys
import argparse
import pickle
import subprocess
import time

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

SIZE_PROPERTIES = ['used', 'usedbychildren', 'usedbydataset',
                   'usedbysnapshots', 'available', 'referenced']

homedir = os.getenv('HOME')
configdir = os.path.join(homedir, '.config')
if os.path.isdir(configdir):
    optsfile = os.path.join(configdir, 'zfs-list-gtk.conf')
else:
    optsfile = os.path.join(homedir, '.zfs-list-gtk.conf')


def human_readable(num, binary=False):
    if binary:
        if abs(num) < 1024:
            return '{}B'.format(num)
        #           ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB']
        for unit in ['B', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
            if abs(num) < 10.0:
                return '{:.2f}{}'.format(num, unit)
            if abs(num) < 1024.0:
                return '{:.1f}{}'.format(num, unit)
            num = num / 1024.0
        return '{:.1f}{}'.format(num, 'YiB')
    else:
        if abs(num) < 1000:
            return '{} B'.format(num)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB']:
            if abs(num) < 10.0:
                return '{:.2f} {}'.format(num, unit)
            if abs(num) < 1000.0:
                return '{:.1f} {}'.format(num, unit)
            num = num / 1000.0
        return '{:.1f} {}'.format(num, 'YB')


def parse_zfs_list_output(lines, props):
    filesystems = []
    for line in lines:
        if line == '': continue
        current_fs_props = {}
        line = line.split('\t')
        for i, prop in enumerate(props):
            current_fs_props[prop] = line[i]
        filesystems.append(current_fs_props)
    return filesystems


def build_treestore(filesystem, props):
    command = ['zfs', 'list', '-Hrpt', 'all', '-o', ','.join(props + ['type'])]
    if filesystem:
        command.append(filesystem)

    try:
        output = subprocess.check_output(command)
    except:
        sys.exit('Error running zfs list')
    output = output.decode().split('\n')
    if output == ['']:
        sys.exit('Error: no zfs filesystems')

    filesystems = parse_zfs_list_output(output, props + ['type'])

    # Initialize columns in the TreeStore
    cols = []
    for prop in props:
        cols.append(str)
        if prop in SIZE_PROPERTIES or prop == 'creation':
            cols.append(float)
    store = Gtk.TreeStore.new(cols)

    for fs in filesystems:
        # Add each value as a column
        row = []
        for prop in props:
            if prop in SIZE_PROPERTIES:
                if fs[prop] == '-':
                    row.append('-')
                    row.append(0)
                else:
                    row.append(human_readable(int(fs[prop]), binary=True))
                    row.append(float(fs[prop]))
            elif prop == 'creation':
                row.append(time.strftime('%a %b %d %H:%M %Y',
                                         time.localtime(int(fs[prop]))))
                row.append(float(fs[prop]))
            else:
                row.append(fs[prop])

        # Append this item to the store
        if fs['type'] == 'filesystem':
            li = store.append(None, row)
            parent = li
        elif fs['type'] == 'snapshot':
            li = store.append(parent, row)
    return store


class Gui:
    def __init__(self, filesystem, props, gui_opts):
        self.filesystem = filesystem
        self.props = props
        self.gui_opts = gui_opts

        self.store = build_treestore(
            self.filesystem, self.props)
        self.tview = Gtk.TreeView(self.store)
        self.selecteditem = None

        # Create a TreeViewColumn for each property
        _index = 0
        for c in self.props:
            if c in ['name', 'mountpoint', 'creation']:
                # Left justify column and header
                col = Gtk.TreeViewColumn(
                    title=c,
                    cell_renderer=Gtk.CellRendererText(),
                    text=_index)
            else:
                # Right justify column and header
                col = Gtk.TreeViewColumn(
                    title=c,
                    cell_renderer=Gtk.CellRendererText(xalign=1),
                    text=_index)
                col.set_alignment(1)

            if c in SIZE_PROPERTIES or c == 'creation':
                col.set_sort_column_id(_index + 1)
                _index += 1
            else:
                col.set_sort_column_id(_index)

            col.set_resizable(True)
            col.set_reorderable(True)
            col.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
            colwidth = gui_opts.get('column_widths', {}).get(c)
            if colwidth: col.set_fixed_width(colwidth)

            self.tview.append_column(col)
            _index += 1

        # Connect signal to selecting row
        self.tview.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)
        self.tview.get_selection().connect('changed', self.on_changed)
        self.tview.connect('row-activated', self.on_row_activated)

        # Prettify the TreeView
        self.tview.set_headers_clickable(True)
        self.tview.set_rules_hint(True)
        self.tview.set_column_drag_function(None, None)

        # Embed the TreeView in a scrolling window
        self.scroll = Gtk.ScrolledWindow()
        # Make scrollbars appear only when needed
        self.scroll.set_policy(Gtk.PolicyType.AUTOMATIC,
                               Gtk.PolicyType.AUTOMATIC)
        self.scroll.set_shadow_type(Gtk.ShadowType.IN)
        self.scroll.add(self.tview)

        # Put the scrolled window into a Box
        box = Gtk.Box()
        box.set_orientation(Gtk.Orientation.VERTICAL)
        box.add(self.scroll)
        box.set_child_packing(self.scroll, True, True, 0, 0)

        # Create box to hold buttons
        hbox = Gtk.ButtonBox.new(Gtk.Orientation.HORIZONTAL)
        hbox.set_spacing(5)
        hbox.set_layout(Gtk.ButtonBoxStyle.SPREAD)
        box.add(hbox)

        # Add buttons to the box
        btn_refresh = Gtk.Button(label='Refresh')
        btn_refresh.connect('clicked', self.on_btn_refresh_clicked)
        hbox.add(btn_refresh)

        # Make the window
        self.window = Gtk.Window()
        self.window.add(box)

        # Necessary for window.get_size() to work
        self.window.connect('delete-event', self.close)

        # Make the window look pretty and size it
        self.window.set_title(self.store[0][0])
        self.window.set_border_width(5)
        self.window.set_default_size(self.gui_opts.get('width', 800),
                                     self.gui_opts.get('height', 600))

        print('pid: {}'.format(os.getpid()))
        self.window.show_all()
        Gtk.main()

    def refresh_tree(self):
        # Remember the currently expanded rows
        expanded_rows = []
        for i, row in enumerate(self.store):
            if self.tview.row_expanded(Gtk.TreePath(i)):
                expanded_rows.append(row[0])

        # Rebuild the treestore
        treestore = build_treestore(
            self.filesystem, self.props)
        self.tview.set_model(treestore)

        # Expand the previously expanded rows
        for i, row in enumerate(self.store):
            if row[0] in expanded_rows:
                self.tview.expand_row(Gtk.TreePath(i), False)

    def on_btn_refresh_clicked(self, button):
        self.refresh_tree()

    def on_changed(self, selection):
        (model, paths) = selection.get_selected_rows()
        self.selecteditems = []
        for i in paths:
            self.selecteditems.append(model[i][0])

    def on_row_activated(self, a, b, c):
        # Called when row is double-clicked
        pass

    def close(self, widget, data):
        # Get the window size
        self.gui_opts = {}
        self.gui_opts['width'], self.gui_opts['height'] = self.window.get_size()

        # Get column widths
        self.gui_opts['column_widths'] = {}
        cols = self.tview.get_columns()
        for c in cols:
            self.gui_opts['column_widths'][c.get_title()] = c.get_width()

        pickle.dump(self.gui_opts, open(optsfile, 'wb'))

        Gtk.main_quit()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-o', nargs='?',
        default='name,used,avail,refer,mountpoint')
    parser.add_argument('filesystem', nargs='?')
    args = parser.parse_args()

    try:
        gui_opts = pickle.load(open(optsfile, 'rb'))
    except:
        print('Could not load options from {}'.format(optsfile))
        gui_opts = {}

    props = args.o.split(',')
    if 'name' not in props:
        props = ['name'] + props
    props = ['available' if p == 'avail' else p for p in props]
    props = ['referenced' if p == 'refer' else p for p in props]
    props = ['compressratio' if p == 'ratio' else p for p in props]

    Gui(args.filesystem, props, gui_opts)
