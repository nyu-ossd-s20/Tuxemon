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
# Derek Clark <derekjohn.clark@gmail.com>
# Leif Theden <leif.theden@gmail.com>
#
#
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os.path
import re
from six.moves import zip_longest
from itertools import product

from tuxemon.compat import Rect
import pygame

import tuxemon.core.monster
import tuxemon.core.sprite
from tuxemon.core import prepare
from tuxemon.core import pyganim
from tuxemon.core.db import db
from tuxemon.core.platform import mixer

logger = logging.getLogger(__name__)


def get_cell_coordinates(rect, point, size):
    """Find the cell of size, within rect, that point occupies."""
    cell = [None, None]
    point = (point[0] - rect.x, point[1] - rect.y)
    cell[0] = (point[0] // size[0]) * size[0]
    cell[1] = (point[1] // size[1]) * size[1]
    return tuple(cell)


def transform_resource_filename(*filename):
    """ Appends the resource folder name to a filename

    :param filename: String
    :rtype: basestring
    """
    return prepare.fetch(*filename)


def load_animated_sprite(filenames, delay, **rect_kwargs):
    """ Load a set of images and return an animated pygame sprite

    Image name will be transformed and converted
    Rect attribute will be set

    Any keyword arguments will be passed to the get_rect method
    of the image for positioning the rect.

    :param filenames: Filenames to load
    :param int delay: Frame interval; time between each frame
    :rtype: core.sprite.Sprite
    """
    anim = []
    for filename in filenames:
        if os.path.exists(filename):
            image = load_and_scale(filename)
            anim.append((image, delay))

    tech = pyganim.PygAnimation(anim, True)
    tech.play()
    sprite = tuxemon.core.sprite.Sprite()
    sprite.image = tech
    sprite.rect = sprite.image.get_rect(**rect_kwargs)
    return sprite


def new_scaled_rect(*args, **kwargs):
    """ Create a new rect and scale it

    :param args: Normal args for a Rect
    :param kwargs: Normal kwargs for a Rect
    :rtype: Rect.Rect
    """
    rect = Rect(*args, **kwargs)
    return scale_rect(rect)


def scale_rect(rect, factor=prepare.SCALE):
    """ Scale a rect.  Returns a new object.

    :param rect: pygame Rect
    :param factor: int
    :rtype: Rect.Rect
    """
    return Rect([i * factor for i in list(rect)])


def scale_sequence(sequence):
    """ Scale the thing

    :param sequence:
    :rtype: list
    """
    return [i * prepare.SCALE for i in sequence]


def scale(number):
    """ Scale the thing

    :param number: int
    :rtype: int
    """
    return prepare.SCALE * number


def check_parameters(parameters, required=0, exit=True):
    """
    Checks to see if a given list has the required number of items
    """
    if len(parameters) < required:
        import inspect
        calling_function = inspect.stack()[1][3]
        logger.error("'" + calling_function + "' requires at least " + str(required) + "parameters.")
        if exit:
            import sys
            sys.exit(1)
        return False

    else:
        return True


def load_sound(slug):
    """ Load a sound from disk, identified by it's slug in the db

    :param slug: slug for the file record to load
    :type slug: String
    :rtype: core.platform.mixer.Sound
    """

    class DummySound(object):
        def play(self):
            pass

    # get the filename from the db
    filename = db.lookup_file("sounds", slug)
    filename = transform_resource_filename("sounds", filename)

    # on some platforms, pygame will silently fail loading
    # a sound if the filename is incorrect so we check here
    if not os.path.exists(filename):
        msg = 'audio file does not exist: {}'.format(filename)
        logger.error(msg)
        return DummySound()

    try:
        return mixer.Sound(filename)
    except MemoryError:
        # raised on some systems if there is no mixer
        logger.error('memoryerror, unable to load sound')
        return DummySound()
    except pygame.error as e:
        # pick one:
        # * there is no mixer
        # * sound has invalid path
        # * mixer has no output (device ok, no speakers)
        logger.error(e)
        logger.error('unable to load sound')
        return DummySound()


def get_avatar(game, avatar):
    """Gets the avatar sprite of a monster or NPC.

    Used to parse the string values for dialog event actions
    If avatar is a number, we're referring to a monster slot in the player's party
    If avatar is a string, we're referring to a monster by name
    TODO: If the monster name isn't found, we're referring to an NPC on the map

    :param avatar: the avatar to be used
    :type avatar: string
    :rtype: Optional[pygame.Surface]
    :returns: The surface of the monster or NPC avatar sprite
    """
    if avatar and avatar.isdigit():
        try:
            player = game.player1
            slot = int(avatar)
            return player.monsters[slot].get_sprite("menu")
        except IndexError:
            logger.debug("invalid avatar monster slot")
            return None
    else:
        try:
            avatar_monster = tuxemon.core.monster.Monster()
            avatar_monster.load_from_db(avatar)
            avatar_monster.flairs = {}  # Don't use random flair graphics
            return avatar_monster.get_sprite("menu")
        except KeyError:
            logger.debug("invalid avatar monster name")
            return None


def calc_dialog_rect(screen_rect):
    """ Return a rect that is the area for a dialog box on the screen

    :param screen_rect:
    :return:
    """
    rect = screen_rect.copy()
    if prepare.CONFIG.large_gui:
        rect.height *= .4
        rect.bottomleft = screen_rect.bottomleft
    else:
        rect.height *= .25
        rect.width *= .8
        rect.center = screen_rect.centerx, screen_rect.bottom - rect.height
    return rect


def open_dialog(game, text, avatar=None, menu=None):
    """ Open a dialog with the standard window size

    :param game:
    :param text: list of strings
    :param avatar: optional avatar sprite
    :param menu: optional menu object

    :rtype: core.states.dialog.DialogState
    """
    rect = calc_dialog_rect(game.screen.get_rect())
    return game.push_state("DialogState", text=text, avatar=avatar, rect=rect, menu=menu)


def nearest(l):
    """ Use rounding to find nearest tile

    :param l:
    :return:
    """
    return tuple(int(round(i)) for i in l)


def trunc(l):
    return tuple(int(i) for i in l)


def round_to_divisible(x, base=16):
    """Rounds a number to a divisible base. This is used to round collision areas that aren't
    defined well. This function assists in making sure collisions work if the map creator
    didn't set the collision areas to round numbers.

    **Examples:**

    >>> round_to_divisible(31.23, base=16)
    32
    >>> round_to_divisible(17.8, base=16)
    16

    :param x: The number we want to round.
    :param base: The base that we want our number to be divisible by. (Default: 16)

    :type x: Float
    :type base: Integer

    :rtype: Integer
    :returns: Rounded number that is divisible by "base".
    """
    return int(base * round(float(x) / base))


def snap_point(point, tile_size):
    """

    :param point:
    :param tile_size:
    :return:
    """
    return (round_to_divisible(point[0], tile_size[0]),
            round_to_divisible(point[1], tile_size[1]))


def split_escaped(string_to_split, delim=","):
    """Splits a string by the specified deliminator excluding escaped
    deliminators.

    :param string_to_split: The string to split.
    :param delim: The deliminator to split the string by.

    :type string_to_split: Str
    :type delim: Str

    :rtype: List
    :returns: A list of the splitted string.

    """
    # Split by "," unless it is escaped by a "\"
    split_list = re.split(r'(?<!\\)' + delim, string_to_split)

    # Remove the escape character from the split list
    split_list = [w.replace('\,', ',') for w in split_list]

    # strip whitespace around each
    split_list = [i.strip() for i in split_list]

    return split_list


def snap_rect(x, y, w, h, tile_size):
    """ Snap the vertices to a grid, pixels to tiles

    :param int x:
    :param int y:
    :param int w:
    :param int h:
    :param tile_size:
    :return:
    """
    tw, th = tile_size
    w = round_to_divisible(w, tw) / tw
    h = round_to_divisible(h, th) / th
    x = round_to_divisible(x, tw) / tw
    y = round_to_divisible(y, th) / th
    return x, y, w, h


def tiles_inside_aabb(rect):
    """ Return all the tiles which are contained by this aabb

    :param rect:
    :return:
    """
    x, y, width, height = rect
    for a, b in product(range(width), range(height)):
        yield a + x, b + y


def number_or_variable(game, value):
    """ Returns a numeric game variable by its name
    If value is already a number, convert from string to float and return that

    :param game:
    :param value: Union[str, float, int]

    :rtype: float

    :raises: ValueError
    """
    player = game.player1
    if value.isdigit():
        return float(value)
    else:
        try:
            return float(player.game_variables[value])
        except (KeyError, ValueError, TypeError):
            logger.error("invalid number or game variable {}".format(value))
            raise ValueError


def cast_values(parameters, valid_parameters):
    """ Change all the string values to the expected type

    This will also check and enforce the correct parameters for actions

    :param parameters:
    :param valid_parameters:
    :return:
    """

    # TODO: stability/testing
    def cast(i):
        ve = False
        t, v = i
        try:
            for tt in t[0]:
                if tt is None:
                    return None

                try:
                    return tt(v)
                except ValueError:
                    ve = True

        except TypeError:
            if v is None:
                return None

            if v == '':
                return None

            return t[0](v)

        if ve:
            raise ValueError

    try:
        return list(map(cast, zip_longest(valid_parameters, parameters)))
    except ValueError:
        logger.error("Invalid parameters passed:")
        logger.error("expected: {}".format(valid_parameters))
        logger.error("got: {}".format(parameters))
        raise
