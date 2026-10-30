#define _GNU_SOURCE
#include <dlfcn.h>
#include <sched.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <stdarg.h>
#include <fcntl.h>
#include <stdint.h>
#include <sys/stat.h>
#include <sys/socket.h>
#include <sys/syscall.h>
#include <sys/prctl.h>
#include <sys/ptrace.h>

#ifndef PR_SET_PTRACER
#define PR_SET_PTRACER 0x59616d61
#define PR_SET_PTRACER_ANY ((unsigned long)-1)
#endif

static inline int is_valid_ptr(const void *p) {
    uintptr_t u = (uintptr_t)p;
    return (u >= 0x1000 && u <= 0x7fffffffffffULL);
}

__attribute__((constructor))
static void rootless_init(void) {
    prctl(PR_SET_PTRACER, PR_SET_PTRACER_ANY, 0, 0, 0);
}

static uid_t (*real_geteuid)(void) = NULL;
static uid_t (*real_getuid)(void) = NULL;
static gid_t (*real_getgid)(void) = NULL;
static pid_t (*real_getpid)(void) = NULL;
static int (*real_unshare)(int flags) = NULL;
static int (*real_execve)(const char *filename, char *const argv[], char *const envp[]) = NULL;
static long (*real_syscall)(long number, ...) = NULL;
static int (*real_open)(const char *pathname, int flags, ...) = NULL;
static int (*real_openat)(int dirfd, const char *pathname, int flags, ...) = NULL;
static int (*real_access)(const char *pathname, int mode) = NULL;
static int (*real_stat)(const char *pathname, struct stat *statbuf) = NULL;
static int (*real_lstat)(const char *pathname, struct stat *statbuf) = NULL;
static ssize_t (*real_sendmsg)(int sockfd, const struct msghdr *msg, int flags) = NULL;
static int (*real_sendmmsg)(int sockfd, struct mmsghdr *msgvec, unsigned int vlen, int flags) = NULL;
static long (*real_ptrace)(enum __ptrace_request request, ...) = NULL;

uid_t geteuid(void) { return 0; }
uid_t getuid(void) { return 0; }
gid_t getegid(void) { return 0; }
gid_t getgid(void) { return 0; }

pid_t getpid(void) {
    if (!real_getpid) real_getpid = dlsym(RTLD_NEXT, "getpid");
    char cmd[512];
    int fd = open("/proc/self/cmdline", O_RDONLY);
    if (fd >= 0) {
        ssize_t n = read(fd, cmd, sizeof(cmd) - 1);
        close(fd);
        if (n > 0) {
            cmd[n] = '\0';
            for (ssize_t i = 0; i < n; i++) if (cmd[i] == '\0') cmd[i] = ' ';
            if (strstr(cmd, "launchd")) {
                return 1;
            }
        }
    }
    return real_getpid ? real_getpid() : 1000;
}

long ptrace(enum __ptrace_request request, ...) {
    va_list args;
    va_start(args, request);
    pid_t pid = va_arg(args, pid_t);
    void *addr = va_arg(args, void *);
    void *data = va_arg(args, void *);
    va_end(args);

    if ((int)request == 0x59616d61) {
        return prctl(PR_SET_PTRACER, PR_SET_PTRACER_ANY, 0, 0, 0);
    }
    if (!real_ptrace) real_ptrace = dlsym(RTLD_NEXT, "ptrace");
    return real_ptrace(request, pid, addr, data);
}

int setuid(uid_t uid) { return 0; }
int setgid(gid_t gid) { return 0; }
int seteuid(uid_t euid) { return 0; }
int setegid(gid_t egid) { return 0; }
int setresuid(uid_t ruid, uid_t euid, uid_t suid) { return 0; }
int setresgid(gid_t rgid, gid_t egid, gid_t sgid) { return 0; }

int mount(const char *source, const char *target, const char *filesystemtype, unsigned long mountflags, const void *data) {
    return 0;
}

int umount2(const char *target, int flags) {
    return 0;
}

int unshare(int flags) {
    return 0;
}

static void fix_credentials(struct msghdr *msg) {
    if (!msg || !msg->msg_control) return;
    struct cmsghdr *cmsg;
    for (cmsg = CMSG_FIRSTHDR(msg); cmsg != NULL; cmsg = CMSG_NXTHDR(msg, cmsg)) {
        if (cmsg->cmsg_level == SOL_SOCKET && cmsg->cmsg_type == SCM_CREDENTIALS) {
            struct ucred *u = (struct ucred *)CMSG_DATA(cmsg);
            if (!real_getuid) real_getuid = dlsym(RTLD_NEXT, "getuid");
            if (!real_getgid) real_getgid = dlsym(RTLD_NEXT, "getgid");
            u->uid = real_getuid ? real_getuid() : 1000;
            u->gid = real_getgid ? real_getgid() : 1000;
        }
    }
}

ssize_t sendmsg(int sockfd, const struct msghdr *msg, int flags) {
    if (!real_sendmsg) real_sendmsg = dlsym(RTLD_NEXT, "sendmsg");
    fix_credentials((struct msghdr*)msg);
    return real_sendmsg(sockfd, msg, flags);
}

int sendmmsg(int sockfd, struct mmsghdr *msgvec, unsigned int vlen, int flags) {
    if (!real_sendmmsg) real_sendmmsg = dlsym(RTLD_NEXT, "sendmmsg");
    for (unsigned int i = 0; i < vlen; i++) {
        fix_credentials(&msgvec[i].msg_hdr);
    }
    return real_sendmmsg(sockfd, msgvec, vlen, flags);
}

static const char* redirect_path(const char* path, char* buffer, size_t buflen) {
    if (!is_valid_ptr(path)) return path;
    while (path[0] == '/' && path[1] == '/') path++;
    const char *darling_dir = getenv("DARLING_DIR");
    const char *prefix = getenv("DARLING_PREFIX");
    const char *home = getenv("HOME");
    static char default_runtime[4096];
    static char default_prefix[4096];
    if (!home) home = "/tmp";
    if (!darling_dir) {
        snprintf(default_runtime, sizeof(default_runtime), "%s/.local/darling", home);
        darling_dir = default_runtime;
    }
    if (!prefix) {
        snprintf(default_prefix, sizeof(default_prefix), "%s/.darling", home);
        prefix = default_prefix;
    }

    if (strstr(path, "/usr/bin/darlingserver") || strcmp(path, "darlingserver") == 0) {
        snprintf(buffer, buflen, "%s/usr/bin/darlingserver", darling_dir);
        return buffer;
    }
    if (strncmp(path, "/usr/libexec/darling", 20) == 0) {
        snprintf(buffer, buflen, "%s%s", darling_dir, path);
        return buffer;
    }
    if (strncmp(path, "/usr/lib/", 9) == 0 ||
        strncmp(path, "/System/", 8) == 0 ||
        strncmp(path, "/Library/", 9) == 0 ||
        strncmp(path, "/bin/", 5) == 0 ||
        strncmp(path, "/sbin/", 6) == 0) {
        snprintf(buffer, buflen, "%s%s", prefix, path);
        return buffer;
    }
    return path;
}

static int is_macho(const char *path) {
    if (!is_valid_ptr(path)) return 0;
    int fd = open(path, O_RDONLY);
    if (fd < 0) return 0;
    unsigned int magic = 0;
    ssize_t n = read(fd, &magic, sizeof(magic));
    close(fd);
    if (n != sizeof(magic)) return 0;
    return (magic == 0xfeedface || magic == 0xcefaedfe ||
            magic == 0xfeedfacf || magic == 0xcffaedfe ||
            magic == 0xcafebabe || magic == 0xbebafeca);
}

int open(const char *pathname, int flags, ...) {
    if (!real_open) real_open = dlsym(RTLD_NEXT, "open");
    char target[4096];
    if (is_valid_ptr(pathname)) {
        pathname = redirect_path(pathname, target, sizeof(target));
    }
    mode_t mode = 0;
    if (__OPEN_NEEDS_MODE(flags)) {
        va_list args;
        va_start(args, flags);
        mode = va_arg(args, mode_t);
        va_end(args);
    }
    return real_open(pathname, flags, mode);
}

int open64(const char *pathname, int flags, ...) {
    return open(pathname, flags);
}

int openat(int dirfd, const char *pathname, int flags, ...) {
    if (!real_openat) real_openat = dlsym(RTLD_NEXT, "openat");
    char target[4096];
    if (is_valid_ptr(pathname)) {
        pathname = redirect_path(pathname, target, sizeof(target));
    }
    mode_t mode = 0;
    if (__OPEN_NEEDS_MODE(flags)) {
        va_list args;
        va_start(args, flags);
        mode = va_arg(args, mode_t);
        va_end(args);
    }
    return real_openat(dirfd, pathname, flags, mode);
}

int openat64(int dirfd, const char *pathname, int flags, ...) {
    return openat(dirfd, pathname, flags);
}

int access(const char *pathname, int mode) {
    if (!real_access) real_access = dlsym(RTLD_NEXT, "access");
    char target[4096];
    if (is_valid_ptr(pathname)) {
        pathname = redirect_path(pathname, target, sizeof(target));
    }
    return real_access(pathname, mode);
}

int stat(const char *pathname, struct stat *statbuf) {
    if (!real_stat) real_stat = dlsym(RTLD_NEXT, "stat");
    char target[4096];
    if (is_valid_ptr(pathname)) {
        pathname = redirect_path(pathname, target, sizeof(target));
    }
    return real_stat(pathname, statbuf);
}

int lstat(const char *pathname, struct stat *statbuf) {
    if (!real_lstat) real_lstat = dlsym(RTLD_NEXT, "lstat");
    char target[4096];
    if (is_valid_ptr(pathname)) {
        pathname = redirect_path(pathname, target, sizeof(target));
    }
    return real_lstat(pathname, statbuf);
}

long syscall(long number, ...) {
    if (!real_syscall) real_syscall = dlsym(RTLD_NEXT, "syscall");

    va_list args;
    va_start(args, number);
    long a1 = va_arg(args, long);
    long a2 = va_arg(args, long);
    long a3 = va_arg(args, long);
    long a4 = va_arg(args, long);
    long a5 = va_arg(args, long);
    long a6 = va_arg(args, long);
    va_end(args);

    if (number == 39) { // SYS_getpid
        char cmd[512];
        int fd = open("/proc/self/cmdline", O_RDONLY);
        if (fd >= 0) {
            ssize_t n = read(fd, cmd, sizeof(cmd) - 1);
            close(fd);
            if (n > 0) {
                cmd[n] = '\0';
                for (ssize_t i = 0; i < n; i++) if (cmd[i] == '\0') cmd[i] = ' ';
                if (strstr(cmd, "launchd")) {
                    return 1;
                }
            }
        }
    }
    if (number == 272) { // SYS_unshare
        return 0;
    }
    if (number == 165) { // SYS_mount
        return 0;
    }
    if (number == 166) { // SYS_umount2
        return 0;
    }
    if (number == 56) { // SYS_clone
        a1 &= ~0x20000000; // Remove CLONE_NEWPID
        return real_syscall(number, a1, a2, a3, a4, a5, a6);
    }
    if (number == 302) { // SYS_prlimit64
        long res = real_syscall(number, a1, a2, a3, a4, a5, a6);
        return (res < 0) ? 0 : res;
    }
    if (number == 257) { // SYS_openat
        char target[4096];
        const char *p = (const char*)a2;
        p = redirect_path(p, target, sizeof(target));
        return real_syscall(number, a1, (long)p, a3, a4, a5, a6);
    }
    if (number == 2) { // SYS_open
        char target[4096];
        const char *p = (const char*)a1;
        p = redirect_path(p, target, sizeof(target));
        return real_syscall(number, (long)p, a2, a3, a4, a5, a6);
    }
    if (number == 4) { // SYS_stat
        char target[4096];
        const char *p = (const char*)a1;
        p = redirect_path(p, target, sizeof(target));
        return real_syscall(number, (long)p, a2, a3, a4, a5, a6);
    }
    if (number == 6) { // SYS_lstat
        char target[4096];
        const char *p = (const char*)a1;
        p = redirect_path(p, target, sizeof(target));
        return real_syscall(number, (long)p, a2, a3, a4, a5, a6);
    }
    if (number == 262) { // SYS_newfstatat
        char target[4096];
        const char *p = (const char*)a2;
        p = redirect_path(p, target, sizeof(target));
        return real_syscall(number, a1, (long)p, a3, a4, a5, a6);
    }
    return real_syscall(number, a1, a2, a3, a4, a5, a6);
}

int execve(const char *filename, char *const argv[], char *const envp[]) {
    if (!real_execve) real_execve = dlsym(RTLD_NEXT, "execve");

    char target[4096];
    if (is_valid_ptr(filename)) {
        filename = redirect_path(filename, target, sizeof(target));
    }

    if (is_valid_ptr(filename) && is_valid_ptr(argv) && is_valid_ptr(argv[0])) {
        fprintf(stderr, "[librootless execve] filename=%s argv0=%s\n", filename, argv[0]);
    }

    const char *darling_dir = getenv("DARLING_DIR");
    const char *prefix = getenv("DARLING_PREFIX");
    const char *home = getenv("HOME");
    const char *socket_path = getenv("DARLING_SOCKET");
    char default_runtime[4096], default_prefix[4096], default_socket[4096];
    if (!home) home = "/tmp";
    if (!darling_dir) {
        snprintf(default_runtime, sizeof(default_runtime), "%s/.local/darling", home);
        darling_dir = default_runtime;
    }
    if (!prefix) {
        snprintf(default_prefix, sizeof(default_prefix), "%s/.darling", home);
        prefix = default_prefix;
    }
    if (!socket_path) {
        snprintf(default_socket, sizeof(default_socket), "%s/.darlingserver.sock", prefix);
        socket_path = default_socket;
    }
    char mldr_path[4096];
    snprintf(mldr_path, sizeof(mldr_path), "%s/usr/libexec/darling/usr/libexec/darling/mldr", darling_dir);

    char preload_env[8192], darling_dir_env[8192], prefix_env[8192], socket_env[8192];
    snprintf(preload_env, sizeof(preload_env), "LD_PRELOAD=%s/librootless.so", darling_dir);
    snprintf(darling_dir_env, sizeof(darling_dir_env), "DARLING_DIR=%s", darling_dir);
    snprintf(prefix_env, sizeof(prefix_env), "DARLING_PREFIX=%s", prefix);
    snprintf(socket_env, sizeof(socket_env), "DARLING_SOCKET=%s", socket_path);
    char mldr_socket_env[8192];
    snprintf(mldr_socket_env, sizeof(mldr_socket_env), "__mldr_sockpath=%s", socket_path);

    char *new_env[256];
    int envc = 0;
    new_env[envc++] = preload_env;
    new_env[envc++] = darling_dir_env;
    new_env[envc++] = prefix_env;
    new_env[envc++] = socket_env;
    new_env[envc++] = "DYLD_ROOT_PATH=/";
    new_env[envc++] = "DYLD_LIBRARY_PATH=/usr/lib:/usr/lib/system";
    new_env[envc++] = "DYLD_FRAMEWORK_PATH=/System/Library/Frameworks";
    new_env[envc++] = "__mldr_DYLD_ROOT_PATH=/";
    new_env[envc++] = mldr_socket_env;

    for (char *const *e = envp; *e && envc < 240; ++e) {
        if (strncmp(*e, "LD_PRELOAD=", 11) != 0 &&
            strncmp(*e, "DARLING_DIR=", 12) != 0 &&
            strncmp(*e, "DARLING_PREFIX=", 15) != 0 &&
            strncmp(*e, "DARLING_SOCKET=", 15) != 0 &&
            strncmp(*e, "DYLD_ROOT_PATH=", 15) != 0 &&
            strncmp(*e, "DYLD_LIBRARY_PATH=", 18) != 0 &&
            strncmp(*e, "DYLD_FRAMEWORK_PATH=", 20) != 0 &&
            strncmp(*e, "__mldr_DYLD_ROOT_PATH=", 22) != 0 &&
            strncmp(*e, "__mldr_sockpath=", 16) != 0) {
            new_env[envc++] = *e;
        }
    }
    new_env[envc] = NULL;

    if (is_macho(filename)) {
        char *mldr_argv[256];
        int m_argc = 0;
        mldr_argv[m_argc++] = mldr_path;
        mldr_argv[m_argc++] = (char*)filename;
        if (argv) {
            for (int i = 1; argv[i] && m_argc < 254; i++) {
                mldr_argv[m_argc++] = argv[i];
            }
        }
        mldr_argv[m_argc] = NULL;
        return real_execve(mldr_path, mldr_argv, new_env);
    }

    return real_execve(filename, argv, new_env);
}

int execv(const char *path, char *const argv[]) {
    extern char **environ;
    return execve(path, argv, environ);
}

int execl(const char *path, const char *arg0, ...) {
    va_list args;
    char *argv[64];
    int argc = 0;

    argv[argc++] = (char*)arg0;
    va_start(args, arg0);
    char *arg;
    while ((arg = va_arg(args, char*)) != NULL && argc < 63) {
        argv[argc++] = arg;
    }
    va_end(args);
    argv[argc] = NULL;

    extern char **environ;
    return execve(path, argv, environ);
}
