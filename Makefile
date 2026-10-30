CC ?= gcc
CFLAGS ?= -O3 -Wall -Wextra -Wpedantic

PREFIX ?= /usr/local
BINDIR ?= $(PREFIX)/bin
UDEVDIR ?= /etc/udev/rules.d
APPDIR ?= /usr/share/applications

all: evofox-ctl

evofox-ctl: tools/evofox-ctl.c
	$(CC) $(CFLAGS) -o evofox-ctl tools/evofox-ctl.c
	cp -p evofox-ctl tools/evofox-ctl

install: evofox-ctl
	install -d $(DESTDIR)$(BINDIR)
	install -m 755 evofox-ctl $(DESTDIR)$(BINDIR)/evofox-ctl
	install -m 755 evofox.py $(DESTDIR)$(BINDIR)/evofox
	install -m 755 evofox-gtk.py $(DESTDIR)$(BINDIR)/evofox-gtk
	install -m 755 evofox-gui.py $(DESTDIR)$(BINDIR)/evofox-gui
	install -m 755 run-evofox $(DESTDIR)$(BINDIR)/run-evofox
	install -d $(DESTDIR)$(UDEVDIR)
	install -m 644 tools/99-evofox.rules $(DESTDIR)$(UDEVDIR)/99-evofox.rules
	install -d $(DESTDIR)$(APPDIR)
	install -m 644 tools/evofox.desktop $(DESTDIR)$(APPDIR)/evofox.desktop
	@command -v udevadm >/dev/null 2>&1 && udevadm control --reload-rules && udevadm trigger --subsystem-match=hidraw --attr-match=idVendor=30fa 2>/dev/null || true
	@echo "Installation complete!"
	@echo "CLI tool: $(BINDIR)/evofox-ctl"
	@echo "GUI tool: $(BINDIR)/run-evofox"

clean:
	rm -f evofox-ctl tools/evofox-ctl

.PHONY: all install clean
