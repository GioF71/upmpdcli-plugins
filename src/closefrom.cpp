/* Copyright (C) 2009 J.F.Dockes
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
 * 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
 */
/*
 * Close all file descriptors above a given value.
 *
 * A Unix execXX() call used to execute another program does not close open 
 * file descriptors by default.
 *
 * The only descriptors closed are those on which the FD_CLOEXEC flag was
 * set. FD_CLOEXEC is not easily usable on files opened by external
 * libraries.
 *
 * There are many reasons for closing file descriptors before
 * an exec (security, pipe control, the possibility that a bug will
 *  trigger an unwanted write, etc.)
 *
 * A process has currently no POSIX way to determine the set of open file 
 * descriptors or at least the highest value. Closing all files (except a few),
 * thus implies performing a close() system call on each entry up to the 
 * maximum, which can be both relatively difficult to determine, and quite
 * high (ie: several thousands), incurring a non-negligible cost.
 *
 * A number of systems have non-portable support for mitigating or solving
 * this problem. 
 * 
 * This module supplies a portable interface to this functionality.
 *
 * The initial data on system interfaces was obtained from:
 * http://stackoverflow.com/questions/899038/\
 *   getting-the-highest-allocated-file-descriptor
 *
 * System interfaces:
 *  FreeBSD/DragonFly:
 *   - Have a closefrom() system call as of release 7.x around Sep 2009
 *   - Have a /dev/fd, directory which shows the current process' open
 *     descriptors. Only descriptors 0, 1, 2 are shown except if
 *     fdescfs is mounted which it is not by default
 *
 *  Solaris:
 *   - Solaris 10+ has closefrom, and can specify closefrom to posix_spawn()
 *
 *  Linux:
 *   - Has nothing. The method we initially used (listing /dev/fd) could
 *     deadlock in multithread fork/exec context. We now use a close()
 *     loop but there is no completely reliable way to determine the high limit.
 *       The glibc maintainer (drepper) thinks that closefrom() is a bad idea
 *       *especially* because it is implemented on *BSD and Solaris. Go figure... 
 *     https://sourceware.org/bugzilla/show_bug.cgi?id=10353
 *     Bug updated 2021/07/08, apparently fixed in glibc 2.35 (not yet available 2022-01, fed35 and
 *     tumble are at 2.34).
 *
 * Interface:
 *
 * int libclf_closefrom(fd)
 *  @param fd All open file descriptors with equal or higher numeric 
 *       values will be closed. fd needs not be a valid descriptor.
 *  @return 0 for success, -1 for error.
 */
#include "closefrom.h"

#include <fcntl.h>

#ifndef _WIN32
#include <unistd.h>
#include <sys/param.h>
#include <sys/time.h>
#include <sys/resource.h>
#else
#include <io.h>
#define close _close
#endif

// #define DEBUG_CLOSEFROM
#ifdef DEBUG_CLOSEFROM
#include <iostream>
#include <stdio.h>
#define DPRINT(X) X
#else
#define DPRINT(X)
#endif

/* Note: sudo has a closefrom implementation, needs a lot of autoconfig, but
 * we could use it instead. It's quite close to this though */

/*************************************************************************/

/* closefrom() exists on Solaris, netbsd and openbsd, but someone will
 * have to provide me the appropriate macro to test */
#if ((defined(__FreeBSD__) && __FreeBSD_version >= 702104)) ||  defined(__DragonFly__)
/* Use closefrom() system call */
int libclf_closefrom(int fd0)
{
    DPRINT((std::cerr <<  "libclf_closefrom: using closefrom(2)\n"));
    closefrom(fd0);
    return 0;
}

/*************************************************************************/
#elif defined(F_CLOSEM)

/* Use fcntl(fd, F_CLOSEM) */

int libclf_closefrom(int fd0)
{
    DPRINT((std::cerr << "libclf_closefrom: using fcntl(F_CLOSEM)\n"));
    // We need a valid descriptor for this to work. Try to dup stdin, else go wild
    if (fcntl(0, F_GETFL) != -1) {
        if (fd0 != 0)
            dup2(0, fd0);
    } else {
        int fd = open("/etc/group", 0); // yes i am a unix man
        if (fd >= 0 && fd != fd0) {
            dup2(fd, fd0);
            close(fd);
        }
    }
    return fcntl(fd0, F_CLOSEM, 0);
}

/*************************************************************************/
#elif 0 && (defined(linux) || defined(__linux))

/* We don't do this on linux anymore because opendir() may call
   malloc which is unsafe in the [fork-exec] interval for a
   multithreaded program. Linux does not have a good solution for
   implementing closefrom as far as I know */

/* Use /proc/self/fd directory */
#include <sys/types.h>
#include <dirent.h>

int libclf_closefrom(int fd0)
{
    DIR *dirp;
    struct dirent *ent;

    DPRINT((std::cerr << "libclf_closefrom: using /proc\n"));
    dirp = opendir("/proc/self/fd");
    if (dirp == 0)
        return -1;

    while ((ent = readdir(dirp)) != 0) {
        int fd;
        if (!strcmp(ent->d_name, ".") || !strcmp(ent->d_name, "..")) 
            continue;

        if (sscanf(ent->d_name, "%d", &fd) == 1 && fd >= fd0 && 
            fd != dirfd(dirp)) {
            close(fd);
        }
    }
    closedir(dirp);
    return 0;
}

/*************************************************************************/

#else 

/* System has no native support for this functionality.
 *
 * Close all descriptors up to compiled/configured maximum.  The caller will usually have an idea of
 * a reasonable maximum, else we retrieve a value from the system.
 *
 * Note that there is actually no real guarantee that no open descriptor higher than the reported
 * limit can exist, as noted by the Solaris man page for closefrom()
 */

static int closefrom_maxfd = -1;

void libclf_setmaxfd(int max)
{
    closefrom_maxfd = max;
}

#include <limits.h>

#ifndef OPEN_MAX
#define OPEN_MAX 1024
#endif

int libclf_closefrom(int fd0)
{
    DPRINT((std::cerr << "libclf_closefrom: no system support, winging it...\n"));
    int i, maxfd = closefrom_maxfd;

    if (maxfd < 0) {
        maxfd = libclf_maxfd();
    }
    if (maxfd < 0)
        maxfd = OPEN_MAX;

    for (i = fd0; i < maxfd; i++) {
        (void)close(i);
    }
    return 0;
}
#endif

// Note that this will not work if the limit was lowered after a higher fd was opened. But we don't
// call setrlimit(nofile) inside recoll code, so we should be ok. It seems that
// sysconf(_SC_OPEN_MAX) usually reports the soft limit, so it's redundant, but it could be useful
// in case getrlimit() is not implemented (unlikely as they're both POSIX.1-2001?)
//
// On some systems / environments, getrlimit() returns an unworkably high value. For example on an
// Arch Linux Docker environment, we get 1E9, which results in a seemingly looping process. Have to
// put a limit somewhere, so it's 8192... You can still use libclf_setmaxfd() before the first
// closefrom call to use a higher value.
int libclf_maxfd(int)
{
#ifdef _WIN32
    // https://docs.microsoft.com/en-us/cpp/c-runtime-library/reference/setmaxstdio?view=msvc-170
    return 8192;
#else
    struct rlimit lim;
    getrlimit(RLIMIT_NOFILE, &lim);
    auto max = lim.rlim_cur;
    DPRINT((std::cerr << "Libclf_maxfd: got " << max << "\n"));
    if (max > 8192)
        max = 8192;
    return int(max);
#endif
}
