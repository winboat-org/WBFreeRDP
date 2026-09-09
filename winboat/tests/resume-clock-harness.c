#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <time.h>
typedef int BOOL;
typedef int64_t INT64;
#define TRUE 1
#define FALSE 0
#define WINPR_UNUSED(x) (void)(x)
static INT64 awake = 10000, slept = 5000;
static INT64 before_boot_delay, after_boot_delay;
static int seen_boot, fail_clock;
static unsigned calls;
static int test_clock_gettime(clockid_t id, struct timespec* value)
{
    calls++;
    if (fail_clock) return -1;
    if (id == CLOCK_BOOTTIME) {
        awake += before_boot_delay;
        before_boot_delay = 0;
        seen_boot = 1;
    } else if (seen_boot) {
        awake += after_boot_delay;
        after_boot_delay = 0;
    }
    INT64 now = awake + (id == CLOCK_BOOTTIME ? slept : 0);
    value->tv_sec = now / 1000;
    value->tv_nsec = (now % 1000) * 1000000;
    return 0;
}
#define clock_gettime test_clock_gettime
/* FUNCTION */
static INT64 previous = -1;
static unsigned checks, failures;
static BOOL probe(void) { seen_boot = 0; return xf_client_resumed(&previous); }
static void check(const char* name, BOOL wanted)
{
    BOOL actual = probe();
    printf("%s{\"case\":\"%s\",\"expected\":%s,\"actual\":%s,\"pass\":%s}",
           checks ? "," : "", name, wanted ? "true" : "false", actual ? "true" : "false",
           actual == wanted ? "true" : "false");
    checks++;
    failures += actual != wanted;
}
static uint32_t random_state = 0x6b136b13;
static uint32_t next_random(void)
{
    random_state ^= random_state << 13;
    random_state ^= random_state >> 17;
    random_state ^= random_state << 5;
    return random_state;
}
int main(void)
{
    printf("{\"cases\":[");
    check("initial", FALSE);
    awake += 1000000; check("awake-time", FALSE);
    after_boot_delay = 1500; check("preempted-sample", FALSE);
    check("healthy-after-preemption", FALSE);
    previous = -1; after_boot_delay = 1500; check("preempted-initial", FALSE);
    check("healthy-after-preempted-initial", FALSE);
    previous = -1; before_boot_delay = 1500; check("preempted-before-boot", FALSE);
    check("refine-initial-upper-bound", FALSE);
    slept += 1000; check("one-second-suspend", TRUE);
    check("one-trigger", FALSE);
    slept += 21600000; check("six-hour-suspend", TRUE);
    after_boot_delay = 1500; check("preemption-after-resume", FALSE);
    check("no-second-trigger-after-preemption", FALSE);
    slept += 1000; after_boot_delay = 2000; check("uncertain-resume-sample", FALSE);
    check("detect-on-healthy-sample", TRUE);
    fail_clock = 1; check("clock-failure", FALSE);
    assert(previous == -1);
    fail_clock = 0; check("clock-recovery-baseline", FALSE);
    slept += 500; check("half-second-suspend", FALSE);
    slept += 500; check("cumulative-one-second", TRUE);
    printf("],\"failures\":%u", failures);
    unsigned false_positives = 0, observed_resumes = 0;
    previous = -1;
    awake = 10000; slept = 5000;
    INT64 last_detected_sleep = slept;
    for (unsigned i = 0; i < 200000; i++) {
        awake += next_random() % 20;
        before_boot_delay = next_random() % 2001;
        after_boot_delay = next_random() % 2001;
        if (i && (i % 4096 == 0)) slept += 1000 + next_random() % 10000;
        if (probe()) {
            false_positives += slept - last_detected_sleep < 1000;
            observed_resumes++;
            last_detected_sleep = slept;
        }
    }
    printf(",\"randomSamples\":200000,\"falsePositives\":%u,\"detectedResumes\":%u,\"clockCalls\":%u}\n",
           false_positives, observed_resumes, calls);
    return 0;
}
