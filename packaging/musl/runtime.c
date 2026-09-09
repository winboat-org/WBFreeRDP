/* SPDX-License-Identifier: Apache-2.0 */
/* Load foreign initial-exec TLS before FreeRDP creates any worker threads. */
#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

#include <libavutil/hwcontext.h>

extern int __real_main(int argc, char** argv);
int __wrap_main(int argc, char** argv);

static int initialize_device(const char* device)
{
	AVBufferRef* context = NULL;
	const int result = av_hwdevice_ctx_create(&context, AV_HWDEVICE_TYPE_VAAPI, device, NULL, 0);
	av_buffer_unref(&context);
	return result >= 0;
}

static int probe_device(const char* device)
{
	const pid_t child = fork();
	if (child < 0)
		return 0;
	if (child == 0)
	{
		(void)signal(SIGALRM, SIG_DFL);
		(void)alarm(10);
		_exit(initialize_device(device) ? 0 : 1);
	}
	int status = 0;
	pid_t result;
	do
	{
		result = waitpid(child, &status, 0);
	} while ((result < 0) && (errno == EINTR));
	return (result == child) && WIFEXITED(status) && (WEXITSTATUS(status) == 0);
}

int __wrap_main(int argc, char** argv)
{
	int probe_only = 0;
	if (argc < 2)
		return __real_main(argc, argv);
	for (int i = 1; i < argc; i++)
	{
		if ((strcmp(argv[i], "/version") == 0) || (strcmp(argv[i], "--version") == 0) ||
		    (strcmp(argv[i], "/buildconfig") == 0) || (strcmp(argv[i], "--buildconfig") == 0) ||
		    (strcmp(argv[i], "/help") == 0) || (strcmp(argv[i], "--help") == 0))
			return __real_main(argc, argv);
		if (strcmp(argv[i], "--wb-vaapi-probe") == 0)
			probe_only = 1;
	}
	const char* mode = getenv("FREERDP_VAAPI_MODE");
	if (mode && (strcmp(mode, "off") == 0))
		return probe_only ? 1 : __real_main(argc, argv);
	if (mode && (strcmp(mode, "auto") != 0))
	{
		fprintf(stderr, "FREERDP_VAAPI_MODE must be auto or off\n");
		return 1;
	}
	const char* device = getenv("FREERDP_VAAPI_DEVICE");
	if (!device)
		device = "/dev/dri/renderD128";
	/* An unsupported SoLo ABI call can abort. Keep initialization failures in a child.
	 * This is a startup check; it cannot contain a later driver crash during decoding. */
	if (!probe_device(device) || !initialize_device(device))
	{
		fprintf(stderr, "[WBFreeRDP] VA-API startup check failed; using software decoding\n");
		if (setenv("FREERDP_VAAPI_MODE", "off", 1) != 0)
			return 1;
		return probe_only ? 1 : __real_main(argc, argv);
	}
	/* SoLo intentionally retains loaded images after libva releases its device.
	 * New threads now inherit the initialized TLS of the driver and its dependencies. */
	fprintf(stderr, "[WBFreeRDP] VA-API driver preloaded for %s\n", device);
	return probe_only ? 0 : __real_main(argc, argv);
}
