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
from collections import defaultdict


class AlbumPropertyDataset:

    def __init__(self):
        # Storage
        self.__metadata_by_id: dict[str, AlbumPropertyMetadata] = defaultdict(list)
        self.__index: dict[tuple[str, str], set[str]] = defaultdict(set)        # (key, val) -> {album_ids}
        self.__key_presence: dict[str, set[str]] = defaultdict(set) # key -> {album_ids}
        self.__representative_ids: dict[str, str] = {}         # (key, val) -> one sample album_id
        self.__dataset_size: int = 0

    def push(self, meta: AlbumPropertyMetadata):
        aid: str = meta.album_id
        k: str = meta.album_property_key
        v: str = meta.album_property_value
        kid: tuple[str, str] = (k, v)
        # 1. Store the full metadata object
        self.__metadata_by_id[aid].append(meta)
        # 2. Update the inverted indices
        self.__index[kid].add(aid)
        self.__key_presence[k].add(aid)
        # 3. Store a representative for thumbnails/UI
        if kid not in self.__representative_ids:
            self.__representative_ids[kid] = aid
        self.__dataset_size += 1


    @property
    def keys(self) -> list[str]:
        """Returns sorted list of all unique metadata keys."""
        return sorted(self.__key_presence.keys())

    @property
    def album_id_count(self) -> int:
        """Returns the number of unique album IDs. Faster than len(album_id_set)."""
        return len(self.__metadata_by_id)

    def get_values(self, key: str) -> list[str]:
        """Returns sorted list of all unique values for a specific key, ignoring None."""
        return sorted({v for (k, v) in self.__index.keys() if k == key and v is not None})

    def get_all_value_counts(self) -> dict[str, int]:
        """Returns {key: count_of_unique_values} mapping."""
        counts = defaultdict(int)
        for prop_key, _ in self.__index.keys():
            counts[prop_key] += 1
        return dict(counts)

    def get_value_frequencies(self, key: str) -> dict[str, int]:
        """Returns {value: album_count} for a specific key."""
        frequencies = {}
        for (prop_key, prop_val), album_ids in self.__index.items():
            if prop_key == key:
                frequencies[prop_val] = len(album_ids)
        return frequencies

    def get_missing_album_ids_for_key(self, key: str) -> set[str]:
        """Returns album IDs that don't have this key at all."""
        return self.album_id_set - self.get_album_id_set_for_key(key)

    def get_all_missing_ids_by_key(self) -> dict[str, set[str]]:
        """Returns {key: set_of_missing_ids} for every key in the dataset."""
        all_ids = self.album_id_set
        return {
            key: all_ids - present_ids 
            for key, present_ids in self.__key_presence.items()
        }

    def get_representative_album_id(self, key: str, value: str) -> str | None:
        """Returns one album ID that carries this key-value pair."""
        return self.__representative_ids.get((key, value))

    @property
    def size(self) -> int:
        return self.__dataset_size

    @property
    def album_id_set(self) -> set[str]:
        """Returns the set of all unique album IDs in the dataset."""
        return set(self.__metadata_by_id.keys())

    def get_album_id_set_for_key(self, key: str) -> set[str]:
        """Returns all album IDs that have at least one value for this key."""
        return self.__key_presence.get(key, set())

    def get_album_id_count_for_key(self, key: str) -> int:
        return len(self.get_album_id_set_for_key(key))

    def get_album_id_set_by_key_value(self, key: str, value: str) -> set[str]:
        """Returns all album IDs matching a specific key-value pair."""
        return self.__index.get((key, value), set())

    def _get_by_album_id(self) -> dict[str, list]:
        """Internal bridge to bypass Name Mangling in the Processor."""
        return self.__metadata_by_id


class AlbumPropertyDatasetProcessor:

    def __init__(self, dataset: AlbumPropertyDataset):
        self.__dataset = dataset

    def apply_filters(self, filter_list: list) -> AlbumPropertyDataset:
        """
        Filters the dataset based on a list of KeyValue objects.
        Optimized for low-IPC CPUs like the J1900.
        """
        if not filter_list:
            return self.__dataset

        # Bypass Name Mangling to get the raw data map
        by_id_map = self.__dataset._get_by_album_id()
        
        # Start with all available IDs as the universe
        matching_ids = set(by_id_map.keys())
        
        # Localize dataset methods to avoid '.' lookups in the loop
        get_by_key = self.__dataset.get_album_id_set_for_key
        get_by_kv = self.__dataset.get_album_id_set_by_key_value
        for f in filter_list:
            key, val = f.key, f.value
            if val is None:
                # Optimized 'None' filter: Subtract IDs that have the key
                current_match = matching_ids - get_by_key(key)
            else:
                # Direct lookup for key-value matches
                current_match = get_by_kv(key, val)
            # Fast in-place intersection (C-level performance)
            matching_ids &= current_match
            # Short-circuit if we hit zero results
            if not matching_ids:
                break
        # Reconstruct the result list using a flat list comprehension
        filtered_metadata = [
            item 
            for aid in matching_ids 
            for item in by_id_map[aid]
        ]
        res: AlbumPropertyDataset = AlbumPropertyDataset()
        curr: AlbumPropertyMetadata
        for curr in filtered_metadata:
            res.push(curr)
        return res
