# -*- coding: utf-8 -*-
#
# Tuxemon
# Copyright (C) 2014, William Edwards <shadowapex@gmail.com>,
#                     Benjamin Bean <superman2k5@gmail.com>
#
# This file is part of Tuxemon.
#
# Tuxemon is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Tuxemon is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Tuxemon.  If not, see <http://www.gnu.org/licenses/>.
#
# Contributor(s):
#
# William Edwards <shadowapex@gmail.com>
# Leif Theden <leif.theden@gmail.com>
#
from __future__ import absolute_import, division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import time

import pygame as pg

from tuxemon.core import cli, networking
from tuxemon.core.clock import Clock
from tuxemon.core.platform import android
from tuxemon.core.state import StateManager
from tuxemon.core.world import World

logger = logging.getLogger(__name__)


class Control(StateManager):
    """

    Contains game loop, platform event handling, and a single world

    """

    def __init__(self, config):
        """ Constructor

        :param TuxemonConfig config: Tuxemon game config/settings
        """
        super(Control, self).__init__()
        self.config = config

        # TODO: move out and into new PygameControl class
        self.input_manager = None
        self.screen = None
        self.init_platform()

        self.world = World()
        self.scheduler = Clock()
        self.current_time = 0.0
        self.exit = False

        # TODO: move out to state manager
        self.package = "tuxemon.core.states"
        self._state_queue = list()
        self._state_dict = dict()
        self._state_stack = list()
        self._state_resume_set = set()
        self._remove_queue = list()

        # Set up our networked controller if enabled.
        self.server = None
        self.client = None
        self.ishost = False
        self.isclient = False
        self.controller_server = None
        if self.config.net_controller_enabled:
            self.server = networking.TuxemonServer(self)
            self.client = networking.TuxemonClient(self)
            self.controller_server = networking.ControllerServer(self)
            # self.combat_engine = CombatEngine(self)
            # self.combat_router = CombatRouter(self, self.combat_engine)

        # Set up the command line. This provides a full python shell for
        # troubleshooting. You can view and manipulate any variables in
        # the game.
        if self.config.cli:
            self.cli = cli.CommandLine(self)

    def init_platform(self):
        """ WIP.  Eventually make options for more input types/handlers

        :return:
        """
        # leave imports here
        import pygame
        from tuxemon.core.platform.platform_pygame.events import PygameEventQueueHandler

        self.input_manager = PygameEventQueueHandler()
        self.screen = pygame.display.get_surface()

    def process_events(self, events):
        """ Process all events for this frame.

        Events are first sent to the active state.
        States can choose to keep the events or return them.
        If they are kept, no other state nor the event engine will get that event.
        If they are returned, they will be passed to the next state.
        Kept or returned, the state may process it.
        Eventually, if all states have returned the event, it will go to the event engine.
        The event engine also can keep or return the event.
        All unused events will be added to Control.key_events each frame.
        Conditions in the the event system can then check that list.

        States can "keep" events by simply returning None from State.process_event

        :param events: Sequence of pg events
        :returns: Iterator of game events
        :rtype: collections.Iterable[pg.event.Event]

        """
        for game_event in events:
            if game_event:
                game_event = self._send_event(game_event)
                if game_event:
                    yield game_event

    def _send_event(self, game_event):
        """ Send event down processing chain

        Probably a poorly named method.  Beginning from top state,
        process event, then as long as a new event is returned from
        the state, the event will be processed by the next active
        state in the stack.

        The final destination for the event will be the event engine.

        :returns: Game Event
        :rtype: pg.event.Event

        """
        for state in self.active_states:
            game_event = state.process_event(game_event)
            if game_event is None:
                break
        else:
            # If no states have handled the event, send it to the World
            game_event = self.world.process_platform_event(game_event)

        return game_event

    def run(self):
        """ Initiates the main game loop. Since we are using Asteria networking
        to handle network events, we pass this core.control.Control instance to
        networking which in turn executes the "main_loop" method every frame.
        This leaves the networking component responsible for the main loop.

        :rtype: None
        """
        update = self.update
        screen = self.screen
        flip = pg.display.update

        def draw(dt):
            self.draw(screen)
            flip()

        self.scheduler.schedule(update, 1 / 100., repeat=True)
        self.scheduler.schedule(draw, 1 / self.config.fps, repeat=True)

        while not self.exit:
            self.scheduler.tick()
            next_event = self.scheduler.get_idle_time()
            if next_event > .001:
                time.sleep(next_event / 2.)

    def update(self, time_delta):
        """Main loop for entire game. This method gets update every frame
        by Asteria Networking's "listen()" function. Every frame we get the
        amount of time that has passed each frame, check game conditions,
        and draw the game to the screen.

        :type time_delta: float
        :rtype: None
        :returns: None

        """
        # Android-specific check for pause
        if android and android.check_pause():
            android.wait_for_resume()

        # Update our networking
        if self.controller_server and self.controller_server:
            self.controller_server.update()
        if self.client and self.client.listening:
            self.client.update(time_delta)
        if self.server and self.server.listening:
            self.server.update()

        # TODO: phase this out in favor of event-dispatch
        # get all the waiting input events, handle them, return the unused events
        events = self.input_manager.process_events()
        events = list(self.process_events(events))
        self.key_events = events

        # Update the game engine
        self.world.update(time_delta)
        self.update_states(time_delta)

    def release_controls(self):
        """ Send inputs which release held buttons/axis

        Use to prevent player from holding buttons while state changes

        :return:
        """
        events = self.input_manager.release_controls()
        self.key_events = list(self.process_events(events))

    def update_states(self, dt):
        """ Checks if a state is done or has called for a game quit.

        :param dt: Time delta - Amount of time passed since last frame.

        :type dt: Float
        """

        for state in self.active_states:
            state.update(dt)

        current_state = self.current_state

        # handle case where the top state has been dismissed
        if current_state is None:
            self.exit = True

        if current_state in self._state_resume_set:
            current_state.resume()
            self._state_resume_set.remove(current_state)

    def draw(self, surface):
        """ Draw all active states

        :type surface: pg.surface.Surface
        """
        # TODO: refactor into Widget

        # iterate through layers and determine optimal drawing strategy
        # this is a big performance boost for states covering other states
        # force_draw is used for transitions, mostly
        to_draw = list()
        full_screen = surface.get_rect()
        for state in self.active_states:
            to_draw.append(state)

            # if this state covers the screen
            # break here so lower screens are not drawn
            if (not state.transparent
                    and state.rect == full_screen
                    and not state.force_draw):
                break

        # draw from bottom up for proper layering
        for state in reversed(to_draw):
            state.draw(surface)

    def handle_fps(self, clock_tick, fps_timer, frames):
        """

        :param clock_tick:
        :param fps_timer:
        :param frames:
        :rtype: Tuple[Float, Float]
        """
        if self.config.show_fps:
            fps_timer += clock_tick
            if fps_timer >= 1:
                with_fps = "{} - {:.2f} FPS".format(self.config.caption, frames / fps_timer)
                pg.display.set_caption(with_fps)
                return 0, 0
            return fps_timer, frames
        return 0, 0
