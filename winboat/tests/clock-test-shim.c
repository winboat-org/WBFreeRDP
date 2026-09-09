#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdlib.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

static long long read_number(const char* name, int consume)
{
    const char* path = getenv(name);
    if (!path) return 0;
    int fd = open(path, (consume ? O_RDWR : O_RDONLY) | O_CLOEXEC);
    if (fd < 0) return 0;
    char text[64] = {0};
    ssize_t length = read(fd, text, sizeof(text)-1);
    long long value = length > 0 ? strtoll(text, NULL, 10) : 0;
    if (consume && value > 0) {
        if (ftruncate(fd, 0) || pwrite(fd, "0\n", 2, 0) != 2) value = 0;
    }
    close(fd);
    return value;
}

int clock_gettime(clockid_t id, struct timespec* value)
{
    int rc = syscall(SYS_clock_gettime, id, value);
    if (rc == 0 && id == CLOCK_BOOTTIME) {
        long long offset = read_number("WBFREERDP_TEST_SUSPEND_MS", 0);
        if (offset > 0) {
            value->tv_sec += offset / 1000;
            value->tv_nsec += (offset % 1000) * 1000000;
            if (value->tv_nsec >= 1000000000) {
                value->tv_sec++;
                value->tv_nsec -= 1000000000;
            }
        }
        long long delay = read_number("WBFREERDP_TEST_CLOCK_DELAY_MS", 1);
        if (delay > 0 && delay <= 10000) {
            struct timespec remaining = { .tv_sec = delay / 1000,
                                         .tv_nsec = (delay % 1000) * 1000000 };
            while (syscall(SYS_nanosleep, &remaining, &remaining) && errno == EINTR) { }
        }
    }
    return rc;
}
