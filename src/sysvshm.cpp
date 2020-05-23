/* Copyright (C) 2017-2018 J.F.Dockes
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
 *   51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
 */
    
#include "sysvshm.h"

#include <stdio.h>
#include <errno.h>
#include <unistd.h>
#include <sys/types.h>
#include <pthread.h>

#ifdef MDU_INCLUDE_LOG
#include MDU_INCLUDE_LOG
#else
#include "log.h"
#endif
#include "smallut.h"

using namespace std;

class ShmSeg::Internal {
    friend class LockableShmSeg;
public:
    int   shmid{-1};
    key_t key{IPC_PRIVATE};
    void *seg{nullptr};
    size_t  bytes{0};
    // Delete seg or leave it behind. 
    bool removeondelete{true};
    bool ok{false};
    bool mycreation{false};
    int lasterrno;
};

void ShmSeg::setremove(bool onoff)
{
    m->removeondelete = onoff;
}

void *ShmSeg::getseg()
{
    return m->seg;
}

size_t ShmSeg::getsize()
{
    return m->bytes;
}

bool ShmSeg::ok()
{
    return m->ok;
}
int ShmSeg::geterrno()
{
    return m->lasterrno;
}

ShmSeg::ShmSeg(key_t ky, size_t size, bool create, int perms)
    : m(new Internal)
{
    // SHMDEB "ShmSeg::ShmSeg: ky %d size %d\n", ky, size ENDLOG;

    if (ky == 0 || ky == IPC_PRIVATE) {
        m->key = IPC_PRIVATE;
        m->removeondelete = true;
    } else {
        m->key = ky;
        m->removeondelete = false;
    }
    int flags = 0;
    if (create) {
        flags = IPC_CREAT|IPC_EXCL;
    } else {
        perms = 0;
    }
    m->lasterrno = 0;
    if ((m->shmid = shmget(m->key, size, flags|perms)) >= 0) {
        if (create) {
            m->mycreation = true;
        }
    } else {
        m->lasterrno = errno;
        if (errno != EEXIST) {
            // Don't log a possibly trivial error, let the caller do it if
            // needed.
            // LOGSYSERR("ShmSeg::ShmSeg", "shmget", size);
            return;
        }
        // If the segment already existed, let's attach it
        m->lasterrno = 0;
        if ((m->shmid = shmget(m->key, size, 0)) < 0) {
            m->lasterrno = errno;
            LOGSYSERR("ShmSeg::ShmSeg", "shmget", size);
            return;
        }
    }
    m->bytes = size;
    // Attach it
    m->lasterrno = 0;
    if ((m->seg = shmat(m->shmid, 0, 0)) == (void *)-1) {
        m->lasterrno = errno;
        LOGSYSERR("ShmSeg::ShmSeg", "shmat", m->shmid);
        shmctl(m->shmid, IPC_RMID, 0);
        return;
    }
    m->ok = true;
}

ShmSeg::ShmSeg(const char*pathname, int proj_id, size_t size, bool create,
               int perms)
    : ShmSeg(ftok(pathname, proj_id), size, create, perms)
{
}

ShmSeg::~ShmSeg()
{
    if (m->seg && (shmdt(m->seg) < 0)) {
        LOGSYSERR("ShmSeg::~ShmSeg", "shmdt", "");
    }
    if (m->shmid != -1 && m->removeondelete) {
        LOGDEB0("ShmSeg::~ShmSeg: removing seg\n");
        if (shmctl(m->shmid, IPC_RMID, 0) < 0) {
            LOGSYSERR("ShmSeg::~ShmSeg", "shmctl RMID", m->shmid);
        }
    }
    // just in case
    m->seg = nullptr;
    m->bytes = 0;
    m->shmid = -1;
    m->ok = false;
}

#define LOCKAREASIZE (((sizeof(pthread_mutex_t)+7)/8)*8)

LockableShmSeg::LockableShmSeg(key_t ky, size_t size, bool create, int perms)
    : ShmSeg(ky, size+LOCKAREASIZE, create, perms)
{
    if (m && m->mycreation && m->seg) {
        memset(m->seg, 0, LOCKAREASIZE);
        int err{0};
        pthread_mutexattr_t attr;
        pthread_mutex_t *mutex = (pthread_mutex_t*)m->seg;
        err = pthread_mutexattr_init(&attr);if (err) goto done;
        err = pthread_mutexattr_setpshared(&attr, PTHREAD_PROCESS_SHARED); 
        if (err) goto done;
#ifndef __APPLE__
        err = pthread_mutexattr_setrobust(&attr, PTHREAD_MUTEX_ROBUST);
        if (err) goto done;
#endif
        err = pthread_mutex_init(mutex, &attr);
        pthread_mutexattr_destroy(&attr);
    done:
        if (err) {
            LOGERR("LockableShmSeg: pthread mutex init failed errno " << errno
                   << " return value " << err << endl);
            m->ok = false;
        }
    }
}

LockableShmSeg::LockableShmSeg(const char*pathname, int proj_id, size_t size,
                               bool create, int perms)
    : LockableShmSeg(ftok(pathname, proj_id), size, create, perms)
{
}

LockableShmSeg::~LockableShmSeg()
{
    if (nullptr == m || !m->ok) {
        return;
    }
    if (m->removeondelete) {
        pthread_mutex_t *mutex = (pthread_mutex_t*)m->seg;
        pthread_mutex_destroy(mutex);
    }
}

void *LockableShmSeg::getseg()
{
    return ShmSeg::getseg();
}

LockableShmSeg::Accessor::Accessor(LockableShmSeg& _lss)
    : lss(_lss)
{
    if (!lss.ok())
        return;
    void *seg = lss.getseg();
    pthread_mutex_t *mutex = (pthread_mutex_t*)seg;
    int err = pthread_mutex_lock(mutex); 
    if (err != 0) {
        LOGSYSERR("LockableShmSeg::Accessor", "pthread_mutex_lock", "");
    }
}

LockableShmSeg::Accessor::~Accessor()
{
    if (!lss.ok())
        return;
    void *seg = lss.getseg();
    pthread_mutex_t *mutex = (pthread_mutex_t*)seg;
    int err = pthread_mutex_unlock(mutex);
    if (err != 0) {
        LOGSYSERR("LockableShmSeg::Accessor", "pthread_mutex_unlock", "");
    }
}

void *LockableShmSeg::Accessor::getseg()
{
    if (!lss.ok())
        return nullptr;
    char *seg = (char*)(lss.getseg());
    return seg + LOCKAREASIZE;
}
