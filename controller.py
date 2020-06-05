# -*- coding: utf-8 -*-

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from aug_search import AUG_TYPE
import pdb


class Controller(nn.Module):
    def __init__(self, hid_size):
        """
        init
        :param hid_size: hidden units in LSTM.
        """
        super(Controller, self).__init__()
        self.hid_size = hid_size
        self.lstm = torch.nn.LSTMCell(self.hid_size, self.hid_size)        
        
        # Embedding is for mapping action into a predifined dictionary.
        self.encoder = nn.Embedding(len(AUG_TYPE)*11, self.hid_size) # action has possibilities of type * magnitude
        
        # action is consist by both aug type and magnitude.
        self.decoder_type = nn.Linear(self.hid_size, len(AUG_TYPE))
        self.decoder_magnitude = nn.Linear(self.hid_size, 11)        # magnitude is discriticized from 0 to 10.


    def forward(self, x, hidden, batch_size):
        if x is None:
            x = self.initHidden(batch_size)
            embed = x
        else:
            embed = self.encoder(x)
        hx, cx = self.lstm(embed, hidden)

        # decode
        type_logit = self.decoder_type(hx)
        magnitude_logit = self.decoder_magnitude(hx)

        return type_logit, magnitude_logit, (hx, cx)


    def initHidden(self, batch_size):
        return torch.zeros(batch_size, self.hid_size, requires_grad=False).cuda(0)


    def sample(self, batch_size, sub_policy_num=5, sub_policy_operation=2):
        
        actions = []
        type_entropies = []
        magnitude_entropies = []
        selected_type_log_probs = []
        selected_mag_log_probs = []

        x = None
        hidden = (self.initHidden(batch_size), self.initHidden(batch_size))

        for i in range(sub_policy_num):
            sub_actions = []
            sub_type_entropies = []
            sub_magnitude_entropies =[]
            sub_selected_type_log_probs = []
            sub_selected_mag_log_probs = []
            for j in range(sub_policy_operation):
                type_logit, magnitude_logit, hidden = self.forward(x, hidden, batch_size)
                action_type_prob = F.softmax(type_logit, dim=-1)
                action_magnitude_prob = F.softmax(magnitude_logit, dim=-1)

                # Entropies as regulizer
                action_type_log_prob = F.log_softmax(type_logit, dim=-1)
                action_magnitude_log_prob = F.log_softmax(magnitude_logit, dim=-1)
                sub_type_entropies.append(-(action_type_log_prob * action_type_prob).sum(1, keepdim=True))       
                sub_magnitude_entropies.append(-(action_magnitude_log_prob * action_magnitude_prob).sum(1, keepdim=True))

                # Get actions
                action_type = action_type_prob.multinomial(1)   # batch_size * 1
                action_magnitude = action_magnitude_prob.multinomial(1)   # batch_size * 1
                action = torch.cat([action_type, action_magnitude], dim=-1) # batch_size * 2

                sub_actions.append(action)

                x = action_type*11 + action_magnitude
                x = x.squeeze(1)
                x = x.requires_grad_(False)

                # Get selected log prob, this will used for policy gradient calculation
                selected_type_log_prob = action_type_log_prob.gather(1, action_type.data)  # batch_size * 1
                sub_selected_type_log_probs.append(selected_type_log_prob)

                selected_mag_log_prob = action_magnitude_log_prob.gather(1, action_magnitude.data) 
                sub_selected_mag_log_probs.append(selected_mag_log_prob)


            # Process all these appended sub lists.   
            # [2, batch_size, 2] -> [batch_size, 2, 2]
            sub_actions = torch.stack(sub_actions).permute(1,0,2)

            # [2, batch_size, 1] -> [batch_size, 1]
            sub_type_entropies = torch.cat(sub_type_entropies, dim=-1).sum(-1, keepdim=True)
            sub_magnitude_entropies = torch.cat(sub_magnitude_entropies, dim=-1).sum(-1, keepdim=True)

            # [2, batch_size, 1] -> [batch_size, 2]
            sub_selected_type_log_probs = torch.cat(sub_selected_type_log_probs, dim=-1)
            sub_selected_mag_log_probs = torch.cat(sub_selected_mag_log_probs, dim=-1)
                    
            actions.append(sub_actions)
            type_entropies.append(sub_type_entropies)
            magnitude_entropies.append(sub_type_entropies)
            selected_type_log_probs.append(sub_selected_type_log_probs)
            selected_mag_log_probs.append(sub_selected_mag_log_probs)
        
        # Process all lists
        # [5, batch_size, 2, 2] -> [batch_size, 5, 2, 2]
        actions = torch.stack(actions).permute(1,0,2,3)
        # [5, batch_size, 1] -> [batch_size, 1]
        type_entropies = torch.cat(type_entropies, dim=-1).sum(-1, keepdim=True)
        magnitude_entropies = torch.cat(magnitude_entropies, dim=-1).sum(-1, keepdim=True)
        # [5, batch_size, 2] -> [batch_size, 5, 2]
        selected_type_log_probs = torch.stack(selected_type_log_probs).permute(1,0,2)
        selected_mag_log_probs = torch.stack(selected_mag_log_probs).permute(1,0,2)


        
        # out: 
        # actions        [bacth_size, 5, 2, 2] (type, mag)
        # type_log_prob  [batch_size, 5, 2]
        # mag_log_prob   [batch_size, 5, 2]
        # type_entropies [batch_size, 1]
        # mag_entropies  [batch_size, 1]

        return actions, {'type':selected_type_log_probs, 'magnitude':selected_mag_log_probs}, \
                        {'type':type_entropies, 'magnitude':magnitude_entropies}
