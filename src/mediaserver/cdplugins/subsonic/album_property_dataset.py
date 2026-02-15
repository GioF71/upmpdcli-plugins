# Copyright (C) 2026 Giovanni Fulco
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


from album_property_metadata import AlbumPropertyMetadata
from album_property_key import AlbumPropertyKeyValue
from collections import defaultdict


class AlbumPropertyDataset:

    def __init__(self, dataset: list[AlbumPropertyMetadata]):
        self.__dataset_size: int = len(dataset)
        self.__dataset: dict[str, list[AlbumPropertyMetadata]] = defaultdict(list)
        self.__key_set: set[str] = set()
        self.__album_id_set: set[str] = set()
        self.__values_by_key: dict[str, set[str]] = defaultdict(set)
        self.__album_id_with_key: dict[str, set[str]] = defaultdict(set)
        self.__album_id_by_key_value: dict[tuple[str, str], set[str]] = defaultdict(set)
        self.__metadata_by_album_id: dict[str, list[AlbumPropertyMetadata]] = defaultdict(list)
        curr: AlbumPropertyMetadata
        for curr in dataset:
            self.__dataset[curr.album_property_key].append(curr)
            self.__album_id_set.add(curr.album_id)
            self.__album_id_with_key[curr.album_property_key].add(curr.album_id)
            self.__key_set.add(curr.album_property_key)
            self.__values_by_key[curr.album_property_key].add(curr.album_property_value)
            self.__album_id_by_key_value[(curr.album_property_key, curr.album_property_value)].add(curr.album_id)
            self.__metadata_by_album_id[curr.album_id].append(curr)

    @property
    def size(self) -> int:
        return self.__dataset_size

    @property
    def keys(self) -> list[str]:
        return list(self.__key_set)

    def get_album_id_set_for_key(self, key: str) -> set[str]:
        album_id_set_by_key: set[str] = self.__album_id_with_key[key] if key in self.__album_id_with_key else set()
        return album_id_set_by_key

    def get_album_id_count_for_key(self, key: str) -> int:
        return len(self.get_album_id_set_for_key(key=key))

    def get_values(self, key: str) -> list[str]:
        return list(self.__values_by_key[key]) if key in self.__values_by_key else []

    def get_album_id_set_by_key_value(self, key: str, value: str) -> list[str]:
        return self.__album_id_by_key_value[(key, value)] if (key, value) in self.__album_id_by_key_value else set()

    def get_album_id_count_by_key_value(self, key: str, value: str) -> int:
        return len(self.__album_id_by_key_value[(key, value)]) if (key, value) in self.__album_id_by_key_value else 0

    def get_album_id_list_by_key_value(self, key: str, value: str) -> list[str]:
        return list(self.__album_id_by_key_value[(key, value)]) if (key, value) in self.__album_id_by_key_value else []

    @property
    def album_id_count(self) -> int:
        return len(self.__album_id_set)

    @property
    def album_id_set(self) -> set[str]:
        return self.__album_id_set

    @property
    def album_id_list(self) -> list[str]:
        return list(self.album_id_set)

    def _get_by_album_id(self) -> dict[str, list[AlbumPropertyMetadata]]:
        return self.__metadata_by_album_id


class AlbumPropertyDatasetProcessor:

    def __init__(
            self,
            dataset: AlbumPropertyDataset):
        self.__dataset: AlbumPropertyDataset = dataset

    def apply_filters(self, filter_list: list[AlbumPropertyKeyValue]) -> AlbumPropertyDataset:
        by_album_id: dict[str, list[AlbumPropertyMetadata]] = self.__dataset._get_by_album_id()
        # ok, now we filter.
        matching_album_id_set: set[str] = set(by_album_id.keys())
        curr_filter: AlbumPropertyKeyValue
        for curr_filter in filter_list if filter_list else []:
            # filter with key or with None?
            if curr_filter.value is None:
                # find matching.
                matching_none: set[str] = self.__dataset.album_id_set - self.__dataset.get_album_id_set_for_key()
                # calculate intersection
                matching_album_id_set = matching_album_id_set & matching_none
            else:
                matching_value: set[str] = self.__dataset.get_album_id_set_by_key_value(
                    key=curr_filter.key,
                    value=curr_filter.value)
                # calculate intersection
                matching_album_id_set = matching_album_id_set & matching_value
        # build list of matching.
        metadata_list: list[AlbumPropertyMetadata] = [item for album_id in matching_album_id_set
                                                      if album_id in by_album_id
                                                      for item in by_album_id[album_id]]
        return AlbumPropertyDataset(metadata_list)
