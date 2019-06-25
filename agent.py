"""AI agent using RL to beat the game.

Authors:
    Gael Colas
    Sanyam Mehra (CS229 teaching staff): HW4 solutions
"""

import numpy as np

# handled type of obstacles
OBSTACLE_TYPES = {'CACTUS_SMALL': 0, 'CACTUS_LARGE': 1, 'PTERODACTYL': 2}
MAX_CONSECUTIVE_OBS = 3
PTERODACTYL_HEIGHTS = [50, 75, 100]

class AIAgent:
    """AI agent controlling the Dino.
    The AI agent is trained by Reinforcement Learning.
    Every time the agent finishes a simulation, he builds an approximate Markov Decision Process based on the transition and the reward observed.
    At the end of the simulation, he computes the approximated value function through Value Iteration.
    This value function is then used to choose the best actions of the next simulation.
    
    Attributes:
        'args' (ArgumentParser): parser gethering all the Game parameters
        'gamma' (float): discount factor
        'eps' (float): epsilon-greedy coefficient
        'mdp' (MDP): approximate MDP current parameters
        
        'dino' (Dino): Dino controller
        
        'state' (dict): the current state of the Dino
        'action' (int): the current action 
                action = 1 if 'jumping', 2 if 'ducking', 0 otherwise
    """
    
    def __init__(self, args, dino):
        super(AIAgent).__init__()
        
        # RL parameters
        self.args = args
        self.gamma = args.gamma
        self.eps = 1.
        self.tolerance = args.tolerance
        # initialize the approximate MDP parameters
        self.initialize_mdp_data()
        
        # Dino controller
        self.dino = dino
        
        # current state and action
        self.state = dino.get_state()
        self.action = 0

    def get_reward(self, isCrashed):
        """Reward function.
        
        Args:
            'isCrashed' (bool): whether the Game has been failed at the current state
            
        Return:
            'reward' (float): reward earned in the current state
            
        Remarks:
            Losing the game: -1000
            Being alive: +1
        """
        if isCrashed:
            reward = -1000
        else:
            reward = 1  
        
        return reward
        
    def reset(self):
        """Reset the simulation parameters.
        """    
        # update the approximate MDP with the simulation observations
        self.update_mdp_parameters()
        
        # make the algorithm more greedy
        self.eps += 0.01
        
        # start a new simulation
        self.dino.start()
        
    def choose_action(self):
        """Choose the next action with an Epsilon-Greedy exploration strategy.
        """        
        if np.random.rand() < self.eps:            
            self.action = self.best_action(self.state)
        else:
            self.action = np.random.rand() < 0.01
            
        if self.action == 1:
            self.dino.jump()
            
        elif self.action == 2:
            self.dino.duck()

    def best_action(self, state):
        """Choose the next action (0, 1 or 2) that is optimal according to your current 'mdp_data'. 
        When there is no optimal action, return 0 has "do nothing" is more frequent.
        
        Args:
            'state' (dict): current state of the Bird
            
        Return:
            'action' (int, 0 or 1): optimal action in the current state according to the approximate MDP
        """
        # get the index of the closest discretized state
        s = self.get_closest_state_idx(state)
        
        # value function if taking each action in the current state 
        score_nothing = self.mdp_data['transition_probs'][s, 0, :].dot(self.mdp_data['value'])
        score_jump = self.mdp_data['transition_probs'][s, 1, :].dot(self.mdp_data['value'])
        score_duck = self.mdp_data['transition_probs'][s, 2, :].dot(self.mdp_data['value'])

        # best action in the current state
        action = (score_jump > score_nothing and score_jump >= score_duck)*1 + (score_duck > score_nothing and score_duck > score_jump)*2
        
        return action
        
    def get_closest_state_idx(self, state, isFail=False):
        """Get the index of the closest discretized state.
        
        Args:
            'state' (dict): the current state of the Bird
            'isFail' (bool): whether the Game is failed
            
        Return:
            'ind' (int): index of the closest discretized state
            
        Remarks:
            State 0 is a FAIL state.
            State 1 is a NO_OBSTACLE state.
        """
        # discretized state
        dx_s, dn_cactus_s, dy_pter_s = self.mdp_data["state_discretization"]
                
        if not state: # no obstacle created yet
            return 1
            
        # check the type of the next obstacle
        obs_type = OBSTACLE_TYPES[state['type']]
        
        if state['type'] == "PTERODACTYL":
            j = np.argmin(abs(dy_pter_s - state['config']))
        else:
            j = np.argmin(abs(dn_cactus_s - state['config']))
        
        # closest discretized state indices
        k = np.argmin(abs(dx_s - state['dx']))
                
        return (not isFail)*(obs_type*dy_pter_s.size*dx_s.size + j*dx_s.size + k + 2)
        
    def initialize_mdp_data(self):
        """Save a attributes 'mdp_data' that contains all the parameters defining the approximate MDP.
        
        Parameters:
            'num_states' (int): the number of discretized states.
                    num_states = n_obs_type * n_config * n_x + 1
        
        Initialization scheme:
            - Value function array initialized to 0
            - Transition probability initialized uniformly: p(x'|x,a) = 1/num_states 
            - State rewards initialized to 0
        """
        
        num_states = ( (len(OBSTACLE_TYPES)-1)*MAX_CONSECUTIVE_OBS + 1*len(PTERODACTYL_HEIGHTS) )*self.args.n_x + 2
        
        # state discretization
        dx_s = np.linspace(0, self.args.max_dx, self.args.n_x)
        dn_cactus_s = np.array(range(1, MAX_CONSECUTIVE_OBS+1))
        dy_pter_s = np.array(PTERODACTYL_HEIGHTS).astype(float)

        # mdp parameters initialization
        transition_counts = np.zeros((num_states, 3, num_states))
        transition_probs = np.ones((num_states, 3, num_states)) / num_states
        reward_counts = np.zeros((num_states, 2))
        reward = np.zeros(num_states)
        value = np.zeros(num_states)

        self.mdp_data = {
            'num_states': num_states,
            'state_discretization': [dx_s, dn_cactus_s, dy_pter_s],
            'transition_counts': transition_counts,
            'transition_probs': transition_probs,
            'reward_counts': reward_counts,
            'reward': reward,
            'value': value
        }
        
    def set_transition(self):
        """Update the approximate MDP with the given transition.
        """
        # whether the Game has been failed at the new state
        isCrashed = self.dino.is_crashed()
        # get the new state
        new_state = self.dino.get_state()
        # get the previous state reward
        reward = self.get_reward(isCrashed)
        # store the given transition
        self.update_mdp_counts(self.state, self.action, new_state, reward, isCrashed)
        
        # update the current state
        self.state = new_state
        
    def update_mdp_counts(self, state, action, new_state, reward, isCrashed):
        """Update the transition counts and reward counts based on the given transition.
        
        Record for all the simulations:
            - the number of times `state, action, new_state` occurs ;
            - the rewards accumulated for every `new_state`.
        
        Args:
            'state' (np.array, [y, dx, dy]): previous state of the Bird
            'action' (int, 0 or 1): last action performed
            'new_state' (np.array, [y, dx, dy]): new state after performing the action in the previous state
            'reward' (float): reward observed in the previous state
        """
        # get the index of the closest discretized previous and new states
        s = self.get_closest_state_idx(state, False)
        new_s = self.get_closest_state_idx(new_state, isCrashed)

        # update the transition and the reward counts
        self.mdp_data['transition_counts'][s, action, new_s] += 1
        self.mdp_data['reward_counts'][new_s, 0] += reward
        self.mdp_data['reward_counts'][new_s, 1] += 1

    def update_mdp_parameters(self):
        """Update the estimated MDP parameters (transition and reward functions) at the end of a simulation.
        Perform value iteration using the new estimated model for the MDP.

        Remarks:
            Only observed transitions are updated.
            Only states with observed rewards are updated.
        """
        temp = self.mdp_data['transition_probs'].copy()
        # update the transition function
        total_num_transitions = np.sum(self.mdp_data['transition_counts'], axis=-1)
        visited_state_action_pairs = total_num_transitions > 0
        self.mdp_data['transition_probs'][visited_state_action_pairs] = self.mdp_data['transition_counts'][visited_state_action_pairs] / total_num_transitions[visited_state_action_pairs, np.newaxis]

        # update the reward function
        visited_states = self.mdp_data['reward_counts'][:, 1] > 0
        self.mdp_data['reward'][visited_states] = self.mdp_data['reward_counts'][visited_states, 0] / self.mdp_data['reward_counts'][visited_states, 1]

        # update the value function through Value Iteration
        while True:           
            # Q(_,a) for the different actions
            value_nojump = np.dot(self.mdp_data['transition_probs'][:,0,:], self.mdp_data['value'])
            value_jump = np.dot(self.mdp_data['transition_probs'][:,1,:], self.mdp_data['value'])

            # Bellman update
            new_value = self.mdp_data['reward'] + self.gamma * np.maximum(value_nojump, value_jump)
            
            # difference with previous value function
            max_diff = np.max(np.abs(new_value - self.mdp_data['value']))

            self.mdp_data['value'] = new_value
            
            # check for convergence
            if max_diff < self.tolerance:
                break