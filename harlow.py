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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse
import random
import numpy as np
import six

import deepmind_lab

import os
import tensorflow as tf
from meta_rl.ac_network import AC_Network
from meta_rl.worker import Worker

from datetime import datetime

import threading
import multiprocessing as mp

from skimage import data
from skimage.color import rgb2gray

def process_obs(obs):
    black_and_white = rgb2gray(obs)
    return black_and_white[1][1:3]

class WrapperEnv(object):
  """A gym-like wrapper environment for DeepMind Lab.

  Attributes:
      env: The corresponding DeepMind Lab environment.
      length: Maximum number of frames

  Args:
      env (deepmind_lab.Lab): DeepMind Lab environment.

  """
  def __init__(self, env, length):
    self.env = env
    self.length = length
    self.l = []
    self.reset()

  def step(self, action):
    tmp_obs = self.env.observations()

    reward = self.env.step(np.array([0, 0, 0, 0, 0, 0, 0], dtype=np.intc), num_steps=1)
    self.l.append(process_obs(tmp_obs['RGB_INTERLEAVED']))
    
    done = not self.env.is_running() or self.env.num_steps() > 3600
    if done:
      self.reset()
    
    print("\033[34mAction Taken: " + ("Left" if action[0] > 0 else "Right") + "\033[0m")
    # real step
    obs = self.env.observations()
    reward += self.env.step(action, num_steps=1)
    self.l.append(process_obs(obs['RGB_INTERLEAVED']))

    if reward > 0:
        print("\033[1;32mTrial reward: " + str(reward) + " :)\033[0m")
    else:
        print("\033[1;31mTrial reward: " + str(reward) + " :(\033[0m")
    return process_obs(obs['RGB_INTERLEAVED']), reward, done, self.env.num_steps()

  def reset(self):
    self.env.reset()
    obs = self.env.observations()

    d = np.array(self.l)
    if (len(d) > 2):
        with open("/floyd/home/obs2.npy", "bw") as file:
            file.write(d.dumps())
    self.l = []

    return process_obs(obs['RGB_INTERLEAVED'])

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

  dir_name = "/floyd/home/python/meta_rl/train_" + datetime.now().strftime("%m%d-%H%M%S")

  # Hyperparameters for training/testing
  gamma = .9
  a_size = 2
  n_seeds = 1
  num_episode_train = 2
  num_episode_test = 50
  collect_seed_transition_probs = []
  for seed_nb in range(n_seeds):

    # initialize the directories' names to save the models for this particular seed
    model_path = dir_name+'/model_' + str(seed_nb)
    frame_path = dir_name+'/frames_' + str(seed_nb)
    plot_path = dir_name+'/plots_' + str(seed_nb)
#     load_model_path = "meta_rl/results/biorxiv/final/model_" + str(seed_nb) + "/model-20000"
    load_model_path = "/floyd/home/python/meta_rl/train_0221-132433/model_0/model-13400"

    # create the directories
    if not os.path.exists(model_path):
      os.makedirs(model_path)
    if not os.path.exists(frame_path):
      os.makedirs(frame_path)
    if not os.path.exists(plot_path):
      os.makedirs(plot_path)

    # in train don't load the model and set train=True
    # in test, load the model and set train=False
    for train, load_model, num_episodes in [[True, False, num_episode_train]]: #[[True,False,num_episode_train], [False, True, num_episode_test]]:

      print ("seed_nb is:", seed_nb)

      tf.reset_default_graph()

      with tf.device("/device:GPU:0"):
        global_episodes = tf.Variable(0,dtype=tf.int32,name='global_episodes',trainable=False)
        trainer = tf.train.RMSPropOptimizer(learning_rate=7e-4)
        master_network = AC_Network(a_size,'global',None, width, height) # Generate global network
        num_workers = 1
        workers = []
        # Create worker classes
        env_list = [deepmind_lab.Lab(level, ['RGB_INTERLEAVED'], config=config) for _ in range(num_workers)]
        for i in range(num_workers):
            env = deepmind_lab.Lab(level, ['RGB_INTERLEAVED'], config=config)
            workers.append(Worker(WrapperEnv(env_list[i], length), i, a_size, trainer,
                model_path, global_episodes, make_gif=False,
                collect_seed_transition_probs=collect_seed_transition_probs,
                plot_path=plot_path, frame_path=frame_path,
                width=width, height=height))
                           
        saver = tf.train.Saver(max_to_keep=5)

      config_t = tf.ConfigProto(allow_soft_placement = True)
      config_t.intra_op_parallelism_threads = 3000
      config_t.inter_op_parallelism_threads = 3000
      with tf.Session(config = config_t) as sess:
        # set the seed
        np.random.seed(seed_nb)
        tf.set_random_seed(seed_nb)

        coord = tf.train.Coordinator()
        if load_model == True:
          print ('Loading Model...')
          ckpt = tf.train.get_checkpoint_state(load_model_path)
          saver.restore(sess,ckpt.model_checkpoint_path)
        else:
          sess.run(tf.global_variables_initializer())
        
        # old multi-threading code
        worker_threads = []
        for worker in workers:
          worker_work = lambda: worker.work(gamma,sess,coord,saver,train,num_episodes)
          thread = threading.Thread(target=(worker_work))
          thread.start()
          worker_threads.append(thread)
        coord.join(worker_threads)
        
        # new multiprocessing code
        
#         def worker_function(worker):
#             print("REALLY DOING ANYTHING MEANINGFUL HERE???")
#             return worker.work(gamma,sess,coord,saver,train,num_episodes)
        
        

#         print("starting")
#         pool = mp.Pool(processes=num_workers)
#         for worker in workers:
#             my_function = worker_function(worker)
#             results = pool.apply_async(my_function, args = ())
# #         output = [p.get() for p in results]
#         pool.close()
#         pool.join()
#         print("finished?")

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
