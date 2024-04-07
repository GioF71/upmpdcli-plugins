/* Copyright (C) 2016 J.F.Dockes
 *   This program is free software; you can redistribute it and/or modify
 *   it under the terms of the GNU Lesser General Public License as published by
 *   the Free Software Foundation; either version 2.1 of the License, or
 *   (at your option) any later version.
 *
 *   This program is distributed in the hope that it will be useful,
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *   GNU Lesser General Public License for more details.
 *
 *   You should have received a copy of the GNU Lesser General Public License
 *   along with this program; if not, write to the
 *   Free Software Foundation, Inc.,
 *   59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
 */

/* conf_post: manual part included by auto-generated config.h. Avoid
 * being clobbered by autoheader, and undefine some problematic
 * symbols.
 */

// Get rid of macro names which could conflict with other package's
#if defined(UPMPDCLI_NEED_PACKAGE_VERSION) && !defined(UPMPDCLI_PACKAGE_VERSION_DEFINED)
#define UPMPDCLI_PACKAGE_VERSION_DEFINED
static const char *UPMPDCLI_PACKAGE_VERSION = UPMPDCLI_VERSION;
#endif

#define UPMPDCLI_SOURCE

// Newer versions of libupnpp export the UPNP_E_XXX error codes from
// the base upnp lib. In consequence, all inclusions of upnp.h, the
// sole reason of which were the errcodes, have been removed. Ensure
// that we still build with older libupnpp versions by defining the
// few codes we actually return. The exact values have no real
// importance anyway, except for success==0/error==negative.
#ifndef UPNP_E_SUCCESS
#define UPNP_E_SUCCESS            0
#define UPNP_E_INVALID_PARAM        -101
#define UPNP_E_INTERNAL_ERROR        -911
#endif

