CC ?= gcc
CFLAGS ?= -O3 -Wall -Wextra

PREFIX ?= /usr/local
BINDIR ?= $(PREFIX)/bin
UDEVDIR ?= /etc/udev/rules.d
APPDIR ?= /usr/share/applications

all: evofox-ctl

evofox-ctl: evofox-ctl.c
	$(CC) $(CFLAGS) -o evofox-ctl evofox-ctl.c

install: evofox-ctl
	install -d $(DESTDIR)$(BINDIR)
	install -m 755 evofox-ctl $(DESTDIR)$(BINDIR)/evofox-ctl
	install -m 755 evofox-gui.py $(DESTDIR)$(BINDIR)/evofox-gui
	install -d $(DESTDIR)$(UDEVDIR)
	install -m 644 99-evofox.rules $(DESTDIR)$(UDEVDIR)/99-evofox.rules
	install -d $(DESTDIR)$(APPDIR)
	install -m 644 evofox.desktop $(DESTDIR)$(APPDIR)/evofox.desktop
	@command -v udevadm >/dev/null 2>&1 && udevadm control --reload-rules && udevadm trigger || true
	@echo "Installation complete!"
	@echo "CLI tool: $(BINDIR)/evofox-ctl"
	@echo "GUI tool: $(BINDIR)/evofox-gui"
	@echo "Desktop application added to your app launcher."

clean:
	rm -f evofox-ctl

.PHONY: all install clean
