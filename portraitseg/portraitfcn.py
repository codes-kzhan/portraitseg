# https://github.com/wkentaro/pytorch-fcn/blob/master/torchfcn/models/fcn8s.py

import numpy as np
import torch
import torch.nn as nn
from torchfcn.models import FCN8s


# https://github.com/wkentaro/pytorch-fcn/blob/master/torchfcn/models/fcn32s.py
def get_upsampling_weight(in_channels, out_channels, kernel_size):
    """Make a 2D bilinear kernel suitable for upsampling"""
    factor = (kernel_size + 1) // 2
    if kernel_size % 2 == 1:
        center = factor - 1
    else:
        center = factor - 0.5
    og = np.ogrid[:kernel_size, :kernel_size]
    filt = (1 - abs(og[0] - center) / factor) * \
           (1 - abs(og[1] - center) / factor)
    weight = np.zeros((in_channels, out_channels, kernel_size, kernel_size),
                      dtype=np.float64)
    weight[range(in_channels), range(out_channels), :, :] = filt
    return torch.from_numpy(weight).float()


class PortraitFCN(FCN8s):

    def __init__(self, n_class=2):
        super().__init__(n_class=n_class)

class PortraitFCNPlus(PortraitFCN):

    def __init__(self, load_weights=True):
        super().__init__()
        if load_weights:
            path_to_weights = "portraitseg/portraitfcn_untrained.pth"
            self.load_state_dict(torch.load(path_to_weights))
        kernels = self.conv1_1.weight.data
        k = 3  # Kernel size
        c_in = 6  # Number of input channels
        c_out = 64  # Number of output channels
        size = (c_in, k, k)
        n = k * k * c_out
        superkernels = torch.from_numpy(np.zeros((c_out, c_in, k, k)))
        for i, kernel in enumerate(kernels):
            superkernel = torch.from_numpy(np.random.normal(0, np.sqrt(2./n), size=size))
            superkernel[:3] = kernel
            superkernels[i] = superkernel
        self.conv1_1.weight.data = superkernels.float()

class FCN8s_probe(FCN8s):

    def __init__(self, n_class=21):
        super().__init__()

    def forward(self, x):
        activations = []

        h = x
        h = self.relu1_1(self.conv1_1(h))
        h = self.relu1_2(self.conv1_2(h))
        h = self.pool1(h)

        h = self.relu2_1(self.conv2_1(h))
        h = self.relu2_2(self.conv2_2(h))
        h = self.pool2(h)

        h = self.relu3_1(self.conv3_1(h))
        h = self.relu3_2(self.conv3_2(h))
        h = self.relu3_3(self.conv3_3(h))
        h = self.pool3(h)
        pool3 = h  # 1/8
        activations.append(('pool3', pool3))

        h = self.relu4_1(self.conv4_1(h))
        h = self.relu4_2(self.conv4_2(h))
        h = self.relu4_3(self.conv4_3(h))
        h = self.pool4(h)
        pool4 = h  # 1/16
        activations.append(('pool4', pool4))

        h = self.relu5_1(self.conv5_1(h))
        h = self.relu5_2(self.conv5_2(h))
        h = self.relu5_3(self.conv5_3(h))
        h = self.pool5(h)

        h = self.relu6(self.fc6(h))
        h = self.drop6(h)

        h = self.relu7(self.fc7(h))
        h = self.drop7(h)
        activations.append(('fr', h))

        h = self.score_fr(h) # 1/32
        activations.append(('score_fr', h))
        h = self.upscore2(h)
        upscore2 = h  # 1/16
        activations.append(('upscore2', upscore2))

        h = self.score_pool4(pool4)
        activations.append(('score_pool4', h))
        h = h[:, :, 5:5 + upscore2.size()[2], 5:5 + upscore2.size()[3]]
        score_pool4c = h  # 1/16

        h = upscore2 + score_pool4c  # 1/16
        h = self.upscore_pool4(h)
        upscore_pool4 = h  # 1/8

        h = self.score_pool3(pool3)
        activations.append(('score_pool3', h))
        h = h[:, :,
              9:9 + upscore_pool4.size()[2],
              9:9 + upscore_pool4.size()[3]]
        score_pool3c = h  # 1/8

        h = upscore_pool4 + score_pool3c  # 1/8

        h = self.upscore8(h)
        h = h[:, :, 31:31 + x.size()[2], 31:31 + x.size()[3]].contiguous()
        activations.append(('output', h))

        return activations