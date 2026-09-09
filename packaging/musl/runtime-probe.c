/* SPDX-License-Identifier: Apache-2.0 */
#include <inttypes.h>
#include <stdio.h>
#include <string.h>
#include <winpr/crypto.h>
#include <winpr/image.h>
#include <winpr/smartcard.h>

static int read_red_image(const char* path)
{
	wImage* image = winpr_image_new();
	if (!image)
		return 0;
	int result = winpr_image_read(image, path);
	if ((result > 0) && (image->width == 4) && (image->height == 4) && (image->bytesPerPixel >= 3))
	{
		for (UINT32 y = 0; y < 4; y++)
		{
			for (UINT32 x = 0; x < 4; x++)
			{
				const BYTE* pixel = image->data + y * image->scanline + x * image->bytesPerPixel;
				if ((pixel[0] > 40) || (pixel[1] > 40) || (pixel[2] < 180))
					result = 0;
			}
		}
	}
	else
		result = 0;
	winpr_image_free(image, TRUE);
	return result > 0;
}

int main(int argc, char** argv)
{
	if (argc != 3)
	{
		fprintf(stderr, "Usage: %s red.png red.jpg\n", argv[0]);
		return 2;
	}
	static const BYTE expected[16] = { 0xa4, 0x48, 0x01, 0x7a, 0xaf, 0x21, 0xd8, 0x52,
		                               0x5f, 0xc1, 0x0a, 0xe8, 0x7a, 0xa6, 0x72, 0x9d };
	BYTE digest[16] = { 0 };
	const int md4 = winpr_Digest(WINPR_MD_MD4, "abc", 3, digest, sizeof(digest)) &&
	                (memcmp(digest, expected, sizeof(digest)) == 0);
	const int png = read_red_image(argv[1]);
	const int jpeg = read_red_image(argv[2]);
	SCARDCONTEXT context = 0;
	const LONG smartcard = SCardEstablishContext(SCARD_SCOPE_SYSTEM, NULL, NULL, &context);
	if (smartcard == SCARD_S_SUCCESS)
		(void)SCardReleaseContext(context);
	printf("{\"md4\":%s,\"png\":%s,\"jpeg\":%s,\"smartcardStatus\":\"0x%08" PRIx32 "\"}\n",
	       md4 ? "true" : "false", png ? "true" : "false", jpeg ? "true" : "false",
	       (UINT32)smartcard);
	return (md4 && png && jpeg &&
	        ((smartcard == SCARD_S_SUCCESS) || (smartcard == SCARD_E_NO_SERVICE) ||
	         (smartcard == SCARD_E_SERVICE_STOPPED)))
	           ? 0
	           : 1;
}
