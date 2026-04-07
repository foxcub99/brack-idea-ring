from leader import Leader

class Team:
    def __init__(self, name):
        self.name = name
        self.members = []

    def add_member(self, member: Leader):
        self.members.append(member)

    def remove_member(self, member: Leader):
        if member in self.members:
            self.members.remove(member)

    def get_members(self):
        return self.members