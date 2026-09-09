/**
 * FreeRDP: A Remote Desktop Protocol Implementation
 * X11 Keyboard Mapping
 *
 * Copyright 2009-2012 Marc-Andre Moreau <marcandre.moreau@gmail.com>
 * Copyright 2023 Bernhard Miklautz <bernhard.miklautz@thincast.com>
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#include <string.h>

#include <X11/X.h>
#include <X11/Xatom.h>
#include <X11/Xlib.h>
#include <X11/XKBlib.h>

#include "xf_debug.h"
#include "keyboard_x11.h"
#include "xkb_layout_ids.h"
#include "xf_utils.h"

static char* xkb_rule_group(char* list, unsigned int group)
{
	for (unsigned int i = 0; i < group; i++)
	{
		char* delimiter = strchr(list, ',');
		if (!delimiter)
			return nullptr;
		list = delimiter + 1;
	}

	char* delimiter = strchr(list, ',');
	if (delimiter)
		*delimiter = '\0';
	return list;
}

static BOOL parse_xkb_rule_names(char* xkb_rule, unsigned long num_bytes, unsigned int group,
                                 char** layout, char** variant)
{
	/* Sample output for "Canadian Multilingual Standard"
	 *
	 * _XKB_RULES_NAMES_BACKUP(STRING) = "xorg", "pc105", "ca", "multi", "magic"
	 *
	 *  Format: "rules", "model", "layout", "variant", "options"
	 *
	 * Where "xorg" is the set of rules
	 * "pc105" the keyboard model
	 * "ca" the keyboard layout(s) (can also be something like 'us,uk')
	 * "multi" the keyboard layout variant(s)  (in the examples, “,winkeys” - which means first
	 *         layout uses some “default” variant and second uses “winkeys” variant)
	 * "magic" - configuration option (in the examples,
	 * “eurosign:e,lv3:ralt_switch,grp:rctrl_toggle”
	 *         - three options)
	 */
	*layout = nullptr;
	*variant = nullptr;
	for (size_t i = 0, index = 0; i < num_bytes; index++)
	{
		char* ptr = xkb_rule + i;
		const size_t length = strnlen(ptr, num_bytes - i);
		if (length == num_bytes - i)
			return FALSE;
		i += length + 1;
		if (index == 2)
			*layout = ptr;
		else if (index == 3)
		{
			*variant = ptr;
			break;
		}
	}
	if (!*layout || !*variant)
		return FALSE;

	*layout = xkb_rule_group(*layout, group);
	/* An omitted variant means the default for that group, not group zero's variant. */
	char* empty_variant = *variant + strlen(*variant);
	*variant = xkb_rule_group(*variant, group);
	if (!*variant)
		*variant = empty_variant;
	return *layout && (**layout != '\0');
}

static DWORD kbd_layout_id_from_x_property(wLog* log, Display* display, Window root,
                                           char* property_name, unsigned int group)
{
	char* layout = nullptr;
	char* variant = nullptr;
	char* rule = nullptr;
	Atom type = None;
	int item_size = 0;
	unsigned long items = 0;
	unsigned long unread_items = 0;
	DWORD layout_id = 0;

	Atom property = XInternAtom(display, property_name, False);
	if (property == None)
		return 0;

	if (LogDynAndXGetWindowProperty(log, display, root, property, 0, 1024, False, XA_STRING, &type,
	                                &item_size, &items, &unread_items,
	                                (unsigned char**)&rule) != Success)
		return 0;

	if (type != XA_STRING || item_size != 8 || unread_items != 0)
	{
		XFree(rule);
		return 0;
	}

	if (!parse_xkb_rule_names(rule, items, group, &layout, &variant))
	{
		XFree(rule);
		return 0;
	}

	WLog_Print(log, WLOG_TRACE, "%s layout: %s, variant: %s", property_name, layout, variant);
	layout_id = xf_find_keyboard_layout_in_xorg_rules(log, layout, variant);

	XFree(rule);

	return layout_id;
}

static DWORD kbd_layout_id_from_symbols(wLog* log, const char* symbols, unsigned int group)
{
	if (!symbols || group >= XkbNumKbdGroups || strnlen(symbols, 4097) > 4096)
		return 0;

	DWORD result = 0;
	const char* cursor = symbols;
	while (*cursor)
	{
		char layout[64] = { 0 };
		char variant[128] = { 0 };
		const size_t length = strcspn(cursor, "(_+:|");
		if (length == 0 || length >= sizeof(layout))
			return 0;
		memcpy(layout, cursor, length);
		cursor += length;
		if (*cursor == '(')
		{
			const char* start = ++cursor;
			const size_t count = strcspn(start, "()");
			if (start[count] != ')' || count >= sizeof(variant))
				return 0;
			memcpy(variant, start, count);
			cursor = start + count + 1;
		}

		/* XKB component groups are one-based. libxkbcommon's serialized names
		 * replace '+' and ':' with '_', but retain '_' inside variant names. */
		unsigned int component_group = 1;
		if (*cursor == ':' || (*cursor == '_' && cursor[1] >= '0' && cursor[1] <= '9'))
		{
			cursor++;
			if (*cursor < '1' || *cursor > '4')
				return 0;
			component_group = (unsigned int)(*cursor++ - '0');
		}
		if (*cursor && *cursor != '+' && *cursor != '_' && *cursor != '|')
			return 0;
		if (*cursor && !*++cursor)
			return 0;

		if (component_group != group + 1)
			continue;
		const DWORD id = xf_find_keyboard_layout_in_xorg_rules(log, layout, variant);
		/* Do not guess when several different layouts contribute to one group. */
		if (id && result && id != result)
			return 0;
		if (id)
			result = id;
	}
	return result;
}

static DWORD kbd_layout_id_from_xwayland(wLog* log, Display* display, unsigned int group)
{
	int opcode = 0;
	int event = 0;
	int error = 0;
	if (!XQueryExtension(display, "XWAYLAND", &opcode, &event, &error))
		return 0;

	DWORD id = 0;
	XkbDescPtr keyboard = XkbGetMap(display, 0, XkbUseCoreKbd);
	if (!keyboard)
		return 0;
	if (XkbGetNames(display, XkbSymbolsNameMask, keyboard) == Success && keyboard->names &&
	    keyboard->names->symbols != None)
	{
		char* symbols = XGetAtomName(display, keyboard->names->symbols);
		id = kbd_layout_id_from_symbols(log, symbols, group);
		WLog_Print(log, WLOG_TRACE, "Xwayland symbols: %s, group: %u, layout: 0x%08" PRIx32,
		           symbols ? symbols : "(none)", group, id);
		XFree(symbols);
	}
	XkbFreeKeyboard(keyboard, 0, True);
	return id;
}

int xf_detect_keyboard_layout_from_xkb_group(wLog* log, DWORD* keyboardLayoutId, int requestedGroup)
{
	if (requestedGroup < -1 || requestedGroup >= XkbNumKbdGroups)
		return 0;
	Display* display = XOpenDisplay(nullptr);

	if (!display)
		return 0;

	Window root = DefaultRootWindow(display);
	if (!root)
	{
		LogDynAndXCloseDisplay(log, display);
		return 0;
	}

	XkbStateRec state = { 0 };
	const unsigned int group =
	    (requestedGroup >= 0)
	        ? (unsigned int)requestedGroup
	        : ((XkbGetState(display, XkbUseCoreKbd, &state) == Success) ? state.group : 0);

	/* Wayland sends a compiled keymap, without RMLVO settings. Xwayland's root
	 * rules property can still describe its initial US map; prefer the live map. */
	DWORD id = kbd_layout_id_from_xwayland(log, display, group);

	/* Keep the native X11/libxklavier path as the fallback. */
	if (0 == id)
		id = kbd_layout_id_from_x_property(log, display, root, "_XKB_RULES_NAMES_BACKUP", group);

	if (0 == id)
		id = kbd_layout_id_from_x_property(log, display, root, "_XKB_RULES_NAMES", group);

	if (0 != id)
		*keyboardLayoutId = id;

	LogDynAndXCloseDisplay(log, display);
	return (int)id;
}

int xf_detect_keyboard_layout_from_xkb(wLog* log, DWORD* keyboardLayoutId)
{
	return xf_detect_keyboard_layout_from_xkb_group(log, keyboardLayoutId, -1);
}
