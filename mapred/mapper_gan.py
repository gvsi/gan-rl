#!/afs/inf.ed.ac.uk/user/s14/s1448512/miniconda3/envs/gan/bin/python

import os
import sys
import gym
import numpy as np
import random
from gym import envs
from gym.envs.registration import register, spec
from datetime import datetime
from json_tricks import dumps, loads
from tqdm import tqdm
from math import sqrt
import socket

from keras.layers import Input, Dense, Reshape, Flatten, Dropout
from keras.layers import BatchNormalization, Activation, ZeroPadding2D
from keras.layers.advanced_activations import LeakyReLU
from keras.layers.convolutional import UpSampling2D, Conv2D
from keras.models import Sequential, Model, save_model
from keras.optimizers import Adam

import keras.backend as K
from keras.models import load_model

def verify(env, Q, num_episodes = 10000):
    # Set learning parameters
    #create lists to contain total rewards and steps per episode
    #jList = []
    rList = []
    successes = 0
    jTot = 0
    for i in tqdm(range(num_episodes)):
        #Reset environment and get first new observation
        s = env.reset()
        rAll = 0
        d = False
        j = 0
        #The Q-Table learning algorithm
        while j < 200:
            j+=1
            #Choose an action by greedily (with noise) picking from Q table
            a = np.argmax(Q[s,:])
            #Get new state and reward from environment
            s1,r,d,_ = env.step(a)
            rAll += r
            s = s1
            if d == True and r > 0:
                jTot += j
                successes += 1
            if d == True:
                break
        rList.append(rAll)
    valid_score = sum(rList)/num_episodes
    try:
        avg_steps = jTot / successes
    except:
        avg_steps = 0
    return valid_score, avg_steps

class Experiment(object):
    def __init__(self, env, num_episodes=10000):
        self.env = env
        self.Q = np.zeros([self.env.observation_space.n, self.env.action_space.n])
        self.machine = socket.gethostname()
        self.num_episodes = num_episodes
        self.done = False
        self.score = None
        self.start = None
        self.end = None
        self.train_successes = []
        self.valid_score = None
        self.valid_avg_steps = None

    def print_score(self):
        if not self.done:
            print("Run first.")
            return
        print("Score over time: " +  str(self.score))

    def run(self):
        # print("Running experiment...")
        if self.done:
            print("Already done running")
            return

        self.start = datetime.now()
        lr = .8
        e = 0.1
        y = .95
        #create lists to contain total rewards and steps per episode
        jList = []
        rList = []
        for i in tqdm(range(self.num_episodes)):
            #Reset environment and get first new observation
            s = self.env.reset()
            rAll = 0
            d = False
            j = 0
            #The Q-Table learning algorithm
            while j < 200:
                j+=1
                #Choose an action by greedily (with noise) picking from Q table
                a = None
                if random.uniform(0,1) < e:
                    a = self.env.action_space.sample()
                else:
                    a = np.argmax(self.Q[s,:])
                #Get new state and reward from environment
                s1,r,d,_ = self.env.step(a)
                if d == True and r != 1:
                    self.Q[s, a] -= 0.01
                #Update Q-Table with new knowledge
                if i < 1000:
                    self.Q[s,a] = self.Q[s,a] + lr*(r + y*np.max(self.Q[s1,:]) - self.Q[s,a])
                else:
                    self.Q[s,a] = self.Q[s,a] + lr*(r + y*np.max(self.Q[s1,:]) - self.Q[s,a])
                    self.Q[s,a] = self.Q[s,a] - 0.5 * np.reshape(get_gradient([np.array([np.expand_dims(self.Q, axis=3)])]), (16, 4))[s,a]
                rAll += r
                s = s1
                if d == True and r > 0:
                    self.train_successes.append((i, j))
                if d == True:
                    #Reduce chance of random action as we train the model.
        #             e = 1./((i/50) + 10)
                    break
            rList.append(rAll)
        self.done = True
        self.end = datetime.now()
        self.score = sum(rList)/self.num_episodes

    def validate(self):
        valid_score, avg_steps = verify(self.env, self.Q)
        self.valid_score = valid_score
        self.valid_avg_steps = avg_steps

    def dumps(self):
        if not self.done:
            print("Run first.")
            return

        return dumps({'Q': self.Q,
                      'start': self.start,
                      'end': self.end,
                      'train_score': self.score,
                      'num_episodes': self.num_episodes,
                      'train_successes': exp.train_successes,
                      'train_machine' : self.machine,
                      'valid_score' : self.valid_score,
                      'valid_avg_steps' : self.valid_avg_steps
                      })

def new_env(env_map, slippery=True, MY_ENV_NAME='MyFrozenLake-v0'):
    if MY_ENV_NAME in envs.registry.env_specs:
        envs.registry.env_specs.pop(MY_ENV_NAME)

    register(
        id=MY_ENV_NAME,
        entry_point='gym.envs.toy_text:FrozenLakeEnv',
        kwargs={'is_slippery': slippery, 'desc': env_map},
        max_episode_steps=100,
        reward_threshold=0.78, # optimum = .8196
    )
    env = gym.make(MY_ENV_NAME)
    return env


discriminator = load_model("../data/gan/D_params_keras.p")

output = discriminator.outputs[-1]
loss = (1 - output) ** 2
grad = K.gradients(loss, discriminator.inputs[-1])
input_tensors = [discriminator.inputs[0]]
get_gradient = K.function(inputs=input_tensors, outputs=grad)


lines = []


for line in sys.stdin:
    w = line.strip()
    map_str_comb, dic = w.split("\t")
    obj = loads(dic)
    # if obj['train_machine'] == socket.gethostname():
    lines.append(map_str_comb)

random.shuffle(lines)

while lines:
    set_name = "data4_valid_mul5_gan"
    w = lines.pop()
    print("Running: " + w)
    if os.path.isfile("../data/"+set_name+"/res/"+w+".txt"):
        continue
    else:
        os.mknod("../data/"+set_name+"/res/"+w+".txt")
        n = int(sqrt(len(w)))
        # split into lines
        map_str = [w[i:i+n] for i in range(0, len(w), n)]
        env = new_env(map_str, slippery=True)
        exp = Experiment(env, num_episodes=2000)
        exp.run()
        for _ in range(5):
            new_exp = Experiment(env, num_episodes=2000)
            new_exp.run()
            if new_exp.score > exp.score:
                exp = new_exp
        print("Validating...")
        exp.validate()
        f = open("../data/"+set_name+"/res/"+w+".txt","w+")
        f.write(w+"\t" + str(exp.dumps()) + "\n")
        f.close()
