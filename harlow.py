# Copyright 2016 Google Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
"""Basic random agent for DeepMind Lab."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse
import random
import numpy as np
import six

import deepmind_lab


def _action(*entries):
  return np.array(entries, dtype=np.intc)


class DiscretizedRandomAgent(object):
  """Simple agent for DeepMind Lab."""

  ACTIONS = {
      'look_left': _action(-120, 0, 0, 0, 0, 0, 0),
      'look_right': _action(120, 0, 0, 0, 0, 0, 0),
  }

  ACTION_LIST = list(six.viewvalues(ACTIONS))

  def __init__(self):
    self.i = 0

    self.rewards = 0

  def step(self, reward, unused_image):
    self.i += 1
    self.rewards += reward
    print(unused_image.shape)
    print("Score:", self.rewards)
    return random.choice(DiscretizedRandomAgent.ACTION_LIST[0:1]) if self.i % 2 == 0 else random.choice(DiscretizedRandomAgent.ACTION_LIST[1:2])
    
    """Gets an image state and a reward, returns an action."""
    return random.choice(DiscretizedRandomAgent.ACTION_LIST)
  
  def reset(self):
    pass


def run(length, width, height, fps, level, record, demo, demofiles, video):
  """Spins up an environment and runs the random agent."""
  config = {
      'fps': str(fps),
      'width': str(width),
      'height': str(height)
  }
  if record:
    config['record'] = record
  if demo:
    config['demo'] = demo
  if demofiles:
    config['demofiles'] = demofiles
  if video:
    config['video'] = video
  env = deepmind_lab.Lab(level, ['RGB_INTERLEAVED'], config=config)

  env.reset()

  agent = DiscretizedRandomAgent()

  reward = 0

  for _ in six.moves.range(length):
    if not env.is_running():
      print('Environment stopped early')
      env.reset()
      agent.reset()
    obs = env.observations()
    action = agent.step(reward, obs['RGB_INTERLEAVED'])
    reward = env.step(action, num_steps=1)

  print('Finished after %i steps. Total reward received is %f'
        % (length, agent.rewards))


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--length', type=int, default=1000,
                      help='Number of steps to run the agent')
  parser.add_argument('--width', type=int, default=80,
                      help='Horizontal size of the observations')
  parser.add_argument('--height', type=int, default=80,
                      help='Vertical size of the observations')
  parser.add_argument('--fps', type=int, default=60,
                      help='Number of frames per second')
  parser.add_argument('--runfiles_path', type=str, default=None,
                      help='Set the runfiles path to find DeepMind Lab data')
  parser.add_argument('--level_script', type=str,
                      default='tests/empty_room_test',
                      help='The environment level script to load')
  parser.add_argument('--record', type=str, default=None,
                      help='Record the run to a demo file')
  parser.add_argument('--demo', type=str, default=None,
                      help='Play back a recorded demo file')
  parser.add_argument('--demofiles', type=str, default=None,
                      help='Directory for demo files')
  parser.add_argument('--video', type=str, default=None,
                      help='Record the demo run as a video')

  args = parser.parse_args()
  if args.runfiles_path:
    deepmind_lab.set_runfiles_path(args.runfiles_path)
  run(args.length, args.width, args.height, args.fps, args.level_script,
      args.record, args.demo, args.demofiles, args.video)
