from idea import Idea

from enum import Enum

class BracketType(Enum):
    ROUND_ROBIN = "Round Robin"
    SINGLE_ELIMINATION = "Single Elimination"
    DOUBLE_ELIMINATION = "Double Elimination"
    SWISS = "Swiss"

class Bracket:
    def __init__(self, name):
        self.name = name
        self.ideas = []
        self.type = None
        
    def add_idea(self, idea: Idea):
        self.ideas.append(idea)
        
    def remove_idea(self, idea: Idea):
        if idea in self.ideas:
            self.ideas.remove(idea)
            
    def get_ideas(self):
        return self.ideas
    
    