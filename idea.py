from leader import Site

class Idea:
    def __init__(self, title, description):
        self.title = title
        self.description = description
        self.point = {Site.MIRANDA: None, Site.KIRRAWEE: None}
        self.backupPoint = {Site.MIRANDA: None, Site.KIRRAWEE: None}
        self.rawScore = 0

    def __str__(self):
        return f"Idea: {self.title}\nDescription: {self.description}"