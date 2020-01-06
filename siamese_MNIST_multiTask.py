#!/usr/bin/env python
# coding: utf-8

from utils import *

from datasets import DatasetTorchvision, SiameseMNIST, SiameseMNIST_MT
from networks import EmbeddingNet, SiameseNet, SiameseNet_ClassNet
from losses import ContrastiveLoss
from losses import ContrastiveLoss_mod, CrossEntropy

import torch
from torchvision import transforms
from torch.optim import lr_scheduler
import torch.optim as optim
from torch.autograd import Variable
import warnings
warnings.filterwarnings("ignore")

from metrics import *
from trainer import fit, fit_siam, fit_org
import numpy as np

# get_ipython().run_line_magic('matplotlib', 'inline')
import matplotlib
import matplotlib.pyplot as plt

import os
from utils import *
import utils
import sys

cuda = torch.cuda.is_available()
"""
######################################################################

1. add metric "siameseEucDist" - Done
2. Do data processing: siamese and classification data togther for multitasking - under procsess
3. Modify the trainer function


######################################################################
"""

def writeAndSave(write_var, mix_weight_list, margin, seed_offset, n_epochs, interval, log_tag, write_list):
    write_list.append(write_var)
    mw_list.append(', '.join(mix_weight_list))
    
    exp_tag = getSaveTag(margin, seed_offset, n_epochs, interval)
    write_txt("log_{}/{}.txt".format(log_tag, exp_tag), write_list)

    print("write var:", write_var)
    return write_list, mw_list
            
seed_offset, ATLW = int(sys.argv[1]), str(sys.argv[2])

dataC = DatasetTorchvision('MNIST')
train_dataset, test_dataset, n_classes = dataC.getDataset()


os.environ["CUDA_VISIBLE_DEVICES"] = "1,2,3,4"
        
batch_size = 2**12

log_interval = 500

siamese_MT_train_dataset = SiameseMNIST_MT(train_dataset, seed=0, noisy_label=False) 
siamese_MT_test_dataset = SiameseMNIST_MT(test_dataset, seed=0, noisy_label=False)
        
# Step 4
margin=1.0
loss_fn = ContrastiveLoss_mod(margin)
loss_fn_ce = CrossEntropy()
loss_fn_tup = (loss_fn, loss_fn_ce)


interval = 0.025
write_list, mw_list = [], []
kwargs = {'num_workers': 1, 'pin_memory': True} if cuda else {}

# For reproducibility
torch.backends.cudnn.deterministic = True
torch.backends.cudnn.benchmark = False

metric_classes=[SimpleSiamDistAcc, AccumulatedAccuracyMetric_mod]

if ATLW   == 'na': # No automatic loss weight tuning: Grid search
    start = 0.5
    n_epochs = 20
    start, interval, end = start, 0.25, start + interval
    seedmax = 1
    log_tag = "grid_search"
elif ATLW == 'kl': # KLMW and MVMW
    init_mix_weight = 0.5
    n_epochs = 2
    start, interval, end = 0, 1, 1
    seedmax = 50
    log_tag = "auto"
elif ATLW == 'gn': # GradNorm method
    init_mix_weight = 0.5
    n_epochs = 20
    start, interval, end = 0, 1, 1
    seedmax = 50
    log_tag = "gradnorm"


for k in range(0, seedmax):
    for mwk, mix_weight in enumerate(np.arange(start, end, interval)):
        if ATLW:
            mix_weight = init_mix_weight
            print("Mix weight count:", mwk, mix_weight)

        # Setting a seed and an initial weight.
        mix_weight = round(mix_weight, 3)
        seed = k + seed_offset
        torch.manual_seed(seed)
        np.random.seed(seed)

        # Data Loader Initialization
        siamese_train_MT_loader = torch.utils.data.DataLoader(siamese_MT_train_dataset, batch_size=batch_size, shuffle=False, **kwargs)
        siamese_test_MT_loader = torch.utils.data.DataLoader(siamese_MT_test_dataset, batch_size=batch_size, shuffle=True, **kwargs)
        
        # Model Initialization
        embedding_net = EmbeddingNet()
        model_mt = SiameseNet_ClassNet(embedding_net, n_classes=n_classes)
        
        # Step 3
        if cuda:
            model_mt.cuda()
            
        optimizer_mt = optim.Adam
        scheduler_mt = None
        
        mix_weight = torch.tensor(mix_weight).cuda()
        write_var, mix_weight, mix_weight_list = fit_siam(siamese_train_MT_loader, siamese_test_MT_loader, model_mt, loss_fn_tup, optimizer_mt, scheduler_mt, n_epochs, cuda, log_interval, mix_weight, ATLW, metric_classes=metric_classes, seed=seed)

        write_list, mw_list = writeAndSave(write_var, mix_weight_list, margin, seed_offset, n_epochs, interval, log_tag, write_list)


