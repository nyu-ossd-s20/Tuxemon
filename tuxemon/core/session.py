class Session(object):
    """

    Contains Control, World, and Player

    """
    def __init__(self, control, world, player):
        self.control = control
        self.world = world
        self.player = player


local_session = Session(None, None, None)
