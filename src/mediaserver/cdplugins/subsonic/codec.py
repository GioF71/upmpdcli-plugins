import uuid

class Codec:

    def __init__(self):
        self.__by_name : dict[str, str] = {}
        self.__by_id : dict[str, str] = {}

    def encode(self, name : str) -> str:
        by_id : str = self.__by_name[name] if name in self.__by_name else None
        if not by_id:
            new_id : str = uuid.uuid4().hex
            self.__by_id[new_id] = name
            self.__by_name[name] = new_id
            by_id = new_id
        return by_id
    
    def decode(self, id : str) -> str:
        if id in self.__by_id: return self.__by_id[id]
        raise Exception("Id not found")

