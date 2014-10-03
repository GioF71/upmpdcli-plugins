/* Copyright (C) 2013 J.F.Dockes
 *   This program is free software; you can redistribute it and/or modify
 *   it under the terms of the GNU General Public License as published by
 *   the Free Software Foundation; either version 2 of the License, or
 *   (at your option) any later version.
 *
 *   This program is distributed in the hope that it will be useful,
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *   GNU General Public License for more details.
 *
 *   You should have received a copy of the GNU General Public License
 *   along with this program; if not, write to the
 *   Free Software Foundation, Inc.,
 *   59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
 */
#ifndef _UPNPPDISC_H_X_INCLUDED_
#define _UPNPPDISC_H_X_INCLUDED_

#include <time.h>                       // for time_t

#include <functional>                   // for function
#include <string>                       // for string

namespace UPnPClient { class UPnPDeviceDesc; }
namespace UPnPClient { class UPnPServiceDesc; }

namespace UPnPClient {

/**
 * Manage UPnP discovery and maintain a directory of active devices. Singleton.
 *
 *
 * The service is initialize on the first call, starting
 * the message-handling thread, registering our message handlers, 
 * and initiating an asynchronous UPnP device search. 
 *
 * The search implies a timeout period (the specified interval
 * over which the servers will send replies at random points). Any
 * subsequent traverse() call will block until the timeout
 * is expired. Use getRemainingDelay() to know the current
 * remaining delay, and use it to do something else.
 *
 * We need a separate thread to process the messages coming up
 * from libupnp, because some of them will in turn trigger other
 * calls to libupnp, and this must not be done from the libupnp
 * thread context which reported the initial message.
 * So there are three threads in action:
 *  - the reporting thread from libupnp.
 *  - the discovery service processing thread, which also runs the callbacks.
 *  - the user thread (typically the main thread), which calls traverse.
 */
class UPnPDeviceDirectory {
public:
    /** Retrieve the singleton object for the discovery service,
     * and possibly start it up if this is the first call. This does not wait
     * significantly, a subsequent traverse() will wait until the
     * initial delay is consumed.
     */
    static UPnPDeviceDirectory *getTheDir(time_t search_window = 3);

    /** Clean up before exit. Do call this.*/
    static void terminate();

    typedef std::function<bool (const UPnPDeviceDesc&, 
                                const UPnPServiceDesc&)> Visitor;

    /** Traverse the directory and call Visitor for each device/service pair */
    bool traverse(Visitor);

    /** Remaining time until current search complete */
    time_t getRemainingDelay();

    /** Set a callback to be called when devices report their existence 
     *  The visitor will be called once per device, with an empty service.
     */
    static unsigned int addCallback(Visitor v);
    static void delCallback(unsigned int idx);

    /** Find device by friendlyName or UDN. Unlike traverse, this does
     * not necessarily wait for the initial timeout, it returns as
     * soon as a device with this name reports (or the timeout expires). 
     * Note that "friendly names" are not necessarily unique.
     */
    bool getDevByFName(const std::string& fname, UPnPDeviceDesc& ddesc);
    bool getDevByUDN(const std::string& udn, UPnPDeviceDesc& ddesc);

    /** My health */
    bool ok() {return m_ok;}
    /** My diagnostic if health is bad */
    const std::string getReason() {return m_reason;}

private:
    UPnPDeviceDirectory(time_t search_window);
    UPnPDeviceDirectory(const UPnPDeviceDirectory &) = delete;
    UPnPDeviceDirectory& operator=(const UPnPDeviceDirectory &) = delete;

    // Start UPnP search and record start of timeout
    bool search();
    // Look at the current pool and remove expired entries
    void expireDevices();

    // This is called by the thread which processes the device events
    // when a new device appears. It wakes up any thread waiting for a
    // device.
    bool deviceFound(const UPnPDeviceDesc&, const UPnPServiceDesc&);

    // Lookup a device in the pool. If not found and a search is active, 
    // use a cond_wait to wait for device events (awaken by deviceFound).
    bool getDevBySelector(bool cmp(const UPnPDeviceDesc&, const std::string&), 
                          const std::string& value, UPnPDeviceDesc& ddesc);

    static void *discoExplorer(void *);

    bool m_ok;
    std::string m_reason;
    int m_searchTimeout;
    time_t m_lastSearch;
};

} // namespace UPnPClient

#endif /* _UPNPPDISC_H_X_INCLUDED_ */
