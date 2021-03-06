import numpy as np
from collections import defaultdict
from itertools import count
import random

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.autograd as autograd
from torch.utils.tensorboard import SummaryWriter

from utils.replay_memory import ReplayMemory
from utils import plotting

USE_CUDA = torch.cuda.is_available()
dtype = torch.cuda.FloatTensor if torch.cuda.is_available() else torch.FloatTensor
writer = SummaryWriter("runs/HRL_GW")

class Variable(autograd.Variable):
    def __init__(self, data, *args, **kwargs):
        if USE_CUDA:
            data = data.cuda()
        super(Variable, self).__init__(data, *args, **kwargs)

# Fucntion takes the input state tuple and output a 30 len goal vector 
def one_hot_state(state):
    dummy_world = np.zeros((6,6))
    row,col = state
    dummy_world[row,col] = 1
    state_vector = np.hstack((dummy_world[0,:3],dummy_world[0,5],dummy_world[1,:],dummy_world[2,:],dummy_world[3,0],dummy_world[3,2:5],dummy_world[4,:],dummy_world[5,:2],dummy_world[5,4:]))
    return np.expand_dims(state_vector, axis=0)

def one_hot_goal(goal):
    dummy_world = np.zeros((6,6))
    goal_vector = np.hstack((dummy_world[0,:3],dummy_world[0,5],dummy_world[1,:],dummy_world[2,:],dummy_world[3,0],dummy_world[3,2:5],dummy_world[4,:],dummy_world[5,:2],dummy_world[5,4:]))
    goal_vector[goal]=1        # original code does  [goal-1] so try that if things do not work out
    #vector = np.zeros(6)
    #vector[goal-1] = 1.0
    return np.expand_dims(goal_vector, axis=0)

def state_to_index(state):
    dummy_world = np.zeros((6,6))
    row,col = state
    dummy_world[row,col] = 1
    state_vector = np.hstack((dummy_world[0,:3],dummy_world[0,5],dummy_world[1,:],dummy_world[2,:],dummy_world[3,0],dummy_world[3,2:5],dummy_world[4,:],dummy_world[5,:2],dummy_world[5,4:]))
    return np.argmax(state_vector)

def index_to_vector(index):
    vector = np.zeros(30)
    vector[index]=1
    return vector


def hdqn_learning(
    env,
    agent,
    num_episodes,
    exploration_schedule,
    gamma=1.0,
    ):

    """The h-DQN learning algorithm.
    All schedules are w.r.t. total number of steps taken in the environment.
    Parameters
    ----------
    env: gym.Env
        gym environment to train on.
    agent:
        a h-DQN agent consists of a meta-controller and controller.
    num_episodes:
        Number (can be divided by 1000) of episodes to run for. Ex: 12000
    exploration_schedule: Schedule (defined in utils.schedule)
        schedule for probability of chosing random action.
    gamma: float
        Discount Factor
    """
    ###############
    # RUN ENV     #
    ###############
    # Keep track of useful statistics
    stats = plotting.EpisodeStats(
        episode_lengths=np.zeros(num_episodes),
        episode_rewards=np.zeros(num_episodes))
    n_thousand_episode = int(np.floor(num_episodes / 1000))
    visits = np.zeros((n_thousand_episode, env.nS))
    total_timestep = 0
    meta_timestep = 0
    ctrl_timestep = defaultdict(int)

    # metrics to log 
    total_rewards_per_intreval = 0
    log_intreval = 20
    visits_to_key = 0

    for i_thousand_episode in range(n_thousand_episode):
        print("\n") 
        print("starting the {}th episode ".format(i_thousand_episode));
        print("\n")
        for i_episode in range(1000):
            episode_length = 0
            current_state = env.reset()
            state_index = state_to_index(current_state)
            visits[i_thousand_episode][state_index-1] = visits[i_thousand_episode][state_index-1] + 1
            encoded_current_state = one_hot_state(current_state)

            done = False
            while not done:
                meta_timestep += 1
                # Get annealing exploration rate (epislon) from exploration_schedule
                meta_epsilon = exploration_schedule.value(total_timestep)
                goal = agent.select_goal(encoded_current_state, meta_epsilon)[0]
                goal_ohc_vector = index_to_vector(goal)
                encoded_goal = one_hot_goal(goal)

                total_extrinsic_reward = 0
                goal_reached = False
                while not done and not goal_reached:

                    # count the visits to the key 
                    if (encoded_current_state[0,7]==1):
                      visits_to_key = visits_to_key + 1

                    total_timestep = total_timestep+1
                    episode_length = episode_length+1
                    ctrl_timestep[goal] = ctrl_timestep[goal] + 1
                    # Get annealing exploration rate (epislon) from exploration_schedule
                    ctrl_epsilon = exploration_schedule.value(total_timestep)
                    joint_state_goal = np.concatenate([encoded_current_state, encoded_goal], axis=1)
                    action = agent.select_action(joint_state_goal, ctrl_epsilon)[0]
                    ### Step the env and store the transition
                    next_state, extrinsic_reward, done, _ = env.step(action)
                    next_state_index = state_to_index(next_state)
                    next_state_ohc_vector = index_to_vector(next_state_index)
                    # Update statistics
                    stats.episode_rewards[i_thousand_episode*1000 + i_episode] = stats.episode_rewards[i_thousand_episode*1000 + i_episode]+  extrinsic_reward
                    stats.episode_lengths[i_thousand_episode*1000 + i_episode] = episode_length
                    visits[i_thousand_episode][next_state_index-1] = visits[i_thousand_episode][next_state_index-1] + 1

                    encoded_next_state = one_hot_state(next_state)
                    intrinsic_reward = agent.get_intrinsic_reward(goal_ohc_vector, next_state_ohc_vector)
                    goal_reached = intrinsic_reward
                    joint_next_state_goal = np.concatenate([encoded_next_state, encoded_goal], axis=1)
                    agent.ctrl_replay_memory.push(joint_state_goal, action, joint_next_state_goal, intrinsic_reward, done)
                    # Update Both meta-controller and controller
                    agent.update_meta_controller(gamma)
                    agent.update_controller(gamma)

                    total_extrinsic_reward = total_extrinsic_reward + extrinsic_reward
                    current_state = next_state
                    encoded_current_state = encoded_next_state
                # Goal Finished
                agent.meta_replay_memory.push(encoded_current_state, goal, encoded_next_state, total_extrinsic_reward, done)
                
                # log metrics 
                total_rewards_per_intreval = total_rewards_per_intreval + total_extrinsic_reward
            if (i_episode%log_intreval==0):
              # log total average rewards per episode 
              episode = i_thousand_episode*1000 + i_episode
              print("completed {} episodes".format(episode))
              #writer.add_scalar("episode/average_reward", total_rewards_per_intreval/log_intreval, episode)
              print("aeverage reward per episode is {}".format(total_rewards_per_intreval/log_intreval))
              total_rewards_per_intreval=0
              # log visits to key 
              #writer.add_scalar("episode/average_visit_to_key", visits_to_key/log_intreval, episode)
              print("average visits to key per episode is {}".format(visits_to_key/log_intreval))
              print("\n")
              print("=================================================================================================")
              visits_to_key=0
    # close the logger
    writer.flush()
    writer.close()



                  



                  








    return agent, stats, visits
