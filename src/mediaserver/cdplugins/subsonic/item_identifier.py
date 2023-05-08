from item_identifier_key import ItemIdentifierKey
import copy

class ItemIdentifier:

    @classmethod
    def from_dict(cls, id_dict : dict[str, any]):
        thing_name : str = ItemIdentifier.__check_mandatory(id_dict, ItemIdentifierKey.THING_NAME)
        thing_value : any = ItemIdentifier.__check_mandatory(id_dict, ItemIdentifierKey.THING_VALUE)
        id : ItemIdentifier = cls(thing_name, thing_value)
        for k,v in id_dict.items():
            if not id.__has_name(k):
                id.__set(k, v)
        return id
        
    def __check_mandatory(id_dict : dict[str, any], id_key : ItemIdentifierKey) -> any:
        if not id_key.getName() in id_dict: raise Exception("Mandatory [{id_key.getName()}] missing")
        return id_dict[id_key.getName()]

    def __init__(self, name : str, value : any):
        self.__dict : dict[str, any] = {}
        if not name: raise Exception("name cannot be empty")
        if not value: raise Exception("value cannot be empty")
        self.set(ItemIdentifierKey.THING_NAME, name)
        self.set(ItemIdentifierKey.THING_VALUE, value)

    def getDictionary(self):
        return copy.deepcopy(self.__dict)

    def has(self, key : ItemIdentifierKey):
        return self.__has_name(key.getName())
    
    def __has_name(self, name : str):
        return name in self.__dict
    
    def get(self, key : ItemIdentifierKey, defaultValue : any = None):
        return self.__get(key.getName(), defaultValue)

    def __get(self, key_name : str, defaultValue : any = None):
        return self.__dict[key_name] if key_name in self.__dict else defaultValue

    def set(self, key : ItemIdentifierKey, value):
        if not self.__valid_key(key): raise Exception(f"Key {key.getName() if key else None} already set")
        self.__set(key.getName(), value)
        
    def __set(self, key_name : str, value):
        if not self.__valid_key_name(key_name): raise Exception(f"Key {key_name} already set")
        self.__dict[key_name] = value

    def __valid_key(self, key : ItemIdentifierKey) -> bool:
        return key and self.__valid_key_name(key.getName())

    def __valid_key_name(self, key_name : str) -> bool:
        return key_name and not key_name in self.__dict

