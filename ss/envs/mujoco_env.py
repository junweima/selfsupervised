"""Adapted from gym/envs/mujoco/mujoco_env.py"""

import os

from gym import error, spaces
from gym.utils import seeding
import numpy as np
from os import path
import gym
import six
import mujoco_py

class MujocoEnv(gym.Env):
    """Superclass for all MuJoCo environments.
    """

    def __init__(self, model_path, frame_skip=1):
        self.frame_skip = frame_skip
        self.model = mujoco_py.load_model_from_path(model_path)
        self.sim = mujoco_py.MjSim(self.model)
        self.data = self.sim.data
        self.viewer = None
        print("VIEWER", self.viewer)
        self.t = 0

        self.metadata = {
            'render.modes': ['human', 'rgb_array'],
            'video.frames_per_second': int(np.round(1.0 / self.dt))
        }

        self.init_qpos = self.data.qpos.ravel().copy()
        self.init_qvel = self.data.qvel.ravel().copy()
        observation, _reward, done, _info = self._step(np.zeros(self.model.nu))
        assert not done
        self.obs_dim = observation.size

        bounds = self.model.actuator_ctrlrange.copy()
        low = bounds[:, 0]
        high = bounds[:, 1]
        self.action_space = spaces.Box(low, high)

        high = np.inf*np.ones(self.obs_dim)
        low = -high
        self.observation_space = spaces.Box(low, high)

        self._seed()

    def _seed(self, seed=None):
        self.np_random, seed = seeding.np_random(seed)
        return [seed]

    # methods to override:
    # ----------------------------

    def get_obs(self):
        return np.concatenate([
            self.sim.data.qpos.flat,
            self.sim.data.qvel.flat
        ])

    def get_reward(self):
        return 0.0

    def set_action(self, u):
        pass

    def reset(self):
        self.t = 0
        ob = self.get_obs()
        return ob

    # -----------------------------

    def set_state(self, qpos, qvel):
        assert qpos.shape == (self.model.nq,) and qvel.shape == (self.model.nv,)
        self.data = self.sim.data
        self.data.qpos[:] = qpos
        self.data.qvel[:] = qvel
        self.sim.forward()

    def _step(self, u):
        self._set_action(u)
        self.sim.step()
        self.sim.forward()
        self.t += 1

        obs = self.get_obs()
        reward = self.get_reward()
        done = False

        return obs, reward, done, {"diverged": False}

    @property
    def dt(self):
        return self.model.opt.timestep * self.frame_skip

    def do_simulation(self, ctrl, n_frames):
        self.model.data.ctrl = ctrl
        for _ in range(n_frames):
            self.model.step()

    def _render(self, mode='human', close=False):
        # if close:
        #     if self.viewer is not None:
        #         self._get_viewer().finish()
        #         self.viewer = None
        #     return
        self._get_viewer().render()
        # if mode == 'rgb_array':
        #     # self._get_viewer().render()

    def get_img(self, width=480, height=480):
        return self.sim.render(width, height, camera_name="maincam")

    def _get_viewer(self):
        if self.viewer is None:
            self.viewer = mujoco_py.MjViewer(self.sim)
        return self.viewer

    def get_body_com(self, body_name):
        idx = self.model.body_names.index(six.b(body_name))
        return self.model.data.com_subtree[idx]

    def get_body_comvel(self, body_name):
        idx = self.model.body_names.index(six.b(body_name))
        return self.model.body_comvels[idx]

    def get_body_xmat(self, body_name):
        idx = self.model.body_names.index(six.b(body_name))
        return self.model.data.xmat[idx].reshape((3, 3))

    def get_site_pos(self, site_name):
        return self.data.get_site_xpos(site_name)  # returns 1D array with shape(3,)

    def state_vector(self):
        return np.concatenate([
            self.sim.data.qpos.flat,
            self.sim.data.qvel.flat
        ])
