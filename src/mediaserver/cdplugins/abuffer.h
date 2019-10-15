#ifndef _ABUFFER_H_INCLUDED_
#define _ABUFFER_H_INCLUDED_

#include <stdlib.h>
#include <string.h>

/// Data buffer used on the queue.
///
/// The implementation details are public because this may be used
/// externally when inserting an intermediary queue to process the
/// data.
///
/// This is a very raw structure and it is never shared. Either
/// the data producer or consumer has exclusive use until the
/// buffer is passed on.
///
/// The producer possibly allocates a buffer (or retrieves a
/// recycled one from somewhere), copies data to it, setting the
/// 'bytes' value, then passes it on.
///
/// The consumer gets the buffer from a queue, then does what it
/// needs with the data, possibly in several chunks, using the
/// curoffs field to keep track. curoffs is private to the
/// consumer (nornally set to zero when getting the buffer).
struct ABuffer {
    /// Initialize by allocating a memory buffer
    ABuffer(size_t bufsize)
        : buf((char*)malloc(bufsize)), allocbytes(bufsize), bytes(0) {
    }

    /// Initialize by taking ownership of an existing buffer
    /// @param buf is is a malloced buffer, and we take ownership. The
    ///   caller MUST NOT free it.
    /// @param bufsize buffer allocated size in bytes.
    /// @param bytes data contents size. 
    ABuffer(char *buf, size_t bufsize, size_t bytes)
        : buf(buf), allocbytes(bufsize), bytes(bytes) {
    }

    ~ABuffer() {
        if (buf)
            free(buf);
    }

    bool reserve(size_t minbytes) {
        if (allocbytes >= minbytes) {
            return true;
        }
        if ((buf = (char *)realloc(buf, minbytes)) == nullptr) {
            return false;
        }
        allocbytes = minbytes;
        return true;
    }

    // Append data. This should not be used casually as we don't take
    // much care to make the reallocation efficient. Typically, this
    // is only used to buffer a bit of data at the beginning of the
    // stream for header forensics.
    bool append(const char *data, int cnt) {
        if (!reserve(2*(cnt+bytes))) {
            return false;
        }
        memcpy(buf + bytes, data, cnt);
        bytes += cnt;
        return true;
    }
    
    /// Create a full copy
    ABuffer *dup() {
        ABuffer *n = new ABuffer(bytes);
        if (nullptr == n || nullptr == n->buf) {
            return nullptr;
        }
        memcpy(n->buf, buf, bytes);
        n->bytes = bytes;
        return n;
    }
    
    char *buf;
    unsigned int allocbytes; // buffer size
    unsigned int bytes; // Useful bytes, set by producer.
    unsigned int curoffs{0}; // Current offset in data, used by the consumer
};

#endif /* _ABUFFER_H_INCLUDED_ */
