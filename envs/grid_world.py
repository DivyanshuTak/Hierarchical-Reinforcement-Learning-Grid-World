from gym import spaces
import random
import numpy as np 

class GridWorld:

    def __init__(self):
        self.world = np.zeros((6,6))
        self.visited_key = False
        self.current_state = (0,0)
        # number of actions (0:l=Left, 1:Right, 2:Top, 3:Bottom)
        self.nA = 4
        # number of states (36 places - 6 blocks)
        self.nS = 30
        self.obstacle_list = [(0,3),(0,4),(3,1),(3,5),(5,2),(5,3)]

    def reset(self):

        # reset the world 
        # blocks -> -50
        # Key -> 5
        # Traps -> -100 (reward)
        # Goal -> 10 (default reward)
        self.world[0,3] = self.world[0,3] = self.world[0,3] = self.world[0,3] = self.world[0,3] = self.world[0,3] = self.world[0,3] = -50
        self.world[1,3] = 5
        self.world[5,5] = 10      
        self.world[2,3] = -100

        self.visited_key = False
        self.current_state = (0,0)
        return self.current_state

    def step(self, action):

        # Action Mapping 
        """
        0 ->  Left 
        1 ->  Right
        2 ->  Top
        3 ->  Bottom
        """
        row,col = self.current_state
        # boundary cases 
        if (action==0) and (col==0):
            self.current_state = self.current_state
            reward=-1
        elif (action==1) and (col==5):
            reward=-1
            self.current_state = self.current_state
        elif (action==2) and (row==0):
            reward=-1
            self.current_state = self.current_state
        elif (action==3) and (row==5):
            reward=-1
            self.current_state = self.current_state
        # free movement 
        else:
            if action==0:
                reward=-1
                self.current_state = (row, col-1)
            elif action==1:
                reward=-1
                self.current_state = (row, col+1)
            elif action==2:
                reward=-1
                self.current_state = (row-1, col)
            elif action==3:
                reward=-1
                self.current_state = (row+1, col)

        # now check if we hit th block 
        row, col = self.current_state
        if (self.current_state in self.obstacle_list):
            if action == 0:
                self.current_state = (row, col+1)
                reward=-1
            elif action == 1:
                self.current_state = (row, col-1)
                reward=-1
            elif action == 2:
                self.current_state = (row+1, col)
                reward=-1
            elif action==3:
                self.current_state = (row-1, col)
                reward=-1


        # check for conditions 
        if self.current_state == (2,3):
            reward = -100
            return self.current_state, reward, True, {}
        if self.current_state == (1,3):
            self.visited_key = True
        if self.current_state == (5,5):
            if self.visited_key:
                reward = 10000
                return self.current_state, reward, True, {}
            else:
                reward = 100
                return self.current_state, reward, True, {}
        else:
            return self.current_state, reward, False, {}

        