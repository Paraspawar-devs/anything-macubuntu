#disable binary striping, in case this is a problem
%global __os_install_post %{nil}
#Disable debug packages, since these are emulated files mostly
%define debug_package %{nil}
%define commit_date %{getenv:DARLING_COMMIT_DATE}
%if "%{commit_date}" == ""
	%define commit_date 0
%endif
%global _buildshell /bin/bash

# explicitly ignore all the bogus dependencies that the auto-scanner finds in `/usr/libexec/anything-mac`
#
# note that we *don't* want to simply use `__requires_exclude_from` to exclude `/usr/libexec/anything-mac` from scanning,
# since we *do* want our Mach-O scanner to scan that tree (and there's no way to only exclude paths for some dependency generators; it's all or nothing).
%global __requires_exclude ^(/bin/sed|/bin/sh|/usr/bin/perl|/usr/bin/python2.7|/System/Library/Frameworks/Python.framework/Versions/2.7/bin/python2.7|/usr/bin/python|/System/Library/Frameworks/Ruby.framework/Versions/2.6/usr/bin/ruby|/usr/bin/env|/usr/bin/ruby)$

Name:           anything-mac
Version:        0.1.%{commit_date}
Release:        1%{?dist}
Summary:        AnythingMac

Group:          Utility
License:        GPLv3
URL:            https://www.anything-machq.org/
# Use this line for Source0 if there are ever official versions.
# Source0:        https://github.com/anything-machq/anything-mac/archive/%%{version}/%%{name}-%%{version}.tar.gz
Source0:        %{name}.tar.gz
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

BuildRequires:  cmake clang bison flex python2 glibc-devel(x86-64) glibc-devel(x86-32)
BuildRequires:  fuse-devel systemd-devel
BuildRequires:  cairo-devel freetype-devel(x86-64) fontconfig-devel(x86-64)
BuildRequires:  freetype-devel(x86-32) fontconfig-devel(x86-32) make
BuildRequires:  libjpeg-turbo-devel(x86-64) libtiff-devel(x86-64)
BuildRequires:  libjpeg-turbo-devel(x86-32)
BuildRequires:  libglvnd-devel mesa-libGL-devel mesa-libEGL-devel
BuildRequires:  libxml2-devel elfutils-libelf-devel
BuildRequires:  libbsd-devel
BuildRequires:  ffmpeg-devel pulseaudio-libs-devel openssl-devel giflib-devel
BuildRequires:  libXrandr-devel libXcursor-devel libxkbfile-devel dbus-devel mesa-libGLU-devel
BuildRequires:  vulkan-headers llvm-devel libcap-devel bash vulkan-loader-devel

Requires: anything-mac-cli anything-mac-python2 anything-mac-ruby anything-mac-perl anything-mac-gui anything-mac-gui-stubs anything-mac-pyobjc

%description
Translation layer for running macOS software on Linux

%package extra
Summary:       Extra components for AnythingMac
Group:         Utility
Requires:      anything-mac anything-mac-jsc anything-mac-cli-extra

%description extra
Extra components for AnythingMac that are not part of a typical ("stock") installation

%package core
Summary:    AnythingMac core components
Group:      Utility
Requires:   xdg-user-dirs

%description core
Core components of AnythingMac

%package system
Summary:    AnythingMac system components
Group:      Utility
Requires:   anything-mac-core

%description system
System components of AnythingMac

%package cli
Summary:    AnythingMac CLI components
Group:      Utility
Requires:   anything-mac-system anything-mac-cli-gui-common anything-mac-cli-python2-common

%description cli
CLI components of AnythingMac

%package ffi
Summary:    libffi for AnythingMac
Group:      Utility
Requires:   anything-mac-core

%description ffi
libffi built for use within AnythingMac

%package cli-gui-common
Summary:    AnythingMac CLI and GUI common components
Group:      Utility
Requires:   anything-mac-system

%description cli-gui-common
Components of AnythingMac that are shared between the CLI and GUI components

%package iokitd
Summary:    AnythingMac IOKit daemon
Group:      Utility
Requires:   anything-mac-system anything-mac-iosurface

%description iokitd
IOKit daemon for AnythingMac

%package cli-devenv-gui-common
Summary:    AnythingMac developer environment and GUI common components
Group:      Utility
Requires:   anything-mac-system

%description cli-devenv-gui-common
Components of AnythingMac that are shared between the developer environment and the GUI components

%package cli-extra
Summary:    Extra AnythingMac CLI components
Group:      Utility
Requires:   anything-mac-cli

%description cli-extra
Non-standard CLI components of AnythingMac

%package gui
Summary:    AnythingMac GUI components
Group:      Utility
Requires:   anything-mac-system anything-mac-cli-devenv-gui-common anything-mac-iokitd anything-mac-cli-gui-common anything-mac-iosurface

%description gui
GUI components of AnythingMac

%package python2
Summary:    Python 2 for AnythingMac
Group:      Utility
Requires:   anything-mac-core anything-mac-cli-python2-common anything-mac-ffi

%description python2
Python 2 (and associated programs) built for use within AnythingMac

%package cli-python2-common
Summary:    AnythingMac CLI and Python 2 common components
Group:      Utility
Requires:   anything-mac-core

%description cli-python2-common
Components of AnythingMac that are shared between the CLI and Python 2 components

%package pyobjc
Summary:    PyObjC for AnythingMac
Group:      Utility
Requires:   anything-mac-gui-stubs anything-mac-python2

%description pyobjc
PyObjC built for use within AnythingMac

%package ruby
Summary:    Ruby for AnythingMac
Group:      Utility
Requires:   anything-mac-core anything-mac-ffi

%description ruby
Ruby built for use within AnythingMac

%package perl
Summary:    Perl for AnythingMac
Group:      Utility
Requires:   anything-mac-core

%description perl
Perl built for use within AnythingMac

%package jsc-webkit-common
Summary:    AnythingMac JavaScriptCore and WebKit common components
Group:      Utility
Requires:   anything-mac-system

%description jsc-webkit-common
Components of AnythingMac that are shared between JavaScriptCore and WebKit

%package jsc
Summary:    JavaScriptCore for AnythingMac
Group:      Utility
Requires:   anything-mac-system anything-mac-jsc-webkit-common

%description jsc
JavaScriptCore built for use within AnythingMac

%package iosurface
Summary:    IOSurface framework for AnythingMac
Group:      Utility
Requires:   anything-mac-system

%description iosurface
IOSurface framework built for use within AnythingMac

%package cli-devenv-gui-stubs-common
Summary:    AnythingMac developer environment and GUI stubs common components
Group:      Utility
Requires:   anything-mac-cli-devenv-gui-common

%description cli-devenv-gui-stubs-common
Components of AnythingMac that are shared between the developer environment and GUI stub components

%package gui-stubs
Summary:    AnythingMac GUI stub components
Group:      Utility
Requires:   anything-mac-gui anything-mac-cli-devenv-gui-stubs-common

%description gui-stubs
GUI stub components of AnythingMac

%prep
%setup -q -n %{name}

%build
%{__mkdir_p} build
pushd build
	# Release is broken https://github.com/anything-machq/anything-mac/issues/331
	#          -DCMAKE_BUILD_TYPE=Release \
	CFLAGS="" CXXFLAGS="" CPPFLAGS="" LDFLAGS="" \
	%{__cmake} -DCMAKE_INSTALL_PREFIX=%{_prefix} \
	           -DOpenGL_GL_PREFERENCE=GLVND \
	           -DDEBIAN_PACKAGING=ON \
	           -DJSC_UNIFIED_BUILD=ON \
	           ..
	%{make_build} -j `nproc`
popd

%install
[ "$RPM_BUILD_ROOT" != "/" ] && rm -rf $RPM_BUILD_ROOT
DARLING_COMPONENTS=(
	core
	system
	cli
	ffi
	cli_gui_common
	iokitd
	cli_dev_gui_common
	cli_extra
	gui
	python
	cli_python_common
	pyobjc
	ruby
	perl
	jsc_webkit_common
	jsc
	iosurface
	cli_dev_gui_stubs_common
	gui_stubs
)
PACKAGE_SUFFIXES=(
	core
	system
	cli
	ffi
	cli-gui-common
	iokitd
	cli-devenv-gui-common
	cli-extra
	gui
	python2
	cli-python2-common
	pyobjc
	ruby
	perl
	jsc-webkit-common
	jsc
	iosurface
	cli-devenv-gui-stubs-common
	gui-stubs
)
pushd build
	for index in {0..18}; do
		rm -rf tmp/${PACKAGE_SUFFIXES[index]}
		DESTDIR=tmp/${PACKAGE_SUFFIXES[index]} %{__cmake} -DCOMPONENT=${DARLING_COMPONENTS[index]} -P cmake_install.cmake
		find tmp/${PACKAGE_SUFFIXES[index]} \( ! -type d -o -type d -empty \) -printf '"/%%P"\n' > files.${PACKAGE_SUFFIXES[index]}.txt
		cp -rla tmp/${PACKAGE_SUFFIXES[index]}/. %{?buildroot}/
	done

	# pack up a "source" (actually binary) tarball for `anything-mac-cli-devenv`
	# NOTE: this is probably not the best approach. fix this if something better comes up.
	rm -rf tmp/cli-devenv
	DESTDIR=tmp/cli-devenv %{__cmake} -DCOMPONENT=cli_dev -P cmake_install.cmake
	rm -f %{_sourcedir}/anything-mac-cli-devenv.tar.gz
	tar --transform "s|^\./|anything-mac-cli-devenv/|" -cf %{_sourcedir}/anything-mac-cli-devenv.tar.gz -C tmp/cli-devenv .
popd

%files
%doc LICENSE

%files extra

%files core -f build/files.core.txt
%files system -f build/files.system.txt
%files cli -f build/files.cli.txt
%files ffi -f build/files.ffi.txt
%files cli-gui-common -f build/files.cli-gui-common.txt
%files iokitd -f build/files.iokitd.txt
%files cli-devenv-gui-common -f build/files.cli-devenv-gui-common.txt
%files cli-extra -f build/files.cli-extra.txt
%files gui -f build/files.gui.txt
%files python2 -f build/files.python2.txt
%files cli-python2-common -f build/files.cli-python2-common.txt
%files pyobjc -f build/files.pyobjc.txt
%files ruby -f build/files.ruby.txt
%files perl -f build/files.perl.txt
%files jsc-webkit-common -f build/files.jsc-webkit-common.txt
%files jsc -f build/files.jsc.txt
%files iosurface -f build/files.iosurface.txt
%files cli-devenv-gui-stubs-common -f build/files.cli-devenv-gui-stubs-common.txt
%files gui-stubs -f build/files.gui-stubs.txt

%changelog
* Tue May 02 2023 Ariel Abreu <facekapow@outlook.com> - 0.1.20230502-1
- Update to latest version and Fedora 37
- Split package into multiple packages (one for each component of AnythingMac)

* Tue Aug 18 2020 Andy Neff <andy@visionsystemsinc.com> - 0.1.20200331-1
- Update for latest version and Fedora 31

* Mon Aug 12 2019 Andy Neff <andy@visionsystemsinc.com> - 0.1-4
- Update for Fedora 30

* Tue Mar 12 2019 Andy Neff <andy@visionsystemsinc.com> - 0.1-3
- Remove bad commented macro, cleanup, and verify master works on Fedora 29

* Wed Jul 18 2018 Andy Neff <andy@visionsystemsinc.com> - 0.1-2
- Update for Fedora 28 and new master

* Tue Jan 23 2018 Andy Neff <andy@visionsystemsinc.com> - 0.1-1
- Initial version working for Fedora 27
