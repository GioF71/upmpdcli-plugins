/*   Copyright (C) 2016 J.F.Dockes
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
#ifndef _BUFFERXCHANGE_H_INCLUDED_
#define _BUFFERXCHANGE_H_INCLUDED_

#include <thread>
#include <string>
#include <queue>
#include <list>
#include <mutex>
#include <condition_variable>
#include <chrono>

#ifdef MDU_INCLUDE_LOG
#include MDU_INCLUDE_LOG
#else
#include "log.h"
#endif

/**
 * A BufferXChange is a synchronized 2 way meeting point for 2 threads
 * exchanging objects (or 1 thread sending objects to another).
 *
 * Example: HTTP proxy, one thread reads data buffers, the other one
 * serves them.
 * Once the objects are used by the consumer, they can be queued back
 * to avoid memory allocations, or just destroyed.
 *
 * T has to be a pointer type.
 * BufXChange will delete excess recycled objects, and any remaining on the 
 * queues at delete time.
 * Terminology: the client is upstream and puts buffers on the
 * queue for the worker downstream to take.
 */
template <class T> class BufXChange {
public:

    /** Create a BufXChange. 
     * @param name for message printing
     * @param hi number of tasks on queue before upstream blocks. Default 0
     *   meaning no limit.
     */
    BufXChange(const std::string& name, size_t hi = 0)
        : m_name(name), m_high(hi) {}

    ~BufXChange() {
        std::unique_lock<std::mutex> lock(m_mutex);
        while (m_queue.size()) {
            T t = m_queue.front();
            m_queue.pop_front();
            delete t;
        }
        while (m_rqueue.size()) {
            T t = m_rqueue.front();
            m_rqueue.pop();
            delete t;
        }
    }
    void set_take_timeout(std::chrono::milliseconds millis) {
        m_take_timeout = millis;
    }
    void set_put_timeout(std::chrono::milliseconds millis) {
        m_put_timeout = millis;
    }
    void set_timeout(std::chrono::milliseconds millis) {
        m_put_timeout = m_take_timeout = millis;
    }

    /** Add item to work queue, called from client.
     *
     * Sleeps if there are already too many.
     */
    bool put(T t, bool flushprevious = false) {
        std::unique_lock<std::mutex> lock(m_mutex);

        while (ok() && m_high > 0 && m_queue.size() >= m_high) {
            m_clients_waiting++;
            if (m_put_timeout == std::chrono::milliseconds::zero()) {
                m_ccond.wait(lock);
            } else {
                if (m_ccond.wait_for(lock, m_put_timeout) == std::cv_status::timeout) {
                    return false;
                }
            }
            m_clients_waiting--;
        }
        if (!ok()) {
            return false;
        }
        if (flushprevious) {
            while (!m_queue.empty()) {
                T t = m_queue.front();
                m_queue.pop_front();
                delete t;
            }
        }

        m_queue.push_back(t);
        if (m_workers_waiting > 0) {
            // Just wake one worker, there is only one new task.
            m_wcond.notify_one();
        }

        return true;
    }

    // Called from worker to put a (probably partially processed)
    // buffer at the front of the queue.
    bool untake(T t) {
        std::unique_lock<std::mutex> lock(m_mutex);
        if (!ok()) {
            return false;
        }
        m_queue.push_front(t);
        return true;
    }
    
    // Take back buffer. This does not wait, it is assumed that the
    // client will allocate another object if none are found on the
    // back queue
    bool take_recycled(T* tp) {
        std::unique_lock<std::mutex> lock(m_mutex);
        if (!ok()) {
            return false;
        }
        if (m_rqueue.empty()) {
            *tp = nullptr;
            return false;
        } else {
            *tp = m_rqueue.front();
            m_rqueue.pop();
            return true;
        }
    }

    /** Wait until the queue is inactive. Called from client. */
    bool waitIdle() {
        std::unique_lock<std::mutex> lock(m_mutex);
        if (!ok()) {
            // This may happen if setTerminate was called by the
            // worker before we're awaken
            LOGDEB("BufXChange::waitIdle:"  << m_name << ": not ok\n");
            return false;
        }

        // We're done when the queue is empty. Unlike workqueue, we
        // don't manage the clients, so we can't check that they are
        // idle.
        while (ok() && (m_queue.size() > 0)) {
            m_clients_waiting++;
            if (m_put_timeout == std::chrono::milliseconds::zero()) {
                m_ccond.wait(lock);
            } else {
                if (m_ccond.wait_for(lock, m_put_timeout) == std::cv_status::timeout) {
                    return false;
                }
            }
            m_clients_waiting--;
        }
        return ok();
    }

    /** Tell the workers we're done here.
     *
     * Does not bother about tasks possibly remaining on the queue, so
     * should be called after waitIdle() for an orderly shutdown.
     */
    void setTerminate() {
        std::unique_lock<std::mutex> lock(m_mutex);
        m_ok = false;
        m_ccond.notify_all();
        m_wcond.notify_all();
    }

    /** Take task from queue. Called from worker.
     *
     * Sleeps if there are not enough. Signal if we go to sleep on empty
     * queue: client may be waiting for our going idle.
     */
    bool take(T* tp, size_t *szp = 0) {
        std::unique_lock<std::mutex> lock(m_mutex);
        while (ok() && m_queue.size() < 1) {
            if (m_queue.empty()) {
                m_ccond.notify_all();
            }
            m_workers_waiting++;
            if (m_take_timeout == std::chrono::milliseconds::zero()) {
                m_wcond.wait(lock);
            } else {
                if (m_wcond.wait_for(lock, m_take_timeout) == std::cv_status::timeout) {
                    return false;
                }
            }
            m_workers_waiting--;
        }

        if (!ok()) {
            return false;
        }

        *tp = m_queue.front();
        if (szp) {
            *szp = m_queue.size();
        }
        m_queue.pop_front();
        if (m_clients_waiting > 0) {
            // No reason to wake up more than one client thread
            m_ccond.notify_one();
        }
        return true;
    }
    bool recycle(T t) {
        std::unique_lock<std::mutex> lock(m_mutex);
        return recycle_nolock(t);
    }
    bool recycle_nolock(T t) {
        while (m_rqueue.size() >= m_maxrecycled) {
            T tt = m_rqueue.front();
            m_rqueue.pop();
            delete tt;
        }
        m_rqueue.push(t);
        return true;
    }

    bool waitminsz(size_t sz) {
        std::unique_lock<std::mutex> lock(m_mutex);
        if (!ok()) {
            return false;
        }

        while (ok() && m_queue.size() < sz) {
            if (m_queue.empty()) {
                m_ccond.notify_all();
            }
            m_workers_waiting++;
            if (m_take_timeout == std::chrono::milliseconds::zero()) {
                m_wcond.wait(lock);
            } else {
                if (m_wcond.wait_for(lock, m_take_timeout) == std::cv_status::timeout) {
                    return false;
                }
            }
            m_workers_waiting--;
            if (!ok()) {
                return false;
            }
        }
        return true;
    }

    /** Advertise exit and abort queue. Called from worker
     *
     * This would happen after an unrecoverable error, or when
     * the queue is terminated by the client.
     */
    void workerExit() {
        LOGDEB("workerExit:" << m_name << "\n");
        setTerminate();
    }

    size_t qsize() {
        std::unique_lock<std::mutex> lock(m_mutex);
        return m_queue.size();
    }

    void visitq(std::function<void(const T&)>v) {
        std::unique_lock<std::mutex> lock(m_mutex);
        for (const auto& it : m_queue) {
            v(it);
        }
    }

    void reset() {
        // Reset to start state.
        std::unique_lock<std::mutex> lock(m_mutex);
        while (m_queue.size()) {
            T t = m_queue.front();
            m_queue.pop_front();
            recycle_nolock(t);
        }
        m_clients_waiting = m_workers_waiting = 0;
        m_ok = true;
        m_ccond.notify_all();
        m_wcond.notify_all();
    }

    const std::string& getname() const {return m_name;}
private:
    bool ok() {
        return m_ok;
    }

    // Configuration
    std::string m_name;
    size_t m_high{0};
    size_t m_maxrecycled{4};

    // Status
    bool m_ok{true};

    // Client/Worker threads currently waiting for a job
    unsigned int m_clients_waiting{0};
    unsigned int m_workers_waiting{0};

    // Jobs input queue.
    std::deque<T> m_queue;

    // Queue for recycling the objects
    std::queue<T> m_rqueue;
    
    // Synchronization
    std::condition_variable m_ccond;
    std::condition_variable m_wcond;
    std::mutex m_mutex;
    std::chrono::milliseconds m_take_timeout{std::chrono::milliseconds(0)};
    std::chrono::milliseconds m_put_timeout{std::chrono::milliseconds(0)};
};

#endif /* _BUFFERXCHANGE_H_INCLUDED_ */
