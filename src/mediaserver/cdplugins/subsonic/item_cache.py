from item_identifier import ItemIdentifier
from item_identifier_key import ItemIdentifierKey

class ItemCache:
    
    def __init__(self):
        self.__thing_map : dict[str, ItemIdentifier] = {}
        
    def get_thing_map(self) -> dict[str, ItemIdentifier]:
        return self.__thing_map
    
    def has(self, key : str) -> bool:
        return key in self.__thing_map
    
    def get(self, key : str) -> bool:
        if not self.has(key): raise Exception(f"Key {key} not found")
        return self.__thing_map[key]
    
    def add(self, 
            key : str, 
            item_identifier : ItemIdentifier, 
            allow_update : bool = True) -> ItemIdentifier:
        if not allow_update and self.has(key): raise Exception(f"Item with key {key} already here")
        self.__thing_map[key] = item_identifier