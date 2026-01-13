from abc import ABC, abstractmethod

class BaseServer(ABC):

    @abstractmethod
    def close(self):
        return