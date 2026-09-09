/* SPDX-License-Identifier: Apache-2.0 */
/* Strict software/VA-API decode check, including a hash of normalized NV12 pixels. */
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <libavcodec/avcodec.h>
#include <libavformat/avformat.h>
#include <libavutil/hwcontext.h>
#include <libavutil/imgutils.h>
#include <libavutil/sha.h>
#include <libswscale/swscale.h>

struct output
{
	struct AVSHA* hash;
	struct SwsContext* scaler;
	uint64_t frames;
	uint64_t hardware_frames;
	int hardware;
};

static enum AVPixelFormat hardware_format(AVCodecContext* context,
                                          const enum AVPixelFormat* formats)
{
	(void)context;
	for (; *formats != AV_PIX_FMT_NONE; formats++)
	{
		if (*formats == AV_PIX_FMT_VAAPI)
			return *formats;
	}
	return AV_PIX_FMT_NONE;
}

static int receive_frames(AVCodecContext* decoder, struct output* output)
{
	int result = 0;
	AVFrame* frame = av_frame_alloc();
	AVFrame* transferred = av_frame_alloc();
	if (!frame || !transferred)
	{
		result = AVERROR(ENOMEM);
		goto out;
	}
	while ((result = avcodec_receive_frame(decoder, frame)) >= 0)
	{
		AVFrame* pixels = frame;
		if (output->hardware)
		{
			if (frame->format != AV_PIX_FMT_VAAPI)
			{
				result = AVERROR_INVALIDDATA;
				goto out;
			}
			result = av_hwframe_transfer_data(transferred, frame, 0);
			if (result < 0)
				goto out;
			pixels = transferred;
			output->hardware_frames++;
		}
		uint8_t* normalized[4] = { 0 };
		int strides[4] = { 0 };
		const int size =
		    av_image_alloc(normalized, strides, pixels->width, pixels->height, AV_PIX_FMT_NV12, 1);
		if (size < 0)
		{
			result = size;
			goto out;
		}
		output->scaler = sws_getCachedContext(output->scaler, pixels->width, pixels->height,
		                                      pixels->format, pixels->width, pixels->height,
		                                      AV_PIX_FMT_NV12, SWS_POINT, NULL, NULL, NULL);
		if (!output->scaler ||
		    (sws_scale(output->scaler, (const uint8_t* const*)pixels->data, pixels->linesize, 0,
		               pixels->height, normalized, strides) != pixels->height))
		{
			av_freep(&normalized[0]);
			result = AVERROR_INVALIDDATA;
			goto out;
		}
		av_sha_update(output->hash, normalized[0], size);
		av_freep(&normalized[0]);
		output->frames++;
		av_frame_unref(transferred);
		av_frame_unref(frame);
	}
	if ((result == AVERROR(EAGAIN)) || (result == AVERROR_EOF))
		result = 0;
out:
	av_frame_free(&transferred);
	av_frame_free(&frame);
	return result;
}

int main(int argc, char** argv)
{
	if ((argc != 3) || ((strcmp(argv[1], "software") != 0) && (strcmp(argv[1], "vaapi") != 0)))
	{
		fprintf(stderr, "Usage: %s software|vaapi input.h264\n", argv[0]);
		return 2;
	}
	int result = 1;
	int status = AVERROR(ENOMEM);
	AVFormatContext* input = NULL;
	AVCodecContext* decoder = NULL;
	AVPacket* packet = av_packet_alloc();
	AVBufferRef* device = NULL;
	struct output output = { .hash = av_sha_alloc(), .hardware = strcmp(argv[1], "vaapi") == 0 };
	if (!packet || !output.hash || (av_sha_init(output.hash, 256) < 0))
		goto out;
	if ((status = avformat_open_input(&input, argv[2], NULL, NULL)) < 0)
		goto out;
	if ((status = avformat_find_stream_info(input, NULL)) < 0)
		goto out;
	const AVCodec* codec = NULL;
	const int stream = av_find_best_stream(input, AVMEDIA_TYPE_VIDEO, -1, -1, &codec, 0);
	if (stream < 0)
	{
		status = stream;
		goto out;
	}
	decoder = avcodec_alloc_context3(codec);
	if (!decoder)
		goto out;
	if ((status = avcodec_parameters_to_context(decoder, input->streams[stream]->codecpar)) < 0)
		goto out;
	if (output.hardware)
	{
		const char* path = getenv("FREERDP_VAAPI_DEVICE");
		if (!path)
			path = "/dev/dri/renderD128";
		status = av_hwdevice_ctx_create(&device, AV_HWDEVICE_TYPE_VAAPI, path, NULL, 0);
		if (status < 0)
			goto out;
		decoder->get_format = hardware_format;
		decoder->hw_device_ctx = av_buffer_ref(device);
		if (!decoder->hw_device_ctx)
			goto out;
	}
	decoder->thread_count = 2;
	if ((status = avcodec_open2(decoder, codec, NULL)) < 0)
		goto out;
	while ((status = av_read_frame(input, packet)) >= 0)
	{
		if (packet->stream_index == stream)
		{
			if ((status = avcodec_send_packet(decoder, packet)) < 0)
				goto out;
			if ((status = receive_frames(decoder, &output)) < 0)
				goto out;
		}
		av_packet_unref(packet);
	}
	if (status != AVERROR_EOF)
		goto out;
	if ((status = avcodec_send_packet(decoder, NULL)) < 0)
		goto out;
	if ((status = receive_frames(decoder, &output)) < 0)
		goto out;
	if (!output.frames || (output.hardware && (output.frames != output.hardware_frames)))
	{
		status = AVERROR_INVALIDDATA;
		goto out;
	}
	uint8_t digest[32];
	av_sha_final(output.hash, digest);
	printf("{\"frames\":%" PRIu64 ",\"hardwareFrames\":%" PRIu64 ",\"sha256\":\"", output.frames,
	       output.hardware_frames);
	for (size_t i = 0; i < sizeof(digest); i++)
		printf("%02x", digest[i]);
	puts("\"}");
	result = 0;
out:
	if (result != 0)
	{
		char message[AV_ERROR_MAX_STRING_SIZE];
		av_strerror(status, message, sizeof(message));
		fprintf(stderr, "Decode probe failed: %s\n", message);
	}
	sws_freeContext(output.scaler);
	av_free(output.hash);
	av_packet_free(&packet);
	avcodec_free_context(&decoder);
	avformat_close_input(&input);
	av_buffer_unref(&device);
	return result;
}
