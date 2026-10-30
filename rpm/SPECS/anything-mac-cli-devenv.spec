# NOTE: this package MUST be built after building the main `anything-mac` package

#disable binary striping, in case this is a problem
%global __os_install_post %{nil}
#Disable debug packages, since these are emulated files mostly
%define debug_package %{nil}
%define commit_date %{getenv:DARLING_COMMIT_DATE}
%if "%{commit_date}" == ""
	%define commit_date 0
%endif
%global _buildshell /bin/bash

Name:           anything-mac-cli-devenv
Version:        0.1.%{commit_date}
Release:        1%{?dist}
Summary:        AnythingMac developer environment

Group:          Utility
License:        GPLv3
URL:            https://www.anything-machq.org/
# Use this line for Source0 if there are ever official versions.
# Source0:        https://github.com/anything-machq/anything-mac/archive/%%{version}/%%{name}-%%{version}.tar.gz
Source0:        %{name}.tar.gz
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

BuildRequires:  bash

Requires:       anything-mac-cli anything-mac-python2 anything-mac-ruby anything-mac-perl anything-mac-cli-devenv-gui-common anything-mac-cli-devenv-gui-stubs-common anything-mac-iosurface
Conflicts:      anything-mac-gui anything-mac-gui-stubs

%description
A AnythingMac environment for CLI-only programs for building and developing using the command line developer tools

%prep
%setup -q -n %{name}

%build
true

%install
[ "$RPM_BUILD_ROOT" != "/" ] && rm -rf $RPM_BUILD_ROOT
cp -rla . %{?buildroot}/

%files
%{_libexecdir}/anything-mac

%changelog
* Tue May 02 2023 Ariel Abreu <facekapow@outlook.com> - 0.1.20230502-1
- Initial version working for Fedora 37
- Split package off from `anything-mac` package
