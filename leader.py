from enum import Enum

class LeaderType(Enum):
    ADULT = "Adult"
    LITE = "Lite"
    
class Site(Enum):
    MIRANDA = "Miranda"
    KIRRAWEE = "Kirrawee"

class Leader:
    def __init__(self, name):
        self.name = name
        self.type = None
        self.site = None
        
    def __str__(self):
        return f"{self.name}"