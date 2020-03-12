class Session(object):
    """

    Contains Control, World, and Player

    Eventually this will be extended to support network sessions

    """
    def __init__(self, control, world, player):
        """
        :param tuxemon.core.control.Control: Game client
        :param tuxemon.core.world.World: Game world
        :param tuxemon.core.player.Player: Player object
        """
        self.control = control
        self.world = world
        self.player = player


# WIP will be filled in later when game starts
local_session = Session(None, None, None)
