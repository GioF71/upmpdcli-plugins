from item_identifier_key import ItemIdentifierKey

class ItemIdentifier:
    
    def __init__(self, name : str, value : any):
        self.__dict : dict[str, any] = {}
        if not name: raise Exception("name cannot be empty")
        self.set(ItemIdentifierKey.THING_NAME, name)
        self.set(ItemIdentifierKey.THING_VALUE, value)

    def has(self, key : ItemIdentifierKey):
        return key.getName() in self.__dict
    
    def get(self, key : ItemIdentifierKey):
        return self.__dict[key.getName()] if key.getName() in self.__dict else None

    def set(self, key : ItemIdentifierKey, value):
        if not self.__valid_key(key): raise Exception(f"Key {key.getName() if key else None} already set")
        self.__dict[key.getName()] = value
        
    def __valid_key(self, key : str) -> bool:
        return key and key.getName() and not key.getName() in self.__dict

