#
# Copyright (C) 2006-2007 Red Hat, Inc.
# Copyright (C) 2006 Hugh O. Brock <hbrock@redhat.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA 02110-1301 USA.
#

import logging
import re

import ipaddr

from gi.repository import Gtk
from gi.repository import Gdk

from virtManager.network import vmmNetwork
from virtManager.baseclass import vmmGObjectUI

PAGE_INTRO = 0
PAGE_NAME = 1
PAGE_IPV4 = 2
PAGE_DHCP = 3
PAGE_FORWARDING = 4
PAGE_SUMMARY = 5


class vmmCreateNetwork(vmmGObjectUI):
    def __init__(self, conn):
        vmmGObjectUI.__init__(self, "vmm-create-net.ui", "vmm-create-net")
        self.conn = conn

        self.builder.connect_signals({
            "on_create_pages_switch_page" : self.page_changed,
            "on_create_cancel_clicked" : self.close,
            "on_vmm_create_delete_event" : self.close,
            "on_create_forward_clicked" : self.forward,
            "on_create_back_clicked" : self.back,
            "on_create_finish_clicked" : self.finish,

            "on_net_name_activate": self.forward,
            "on_net_forward_toggled" : self.change_forward_type,
            "on_net_network_changed": self.change_network,
            "on_net_dhcp_enable_toggled": self.change_dhcp_enable,
            "on_net_dhcp_start_changed": self.change_dhcp_start,
            "on_net_dhcp_end_changed": self.change_dhcp_end,
        })
        self.bind_escape_key_close()

        finish_img = Gtk.Image.new_from_stock(Gtk.STOCK_QUIT,
                                              Gtk.IconSize.BUTTON)
        self.widget("create-finish").set_image(finish_img)

        self.set_initial_state()

    def show(self, parent):
        logging.debug("Showing new network wizard")
        self.reset_state()
        self.topwin.set_transient_for(parent)
        self.topwin.present()

    def is_visible(self):
        return self.topwin.get_visible()

    def close(self, ignore1=None, ignore2=None):
        logging.debug("Closing new network wizard")
        self.topwin.hide()
        return 1

    def _cleanup(self):
        self.conn = None

    def set_initial_state(self):
        notebook = self.widget("create-pages")
        notebook.set_show_tabs(False)

        black = Gdk.Color.parse("#000")[1]
        for num in range(PAGE_SUMMARY + 1):
            name = "page" + str(num) + "-title"
            self.widget(name).modify_bg(Gtk.StateType.NORMAL, black)

        fw_list = self.widget("net-forward")
        # [ label, dev name ]
        fw_model = Gtk.ListStore(str, str)
        fw_list.set_model(fw_model)
        text = Gtk.CellRendererText()
        fw_list.pack_start(text, True)
        fw_list.add_attribute(text, 'text', 0)

        fw_model.append([_("Any physical device"), None])
        for path in self.conn.list_net_device_paths():
            net = self.conn.get_net_device(path)
            fw_model.append([_("Physical device %s") % (net.get_name()),
                             net.get_name()])

        mode_list = self.widget("net-forward-mode")
        # [ label, mode ]
        mode_model = Gtk.ListStore(str, str)
        mode_list.set_model(mode_model)
        text = Gtk.CellRendererText()
        mode_list.pack_start(text, True)
        mode_list.add_attribute(text, 'text', 0)

        mode_model.append([_("NAT"), "nat"])
        mode_model.append([_("Routed"), "route"])

    def reset_state(self):
        notebook = self.widget("create-pages")
        notebook.set_current_page(0)

        self.page_changed(None, None, 0)

        self.widget("net-name").set_text("")
        self.widget("net-network").set_text("192.168.100.0/24")
        self.widget("net-dhcp-enable").set_active(True)
        self.widget("net-dhcp-start").set_text("")
        self.widget("net-dhcp-end").set_text("")
        self.widget("net-forward-none").set_active(True)

        self.widget("net-forward").set_active(0)
        self.widget("net-forward-mode").set_active(0)


    def forward(self, ignore=None):
        notebook = self.widget("create-pages")
        if self.validate(notebook.get_current_page()) is not True:
            return

        self.widget("create-forward").grab_focus()
        notebook.next_page()

    def back(self, ignore=None):
        notebook = self.widget("create-pages")
        notebook.prev_page()

    def change_network(self, src):
        ip = self.get_config_ip4()
        green = Gdk.Color.parse("#c0ffc0")[1]
        red = Gdk.Color.parse("#ffc0c0")[1]
        black = Gdk.Color.parse("#000000")[1]
        src.modify_text(Gtk.StateType.NORMAL, black)

        # No IP specified or invalid IP
        if ip is None or ip.version != 4:
            src.modify_base(Gtk.StateType.NORMAL, red)
            self.widget("net-info-netmask").set_text("")
            self.widget("net-info-broadcast").set_text("")
            self.widget("net-info-gateway").set_text("")
            self.widget("net-info-size").set_text("")
            self.widget("net-info-type").set_text("")
            return

        # FIXME: handle other networks and not just private?
        # We've got a valid IP
        if ip.numhosts < 16 or not ip.is_private:
            src.modify_base(gtk.STATE_NORMAL, red)
        else:
            src.modify_base(Gtk.StateType.NORMAL, green)
        self.widget("net-info-netmask").set_text(str(ip.netmask))
        self.widget("net-info-broadcast").set_text(str(ip.broadcast))

        if ip.prefixlen == 32:
            self.widget("net-info-gateway").set_text("")
        else:
            self.widget("net-info-gateway").set_text(str(ip.network + 1))
        self.widget("net-info-size").set_text(_("%d addresses") %
                                                         (ip.numhosts))

        if ip.is_private:
            self.widget("net-info-type").set_text(_("Private"))
        elif ip.is_reserved:
            self.widget("net-info-type").set_text(_("Reserved"))
        else:
            self.widget("net-info-type").set_text(_("Other"))

    def change_dhcp_enable(self, src):
        val = src.get_active()
        self.widget("net-dhcp-start").set_sensitive(val)
        self.widget("net-dhcp-end").set_sensitive(val)

    def change_dhcp_start(self, src):
        start = self.get_config_dhcp_start()
        self.change_dhcp(src, start)

    def change_dhcp_end(self, src):
        end = self.get_config_dhcp_end()
        self.change_dhcp(src, end)

    def change_dhcp(self, src, addr):
        ip = self.get_config_ip4()
        black = Gdk.Color.parse("#000000")[1]
        src.modify_text(Gtk.StateType.NORMAL, black)

        if addr is None or not ip.overlaps(addr):
            red = Gdk.Color.parse("#ffc0c0")[1]
            src.modify_base(Gtk.StateType.NORMAL, red)
        else:
            green = Gdk.Color.parse("#c0ffc0")[1]
            src.modify_base(Gtk.StateType.NORMAL, green)

    def change_forward_type(self, src_ignore):
        skip_fwd = self.widget("net-forward-none").get_active()

        self.widget("net-forward-mode").set_sensitive(not skip_fwd)
        self.widget("net-forward").set_sensitive(not skip_fwd)

    def get_config_name(self):
        return self.widget("net-name").get_text()

    def get_config_ip4(self):
        try:
            return ipaddr.IPNetwork(self.widget("net-network").get_text())
        except:
            return None

    def get_config_dhcp_start(self):
        try:
            return ipaddr.IPNetwork(self.widget("net-dhcp-start").get_text())
        except:
            return None
    def get_config_dhcp_end(self):
        try:
            return ipaddr.IPNetwork(self.widget("net-dhcp-end").get_text())
        except:
            return None


    def get_config_forwarding(self):
        if self.widget("net-forward-none").get_active():
            return [None, None]
        else:
            dev = self.widget("net-forward")
            model = dev.get_model()
            active = dev.get_active()
            name = model[active][1]

            mode_w = self.widget("net-forward-mode")
            mode = mode_w.get_model()[mode_w.get_active()][1]
            return [name, mode]

    def get_config_dhcp_enable(self):
        return self.widget("net-dhcp-enable").get_active()

    def populate_summary(self):
        dodhcp = self.get_config_dhcp_enable()
        self.widget("summary-name").set_text(self.get_config_name())

        ip = self.get_config_ip4()
        self.widget("summary-ip4-network").set_text(str(ip))
        self.widget("summary-ip4-gateway").set_text(str(ip.network + 1))
        self.widget("summary-ip4-netmask").set_text(str(ip.netmask))

        self.widget("label-dhcp-end").set_property("visible", dodhcp)
        self.widget("summary-dhcp-end").set_property("visible", dodhcp)
        if dodhcp:
            start = self.get_config_dhcp_start()
            end = self.get_config_dhcp_end()
            self.widget("summary-dhcp-start").set_text(str(start.network))
            self.widget("summary-dhcp-end").set_text(str(end.network))
            self.widget("label-dhcp-start").set_text(_("Start address:"))
            self.widget("label-dhcp-end").show()
            self.widget("summary-dhcp-end").show()
        else:
            self.widget("label-dhcp-start").set_text(_("Status:"))
            self.widget("summary-dhcp-start").set_text(_("Disabled"))

        forward_txt = ""
        dev, mode = self.get_config_forwarding()
        forward_txt = vmmNetwork.pretty_desc(mode, dev)
        self.widget("summary-forwarding").set_text(forward_txt)

    def populate_dhcp(self):
        ip = self.get_config_ip4()
        start = int(ip.numhosts / 2)
        end   = int(ip.numhosts - 2)

        if self.widget("net-dhcp-start").get_text() == "":
            self.widget("net-dhcp-start").set_text(str(ip.network + start))
        if self.widget("net-dhcp-end").get_text() == "":
            self.widget("net-dhcp-end").set_text(str(ip.network + end))

    def page_changed(self, ignore1, ignore2, page_number):
        if page_number == PAGE_NAME:
            name_widget = self.widget("net-name")
            name_widget.grab_focus()
        elif page_number == PAGE_DHCP:
            self.populate_dhcp()
        elif page_number == PAGE_SUMMARY:
            self.populate_summary()

        if page_number == PAGE_INTRO:
            self.widget("create-back").set_sensitive(False)
        else:
            self.widget("create-back").set_sensitive(True)

        if page_number == PAGE_SUMMARY:
            self.widget("create-forward").hide()
            self.widget("create-finish").show()
            self.widget("create-finish").grab_focus()
        else:
            self.widget("create-forward").show()
            self.widget("create-finish").hide()


    def finish(self, ignore=None):
        name = self.get_config_name()
        ip = self.get_config_ip4()
        start = self.get_config_dhcp_start()
        end = self.get_config_dhcp_end()
        dev, mode = self.get_config_forwarding()

        xml = "<network>\n"
        xml += "  <name>%s</name>\n" % name

        if mode:
            if dev is not None:
                xml += "  <forward mode='%s' dev='%s'/>\n" % (mode, dev)
            else:
                xml += "  <forward mode='%s'/>\n" % mode

        xml += "  <ip address='%s' netmask='%s'>\n" % (str(ip.network + 1),
                                                       str(ip.netmask))

        if self.get_config_dhcp_enable():
            xml += "    <dhcp>\n"
            xml += "      <range start='%s' end='%s'/>\n" % (str(start.network),
                                                             str(end.network))
            xml += "    </dhcp>\n"

        xml += "  </ip>\n"
        xml += "</network>\n"

        logging.debug("Generated network XML:\n" + xml)

        try:
            self.conn.create_network(xml)
        except Exception, e:
            self.err.show_err(_("Error creating virtual network: %s" % str(e)))
            return

        self.conn.tick(noStatsUpdate=True)
        self.close()

    def validate_name(self):
        name = self.widget("net-name").get_text()
        if len(name) > 50 or len(name) == 0:
            return self.err.val_err(_("Invalid Network Name"),
                        _("Network name must be non-blank and less than "
                          "50 characters"))
        if re.match("^[a-zA-Z0-9_]*$", name) is None:
            return self.err.val_err(_("Invalid Network Name"),
                        _("Network name may contain alphanumeric and '_' "
                          "characters only"))
        return True

    def validate_ipv4(self):
        ip = self.get_config_ip4()
        if ip is None:
            return self.err.val_err(_("Invalid Network Address"),
                    _("The network address could not be understood"))

        if ip.version != 4:
            return self.err.val_err(_("Invalid Network Address"),
                    _("The network must be an IPv4 address"))

        if ip.numhosts < 16:
            return self.err.val_err(_("Invalid Network Address"),
                    _("The network prefix must be at least /28 (16 addresses)"))

        if not ip.is_private:
            res = self.err.yes_no(_("Check Network Address"),
                    _("The network should normally use a private IPv4 "
                      "address. Use this non-private address anyway?"))
            if not res:
                return False

        return True

    def validate_dhcp(self):
        ip = self.get_config_ip4()
        start = self.get_config_dhcp_start()
        end = self.get_config_dhcp_end()
        enabled = self.widget("net-dhcp-enable").get_active()

        if enabled and start is None:
            return self.err.val_err(_("Invalid DHCP Address"),
                        _("The DHCP start address could not be understood"))
        if enabled and end is None:
            return self.err.val_err(_("Invalid DHCP Address"),
                        _("The DHCP end address could not be understood"))

        if enabled and not ip.overlaps(start):
            return self.err.val_err(_("Invalid DHCP Address"),
                    (_("The DHCP start address is not with the network %s") %
                     (str(ip))))
        if enabled and not ip.overlaps(end):
            return self.err.val_err(_("Invalid DHCP Address"),
                    (_("The DHCP end address is not with the network %s") %
                     (str(ip))))
        return True

    def validate_forwarding(self):
        if not self.widget("net-forward-dev").get_active():
            return True

        dev = self.widget("net-forward")
        if dev.get_active() == -1:
            return self.err.val_err(_("Invalid forwarding mode"),
                    _("Please select where the traffic should be forwarded"))
        return True

    def validate(self, page_num):
        if page_num == PAGE_NAME:
            return self.validate_name()
        elif page_num == PAGE_IPV4:
            return self.validate_ipv4()
        elif page_num == PAGE_DHCP:
            return self.validate_dhcp()
        elif page_num == PAGE_FORWARDING:
            return self.validate_forwarding()
        return True