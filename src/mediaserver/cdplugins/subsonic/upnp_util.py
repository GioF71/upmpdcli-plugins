# Copyright (C) 2023,2024,2025 Giovanni Fulco
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import upmplgmodels
import upmpdmeta
import album_util
import constants

from subsonic_connector.album import Album
import html


def set_entry_value(key_name: str, key_value: str, target: dict):
    if key_name and key_value:
        target[key_name] = key_value


def set_class(upnp_class: str, target: dict):
    target["upnp:class"] = upnp_class


def set_class_artist(target: dict):
    set_class(target=target, upnp_class=upmplgmodels.Artist.upnpclass)


def set_class_music_track(target: dict):
    set_class(target=target, upnp_class=upmplgmodels.Track.upnpclass)


def set_class_album(target: dict):
    set_class(target=target, upnp_class=upmplgmodels.Album.upnpclass)


def set_class_playlist_container(target: dict):
    set_class(target=target, upnp_class=upmplgmodels.Playlist.upnpclass)


def set_track_number(track_number: str, target: dict):
    target['upnp:originalTrackNumber'] = track_number


def get_album_art_uri(entry: dict):
    return entry['upnp:albumArtURI'] if 'upnp:albumArtURI' in entry else None


def set_album_art_from_uri(album_art_uri: str, target: dict):
    set_entry_value(key_name="upnp:albumArtURI", key_value=album_art_uri, target=target)


def set_track_title(track_title: str, target: dict):
    set_entry_value(key_name="tt", key_value=track_title, target=target)


def set_album_id(album_id: str, target: dict):
    target['album_id'] = album_id


def set_artist(artist: str, target: dict):
    target["upnp:" + constants.UpnpMeta.ARTIST.value] = artist


def set_date_from_album(album: Album, target: dict):
    date_str: str = album_util.get_album_original_release_date(album)
    if not date_str:
        # fallback to year
        date_str = str(album.getYear()) if album.getYear() else ""
    set_date_str(date_str=date_str, target=target)


def set_date_str(date_str: str, target: dict):
    target['dc:date'] = date_str


def get_as_int(entry_key: str, entry: dict) -> int:
    v: str = (entry[entry_key]
              if entry_key in entry else None)
    return int(v) if v else None


def get_bit_depth(entry: dict) -> int:
    return get_as_int(entry_key="res:bitsPerSample", entry=entry)


def set_bit_depth(bit_depth: int, target: dict):
    if bit_depth:
        target["res:bitsPerSample"] = str(bit_depth)


def get_channel_count(entry: dict) -> int:
    return get_as_int(entry_key="res:channels", entry=entry)


def set_channel_count(channel_count: int, target: dict):
    if channel_count:
        target['res:channels'] = str(channel_count)


def get_sample_reate(entry: dict) -> int:
    return get_as_int(entry_key="res:samplefreq", entry=entry)


def set_sample_rate(sample_rate: int, target: dict):
    if sample_rate:
        target['res:samplefreq'] = str(sample_rate)


def get_bit_rate(entry: dict) -> int:
    return get_as_int(entry_key="kbs", entry=entry)


def set_bit_rate(bit_rate: int, target: dict):
    if bit_rate:
        target['kbs'] = str(bit_rate)


def get_mimetype(entry: dict[str, any]) -> str:
    return entry["res:mime"] if "res:mime" in entry else None

def set_mimetype(mimetype: str, target: dict):
    if mimetype:
        target['res:mime'] = mimetype


def build_didlfrag(key: str, role: str, value: str):
    return f"<{key} role=\"{role}\">{html.escape(value)}</{key}>"


def set_didlfrag(didlfrag: str, target: dict):
    if didlfrag:
        target["didlfrag"] = didlfrag


def set_raw_metadata(raw_metadata_name: str, metadata_value: str, target: dict):
    if not metadata_value:
        return
    if isinstance(metadata_value, int):
        metadata_value = str(metadata_value)
    if len(metadata_value) > 0:
        target[raw_metadata_name] = metadata_value


def set_upnp_meta(metadata_name: constants.UpnpMeta, metadata_value: str, target: dict):
    set_raw_metadata(
        raw_metadata_name=f"upnp:{metadata_name.value}",
        metadata_value=metadata_value,
        target=target)


def set_upmpd_meta(metadata_name: upmpdmeta.UpMpdMeta, metadata_value: str, target: dict):
    set_raw_metadata(
        raw_metadata_name=f"upmpd:{metadata_name.value}",
        metadata_value=metadata_value,
        target=target)
