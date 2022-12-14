import os, sys
import numpy as np
import torch
from dgl import graph
import pickle as pkl


class GraphDataset():

    def __init__(self, category = 'suzuki', split = 'trn', use_rxnfp = False, seed = None):

        assert split in ['trn', 'val', 'tst']

        self.category = category
        self.split = split
        self.use_rxnfp = use_rxnfp
        self.seed = seed
        
        self.load()


    def load(self, frac_val = 0.1):

        _, clist = np.load('./data/data_%s.npz'%self.category, allow_pickle = True)['data']
        
        if self.split in ['trn', 'val']:
            with open('./data/data_dgl_%s_trn.pkl'%self.category, 'rb') as f:  
                self.rmol_graphs, self.pmol_graphs, self.y, self.rsmi = pkl.load(f)
            
            np.random.seed(self.seed)
            split_trn = int(len(self.y) * (1 - frac_val))
            if self.split == 'trn': indices = np.random.permutation(len(self.y))[:split_trn] 
            elif self.split == 'val': indices = np.random.permutation(len(self.y))[split_trn:]
            
            self.rmol_graphs = [self.rmol_graphs[i] for i in indices]
            self.pmol_graphs = [self.pmol_graphs[i] for i in indices]
            self.y = [self.y[i] for i in indices]
            self.rsmi = [self.rsmi[i] for i in indices]
                
        else:
            with open('./data/data_dgl_%s_%s.pkl'%(self.category, self.split), 'rb') as f:  
                self.rmol_graphs, self.pmol_graphs, self.y, self.rsmi = pkl.load(f)

        self.n_classes = len(clist)
        self.rmol_max_cnt = len(self.rmol_graphs[0])
        self.pmol_max_cnt = len(self.pmol_graphs[0])
        self.node_dim = self.rmol_graphs[0][0].ndata['node_attr'].shape[1]
        self.edge_dim = self.rmol_graphs[0][0].edata['edge_attr'].shape[1]
        self.cnt_list = [len(a) for a in self.y]
        self.n_reactions = len(self.y)
        self.n_conditions = np.sum(self.cnt_list)
        
        if self.split == 'trn':
            self.rmol_graphs = sum([[self.rmol_graphs[i]] * self.cnt_list[i] for i in range(len(self.y))], [])
            self.pmol_graphs = sum([[self.pmol_graphs[i]] * self.cnt_list[i] for i in range(len(self.y))], [])
            self.rsmi = np.repeat(self.rsmi, self.cnt_list, 0).tolist()
            self.y = sum(self.y, [])
            
        assert len(self.rmol_graphs) == len(self.y)
        
        if self.use_rxnfp:
            del self.rmol_graphs
            del self.pmol_graphs
        
            from rdkit import Chem
            from rdkit.Chem import AllChem
            
            self.fp_dim = 16384
            self.rxnfp = []
            for rs in self.rsmi:
                rmol, pmol = rs.split('>>')
                rfp = AllChem.GetMorganFingerprintAsBitVect(mol = Chem.MolFromSmiles(rmol), radius=2, nBits = self.fp_dim, useFeatures = False, useChirality = True)
                pfp = AllChem.GetMorganFingerprintAsBitVect(mol = Chem.MolFromSmiles(pmol), radius=2, nBits = self.fp_dim, useFeatures = False, useChirality = True)
                rxnfp = np.array(pfp.ToList(), dtype = np.int8) - np.array(rfp.ToList(), dtype = np.int8)
                
                self.rxnfp.append(rxnfp)
                
            self.rxnfp = np.array(self.rxnfp)
            

    def __getitem__(self, idx):

        if self.split == 'trn':
            label = np.zeros(self.n_classes, dtype = bool)
            label[self.y[idx]] = 1
        else:
            label = 0

        if self.use_rxnfp:
            return torch.FloatTensor(self.rxnfp[idx]), torch.FloatTensor(label)
        
        else:
            rg = self.rmol_graphs[idx]
            pg = self.pmol_graphs[idx]
            
            for g in rg:
                g.ndata['node_attr'] = g.ndata['node_attr'].float()
                g.edata['edge_attr'] = g.edata['edge_attr'].float()
                
            for g in pg:
                g.ndata['node_attr'] = g.ndata['node_attr'].float()
                g.edata['edge_attr'] = g.edata['edge_attr'].float()
            
            if self.split == 'trn':
                label = np.zeros(self.n_classes, dtype = bool)
                label[self.y[idx]] = 1
            else:
                label = 0
    
            return *rg, *pg, label
        
        
    def __len__(self):

        return len(self.y)