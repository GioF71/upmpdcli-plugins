/* Copyright (C) 2004 J.F.Dockes
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

#ifndef TEST_PATHUT
#ifdef BUILDING_RECOLL
#include "autoconfig.h"
#else
#include "config.h"
#endif

#include <stdio.h>
#include <math.h>
#include <errno.h>

#ifdef _WIN32
#include "dirent.h"
#include "safefcntl.h"
#include "safeunistd.h"
#include "safewindows.h"
#include "safesysstat.h"

#else // Not windows ->
#include <fcntl.h>
#include <unistd.h>
#include <sys/param.h>
#include <pwd.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <dirent.h>
#include <sys/statvfs.h>
#include <sys/types.h>

#endif

#include <cstdlib>
#include <cstring>
#include <iostream>
#include <sstream>
#include <stack>
#include <set>
#include <vector>

#include "pathut.h"
#include "smallut.h"

using namespace std;

#ifdef _WIN32
/// Convert \ separators to /
void path_slashize(string& s)
{
    for (string::size_type i = 0; i < s.size(); i++) {
        if (s[i] == '\\') {
            s[i] = '/';
        }
    }
}
void path_backslashize(string& s)
{
    for (string::size_type i = 0; i < s.size(); i++) {
        if (s[i] == '/') {
            s[i] = '\\';
        }
    }
}
static bool path_strlookslikedrive(const string& s)
{
    return s.size() == 2 && isalpha(s[0]) && s[1] == ':';
}

static bool path_hasdrive(const string& s)
{
    if (s.size() >= 2 && isalpha(s[0]) && s[1] == ':') {
        return true;
    }
    return false;
}
static bool path_isdriveabs(const string& s)
{
    if (s.size() >= 3 && isalpha(s[0]) && s[1] == ':' && s[2] == '/') {
        return true;
    }
    return false;
}
#endif

bool fsocc(const string& path, int *pc, long long *avmbs)
{
    static const int FSOCC_MB = 1024 * 1024;
#ifdef _WIN32
    ULARGE_INTEGER freebytesavail;
    ULARGE_INTEGER totalbytes;
    if (!GetDiskFreeSpaceEx(path.c_str(), &freebytesavail,
                            &totalbytes, NULL)) {
        return false;
    }
    if (pc) {
        *pc = int((100 * freebytesavail.QuadPart) / totalbytes.QuadPart);
    }
    if (avmbs) {
        *avmbs = int(totalbytes.QuadPart / FSOCC_MB);
    }
    return true;
#else // not windows ->

    struct statvfs buf;
    if (statvfs(path.c_str(), &buf) != 0) {
        return false;
    }

    if (pc) {
        double fsocc_used = double(buf.f_blocks - buf.f_bfree);
        double fsocc_totavail = fsocc_used + double(buf.f_bavail);
        double fpc = 100.0;
        if (fsocc_totavail > 0) {
            fpc = 100.0 * fsocc_used / fsocc_totavail;
        }
        *pc = int(fpc);
    }
    if (avmbs) {
        *avmbs = 0;
        if (buf.f_bsize > 0) {
            int ratio = buf.f_frsize > FSOCC_MB ? buf.f_frsize / FSOCC_MB :
                        FSOCC_MB / buf.f_frsize;

            *avmbs = buf.f_frsize > FSOCC_MB ?
                     ((long long)buf.f_bavail) * ratio :
                     ((long long)buf.f_bavail) / ratio;
        }
    }
    return true;
#endif
}


string path_PATHsep()
{
    static const string w(";");
    static const string u(":");
#ifdef _WIN32
    return w;
#else
    return u;
#endif
}

void path_catslash(string& s)
{
#ifdef _WIN32
    path_slashize(s);
#endif
    if (s.empty() || s[s.length() - 1] != '/') {
        s += '/';
    }
}

string path_cat(const string& s1, const string& s2)
{
    string res = s1;
    path_catslash(res);
    res +=  s2;
    return res;
}

string path_getfather(const string& s)
{
    string father = s;
#ifdef _WIN32
    path_slashize(father);
#endif

    // ??
    if (father.empty()) {
        return "./";
    }

    if (path_isroot(father)) {
        return father;
    }

    if (father[father.length() - 1] == '/') {
        // Input ends with /. Strip it, root special case was tested above
        father.erase(father.length() - 1);
    }

    string::size_type slp = father.rfind('/');
    if (slp == string::npos) {
        return "./";
    }

    father.erase(slp);
    path_catslash(father);
    return father;
}

string path_getsimple(const string& s)
{
    string simple = s;
#ifdef _WIN32
    path_slashize(simple);
#endif

    if (simple.empty()) {
        return simple;
    }

    string::size_type slp = simple.rfind('/');
    if (slp == string::npos) {
        return simple;
    }

    simple.erase(0, slp + 1);
    return simple;
}

string path_basename(const string& s, const string& suff)
{
    string simple = path_getsimple(s);
    string::size_type pos = string::npos;
    if (suff.length() && simple.length() > suff.length()) {
        pos = simple.rfind(suff);
        if (pos != string::npos && pos + suff.length() == simple.length()) {
            return simple.substr(0, pos);
        }
    }
    return simple;
}

string path_suffix(const string& s)
{
    string::size_type dotp = s.rfind('.');
    if (dotp == string::npos) {
        return string();
    }
    return s.substr(dotp + 1);
}

string path_home()
{
#ifdef _WIN32
    string dir;
    const char *cp = getenv("USERPROFILE");
    if (cp != 0) {
        dir = cp;
    }
    if (dir.empty()) {
        cp = getenv("HOMEDRIVE");
        if (cp != 0) {
            const char *cp1 = getenv("HOMEPATH");
            if (cp1 != 0) {
                dir = string(cp) + string(cp1);
            }
        }
    }
    if (dir.empty()) {
        dir = "C:\\";
    }
    dir = path_canon(dir);
    path_catslash(dir);
    return dir;
#else
    uid_t uid = getuid();

    struct passwd *entry = getpwuid(uid);
    if (entry == 0) {
        const char *cp = getenv("HOME");
        if (cp) {
            return cp;
        } else {
            return "/";
        }
    }

    string homedir = entry->pw_dir;
    path_catslash(homedir);
    return homedir;
#endif
}

// The default place to store the default config and other stuff (e.g webqueue)
string path_homedata()
{
#ifdef _WIN32
    const char *cp = getenv("LOCALAPPDATA");
    string dir;
    if (cp != 0) {
        dir = path_canon(cp);
    }
    if (dir.empty()) {
        dir = path_cat(path_home(), "AppData/Local/");
    }
    return dir;
#else
    // We should use an xdg-conforming location, but, history...
    return path_home();
#endif
}

string path_tildexpand(const string& s)
{
    if (s.empty() || s[0] != '~') {
        return s;
    }
    string o = s;
#ifdef _WIN32
    path_slashize(o);
#endif

    if (s.length() == 1) {
        o.replace(0, 1, path_home());
    } else if (s[1] == '/') {
        o.replace(0, 2, path_home());
    } else {
        string::size_type pos = s.find('/');
        string::size_type l = (pos == string::npos) ? s.length() - 1 : pos - 1;
#ifdef _WIN32
        // Dont know what this means. Just replace with HOME
        o.replace(0, l + 1, path_home());
#else
        struct passwd *entry = getpwnam(s.substr(1, l).c_str());
        if (entry) {
            o.replace(0, l + 1, entry->pw_dir);
        }
#endif
    }
    return o;
}

bool path_isroot(const string& path)
{
    if (path.size() == 1 && path[0] == '/') {
        return true;
    }
#ifdef _WIN32
    if (path.size() == 3 && isalpha(path[0]) && path[1] == ':' &&
            (path[2] == '/' || path[2] == '\\')) {
        return true;
    }
#endif
    return false;
}

bool path_isabsolute(const string& path)
{
    if (!path.empty() && (path[0] == '/'
#ifdef _WIN32
                          || path_isdriveabs(path)
#endif
                         )) {
        return true;
    }
    return false;
}

string path_absolute(const string& is)
{
    if (is.length() == 0) {
        return is;
    }
    string s = is;
#ifdef _WIN32
        path_slashize(s);
#endif
    if (!path_isabsolute(s)) {
        char buf[MAXPATHLEN];
        if (!getcwd(buf, MAXPATHLEN)) {
            return string();
        }
        s = path_cat(string(buf), s);
#ifdef _WIN32
        path_slashize(s);
#endif
    }
    return s;
}

string path_canon(const string& is, const string* cwd)
{
    if (is.length() == 0) {
        return is;
    }
    string s = is;
#ifdef _WIN32
    path_slashize(s);
    // fix possible path from file: absolute url
    if (s.size() && s[0] == '/' && path_hasdrive(s.substr(1))) {
        s = s.substr(1);
    }
#endif

    if (!path_isabsolute(s)) {
        char buf[MAXPATHLEN];
        const char *cwdp = buf;
        if (cwd) {
            cwdp = cwd->c_str();
        } else {
            if (!getcwd(buf, MAXPATHLEN)) {
                return string();
            }
        }
        s = path_cat(string(cwdp), s);
    }
    vector<string> elems;
    stringToTokens(s, elems, "/");
    vector<string> cleaned;
    for (vector<string>::const_iterator it = elems.begin();
            it != elems.end(); it++) {
        if (*it == "..") {
            if (!cleaned.empty()) {
                cleaned.pop_back();
            }
        } else if (it->empty() || *it == ".") {
        } else {
            cleaned.push_back(*it);
        }
    }
    string ret;
    if (!cleaned.empty()) {
        for (vector<string>::const_iterator it = cleaned.begin();
                it != cleaned.end(); it++) {
            ret += "/";
#ifdef _WIN32
            if (it == cleaned.begin() && path_strlookslikedrive(*it)) {
                // Get rid of just added initial "/"
                ret.clear();
            }
#endif
            ret += *it;
        }
    } else {
        ret = "/";
    }

#ifdef _WIN32
    // Raw drive needs a final /
    if (path_strlookslikedrive(ret)) {
        path_catslash(ret);
    }
#endif

    return ret;
}

bool path_makepath(const string& ipath, int mode)
{
    string path = path_canon(ipath);
    vector<string> elems;
    stringToTokens(path, elems, "/");
    path = "/";
    for (vector<string>::const_iterator it = elems.begin();
            it != elems.end(); it++) {
#ifdef _WIN32
        if (it == elems.begin() && path_strlookslikedrive(*it)) {
            path = "";
        }
#endif
        path += *it;
        // Not using path_isdir() here, because this cant grok symlinks
        // If we hit an existing file, no worry, mkdir will just fail.
        if (access(path.c_str(), 0) != 0) {
            if (mkdir(path.c_str(), mode) != 0)  {
                return false;
            }
        }
        path += "/";
    }
    return true;
}

bool path_isdir(const string& path)
{
    struct stat st;
    if (lstat(path.c_str(), &st) < 0) {
        return false;
    }
    if (S_ISDIR(st.st_mode)) {
        return true;
    }
    return false;
}

long long path_filesize(const string& path)
{
    struct stat st;
    if (stat(path.c_str(), &st) < 0) {
        return -1;
    }
    return (long long)st.st_size;
}

int path_fileprops(const std::string path, struct stat *stp, bool follow)
{
    if (!stp) {
        return -1;
    }
    memset(stp, 0, sizeof(struct stat));
    struct stat mst;
    int ret = follow ? stat(path.c_str(), &mst) : lstat(path.c_str(), &mst);
    if (ret != 0) {
        return ret;
    }
    stp->st_size = mst.st_size;
    stp->st_mode = mst.st_mode;
    stp->st_mtime = mst.st_mtime;
#ifdef _WIN32
    stp->st_ctime = mst.st_mtime;
#else
    stp->st_ino = mst.st_ino;
    stp->st_dev = mst.st_dev;
    stp->st_ctime = mst.st_ctime;
#endif
    return 0;
}

bool path_exists(const string& path)
{
    return access(path.c_str(), 0) == 0;
}

// Allowed punctuation in the path part of an URI according to RFC2396
// -_.!~*'():@&=+$,
/*
21 !
    22 "
    23 #
24 $
    25 %
26 &
27 '
28 (
29 )
2A *
2B +
2C ,
2D -
2E .
2F /
30 0
...
39 9
3A :
    3B ;
    3C <
3D =
    3E >
    3F ?
40 @
41 A
...
5A Z
    5B [
    5C \
    5D ]
    5E ^
5F _
    60 `
61 a
...
7A z
    7B {
    7C |
    7D }
7E ~
    7F DEL
*/
string url_encode(const string& url, string::size_type offs)
{
    string out = url.substr(0, offs);
    const char *cp = url.c_str();
    for (string::size_type i = offs; i < url.size(); i++) {
        unsigned int c;
        const char *h = "0123456789ABCDEF";
        c = cp[i];
        if (c <= 0x20 ||
                c >= 0x7f ||
                c == '"' ||
                c == '#' ||
                c == '%' ||
                c == ';' ||
                c == '<' ||
                c == '>' ||
                c == '?' ||
                c == '[' ||
                c == '\\' ||
                c == ']' ||
                c == '^' ||
                c == '`' ||
                c == '{' ||
                c == '|' ||
                c == '}') {
            out += '%';
            out += h[(c >> 4) & 0xf];
            out += h[c & 0xf];
        } else {
            out += char(c);
        }
    }
    return out;
}

string url_gpath(const string& url)
{
    // Remove the access schema part (or whatever it's called)
    string::size_type colon = url.find_first_of(":");
    if (colon == string::npos || colon == url.size() - 1) {
        return url;
    }
    // If there are non-alphanum chars before the ':', then there
    // probably is no scheme. Whatever...
    for (string::size_type i = 0; i < colon; i++) {
        if (!isalnum(url.at(i))) {
            return url;
        }
    }

    // In addition we canonize the path to remove empty host parts
    // (for compatibility with older versions of recoll where file://
    // was hardcoded, but the local path was used for doc
    // identification.
    return path_canon(url.substr(colon + 1));
}

string url_parentfolder(const string& url)
{
    // In general, the parent is the directory above the full path
    string parenturl = path_getfather(url_gpath(url));
    // But if this is http, make sure to keep the host part. Recoll
    // only has file or http urls for now.
    bool isfileurl = urlisfileurl(url);
    if (!isfileurl && parenturl == "/") {
        parenturl = url_gpath(url);
    }
    return isfileurl ? string("file://") + parenturl :
           string("http://") + parenturl;
}


// Convert to file path if url is like file:
// Note: this only works with our internal pseudo-urls which are not
// encoded/escaped
string fileurltolocalpath(string url)
{
    if (url.find("file://") == 0) {
        url = url.substr(7, string::npos);
    } else {
        return string();
    }

#ifdef _WIN32
    // Absolute file urls are like: file:///c:/mydir/...
    // Get rid of the initial '/'
    if (url.size() >= 3 && url[0] == '/' && isalpha(url[1]) && url[2] == ':') {
        url = url.substr(1);
    }
#endif

    // Removing the fragment part. This is exclusively used when
    // executing a viewer for the recoll manual, and we only strip the
    // part after # if it is preceded by .html
    string::size_type pos;
    if ((pos = url.rfind(".html#")) != string::npos) {
        url.erase(pos + 5);
    } else if ((pos = url.rfind(".htm#")) != string::npos) {
        url.erase(pos + 4);
    }

    return url;
}

static const string cstr_fileu("file://");

string path_pathtofileurl(const string& path)
{
    // We're supposed to receive a canonic absolute path, but on windows we
    // may need to add a '/' in front of the drive spec
    string url(cstr_fileu);
    if (path.empty() || path[0] != '/') {
        url.push_back('/');
    }
    url += path;
    return url;
}

bool urlisfileurl(const string& url)
{
    return url.find("file://") == 0;
}

bool readdir(const string& dir, string& reason, set<string>& entries)
{
    struct stat st;
    int statret;
    ostringstream msg;
    DIR *d = 0;
    statret = lstat(dir.c_str(), &st);
    if (statret == -1) {
        msg << "readdir: cant stat " << dir << " errno " <<  errno;
        goto out;
    }
    if (!S_ISDIR(st.st_mode)) {
        msg << "readdir: " << dir <<  " not a directory";
        goto out;
    }
    if (access(dir.c_str(), R_OK) < 0) {
        msg << "readdir: no read access to " << dir;
        goto out;
    }

    d = opendir(dir.c_str());
    if (d == 0) {
        msg << "readdir: cant opendir " << dir << ", errno " << errno;
        goto out;
    }

    struct dirent *ent;
    while ((ent = readdir(d)) != 0) {
        if (!strcmp(ent->d_name, ".") || !strcmp(ent->d_name, "..")) {
            continue;
        }
        entries.insert(ent->d_name);
    }

out:
    if (d) {
        closedir(d);
    }
    reason = msg.str();
    if (reason.empty()) {
        return true;
    }
    return false;
}

// We do not want to mess with the pidfile content in the destructor:
// the lock might still be in use in a child process. In fact as much
// as we'd like to reset the pid inside the file when we're done, it
// would be very difficult to do it right and it's probably best left
// alone.
Pidfile::~Pidfile()
{
    if (m_fd >= 0) {
        ::close(m_fd);
    }
    m_fd = -1;
}

pid_t Pidfile::read_pid()
{
    int fd = ::open(m_path.c_str(), O_RDONLY);
    if (fd == -1) {
        return (pid_t) - 1;
    }

    char buf[16];
    int i = read(fd, buf, sizeof(buf) - 1);
    ::close(fd);
    if (i <= 0) {
        return (pid_t) - 1;
    }
    buf[i] = '\0';
    char *endptr;
    pid_t pid = strtol(buf, &endptr, 10);
    if (endptr != &buf[i]) {
        return (pid_t) - 1;
    }
    return pid;
}

int Pidfile::flopen()
{
    const char *path = m_path.c_str();
    if ((m_fd = ::open(path, O_RDWR | O_CREAT, 0644)) == -1) {
        m_reason = "Open failed: [" + m_path + "]: " + strerror(errno);
        return -1;
    }

#ifdef sun
    struct flock lockdata;
    lockdata.l_start = 0;
    lockdata.l_len = 0;
    lockdata.l_type = F_WRLCK;
    lockdata.l_whence = SEEK_SET;
    if (fcntl(m_fd, F_SETLK,  &lockdata) != 0) {
        int serrno = errno;
        (void)::close(m_fd);
        errno = serrno;
        m_reason = "fcntl lock failed";
        return -1;
    }
#else
#ifdef _WIN32
    return 0;
#else
    int operation = LOCK_EX | LOCK_NB;
    if (flock(m_fd, operation) == -1) {
        int serrno = errno;
        (void)::close(m_fd);
        errno = serrno;
        m_reason = "flock failed";
        return -1;
    }
#endif // ! win32
#endif // ! sun

    if (ftruncate(m_fd, 0) != 0) {
        /* can't happen [tm] */
        int serrno = errno;
        (void)::close(m_fd);
        errno = serrno;
        m_reason = "ftruncate failed";
        return -1;
    }
    return 0;
}

pid_t Pidfile::open()
{
    if (flopen() < 0) {
        return read_pid();
    }
    return (pid_t)0;
}

int Pidfile::write_pid()
{
    /* truncate to allow multiple calls */
    if (ftruncate(m_fd, 0) == -1) {
        m_reason = "ftruncate failed";
        return -1;
    }
    char pidstr[20];
    sprintf(pidstr, "%u", int(getpid()));
    lseek(m_fd, 0, 0);
    if (::write(m_fd, pidstr, strlen(pidstr)) != (ssize_t)strlen(pidstr)) {
        m_reason = "write failed";
        return -1;
    }
    return 0;
}

int Pidfile::close()
{
    return ::close(m_fd);
}

int Pidfile::remove()
{
    return unlink(m_path.c_str());
}

// Call funcs that need static init (not initially reentrant)
void pathut_init_mt()
{
    path_home();
}


#else // TEST_PATHUT
#include <stdlib.h>
#include <iostream>
using namespace std;

#include "pathut.h"

void path_to_thumb(const string& _input)
{
    string input(_input);
    // Make absolute path if needed
    if (input[0] != '/') {
        input = path_absolute(input);
    }

    input = string("file://") + path_canon(input);

    string path;
    //path = url_encode(input, 7);
    thumbPathForUrl(input, 7, path);
    cout << path << endl;
}

const char *tstvec[] = {"", "/", "/dir", "/dir/", "/dir1/dir2",
                        "/dir1/dir2",
                        "./dir", "./dir1/", "dir", "../dir", "/dir/toto.c",
                        "/dir/.c", "/dir/toto.txt", "toto.txt1"
                       };

const string ttvec[] = {"/dir", "", "~", "~/sub", "~root", "~root/sub",
                        "~nosuch", "~nosuch/sub"
                       };
int nttvec = sizeof(ttvec) / sizeof(string);

const char *thisprog;

int main(int argc, const char **argv)
{
    thisprog = *argv++;
    argc--;

    string s;
    vector<string>::const_iterator it;
#if 0
    for (unsigned int i = 0; i < sizeof(tstvec) / sizeof(char *); i++) {
        cout << tstvec[i] << " Father " << path_getfather(tstvec[i]) << endl;
    }
    for (unsigned int i = 0; i < sizeof(tstvec) / sizeof(char *); i++) {
        cout << tstvec[i] << " Simple " << path_getsimple(tstvec[i]) << endl;
    }
    for (unsigned int i = 0; i < sizeof(tstvec) / sizeof(char *); i++) {
        cout << tstvec[i] << " Basename " <<
             path_basename(tstvec[i], ".txt") << endl;
    }
#endif

#if 0
    for (int i = 0; i < nttvec; i++) {
        cout << "tildexp: '" << ttvec[i] << "' -> '" <<
             path_tildexpand(ttvec[i]) << "'" << endl;
    }
#endif

#if 0
    const string canontst[] = {"/dir1/../../..", "/////", "",
                               "/dir1/../../.././/////dir2///////",
                               "../../",
                               "../../../../../../../../../../"
                              };
    unsigned int nttvec = sizeof(canontst) / sizeof(string);
    for (unsigned int i = 0; i < nttvec; i++) {
        cout << "canon: '" << canontst[i] << "' -> '" <<
             path_canon(canontst[i]) << "'" << endl;
    }
#endif
#if 0
    if (argc != 2) {
        cerr << "Usage: trpathut <dir> <pattern>" << endl;
        exit(1);
    }
    string dir = *argv++;
    argc--;
    string pattern =  *argv++;
    argc--;
    vector<string> matched = path_dirglob(dir, pattern);
    for (it = matched.begin(); it != matched.end(); it++) {
        cout << *it << endl;
    }
#endif

#if 0
    if (argc != 1) {
        fprintf(stderr, "Usage: fsocc: trpathut <path>\n");
        exit(1);
    }
    string path = *argv++;
    argc--;

    int pc;
    long long blocks;
    if (!fsocc(path, &pc, &blocks)) {
        fprintf(stderr, "fsocc failed\n");
        return 1;
    }
    printf("pc %d, megabytes %ld\n", pc, blocks);
#endif

#if 0
    Pidfile pidfile("/tmp/pathutpidfile");
    pid_t pid;
    if ((pid = pidfile.open()) != 0) {
        cerr << "open failed. reason: " << pidfile.getreason() <<
             " return " << pid << endl;
        exit(1);
    }
    pidfile.write_pid();
    sleep(10);
    pidfile.close();
    pidfile.remove();
#endif

#if 0
    if (argc > 1) {
        cerr <<  "Usage: thumbpath <filepath>" << endl;
        exit(1);
    }
    string input;
    if (argc == 1) {
        input = *argv++;
        if (input.empty())  {
            cerr << "Usage: thumbpath <filepath>" << endl;
            exit(1);
        }
        path_to_thumb(input);
    } else {
        while (getline(cin, input)) {
            path_to_thumb(input);
        }
    }


    exit(0);
#endif

#if 0
    if (argc != 1) {
        cerr << "Usage: trpathut <filename>" << endl;
        exit(1);
    }
    string fn = *argv++;
    argc--;
    string ext = path_suffix(fn);
    cout << "Suffix: [" << ext << "]" << endl;
    return 0;
#endif

#if 0
    if (argc != 1) {
        cerr << "Usage: trpathut url" << endl;
        exit(1);
    }
    string url = *argv++;
    argc--;

    cout << "File: [" << fileurltolocalpath(url) << "]\n";
    return 0;
#endif

#if 1
    if (argc != 1) {
        cerr << "Usage: trpathut path" << endl;
        exit(1);
    }
    string path = *argv++;
    argc--;

    int pc;
    long long avmbs;
    if (fsocc(path, &pc, &avmbs)) {
        cout << "Percent occup " << pc << " avmbs " << avmbs << endl;
        return 0;
    } else {
        cerr << "fsocc failed\n";
        return 1;
    }
#endif



}

#endif // TEST_PATHUT

