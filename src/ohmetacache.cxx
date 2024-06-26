/* Copyright (C) 2014-2020 J.F.Dockes
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU Lesser General Public License as published by
 * the Free Software Foundation; either version 2.1 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public License
 * along with this program; if not, write to the
 * Free Software Foundation, Inc.,
 * 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
 */

#include "ohmetacache.hxx"

#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

#include <iostream>
#include <utility>

#include "libupnpp/log.h"
#include "workqueue.h"
#include "smallut.h"

using namespace std;

static unsigned int slptimesecs;
void dmcacheSetOpts(unsigned int slpsecs)
{
    slptimesecs = slpsecs;
}

class SaveCacheTask {
public:
    SaveCacheTask(const string& fn, const mcache_type& cache)
        : m_fn(fn), m_cache(cache)
        {}

    string m_fn;
    mcache_type m_cache;
};
static WorkQueue<SaveCacheTask*> saveQueue("SaveQueue");

void freeSaveCacheTask(SaveCacheTask*& t)
{
    delete t;
}

// Encode uris and values so that they can be decoded (escape %, =, and eol)
static string encode(const string& in)
{
    string out;
    const char *cp = in.c_str();
    for (string::size_type i = 0; i < in.size(); i++) {
        unsigned int c;
        const char *h = "0123456789ABCDEF";
        c = cp[i];
        if (c == '%' || c == '=' || c == '\n' || c == '\r') {
            out += '%';
            out += h[(c >> 4) & 0xf];
            out += h[c & 0xf];
        } else {
            out += char(c);
        }
    }
    return out;
}

bool dmcacheSave(const string& fn, const mcache_type& cache)
{
    SaveCacheTask *tsk = new SaveCacheTask(fn, cache);
    // Use the flush option to put() so that only the latest version stays on the queue, possibly
    // saving writes.
    if (!saveQueue.put(tsk, true)) {
        LOGERR("dmcacheSave: can't queue save task\n");
        return false;
    }
    return true;
}

static void *dmcacheSaveWorker(void *)
{
    for (;;) {
        SaveCacheTask *tsk = 0;
        size_t qsz;
        if (!saveQueue.take(&tsk, &qsz)) {
            LOGERR("dmcacheSaveWorker: can't get task from queue" << "\n");
            saveQueue.workerExit();
            return (void*)1;
        }
        LOGDEB("dmcacheSave: got save task: " << tsk->m_cache.size() << 
               " entries to " << tsk->m_fn << "\n");

        string tfn = tsk->m_fn + "-";
        ofstream output(tfn, ios::out | ios::trunc);
        if (!output.is_open()) {
            LOGERR("dmcacheSave: could not open " << tfn << " for writing" << "\n");
            delete tsk;
            continue;
        }

        for (const auto& [key, value] : tsk->m_cache) {
            output << encode(key) << '=' << encode(value) << '\n';
            if (!output.good()) {
                LOGERR("dmcacheSave: write error while saving to " << tfn << "\n");
                break;
            }
        }
        output.flush();
        if (!output.good()) {
            LOGERR("dmcacheSave: flush error while saving to " << tfn << "\n");
        }
        if (rename(tfn.c_str(), tsk->m_fn.c_str()) != 0) {
            LOGSYSERR("dmcacheSave", "rename", tfn + ", " + tsk->m_fn);
        }

        delete tsk;
        if (slptimesecs) {
            LOGDEB1("dmcacheSave: sleeping " << slptimesecs << "\n");
            sleep(slptimesecs);
        }
    }
}

// Max size of metadata element ??
#define LL 20*1024

bool dmcacheRestore(const string& fn, mcache_type& cache)
{
    // Restore is called once at startup, so seize the opportunity to start the save thread
    saveQueue.setTaskFreeFunc(freeSaveCacheTask);
    if (!saveQueue.start(1, dmcacheSaveWorker, 0)) {
        LOGERR("dmcacheRestore: could not start save thread" << "\n");
        return false;
    }

    ifstream input;
    input.open(fn, ios::in);
    if (!input.is_open()) {
        LOGERR("dmcacheRestore: could not open " << fn << "\n");
        return false;
    }

    char cline[LL];
    for (;;) {
        input.getline(cline, LL-1, '\n');
        if (input.eof())
            break;
        if (!input.good()) {
            LOGERR("dmcacheRestore: read error on " << fn << "\n");
            return false;
        }
        char *cp = strchr(cline, '=');
        if (cp == 0) {
            LOGERR("dmcacheRestore: no = in line !" << "\n");
            return false;
        }
        *cp = 0;
        cache[pc_decode(cline)] = pc_decode(cp+1);
    }
    return true;
}
