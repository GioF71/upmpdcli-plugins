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
        self.__dataset_size = len(dataset)
        # Main storage: Key is album_id
        self.__metadata_by_id: dict[str, list[AlbumPropertyMetadata]] = defaultdict(list)
        # Reverse index: (key, value) -> set of album_ids
        self.__index: dict[tuple[str, str], set[str]] = defaultdict(set)
        # Track which IDs have which keys for the "None" filter logic
        self.__key_presence: dict[str, set[str]] = defaultdict(set)
        self.__representative_ids: dict[tuple[str, str], str] = {}
        curr: AlbumPropertyMetadata
        for curr in dataset:
            self.__metadata_by_id[curr.album_id].append(curr)
            self.__index[(curr.album_property_key, curr.album_property_value)].add(curr.album_id)
            self.__key_presence[curr.album_property_key].add(curr.album_id)
            # Only store the first one we encounter for this specific (key, value)
            if (curr.album_property_key, curr.album_property_value) not in self.__representative_ids:
                self.__representative_ids[(curr.album_property_key, curr.album_property_value)] = curr.album_id

    @property
    def size(self) -> int:
        return self.__dataset_size

    @property
    def keys(self) -> set[str]:
        # Derived from the keys in our presence tracker
        return set(self.__key_presence.keys())

    def get_album_id_set_for_key(self, key: str) -> set[str]:
        return self.__key_presence.get(key, set())

    def get_values(self, key: str) -> set[str]:
        # Extract values from the tuple keys in our index
        return {k[1] for k in self.__index.keys() if k[0] == key}

    def get_value_count_by_key(self, key: str) -> int:
        # Efficiently calculates unique values without storing a separate dict
        return len(self.get_values(key))

    def get_album_id_set_by_key_value(self, key: str, value: str) -> set[str]:
        return self.__index.get((key, value), set())

    def get_album_id_count_for_key(self, key: str) -> int:
        # Returns the number of unique album_ids that have this property key
        return len(self.__key_presence.get(key, set()))

    def get_missing_album_ids_for_key(self, key: str) -> set[str]:
        # Returns album_ids that have NO entries for the specified key
        return self.album_id_set - self.__key_presence.get(key, set())
    
    def get_all_value_counts(self) -> dict[str, int]:
        # Aggregates the number of unique values for every key in one pass
        counts: dict[str, int] = defaultdict(int)
        
        # self.__index.keys() contains tuples of (key, value)
        for prop_key, _ in self.__index.keys():
            counts[prop_key] += 1
            
        return dict(counts)
        
    def get_value_frequencies(self, key: str) -> dict[str, int]:
        # Returns a mapping of {value: count_of_albums} for a specific key
        # e.g., {"Rock": 15, "Pop": 10}
        frequencies: dict[str, int] = {}
        # We look at our index keys that match the requested property key
        for (prop_key, prop_val), album_ids in self.__index.items():
            if prop_key == key:
                frequencies[prop_val] = len(album_ids)
        return frequencies
    
    @property
    def album_id_set(self) -> set[str]:
        return set(self.__metadata_by_id.keys())

    @property
    def album_id_count(self) -> int:
        return len(self.__metadata_by_id)

    def get_representative_album_id(self, key: str, value: str) -> str | None:
        """Returns a single album_id for cover art purposes without fetching the full set."""
        return self.__representative_ids.get((key, value))
    
    def _get_by_album_id(self) -> dict[str, list[AlbumPropertyMetadata]]:
        return self.__metadata_by_id


class AlbumPropertyDatasetProcessor:
    
    def __init__(self, dataset: AlbumPropertyDataset):
        self.__dataset = dataset

    def apply_filters(self, filter_list: list[AlbumPropertyKeyValue]) -> AlbumPropertyDataset:
        if not filter_list:
            return self.__dataset

        # Start with all possible IDs
        all_ids = self.__dataset.album_id_set
        matching_ids = all_ids

        for f in filter_list:
            if f.value is None:
                # Albums that DO NOT have this key
                current_match = all_ids - self.__dataset.get_album_id_set_for_key(f.key)
            else:
                current_match = self.__dataset.get_album_id_set_by_key_value(f.key, f.value)
            
            # Efficient intersection
            matching_ids &= current_match
            
            # Short-circuit: if no IDs match, stop processing filters
            if not matching_ids:
                break

        # Reconstruct the dataset
        by_id = self.__dataset._get_by_album_id()
        filtered_metadata = [
            item 
            for aid in matching_ids 
            for item in by_id.get(aid, [])
        ]
        
        return AlbumPropertyDataset(filtered_metadata)
