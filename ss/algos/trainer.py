"""Implements the DDPG training loop"""

import os
import time
from collections import deque
import pickle

from ss.algos.ddpg import DDPG
from baselines.ddpg.util import mpi_mean, mpi_std, mpi_max, mpi_sum
import baselines.common.tf_util as U

from baselines import logger
import numpy as np
import tensorflow as tf
from mpi4py import MPI

import pdb

from ss.remote import s3
from ss.utils.rollout import Rollout
import ss.path as path

class Trainer:
    def __init__(self, **params):
        self.params = params
        for k in params:
            setattr(self, k, params[k])

    def train(self):
        rank = MPI.COMM_WORLD.Get_rank()

        logdir = logger.get_dir()
        if rank == 0 and logdir:
            path.mkdir(os.path.join(logdir, 'rollouts'))
            path.mkdir(os.path.join(logdir, 'policies'))
            with open(os.path.join(logdir, 'params.pkl'), 'wb') as f:
                pickle.dump(self, f)

        env = self.env

        assert (np.abs(env.action_space.low) == env.action_space.high).all()  # we assume symmetric actions.
        max_action = env.action_space.high
        logger.info('scaling actions by {} before executing in env'.format(max_action))
        agent = DDPG(**self.params)
        logger.info('Using agent with the following configuration:')
        logger.info(str(agent.__dict__.items()))

        # Set up logging stuff only for a single worker.
        if rank == 0:
            saver = tf.train.Saver()
        else:
            saver = None

        step = 0
        episode = 0
        with U.single_threaded_session() as sess:
            # Prepare everything.
            agent.initialize(sess)
            sess.graph.finalize()

            agent.reset()
            obs = env.reset()
            done = False
            episode_reward = 0.
            episode_step = 0
            episodes = 0
            t = 0

            epoch = 0
            start_time = time.time()


            epoch_episode_steps = []
            epoch_start_time = time.time()
            epoch_episodes = 0
            rollouts = []
            for epoch in range(self.nb_epochs):
                epoch_episode_rewards = []
                epoch_episode_success = []
                epoch_actions = []
                epoch_qs = []
                epoch_actor_losses = []
                epoch_critic_losses = []

                for cycle in range(self.nb_epoch_cycles):
                    # Perform rollouts.

                    rollout = Rollout()
                    for t_rollout in range(self.horizon):
                        # Predict next action.
                        action, q = agent.pi(obs, apply_noise=True, compute_Q=True)
                        state = env.get_state_data()
                        assert action.shape == env.action_space.shape

                        # Execute next action.
                        if rank == 0 and self.render:
                            env.render()
                        assert max_action.shape == action.shape
                        new_obs, r, done, info = env.step(max_action * action)  # scale for execution in env (as far as DDPG is concerned, every action is in [-1, 1])

                        rollout.store_transition(state, action, r)
                        t += 1
                        if rank == 0 and self.render:
                            env.render()
                        episode_reward += r
                        episode_step += 1

                        # Book-keeping.
                        epoch_actions.append(action)
                        epoch_qs.append(q)
                        agent.store_transition(obs, action, r, new_obs, done)
                        obs = new_obs

                    state = env.get_state_data()
                    rollout.store_transition(state, None, None) # store final state
                    if cycle == 0: # save 1 rollout per epoch
                        rollouts.append(rollout)

                    epoch_episode_rewards.append(episode_reward)
                    epoch_episode_success.append(r + 1)
                    epoch_episode_steps.append(episode_step)
                    episode_reward = 0.
                    episode_step = 0
                    epoch_episodes += 1
                    episodes += 1

                    agent.reset()
                    obs = env.reset()

                    # Train.
                    for t_train in range(self.nb_train_steps):
                        cl, al = agent.train()
                        epoch_critic_losses.append(cl)
                        epoch_actor_losses.append(al)
                agent.update_target_net()

                # Log stats.
                epoch_train_duration = time.time() - epoch_start_time
                duration = time.time() - start_time
                stats = agent.get_stats()
                combined_stats = {}
                for key in sorted(stats.keys()):
                    combined_stats[key] = mpi_mean(stats[key])

                # Rollout statistics.
                combined_stats['rollout/return'] = mpi_mean(epoch_episode_rewards)
                combined_stats['rollout/success'] = mpi_mean(epoch_episode_success)
                combined_stats['rollout/episode_steps'] = mpi_mean(epoch_episode_steps)
                combined_stats['rollout/episodes'] = mpi_sum(epoch_episodes)
                combined_stats['rollout/actions_mean'] = mpi_mean(epoch_actions)
                combined_stats['rollout/actions_std'] = mpi_std(epoch_actions)
                combined_stats['rollout/Q_mean'] = mpi_mean(epoch_qs)

                # Train statistics.
                combined_stats['train/loss_actor'] = mpi_mean(epoch_actor_losses)
                combined_stats['train/loss_critic'] = mpi_mean(epoch_critic_losses)

                # Total statistics.
                combined_stats['total/duration'] = mpi_mean(duration)
                combined_stats['total/steps_per_second'] = mpi_mean(float(t) / float(duration))
                combined_stats['total/episodes'] = mpi_mean(episodes)
                combined_stats['total/epochs'] = epoch + 1
                combined_stats['total/steps'] = t

                for key in sorted(combined_stats.keys()):
                    logger.record_tabular(key, combined_stats[key])
                logger.dump_tabular()
                logger.info('')
                if rank == 0 and logdir:
                    if hasattr(env, 'get_state'):
                        with open(os.path.join(logdir, 'env_state.pkl'), 'wb') as f:
                            pickle.dump(env.get_state(), f)

                    if epoch % 100 == 0:
                        # saver.save(sess, logdir + 'models/model', global_step=epoch)
                        with open(os.path.join(logdir, 'policies/agent_%d.pkl' % epoch), 'wb') as f:
                            pickle.dump(agent, f)

                        with open(os.path.join(logdir, 'rollouts/rollouts_%d.pkl' % epoch), 'wb') as f:
                            pickle.dump(rollouts, f)
                        rollouts = []

                        # todo: break this out into its own frequency parameter (one for sync, one for dumping the agent)
                        s3.sync_up_expdir()

    # TODO: this should restore the state of a training. But for now it just pickles params
    def __getstate__(self):
        exclude_vars = set(["env"])
        args = {}
        for k in self.params:
            if k not in exclude_vars:
                args[k] = self.params[k]
        return {'params': args}
