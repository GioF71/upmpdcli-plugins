# Copyright (C) 2023 Giovanni Fulco
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

from radio_station_entry import RadioStationEntry

codec_flac : str = "flac"
codec_aac : str = "aac"

mimetype_flac : str = "audio/flac"
mimetype_aac : str = "audio/aac"

radio_station_list : list[RadioStationEntry] = list()
radio_station_list.append(RadioStationEntry(id = 1, url = "http://stream.radioparadise.com/flacm", title = "RP Main Mix", codec = codec_flac, mimetype = mimetype_flac))
radio_station_list.append(RadioStationEntry(id = 2, url = "http://stream.radioparadise.com/aac-128", title = "RP Main Mix", codec = codec_aac, mimetype = mimetype_aac))
radio_station_list.append(RadioStationEntry(id = 3, url = "http://stream.radioparadise.com/mellow-flacm", title = "RP Mellow Mix", codec = codec_flac, mimetype = mimetype_flac))
radio_station_list.append(RadioStationEntry(id = 4, url = "http://stream.radioparadise.com/mellow-128", title = "RP Mellow Mix", codec = codec_aac, mimetype = mimetype_aac))
radio_station_list.append(RadioStationEntry(id = 5, url = "http://stream.radioparadise.com/rock-flacm", title = "RP Rock Mix", codec = codec_flac, mimetype = mimetype_flac))
radio_station_list.append(RadioStationEntry(id = 6, url = "http://stream.radioparadise.com/rock-128", title = "RP Rock Mix", codec = codec_aac, mimetype = mimetype_aac))
radio_station_list.append(RadioStationEntry(id = 7, url = "http://stream.radioparadise.com/global-flacm", title = "RP Global Mix", codec = codec_flac, mimetype = mimetype_flac))
radio_station_list.append(RadioStationEntry(id = 8, url = "http://stream.radioparadise.com/global-128", title = "RP Global Mix", codec = codec_aac, mimetype = mimetype_aac))
