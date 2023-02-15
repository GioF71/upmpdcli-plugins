Summary:        UPnP Media Renderer front-end to MPD, the Music Player Daemon
Name:           upmpdcli
Version:        1.7.2
Release:        1%{?dist}
Group:          Applications/Multimedia
License:        GPLv2+
URL:            http://www.lesbonscomptes.com/updmpdcli
Source0:        http://www.lesbonscomptes.com/upmpdcli/downloads/upmpdcli-%{version}.tar.gz
Patch0:         configure_cxxflags_pic.patch
Requires(pre):  shadow-utils
Requires(post): systemd
Requires(preun): systemd
Requires(postun): systemd
Requires: python-requests
# Because of the configure.ac/Makefile.am patch, needs autotools
BuildRequires:  autoconf
BuildRequires:  automake
BuildRequires:  libupnpp
BuildRequires:  libmpdclient-devel
BuildRequires:  libmicrohttpd-devel
BuildRequires:  jsoncpp-devel
BuildRequires:  expat-devel
BuildRequires:  systemd-units
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

%global __python %{__python3}

%description
Upmpdcli turns MPD, the Music Player Daemon into an UPnP Media Renderer,
usable with most UPnP Control Point applications, such as those which run
on Android tablets or phones.


%prep
%setup -q
%patch0 -p1
sh autogen.sh

%build
%configure
%{__make} %{?_smp_mflags}

%pre
getent group upmpdcli >/dev/null || groupadd -r upmpdcli
getent passwd upmpdcli >/dev/null || \
    useradd -r -g upmpdcli -G audio -d /nonexistent -s /sbin/nologin \
    -c "upmpdcli mpd UPnP front-end" upmpdcli
exit 0

%install
%{__rm} -rf %{buildroot}
%{__make} install DESTDIR=%{buildroot} STRIP=/bin/true INSTALL='install -p'
install -D -m644 systemd/upmpdcli.service \
        %{buildroot}%{_unitdir}/upmpdcli.service


%clean
%{__rm} -rf %{buildroot}

%files
%defattr(-, root, root, -)
%{_bindir}/%{name}
%{_bindir}/scctl
%{_datadir}/%{name}
%{_mandir}/man1/%{name}.1*
%{_unitdir}/upmpdcli.service
%config(noreplace) /etc/upmpdcli.conf

%post
%systemd_post upmpdcli.service

%preun
%systemd_preun upmpdcli.service

%postun
%systemd_postun_with_restart upmpdcli.service 

%changelog
* Wed Feb 26 2020 J.F. Dockes <jf@dockes.org> - 1.4.7
- Fix previous fix for resetting mpd single mode on playlist init. The
  previous method confused Kazoo.
