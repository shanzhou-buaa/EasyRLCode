#!/usr/bin/env python

# simple_grid.py
# based on frozen_lake.py
# adapted by Frans Oliehoek.
# 
import sys
from contextlib import closing

import numpy as np
from io import StringIO
#from six import StringIO, b
import gym
from gym import utils
from gym import Env, spaces
from gym.utils import seeding


def categorical_sample(prob_n, np_random):
    """
    Sample from categorical distribution
    Each row specifies class probabilities
    从分类分布中采样 每一行指定类别的概率
    """
    # 将输入转换为numpy数组
    prob_n = np.asarray(prob_n)
    # 对概率分布 prob_n 进行累加求和,得到累积概率数组 csprob_n
    csprob_n = np.cumsum(prob_n)

    # np_random.random() 生成一个在 [0, 1) 范围内的随机浮点数
    # csprob_n > np_random.random() 返回一个布尔数组,表示每个累积概率是否大于随机数
    # .argmax() 返回第一个 True 的索引,即找到第一个满足条件的类别索引
    # 这个索引就是从分类分布中采样得到的类别
    # 这个函数的作用是从给定的概率分布中随机选择一个类别
    # 该类别的选择是基于累积概率分布的
    # 返回值是一个整数,表示所选类别的索引
    return (csprob_n > np_random.random()).argmax()


class DiscreteEnv(Env):

    """
    Has the following members
    - nS: number of states
    - nA: number of actions
    - P: transitions (*) 转移概率矩阵并不是只有一个概率
    - isd: initial state distribution (**)

    转移概率矩阵的形式
    (*) dictionary of lists, where
      P[s][a] == [(probability, nextstate, reward, done), ...]
    (**) list or array of length nS


    """

    def __init__(self, nS, nA, P, isd):
        self.P = P
        self.isd = isd
        self.lastaction = None  # for rendering
        self.nS = nS
        self.nA = nA

        # 离散动作空间类，表示可用的动作
        # 将左下右上四个方向表示为0~3
        self.action_space = spaces.Discrete(self.nA)
        self.observation_space = spaces.Discrete(self.nS)

        self.seed()
        self.s = categorical_sample(self.isd, self.np_random)

    def seed(self, seed=None):
        self.np_random, seed = seeding.np_random(seed)
        return [seed]

    def reset(self):
        self.s = categorical_sample(self.isd, self.np_random)
        self.lastaction = None
        return int(self.s)

    def step(self, a):
        transitions = self.P[self.s][a]
        i = categorical_sample([t[0] for t in transitions], self.np_random)
        p, s, r, d = transitions[i]
        self.s = s
        self.lastaction = a
        return (int(s), r, d, {"prob": p})

# 四个方向
LEFT = 0
DOWN = 1
RIGHT = 2
UP = 3
# 预设地图
MAPS = {
    "theAlley": [
        "S...H...H...G"
    ],
    "walkInThePark": [
        "S.......",
        ".....H..",
        "........",
        "......H.",
        "........",
        "...H...G"
    ],
    "1Dtest": [

    ],
    "4x4": [
        "S...",
        ".H.H",
        "...H",
        "H..G"
    ],
    "8x8": [
        "S.......",
        "........",
        "...H....",
        ".....H..",
        "...H....",
        ".HH...H.",
        ".H..H.H.",
        "...H...G"
    ],
}

# 在POTHOLE上摔倒的概率,20%概率在坑洞上摔倒
# REWARD为到达终点的奖励值
POTHOLE_PROB = 0.2
# BROKEN_LEG_PENALTY为摔倒的惩罚值
BROKEN_LEG_PENALTY = -5
# SLEEP_DEPRIVATION_PENALTY为睡眠剥夺的惩罚值
SLEEP_DEPRIVATION_PENALTY = -0.0
REWARD = 10

# 随机生成地图
def generate_random_map(size=8, p=0.8):
    """
    Generates a random valid map (one that has a path from start to goal)
    :param size: size of each side of the grid
    :param p: probability that a tile is frozen
    """
    valid = False

    # DFS to check that it's a valid path.
    # 深度优先确定能有到达终点的路线
    def is_valid(res):
        frontier, discovered = [], set()
        frontier.append((0,0))
        while frontier:
            r, c = frontier.pop()
            if not (r,c) in discovered:
                discovered.add((r,c))
                directions = [(1, 0), (0, 1), (-1, 0), (0, -1)]
                for x, y in directions:
                    r_new = r + x
                    c_new = c + y
                    if r_new < 0 or r_new >= size or c_new < 0 or c_new >= size:
                        continue
                    if res[r_new][c_new] == 'G':
                        return True
                    if (res[r_new][c_new] not in '#H'):
                        frontier.append((r_new, c_new))
        return False

    while not valid:
        p = min(1, p) # 确保概率在0到1之间
        # choice生成一个大小为(size, size)的矩阵
        # 其中每个元素以p概率是'.'（正常路面）或'H'（坑洞）
        res = np.random.choice(['.', 'H'], (size, size), p=[p, 1-p])
        # 'S'为起点,'G'为终点
        res[0][0] = 'S'
        res[-1][-1] = 'G'
        valid = is_valid(res)

    # Convert to list of strings
    return ["".join(x) for x in res]


class DrunkenWalkEnv(DiscreteEnv):
    """
    A simple grid environment, completely based on the code of 'FrozenLake', credits to 
    the original authors.

    You're finding your way home (G) after a great party which was happening at (S).
    Unfortunately, due to recreational intoxication you find yourself only moving into 
    the intended direction 80% of the time, and perpendicular to that the other 20%.
    80%朝给定方向前进,20%朝垂直方向前进

    To make matters worse, the local community has been cutting the budgets for pavement
    maintenance, which means that the way to home is full of potholes, which are very likely
    to make you trip. If you fall, you are obviously magically transported back to the party, 
    without getting some of that hard-earned sleep.

        S...
        .H.H
        ...H
        H..G

    S : starting point
    . : normal pavement
    H : pothole, you have a POTHOLE_PROB chance of tripping
    G : goal, time for bed

    The episode ends when you reach the goal or trip.
    You receive a reward of +10 if you reach the goal, 
    but get a SLEEP_DEPRIVATION_PENALTY and otherwise.

    """

    # gym环境支持“人类可读”和“ANSI终端”两种渲染模式。
    metadata = {'render.modes': ['human', 'ansi']}

    def __init__(self, desc=None, map_name="4x4",is_slippery=True):
        """ 
        This generates a map and sets all transition probabilities.
        (by passing constructed nS, nA, P, isd to DiscreteEnv)
        desc地图描述,二维字符数组或列表,用于自定义环境地图
        如果为 None,则根据 map_name 选择预设地图或随机生成地图
        is_slippery表示在移动时是否有滑动的可能性。
        """
        # 生成地图
        if desc is None and map_name is None:
            desc = generate_random_map()
        elif desc is None:
            desc = MAPS[map_name]

        # 把传入的地图描述（如列表或字符串列表）转换为 numpy 的二维字节字符数组
        self.desc = desc = np.asarray(desc,dtype='c')
        self.nrow, self.ncol = nrow, ncol = desc.shape
        # 设置奖励的上下界，但是在这个文件别的地方也没用到这个变量
        # 意义不明，可能外部调用这个环境的时候会修改
        self.reward_range = (0, 1)

        # 动作和状态的个数
        nA = 4
        nS = nrow * ncol

        # isd是初始状态概率分布
        # desc == b'S'判断地图中每个格子是否为起点 'S'，返回一个布尔数组
        # astype将desc == b'S'c判断起点的布尔数组转换为浮点型数组，True 变为 1.0，False 变为 0.0
        # .ravel()将二维数组拉平成一维数组
        isd = np.array(desc == b'S').astype('float64').ravel()
        # 即最开始智能体只会出现在若干个起点，且满足均匀分布
        isd /= isd.sum()

        # We need to pass 'P' to DiscreteEnv:
        # P dictionary dict of dicts of lists, where
        # P[s][a] == [(probability, nextstate, reward, done), ...]
        # 嵌套字典，P[s][a]表示从状态s采取动作a的所有可能转移
        # 但是这里并没有填充内层字典的value
        P = {s : {a : [] for a in range(nA)} for s in range(nS)}

        # 将行列对应为状态
        def convert_rc_to_s(row, col):
            return row*ncol + col

        #def inc(row, col, a):
        def intended_destination(row, col, a):
            if a == LEFT:
                col = max(col-1,0)
            elif a == DOWN:
                row = min(row+1,nrow-1)
            elif a == RIGHT:
                col = min(col+1,ncol-1)
            elif a == UP:
                row = max(row-1,0)
            return (row, col)

        def construct_transition_for_intended(row, col, a, prob, li):
            """ 
            this constructs a transition to the "intended_destination(row, col, a)"
                and adds it to the transition list (which could be for a different action b).
            """
            newrow, newcol = intended_destination(row, col, a) # 位置
            newstate = convert_rc_to_s(newrow, newcol) # 状态编号
            newletter = desc[newrow, newcol] # 新位置对应的字母(用字母表示该位置的状态)
            done = bytes(newletter) in b'G'
            rew = REWARD if newletter == b'G' else SLEEP_DEPRIVATION_PENALTY
            # prob是转移到新状态的概率
            # newstate是新状态编号
            # rew是新状态的奖励值
            # done表示是否到达终点
            # 将转移信息添加到列表中
            li.append( (prob, newstate, rew, done) )


        #THIS IS WHERE THE MATRIX OF TRANSITION PROBABILITIES IS COMPUTED.
        for row in range(nrow):
            for col in range(ncol):
                # specify transitions for s=(row, col)
                s = convert_rc_to_s(row, col)
                letter = desc[row, col]
                for a in range(4):
                    # specify transitions for action a
                    li = P[s][a]
                    if letter in b'G':
                        # We are at the goal ('G').... 
                        # This is a strange case:
                        # - conceptually, we can think of this as:
                        #     always transition to a 'terminated' state where we will get 0 reward.
                        #
                        # - But in gym, in practie, this case should not be happening at all!!!
                        #   Gym will alreay have returned 'done' when transitioning TO the goal state (not from it).
                        #   So we will never use the transition probabilities *from* the goal state.
                        #   So, from gym's perspective we could specify anything we like here. E.g.,:
                        #       li.append((1.0, 59, 42000000, True))
                        #
                        # However, if we want to be able to use the transition matrix to do value iteration, it is important
                        # that we get 0 reward ever after.
                        li.append((1.0, s, 0, True))

                    if letter in b'H':
                        # We are at a pothole ('H')
                        # when we are at a pothole, we trip with prob. POTHOLE_PROB
                        li.append((POTHOLE_PROB, s, BROKEN_LEG_PENALTY, True))
                        construct_transition_for_intended(row, col, a, 1.0 - POTHOLE_PROB, li)
                        
                    else:
                        # We are at normal pavement (.)
                        # with prob. 0.8 we move as intended:
                        construct_transition_for_intended(row, col, a, 0.8, li)
                        # but with prob. 0.1 we move sideways to intended:
                        for b in [(a-1)%4, (a+1)%4]:
                            construct_transition_for_intended(row, col, b, 0.1, li)

        super(DrunkenWalkEnv, self).__init__(nS, nA, P, isd)

    def action_to_string(self, action_index):
        # 将动作索引转换为字符串表示
        s ="{}".format(["Left","Down","Right","Up"][action_index])
        return s

    def state_to_string(self, state_index):
        # 将状态索引转换为字符串表示
        row = state_index // self.ncol
        col = state_index % self.ncol
        return "({}, {})".format(row, col)

    def render(self, mode='human'):
        outfile = StringIO() if mode == 'ansi' else sys.stdout

        row, col = self.s // self.ncol, self.s % self.ncol
        desc = self.desc.tolist()
        desc = [[c.decode('utf-8') for c in line] for line in desc]
        desc[row][col] = utils.colorize(desc[row][col], "red", highlight=True)
        if self.lastaction is not None:
            outfile.write(" (last action was '{action}')\n".format( action=self.action_to_string(self.lastaction) ) )
        else:
            outfile.write("\n")
        reset = '\x1b[0m'
        outfile.write("\n".join(''.join(line) for line in desc)+"\n")

        if mode != 'human':
            with closing(outfile):
                return outfile.getvalue()
            
if __name__ == "__main__":
    env = DrunkenWalkEnv(map_name="4x4")
    # env = DrunkenWalkEnv(map_name="theAlley")
    n_states = env.observation_space.n
    n_actions = env.action_space.n
    print('run successfully!')

    # 打印env的状态和动作
    for _ in range(n_actions):
        print("Action {}: {}".format(_, env.action_to_string(_)))
    for _ in range(n_states):
        print("State {}: {}".format(_, env.state_to_string(_)))
    
    print("Initial state distribution: ", env.isd)

    # print("Transition probabilities: ")
    # for s in range(n_states):
    #     for a in range(n_actions):
    #         print("P[{}][{}] = {}".format(s, a, env.P[s][a]))

    print("Random map: ", env.desc)
    print("Random initial state: ", env.reset())
    done = False
    while not done:
        action = env.action_space.sample()
        print("Taking action: ", action)
        next_state, reward, done, info = env.step(action)
        print("Next state: ", next_state, "Reward: ", reward, "Done: ", done)
        env.render()
        print('\n')
    print("Episode finished.")
    env.close()