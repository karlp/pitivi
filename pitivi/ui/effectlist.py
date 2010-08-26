# PiTiVi , Non-linear video editor
#
#       ui/effectlist.py
#
# Copyright (c) 2010, Thibault Saunier <tsaunier@gnome.org>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.

import gtk
import pango
import os
import time

from gettext import gettext as _

import pitivi.ui.dnd as dnd

from pitivi.configure import get_pixmap_dir

from pitivi.log.loggable import Loggable
from pitivi.effects import AUDIO_EFFECT, VIDEO_EFFECT
from pitivi.ui.common import SPACING, PADDING

(COL_NAME_TEXT,
 COL_DESC_TEXT,
 COL_EFFECT_TYPE,
 COL_EFFECT_CATEGORIES,
 COL_FACTORY,
 COL_ELEMENT_NAME) = range(6)

INVISIBLE = gtk.gdk.pixbuf_new_from_file(os.path.join(get_pixmap_dir(),
    "invisible.png"))

class EffectList(gtk.VBox, Loggable):
    """ Widget for listing effects """

    def __init__(self, instance, uiman):
        gtk.VBox.__init__(self)
        Loggable.__init__(self)

        self.app = instance
        self.settings = instance.settings

        #TODO check that
        self._dragButton = None
        self._dragStarted = False
        self._dragSelection = False
        self._dragX = 0
        self._dragY = 0

        #Tooltip handling
        self._current_effect_name = None
        self._current_tooltip_icon = None

        self.set_spacing(SPACING)

        #Searchbox and combobox
        Hfilters = gtk.HBox()
        Hfilters.set_spacing(SPACING)
        self.effectType = gtk.combo_box_new_text()
        self.effectType.append_text(_("Video effects"))
        self.effectType.append_text(_("Audio effects"))
        self.effectCategory = gtk.combo_box_new_text()
        self.show_categories(VIDEO_EFFECT)
        self.effectType.set_active(VIDEO_EFFECT)


        Hfilters.pack_start(self.effectType, expand=True)
        Hfilters.pack_end(self.effectCategory, expand=True)

        Hsearch = gtk.HBox()
        Hsearch.set_spacing(SPACING)
        searchStr = gtk.Label(_("Search:"))
        self.searchEntry = gtk.Entry()
        self.searchEntry.set_icon_from_stock(gtk.ENTRY_ICON_SECONDARY, "gtk-clear")
        Hsearch.pack_start(searchStr, expand=False)
        Hsearch.pack_end(self.searchEntry, expand=True)

        # Store
        self.storemodel = gtk.ListStore(str, str, int, object, object, str)

        # Scrolled Windows
        self.treeview_scrollwin = gtk.ScrolledWindow()
        self.treeview_scrollwin.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        self.treeview_scrollwin.set_shadow_type(gtk.SHADOW_ETCHED_IN)

        # TreeView
        # Displays name, description
        self.treeview = gtk.TreeView(self.storemodel)
        self.treeview_scrollwin.add(self.treeview)
        self.treeview.set_property("rules_hint", True)
        self.treeview.set_property("has_tooltip", True)
        tsel = self.treeview.get_selection()
        tsel.set_mode(gtk.SELECTION_SINGLE)

        namecol = gtk.TreeViewColumn(_("Name"))
        namecol.set_sort_column_id(COL_NAME_TEXT)
        self.treeview.append_column(namecol)
        namecol.set_spacing(SPACING)
        namecol.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        namecol.set_fixed_width(150)
        namecell = gtk.CellRendererText()
        namecell.props.xpad = 6
        namecell.set_property("ellipsize", pango.ELLIPSIZE_END)
        namecol.pack_start(namecell)
        namecol.add_attribute(namecell, "text", COL_NAME_TEXT)

        desccol = gtk.TreeViewColumn(_("Description"))
        desccol.set_sort_column_id(COL_DESC_TEXT)
        self.treeview.append_column(desccol)
        desccol.set_expand(True)
        desccol.set_spacing(SPACING)
        desccol.set_sizing(gtk.TREE_VIEW_COLUMN_AUTOSIZE)
        desccol.set_min_width(150)
        desccell = gtk.CellRendererText()
        desccell.props.xpad = 6
        desccell.set_property("ellipsize", pango.ELLIPSIZE_END)
        desccol.pack_start(desccell)
        desccol.add_attribute(desccell, "text", COL_DESC_TEXT)

        self.effectType.connect ("changed", self._effectTypeChangedCb)

        self.effectCategory.connect ("changed", self._effectCategoryChangedCb)

        self.searchEntry.connect ("changed", self.searchEntryChangedCb)
        self.searchEntry.connect ("button-press-event", self.searchEntryActivateCb)
        self.searchEntry.connect ("focus-out-event", self.searchEntryDesactvateCb)
        self.searchEntry.connect ("icon-press", self.searchEntryIconClickedCb)

        self.treeview.connect("button-press-event", self._treeViewButtonPressEventCb)
        self.treeview.connect("select-cursor-row", self._treeViewEnterPressEventCb)
        self.treeview.connect("motion-notify-event", self._treeViewMotionNotifyEventCb)
        self.treeview.connect("query-tooltip", self._treeViewQueryTooltipCb)
        self.treeview.connect("button-release-event", self._treeViewButtonReleaseCb)
        self.treeview.connect("drag_begin", self._dndDragBeginCb)
        self.treeview.connect("drag_data_get", self._dndDataGetCb)

        self.pack_start(Hfilters, expand=False)
        self.pack_start(Hsearch, expand=False, padding=PADDING)
        self.pack_end(self.treeview_scrollwin, expand=True)

        #create the filterModel
        self.modelFilter = self.storemodel.filter_new()
        self.modelFilter.set_visible_func(self._setRowVisible, data=None)
        self.treeview.set_model(self.modelFilter)

        #Add factories
        self._addFactories(self.app.effects.getAllVideoEffects(), VIDEO_EFFECT)
        self._addFactories(self.app.effects.getAllAudioEffects(), AUDIO_EFFECT)

        self.treeview_scrollwin.show_all()
        Hfilters.show_all()
        Hsearch.show_all()

    def _addFactories(self, elements, effectType):
        for element in elements:
            name =element.get_name()
            effect = self.app.effects.getFactoryFromName(name)
            self.storemodel.append([ effect.getHumanName(),
                                     effect.getDescription(), effectType, effect.getCategories(),\
                                     effect, element.get_name()])

            self.storemodel.set_sort_column_id(COL_NAME_TEXT, gtk.SORT_ASCENDING)

    def show_categories(self, effectType):
        self.effectCategory.get_model().clear()

        if effectType is VIDEO_EFFECT:
            for categorie in self.app.effects.video_categories:
                self.effectCategory.append_text(categorie)

        if effectType is AUDIO_EFFECT:
            for categorie in self.app.effects.audio_categories:
                self.effectCategory.append_text(categorie)

        self.effectCategory.set_active(0)

    def _dndDragBeginCb(self, view, context):
        self.info("tree drag_begin")
        path = self.treeview.get_selection().get_selected_rows()[1]

        if len(path) < 1:
            context.drag_abort(int(time.time()))
        else:
            row = self.storemodel[path[0]]
            #FIXME
            #if row[COL_ICON]:
                #context.set_icon_pixbuf(row[COL_ICON], 0, 0)

    def _rowUnderMouseSelected(self, view, event):
        result = view.get_path_at_pos(int(event.x), int(event.y))
        if result:
            path = result[0]
            selection = view.get_selection()
            return selection.path_is_selected(path) and selection.count_selected_rows() > 0

        return False

    def _treeViewEnterPressEventCb(self, treeview, event):
        factory_name = self.getSelectedItems()
        self.app.gui.clipconfig.effect_expander.addEffectToCurrentSelection(factory_name)

    def _treeViewButtonPressEventCb(self, treeview, event):
        chain_up = True

        if event.button == 3:
            chain_up = False
        elif event.type is gtk.gdk._2BUTTON_PRESS:
            factory_name = self.getSelectedItems()
            self.app.gui.clipconfig.effect_expander.addEffectToCurrentSelection(factory_name)
        else:
            chain_up = not self._rowUnderMouseSelected(treeview, event)

            self._dragStarted = False
            self._dragSelection = False
            self._dragButton = event.button
            self._dragX = int(event.x)
            self._dragY = int(event.y)

        if chain_up:
            gtk.TreeView.do_button_press_event(treeview, event)
        else:
            treeview.grab_focus()

        return True

    def _treeViewButtonReleaseCb(self, treeview, event):
        if event.button == self._dragButton:
            self._dragButton = None
        return False

    def _treeViewMotionNotifyEventCb(self, treeview, event):
        chain_up = True

        if not self._dragButton:
            return True

        if self._nothingUnderMouse(treeview, event):
            return True

        if not event.state & (gtk.gdk.CONTROL_MASK | gtk.gdk.SHIFT_MASK):
            chain_up = not self._rowUnderMouseSelected(treeview, event)

        if treeview.drag_check_threshold(self._dragX, self._dragY,
            int(event.x), int(event.y)):
            context = treeview.drag_begin(
                self._getDndTuple(),
                gtk.gdk.ACTION_COPY,
                self._dragButton,
                event)
            self._dragStarted = True

        if chain_up:
            gtk.TreeView.do_button_press_event(treeview, event)
        else:
            treeview.grab_focus()

        return False

    def _treeViewQueryTooltipCb(self, treeview, x, y, keyboard_mode, tooltip):
        context = treeview.get_tooltip_context(x, y, keyboard_mode)

        if context is None:
            return False

        treeview.set_tooltip_row (tooltip, context[1][0])
        name = self.modelFilter.get_value(context[2], COL_ELEMENT_NAME)
        if self._current_effect_name != name: 
            self._current_effect_name = name
            icon = self.app.effects.getEffectIcon(name)
            self._current_tooltip_icon = icon

        tooltip.set_icon(self._current_tooltip_icon)
        tooltip.set_text(self.modelFilter.get_value(context[2], COL_DESC_TEXT))

        return True

    def getSelectedItems(self):
        model, rows = self.treeview.get_selection().get_selected_rows()
        path = self.modelFilter.convert_path_to_child_path(rows[0])
        return self.storemodel[path][COL_ELEMENT_NAME]

    def _dndDataGetCb(self, unused_widget, context, selection,
                      targettype, unused_eventtime):
        self.info("data get, type:%d", targettype)
        factory = self.getSelectedItems()

        if len(factory) < 1:
            return

        selection.set(selection.target, 8, factory)
        context.set_icon_pixbuf(INVISIBLE, 0, 0)

    def _effectTypeChangedCb(self, combobox):
        self.modelFilter.refilter()
        self.show_categories(combobox.get_active())

    def _effectCategoryChangedCb(self, combobox):
        self.modelFilter.refilter()

    def searchEntryChangedCb (self, entry):
        self.modelFilter.refilter()

    def searchEntryIconClickedCb (self, entry, unused, unsed1):
        entry.set_text("")

    def searchEntryDesactvateCb(self, entry, event):
        self.app.gui.setActionsSensitive(['FullScreen', 'Split',], True)

    def searchEntryActivateCb(self, entry, event):
        self.app.gui.setActionsSensitive(['FullScreen', 'Split',], False)

    def _setRowVisible(self, model, iter, data):
        if self.effectType.get_active() == model.get_value(iter, COL_EFFECT_TYPE):
            if model.get_value(iter, COL_EFFECT_CATEGORIES) is None:
                return False
            if self.effectCategory.get_active_text() in model.get_value(iter, COL_EFFECT_CATEGORIES):
                text = self.searchEntry.get_text().lower()
                return text in model.get_value(iter, COL_DESC_TEXT).lower() or\
                       text in model.get_value(iter, COL_NAME_TEXT).lower()
            else:
                return False
        else:
            return False

    def _nothingUnderMouse(self, view, event):
        return not bool(view.get_path_at_pos(int(event.x), int(event.y)))

    def _getDndTuple(self):
         if self.effectType.get_active() == VIDEO_EFFECT:
            return [dnd.VIDEO_EFFECT_TUPLE, dnd.EFFECT_TUPLE]
         else:
            return [dnd.AUDIO_EFFECT_TUPLE, dnd.EFFECT_TUPLE]
