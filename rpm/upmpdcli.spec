Summary:        UPnP Media Renderer front-end to MPD, the Music Player Daemon
Name:           upmpdcli
Version:        1.8.11
Release:        1%{?dist}
Group:          Applications/Multimedia
License:        GPLv2+
URL:            http://www.lesbonscomptes.com/updmpdcli
Source0:        http://www.lesbonscomptes.com/upmpdcli/downloads/upmpdcli-%{version}.tar.gz
Requires(pre):  shadow-utils
Requires(post): systemd
Requires(preun): systemd
Requires(postun): systemd
Requires: python-requests
BuildRequires:  meson
BuildRequires:  gcc-c++
BuildRequires:  libupnpp
BuildRequires:  libcurl-devel
BuildRequires:  libmicrohttpd-devel
BuildRequires:  jsoncpp-devel
BuildRequires:  libmpdclient-devel
BuildRequires:  systemd-units
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

%global __python %{__python3}

%description
Upmpdcli turns MPD, the Music Player Daemon into an UPnP Media Renderer,
usable with most UPnP Control Point applications, such as those which run
on Android tablets or phones.


%prep
%autosetup

%build
%meson -Dscctl=true
%meson_build

%pre
getent group upmpdcli >/dev/null || groupadd -r upmpdcli
getent passwd upmpdcli >/dev/null || \
    useradd -r -g upmpdcli -G audio -d /nonexistent -s /sbin/nologin \
    -c "upmpdcli mpd UPnP front-end" upmpdcli
exit 0

%install
%meson_install
install -D -m644 systemd/upmpdcli.service  %{buildroot}%{_unitdir}/upmpdcli.service

%clean
%{__rm} -rf %{buildroot}

%files
%defattr(-, root, root, -)
%{_bindir}/%{name}
%{_bindir}/scctl
%{_datadir}/%{name}
%{_mandir}/man1/%{name}.1*
%{_mandir}/man5/upmpdcli.conf.5*
%{_unitdir}/upmpdcli.service
%{_sysconfdir}/upmpdcli.conf-dist
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
