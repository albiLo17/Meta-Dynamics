import torch
import numpy as np
import math
from torch.utils.data import Dataset
import json
import os
from tqdm import tqdm
import time


def make_maml_batch(domains, read_domain, n_trj, len_trj, t_steps, K):
    x_support = []
    a_support = []
    y_support = []
    x_query = []
    a_query = []
    y_query = []

    for domain in domains:
        x, x1, a = read_domain(domain)

        support_idxs = np.random.choice(x.shape[0], K, replace=False)
        query_idxs = list(range(x.shape[0]))
        for support_idx in support_idxs:
            query_idxs.remove(support_idx)

        x_s = np.reshape(x[support_idxs], (K * (len_trj - t_steps + 1), -1))
        x1_s = np.reshape(x1[support_idxs], (K * (len_trj - t_steps + 1), -1))
        a_s = np.reshape(a[support_idxs], (K * (len_trj - t_steps + 1), -1))
        x_q = np.reshape(x[query_idxs], ((n_trj - K) * (len_trj - t_steps + 1), -1))
        x1_q = np.reshape(x1[query_idxs], ((n_trj - K) * (len_trj - t_steps + 1), -1))
        a_q = np.reshape(a[query_idxs], ((n_trj - K) * (len_trj - t_steps + 1), -1))

        idx = list(range(x_s.shape[0]))
        np.random.shuffle(idx)

        x_support.append(np.expand_dims(x_s[idx], 0))
        y_support.append(np.expand_dims(x1_s[idx], 0))
        a_support.append(np.expand_dims(a_s[idx], 0))

        idx = list(range(x_q.shape[0]))
        np.random.shuffle(idx)

        x_query.append(np.expand_dims(x_q[idx], 0))
        y_query.append(np.expand_dims(x1_q[idx], 0))
        a_query.append(np.expand_dims(a_q[idx], 0))

    x_support = torch.from_numpy(np.concatenate(x_support, 0)).float()
    a_support = torch.from_numpy(np.concatenate(a_support, 0)).float()
    y_support = torch.from_numpy(np.concatenate(y_support, 0)).float()
    x_query = torch.from_numpy(np.concatenate(x_query, 0)).float()
    a_query = torch.from_numpy(np.concatenate(a_query, 0)).float()
    y_query = torch.from_numpy(np.concatenate(y_query, 0)).float()

    return x_support, a_support, y_support, x_query, a_query, y_query


def make_non_maml_batch(domains, read_domain, n_trj, len_trj, t_steps):
    x_data = []
    a_data = []
    y_data = []

    for domain in domains:
        x, x1, a = read_domain(domain)

        x_s = np.reshape(x, (n_trj * (len_trj - t_steps + 1), -1))
        x1_s = np.reshape(x1, (n_trj * (len_trj - t_steps + 1), -1))
        a_s = np.reshape(a, (n_trj * (len_trj - t_steps + 1), -1))

        idx = list(range(x_s.shape[0]))
        np.random.shuffle(idx)

        x_data.append(np.expand_dims(x_s[idx], 0))
        y_data.append(np.expand_dims(x1_s[idx], 0))
        a_data.append(np.expand_dims(a_s[idx], 0))

    # todo: load numpy not torch?
    x_data = torch.from_numpy(np.concatenate(x_data, 0)).float()
    a_data = torch.from_numpy(np.concatenate(a_data, 0)).float()
    y_data = torch.from_numpy(np.concatenate(y_data, 0)).float()

    return x_data, a_data, y_data


def euler_yaw_z_from_quaternion(quat):
    x = quat[0]
    y = quat[1]
    z = quat[2]
    w = quat[3]
    t3 = +2.0 * (w * z + x * y)
    t4 = +1.0 - 2.0 * (y * y + z * z)
    yaw_z = math.atan2(t3, t4)
    return yaw_z

class PushingDataset(Dataset):

    def __init__(self, params):

        self.subset = params['subset']
        self.val_ratio = params['test_split']

        self.dlo_only = params['dlo_only']
        self.obj_only = params['obj_only']
        self.obj_input = params['obj_input']

        self.maml = params['maml']
        self.t_steps = params['t_steps']

        self.max_len_dlo = 32
        self.max_n_obj = 3
        self.n_trj = 500
        self.len_trj = 20  # 21 steps, 20 to predict

        # self.data_dir = '/Midgard/Data/areichlin/Robert_meta_learn/meta_learn3_clean'
        # self.data_dir = './meta_learn2_clean'
        self.data_dir = './meta_learn'

        self.subset_values = []
        self.subset_training_data = []
        self.subset_test_data = []

        self.data = {}

        for dir in os.listdir(self.data_dir):
            with open(self.data_dir+'/'+dir+'/params.json', 'r') as f:
                datapoint = json.load(f)
                self.data[str(datapoint["domain_id"])] = datapoint

        self.training_data = []
        self.test_data = []

        self.ordered_data = {}

        for m_type in ['soft', 'flexible', 'elastoplastic']:
            self.ordered_data[m_type] = {}
            for att in ['none', 'movable', 'fixed']:
                self.ordered_data[m_type][att] = {}
                for l in [0.1, 0.11, 0.12, 0.13, 0.14, 0.15, 0.16]:
                    self.ordered_data[m_type][att][l] = {}
                    for n_obj in [0, 1, 2, 3]:
                        self.ordered_data[m_type][att][l][n_obj] = []



        for key, value in self.data.items():
            self.ordered_data[value['dlo']['material_type']][value['dlo']['attachment']][value['dlo']['length']][len(value['rigid_objects'])].append(key)






        # import matplotlib.pyplot as plt
        # sub_set = []
        # for m_type in ['flexible']:
        #     for att in ['none']:
        #         for l in [0.1]:
        #             for n_obj in [3]:
        #                 sub_set.extend(self.ordered_data[m_type][att][l][n_obj])
        # count = 0
        # for dom in sub_set:
        #     x, x1, a = self.read_domain(dom)
        #     for trj in range(2):
        #         fig = plt.figure()
        #         for t in range(19):
        #             for dlo in range(20):
        #                 plt.plot(x1[trj, t, dlo, 0], x1[trj, t, dlo, 1], 'ro', alpha=(t*1/20.))
        #         plt.show()
        #         count += 1
        #         if count == 20:
        #             break
        # print()






        for m_type in ['soft', 'flexible', 'elastoplastic']:
            for att in ['none', 'movable', 'fixed']:
                for l in [0.1, 0.11, 0.12, 0.13, 0.14, 0.15, 0.16]:
                    for n_obj in [0, 1, 2, 3]:
                        train_split = int(len(self.ordered_data[m_type][att][l][n_obj])*(1. - self.val_ratio))
                        self.training_data.extend(self.ordered_data[m_type][att][l][n_obj][:train_split])
                        self.test_data.extend(self.ordered_data[m_type][att][l][n_obj][train_split:])

        if self.subset == 1:
            self.load_subset()

    def load_subset(self):
        for m_type in ['soft', 'flexible', 'elastoplastic']:
            for att in ['none', 'movable', 'fixed']:
                for l in [0.16]:
                    for n_obj in [0]:
                        train_split = int(len(self.ordered_data[m_type][att][l][n_obj]) * (1. - self.val_ratio))
                        self.subset_training_data.extend(self.ordered_data[m_type][att][l][n_obj][:train_split])
                        self.subset_test_data.extend(self.ordered_data[m_type][att][l][n_obj][train_split:])

        for indeces in [self.subset_training_data, self.subset_test_data]:
            x_data = []
            a_data = []
            y_data = []
            for domain in indeces:
                x, x1, a = self.read_domain(domain)
                x_data.append(torch.from_numpy(x).float())
                a_data.append(torch.from_numpy(a).float())
                y_data.append(torch.from_numpy(x1).float())
            self.subset_values.append({'x': x_data, 'a': a_data, 'y': y_data})

    def get_subset_batch(self, mode, N, K):

        if mode == 'train':
            mode_idx = 0
        else:
            mode_idx = 1

        if mode_idx == 0:
            task_sims = np.random.choice(range(len(self.subset_values[mode_idx]['x'])), N, replace=False)
        else:
            task_sims = range(len(self.subset_values[mode_idx]['x']))

        if self.maml == 0:
            x_s, a_s, y_s = [], [], []
            for task in task_sims:

                idx = list(range(self.n_trj * (self.len_trj - self.t_steps + 1)))
                np.random.shuffle(idx)

                x_s.append(torch.reshape(self.subset_values[mode_idx]['x'][task], (1, self.n_trj * (self.len_trj - self.t_steps + 1), -1))[:, idx])
                a_s.append(torch.reshape(self.subset_values[mode_idx]['a'][task], (1, self.n_trj * (self.len_trj - self.t_steps + 1), -1))[:, idx])
                y_s.append(torch.reshape(self.subset_values[mode_idx]['y'][task], (1, self.n_trj * (self.len_trj - self.t_steps + 1), -1))[:, idx])

            x_s = torch.cat(x_s, 0)
            a_s = torch.cat(a_s, 0)
            y_s = torch.cat(y_s, 0)

            return x_s, a_s, y_s, None, None, None

        else:
            x_s, a_s, y_s, x_q, a_q, y_q = [], [], [], [], [], []
            for task in task_sims:

                idx = list(range(self.subset_values[mode_idx]['x'][task].shape[0]))
                np.random.shuffle(idx)

                # idx_s = list(range((K) * (self.len_trj - self.t_steps + 1)))
                # np.random.shuffle(idx)
                #
                # idx_q = list(range((self.n_trj - K) * (self.len_trj - self.t_steps + 1)))
                # np.random.shuffle(idx)

                x_s.append(torch.reshape(self.subset_values[mode_idx]['x'][task][idx[:K]], (1, (K) * (self.len_trj - self.t_steps + 1), -1)))#[:, idx_s])
                a_s.append(torch.reshape(self.subset_values[mode_idx]['a'][task][idx[:K]], (1, (K) * (self.len_trj - self.t_steps + 1), -1)))#[:, idx_s])
                y_s.append(torch.reshape(self.subset_values[mode_idx]['y'][task][idx[:K]], (1, (K) * (self.len_trj - self.t_steps + 1), -1)))#[:, idx_s])
                x_q.append(torch.reshape(self.subset_values[mode_idx]['x'][task][idx[K:]], (1, (self.n_trj - K) * (self.len_trj - self.t_steps + 1), -1)))#[:, idx_q])
                a_q.append(torch.reshape(self.subset_values[mode_idx]['a'][task][idx[K:]], (1, (self.n_trj - K) * (self.len_trj - self.t_steps + 1), -1)))#[:, idx_q])
                y_q.append(torch.reshape(self.subset_values[mode_idx]['y'][task][idx[K:]], (1, (self.n_trj - K) * (self.len_trj - self.t_steps + 1), -1)))#[:, idx_q])

            x_s = torch.cat(x_s, 0)
            a_s = torch.cat(a_s, 0)
            y_s = torch.cat(y_s, 0)
            x_q = torch.cat(x_q, 0)
            a_q = torch.cat(a_q, 0)
            y_q = torch.cat(y_q, 0)

            return x_s, a_s, y_s, x_q, a_q, y_q

    def get_batch(self, mode, N, K):

        if self.subset == 1:
            return self.get_subset_batch(mode, N, K)

        if mode == 'train':
            sims = self.training_data
        else:
            sims = self.test_data

        task_sims = np.random.choice(sims, N)

        if self.maml == 0:

            x_data, a_data, y_data = make_non_maml_batch(task_sims, self.read_domain, self.n_trj, self.len_trj, self.t_steps)

            return x_data, a_data, y_data, None, None, None

        x_support, a_support, y_support, x_query, a_query, y_query = make_maml_batch(task_sims, self.read_domain, self.n_trj, self.len_trj, self.t_steps, K)

        return x_support, a_support, y_support, x_query, a_query, y_query

    def get_domain(self, K):

        sims = self.test_data
        if self.subset:
            sims = self.subset_test_data

        task_sims = np.random.choice(sims, 1)

        if self.maml == 0:

            x_data, a_data, y_data = make_non_maml_batch(task_sims, self.read_domain, self.n_trj, self.len_trj, self.t_steps)

            return x_data, a_data, y_data, None, None, None

        x_support, a_support, y_support, x_query, a_query, y_query = make_maml_batch(task_sims, self.read_domain, self.n_trj, self.len_trj, self.t_steps, K)

        return x_support, a_support, y_support, x_query, a_query, y_query

    def read_domain(self, folder):

        if self.subset:
            last_dim = 2
        else:
            last_dim = 3

        data_info = self.data[folder]

        folder = '0'*(5-len(folder)) + folder
        data_dir = self.data_dir + '/' + folder

        # Load state space data
        f_pos_data = "%s/data_pos_all.npy" % data_dir
        f_or_data = "%s/data_or_all.npy" % data_dir
        f_action_data = "%s/data_true_action_all.npy" % data_dir

        # Load position data
        pos_data = np.load(f_pos_data)

        # Load orientation data
        or_data = np.load(f_or_data)

        # Load action data
        actions_data = np.load(f_action_data)

        n_traj = pos_data.shape[0]
        n_states_per_traj = pos_data.shape[1]
        # self.n_interactions = self.n_traj * (self.n_states_per_traj - 1)
        n_dlo_segments = int(data_info["dlo"]["length"] * 200)  # a new segment every 5mm
        n_rigid_objects = len(data_info["rigid_objects"])  # number of rigid object can be taken form params file

        # Get position of pusher
        pusher_pos_all = np.ones((n_traj, n_states_per_traj, 1, last_dim))
        pusher_pos_all[:, :, 0, :2] = pos_data[:, :, 0]  # first element in pos is pusher

        # Get position of segments
        seg_pos_all = np.zeros((n_traj, n_states_per_traj, self.max_len_dlo, last_dim))
        seg_pos_all[:, :, :n_dlo_segments, :2] = pos_data[:, :, 1:1+n_dlo_segments]  # following ones are segment positions
        if not self.subset:
            seg_pos_all[:, :, :n_dlo_segments, 2] = 1

        # Get data for rigid objects
        # rigid_object_or_all = np.zeros((n_traj, n_states_per_traj, self.max_n_obj, last_dim))
        # rigid_object_pos_all = np.zeros((n_traj, n_states_per_traj, self.max_n_obj, last_dim))
        if n_rigid_objects > 0:
            rigid_object_or_all = np.zeros((n_traj, n_states_per_traj, self.max_n_obj, last_dim))
            rigid_object_pos_all = np.zeros((n_traj, n_states_per_traj, self.max_n_obj, last_dim))
            # Saved orientations are represented using quaternions.
            # We compute the euler angle around the z-axis to get a more compact representation.
            # An even better encoding is probably to split into sine and cosine of the angle (what I did here...)
            # rigid_object_or_all = np.zeros(shape=(or_data.shape[0], or_data.shape[1], n_rigid_objects, 2))
            for i in range(or_data.shape[0]):
                for j in range(or_data[i].shape[0]):
                    for k in range(n_rigid_objects):
                        orientation = euler_yaw_z_from_quaternion(or_data[i, j, -n_rigid_objects + k])
                        or_data[i, j, k, 0] = np.sin(orientation)
                        or_data[i, j, k, 1] = np.cos(orientation)

            rigid_object_or_all[:, :, :n_rigid_objects, :2] = or_data[:, :, :, :2]
            if not self.subset:
                rigid_object_or_all[:, :, :n_rigid_objects, 2] = 1

            # For the rigid objects we are interested in the positions of the bodies (might contain multiple geometries)
            # Body positions are in the second part of the pos array
            rigid_object_pos_all[:, :, :n_rigid_objects, :2] = pos_data[:, :, -n_rigid_objects:]
            if not self.subset:
                rigid_object_pos_all[:, :, :n_rigid_objects, 2] = 1

        if self.dlo_only != 1:
            states = np.concatenate([pusher_pos_all, seg_pos_all, rigid_object_pos_all, rigid_object_or_all], -2)
        else:
            states = np.concatenate([pusher_pos_all, seg_pos_all], -2)

        actions = np.zeros((n_traj, n_states_per_traj-self.t_steps, 2*self.t_steps))
        for t in range(n_states_per_traj-self.t_steps):
            actions[:, t] = np.reshape(actions_data[:, t:t+self.t_steps], (self.n_trj, -1))

        current_states = states[:, :(n_states_per_traj-self.t_steps)]
        next_states = states[:, self.t_steps:, :, :2]
        if self.dlo_only == 1:
            next_states = states[:, self.t_steps:, 1:(1+n_dlo_segments), :2]

        if self.obj_only == 1:
            next_states = states[:, self.t_steps:, (1 + n_dlo_segments):-3, :2]

        return current_states, next_states, actions

