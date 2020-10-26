/* Copyright (C) 2015 J.F.Dockes
 *   This program is free software; you can redistribute it and/or modify
 *   it under the terms of the GNU Lesser General Public License as published by
 *   the Free Software Foundation; either version 2.1 of the License, or
 *   (at your option) any later version.
 *
 *   This program is distributed in the hope that it will be useful,
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *   GNU Lesser General Public License for more details.
 *
 *   You should have received a copy of the GNU Lesser General Public License
 *   along with this program; if not, write to the
 *   Free Software Foundation, Inc.,
 *   59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
 */
#ifndef _OHSNDRCV_H_X_INCLUDED_
#define _OHSNDRCV_H_X_INCLUDED_

/** 
 * This implements a special mode of operation for upmpdcli where a
 * Songcast Sender is created (playing the current playlist) and we
 * switch to Receiver mode. Other Receivers may then be connected for
 * synchronized multiroom playing.
 *
 * On entering the mode, the following operations are performed.
 *  - Tell MPD to stop playing.
 *  - Start another MPD process which one FIFO output.
 *  - Start a Songcast Sender (uxsender) process, playing from the
 *    FIFO. 
 *  - (The two above steps are implement by an external script)
 *  - Copy the playlist to the new MPD, and play approximately from
 *    where we stopped.
 *  - Switch to receiver mode and play from the just created Sender.
 * At this point other Receivers may be connected.
 *
 * The mode is entered by selecting the SenderReceiver source in
 * OHProduct::setSource. This is a slight abuse of the function, but
 * allows controlling this from any CP implementing setSource.
 */

#include <string>

class UpMpd;
class UpMpdOpenHome;

class SenderReceiver {
public:
    SenderReceiver(UpMpd *dev, UpMpdOpenHome *udev,
                   const std::string& senderstarterpath, int mpdport);
    ~SenderReceiver();

    // script can be empty when using an internal source (radio or
    // playlist) or be a path to an external script for an extern
    // analog source
    bool start(const std::string& script, int seekms = 0);
    bool stop();

    class Internal;
private:
    Internal *m;
};

#endif /* _OHSNDRCV_H_X_INCLUDED_ */
