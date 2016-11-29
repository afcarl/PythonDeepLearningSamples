# note must import tensorflow before gym
import random
from collections import deque

import tensorflow as tf
import gym
import numpy as np

env = gym.make('CartPole-v0')

MAX_REWARD = 10.
ACTIONS_COUNT = 2
FUTURE_REWARD_DISCOUNT = 0.99
OBSERVATION_STEPS = 10000.  # time steps to observe before training
EXPLORE_STEPS = 10000.  # frames over which to anneal epsilon
INITIAL_RANDOM_ACTION_PROB = 1.0  # starting chance of an action being random
FINAL_RANDOM_ACTION_PROB = 0.0  # final chance of an action being random
MEMORY_SIZE = 100000  # number of observations to remember
MINI_BATCH_SIZE = 200  # size of mini batches
OBS_LAST_STATE_INDEX, OBS_ACTION_INDEX, OBS_REWARD_INDEX, OBS_CURRENT_STATE_INDEX, OBS_TERMINAL_INDEX = range(5)
LEARN_RATE = 1e-5
STORE_SCORES_LEN = 100.
INPUT_NODES = env.observation_space.shape[0]


session = tf.Session()

feed_forward_weights_1 = tf.Variable(tf.truncated_normal([INPUT_NODES, ACTIONS_COUNT], stddev=0.01))
feed_forward_bias_1 = tf.Variable(tf.constant(0.0, shape=[ACTIONS_COUNT]))

input_placeholder = tf.placeholder("float", [None, INPUT_NODES])
output_layer = tf.matmul(input_placeholder, feed_forward_weights_1) + feed_forward_bias_1

action_placeholder = tf.placeholder("float", [None, ACTIONS_COUNT])
target_placeholder = tf.placeholder("float", [None])

readout_action = tf.reduce_sum(tf.mul(output_layer, action_placeholder), reduction_indices=1)

cost = tf.reduce_mean(tf.square(target_placeholder - readout_action))
train_operation = tf.train.AdamOptimizer(LEARN_RATE).minimize(cost)

observations = deque(maxlen=MEMORY_SIZE)
scores = deque(maxlen=STORE_SCORES_LEN)

# set the first action to do nothing
last_action = np.zeros(ACTIONS_COUNT)
last_action[1] = 1

probability_of_random_action = INITIAL_RANDOM_ACTION_PROB
_time = 0

session.run(tf.initialize_all_variables())


def choose_next_action():
    new_action = np.zeros([ACTIONS_COUNT])

    if random.random() <= probability_of_random_action:
        # choose an action randomly
        action_index = random.randrange(ACTIONS_COUNT)
    else:
        # choose an action given our last state
        readout_t = session.run(output_layer, feed_dict={input_placeholder: [last_state]})[0]
        action_index = np.argmax(readout_t)

    new_action[action_index] = 1
    return new_action


def train():
    # sample a mini_batch to train on
    mini_batch = random.sample(observations, MINI_BATCH_SIZE)

    # get the batch variables
    previous_states = [d[OBS_LAST_STATE_INDEX] for d in mini_batch]
    actions = [d[OBS_ACTION_INDEX] for d in mini_batch]
    rewards = [d[OBS_REWARD_INDEX] for d in mini_batch]
    current_states = [d[OBS_CURRENT_STATE_INDEX] for d in mini_batch]
    agents_expected_reward = []
    # this gives us the agents expected reward for each action we might take
    agents_reward_per_action = session.run(output_layer, feed_dict={input_placeholder: current_states})
    agents_reward_per_action = np.clip(agents_reward_per_action, -MAX_REWARD, MAX_REWARD)
    for i in range(len(mini_batch)):
        if mini_batch[i][OBS_TERMINAL_INDEX]:
            # this was a terminal frame so there is no future reward...
            agents_expected_reward.append(rewards[i])
        else:
            agents_expected_reward.append(
                rewards[i] + FUTURE_REWARD_DISCOUNT * np.max(agents_reward_per_action[i]))

    # learn that these actions in these states lead to this reward
    session.run(train_operation, feed_dict={
        input_placeholder: previous_states,
        action_placeholder: actions,
        target_placeholder: agents_expected_reward})


last_state = env.reset()
next_action = 1
total_reward = 0

while True:
    env.render()

    current_state, reward, terminal, info = env.step(next_action)
    total_reward += reward

    if terminal:
        terminal = True
        reward = -MAX_REWARD

        scores.append(total_reward)
        if len(scores) > STORE_SCORES_LEN:
            scores.popleft()

        print("Time: %s random_action_prob: %s reward %s scores differential %s" %
              (_time, probability_of_random_action, total_reward,
               np.mean(scores)))
        total_reward = 0

    # store the transition in previous_observations
    observations.append((last_state, last_action, reward, current_state, terminal))

    if len(observations) > MEMORY_SIZE:
        observations.popleft()

    # only train if done observing
    if len(observations) > OBSERVATION_STEPS:
        train()
        _time += 1

    # update the old values
    if terminal:
        last_state = env.reset()
    else:
        last_state = current_state

    last_action = choose_next_action()
    next_action = np.argmax(last_action)

    # gradually reduce the probability of a random action
    if probability_of_random_action > FINAL_RANDOM_ACTION_PROB \
            and len(observations) > OBSERVATION_STEPS:
        probability_of_random_action -= \
            (INITIAL_RANDOM_ACTION_PROB - FINAL_RANDOM_ACTION_PROB) / EXPLORE_STEPS
