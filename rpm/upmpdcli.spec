Summary:        UPnP Media Renderer front-end to MPD, the Music Player Daemon
Name:           upmpdcli
Version:        1.4.5
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
BuildRequires:  libupnpp
BuildRequires:  libupnp-devel
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
* Sat Sep 15 2018 J.F. Dockes <jf@dockes.org> - 1.3.2
- Support OpenHome Credentials for direct Qobuz/Tidal access from kazoo
* Tue Jan 03 2017 J.F. Dockes <jf@dockes.org> - 1.2.12
- Fix bug in content directory browse interface (for Kazoo).
* Mon Dec 26 2016 J.F. Dockes <jf@dockes.org> - 1.2.11
- Radio dynamic artwork and improved qobuz interface
* Sun Nov 20 2016 J.F. Dockes <jf@dockes.org> - 1.2.10
- Small bug fixes.
* Sun Oct 09 2016 J.F. Dockes <jf@dockes.org> - 1.2.6
- Small fixes.
* Sun Sep 11 2016 J.F. Dockes <jf@dockes.org> - 1.2.2
- Implement Media Server for acessing streaming services (Google Play
  Music, Qobuz and Tidal)
* Thu Mar 17 2016 J.F. Dockes <jf@dockes.org> - 1.1.3
- Fix cover art display, which sometimes vanished.
- Allow changing the xml data directory in the run time config.
- Fix execution of onvolumechange (command could not have args).
* Fri Feb 26 2016 J.F. Dockes <jf@dockes.org> - 1.1.2
- Fix Songcast Receiver in scplaymethod=mpd mode
* Thu Feb 18 2016 J.F. Dockes <jf@dockes.org> - 1.1.1
- Improve play state management when switching sources
- Support external scripts for volume control
- Avoid losing metadata (e.g. album art) when switching from Playlist to
  Radio and back
* Fri Feb 05 2016 J.F. Dockes <jf@dockes.org> - 1.1.0
- Add OpenHome Radio Source (play internet radios). Needs Python.
- Add capability to forward ALSA input channel to Songcast (needs
  sc2mpd 0.14).
- Fix Receiver detection from Windows Songcast
* Wed Dec 23 2015 J.F. Dockes <jf@dockes.org> - 0.13.1
- many changes since 0.8... Specific in 0.13: turn off mpd 'single' if set
  and support OpenHome Sender mode. ohproduct eventing fixes.
* Mon Jun 09 2014 J.F. Dockes <jf@dockes.org> - 0.8.4
- Separated libupnpp
* Mon Jun 09 2014 J.F. Dockes <jf@dockes.org> - 0.7.1
- Implement OpenHome services
* Sun Apr 20 2014 J.F. Dockes <jf@dockes.org> - 0.6.4
- Configuration of UPnP interface and port, MPD password.
* Wed Mar 26 2014 J.F. Dockes <jf@dockes.org> - 0.6.3
- Version 0.6.3 fixes seeking
* Sun Mar 02 2014 J.F. Dockes <jf@dockes.org> - 0.6.2
- Version 0.6.2
* Wed Feb 26 2014 J.F. Dockes <jf@dockes.org> - 0.6.1
- Version 0.6.1
* Thu Feb 13 2014 J.F. Dockes <jf@dockes.org> - 0.5
- Version 0.5
* Wed Feb 12 2014 J.F. Dockes <jf@dockes.org> - 0.4
- Version 0.4
