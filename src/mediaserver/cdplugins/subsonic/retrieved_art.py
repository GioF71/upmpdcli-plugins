# Copyright (C) 2023,2024 Giovanni Fulco
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

class RetrievedArt:

    def __init__(self, cover_art : str = None, art_url : str = None):
        self._cover_art : str = cover_art
        self._art_url : str = art_url

    @property
    def cover_art(self) -> str:
        return self._cover_art

    @property
    def art_url(self) -> str:
        return self._art_url
