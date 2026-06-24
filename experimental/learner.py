#!/usr/bin/env python3
"""
Lightweight Reinforcement Learning for Nur.
NOT deep learning - simple Q-learning that works on 4GB RAM.
Learns from past trades to improve future decisions.
"""

import numpy as np
import pandas as pd
import json
import os
from collections import defaultdict
import pickle

class NurLearner:
    """
    Lightweight Q-learning for trading decisions.
    
    Key Features:
    1. Learns which market conditions lead to profitable trades
    2. Adjusts exit timing based on past performance
    3. Works with minimal memory (4GB RAM compatible)
    4. No GPU required
    
    Learning Method:
    - State: Simplified market condition (EMA distance, candle size, trend)
    - Action: Trading decision (enter, hold, exit early/late)
    - Reward: Based on trade outcome (+1 for TP, -1 for SL, -0.2 for early exit loss)
    """
    
    def __init__(self, config=None):
        self.config = config or {
            'learning_rate': 0.1,      # Alpha - how quickly to learn
            'discount_factor': 0.9,    # Gamma - importance of future rewards
            'exploration_rate': 0.3,   # Epsilon - probability of exploring
            'exploration_decay': 0.995,# Decay exploration over time
            'min_exploration': 0.01,   # Minimum exploration rate
            
            # State discretization
            'price_bins': 10,          # How many bins for price distance
            'volume_bins': 5,          # How many bins for volume
            'trend_bins': 3,           # Up, down, sideways
            
            # Memory limits (for 4GB RAM)
            'max_states': 1000,        # Maximum unique states to remember
            'max_memory': 10000,       # Maximum experiences to store
        }
        
        # Q-table: state -> action -> value
        self.q_table = defaultdict(lambda: defaultdict(float))
        
        # Experience memory for batch learning
        self.memory = []
        
        # Statistics
        self.stats = {
            'total_updates': 0,
            'states_learned': 0,
            'exploration_used': 0,
            'exploitation_used': 0,
            'rewards_received': 0,
            'positive_rewards': 0,
            'negative_rewards': 0,
        }
        
        # Load previous learning if exists
        self.load()
    
    def get_state(self, market_data, current_idx):
        """
        Convert complex market data into a simplified state for Q-learning.
        
        State includes:
        1. Price distance to EMA (normalized)
        2. Recent candle size (volatility)
        3. Volume trend
        4. Overall trend (last 10 candles)
        
        Returns: discretized state string
        """
        if current_idx < 10:  # Need enough history
            return "initial"
        
        try:
            current_candle = market_data.get_candle(current_idx)
            ema_value = current_candle.get('ema_200')
            
            if ema_value is None:
                return "no_ema"
            
            # 1. Price distance to EMA (normalized)
            price = current_candle['close']
            distance_pct = abs(price - ema_value) / ema_value * 100
            
            # Discretize distance
            if distance_pct < 0.05:
                distance_state = "very_close"
            elif distance_pct < 0.1:
                distance_state = "close"
            elif distance_pct < 0.2:
                distance_state = "medium"
            else:
                distance_state = "far"
            
            # 2. Recent candle size (volatility)
            candle_sizes = []
            for i in range(5):
                candle = market_data.get_candle(current_idx - i)
                if candle:
                    size = (candle['high'] - candle['low']) / candle['close'] * 100
                    candle_sizes.append(size)
            
            avg_candle_size = np.mean(candle_sizes) if candle_sizes else 0
            
            if avg_candle_size < 0.03:
                volatility_state = "low"
            elif avg_candle_size < 0.08:
                volatility_state = "medium"
            else:
                volatility_state = "high"
            
            # 3. Volume trend (if available)
            volumes = []
            for i in range(5):
                candle = market_data.get_candle(current_idx - i)
                if candle and 'tick_vol' in candle:
                    volumes.append(candle.get('tick_vol', 0))
            
            if len(volumes) >= 3:
                volume_trend = "increasing" if volumes[-1] > volumes[0] else "decreasing"
            else:
                volume_trend = "unknown"
            
            # 4. Overall trend (last 10 candles)
            prices = []
            for i in range(10):
                candle = market_data.get_candle(current_idx - i)
                if candle:
                    prices.append(candle['close'])
            
            if len(prices) >= 5:
                price_change = (prices[0] - prices[-1]) / prices[-1] * 100
                if price_change > 0.1:
                    trend_state = "uptrend"
                elif price_change < -0.1:
                    trend_state = "downtrend"
                else:
                    trend_state = "sideways"
            else:
                trend_state = "unknown"
            
            # Combine into state string
            state = f"{distance_state}_{volatility_state}_{volume_trend}_{trend_state}"
            
            # Limit number of unique states
            if len(self.q_table) > self.config['max_states']:
                # Remove least used states
                self._prune_states()
            
            return state
            
        except Exception as e:
            print(f"⚠️  Error getting state: {e}")
            return "error"
    
    def get_action(self, state, available_actions, trade_context=None):
        """
        Choose an action using epsilon-greedy strategy.
        
        Args:
            state: Current market state
            available_actions: List of possible actions
            trade_context: Optional context about current trade
        
        Returns:
            Selected action
        """
        if not available_actions:
            return None
        
        # Exploration vs Exploitation
        if np.random.random() < self.config['exploration_rate']:
            # Explore: choose random action
            action = np.random.choice(available_actions)
            self.stats['exploration_used'] += 1
            print(f"🔍 Exploring: {action} (state: {state})")
        else:
            # Exploit: choose best known action
            action_values = {a: self.q_table[state][a] for a in available_actions}
            if action_values:
                # Get action with highest Q-value
                action = max(action_values, key=action_values.get)
                self.stats['exploitation_used'] += 1
                print(f"🎯 Exploiting: {action} (value: {action_values[action]:.3f})")
            else:
                # No Q-values yet, explore
                action = np.random.choice(available_actions)
                self.stats['exploration_used'] += 1
                print(f"🔍 Initial explore: {action}")
        
        # Apply trade context if provided
        if trade_context:
            action = self._apply_trade_context(action, trade_context)
        
        # Decay exploration rate
        self.config['exploration_rate'] = max(
            self.config['min_exploration'],
            self.config['exploration_rate'] * self.config['exploration_decay']
        )
        
        return action
    
    def _apply_trade_context(self, action, trade_context):
        """
        Modify action based on current trade context.
        
        Example: If trade is already in profit, be more conservative.
        """
        if 'current_pnl_pct' in trade_context:
            pnl = trade_context['current_pnl_pct']
            
            # If in good profit, be more conservative with exits
            if pnl > 0.5 and action == 'exit_early':
                # Consider holding longer when in profit
                if np.random.random() < 0.7:  # 70% chance to hold
                    return 'hold'
        
        return action
    
    def update(self, state, action, reward, next_state, is_terminal=False):
        """
        Update Q-values using Q-learning algorithm.
        
        Q(s,a) = Q(s,a) + α * [r + γ * max(Q(s',a')) - Q(s,a)]
        
        Where:
        α = learning rate
        γ = discount factor
        r = reward
        s = current state
        a = action taken
        s' = next state
        """
        if state is None or action is None:
            return
        
        # Current Q-value
        current_q = self.q_table[state][action]
        
        # Maximum future Q-value
        if is_terminal:
            # Terminal state has no future rewards
            max_future_q = 0
        else:
            # Get max Q-value for next state
            if next_state in self.q_table:
                max_future_q = max(self.q_table[next_state].values(), default=0)
            else:
                max_future_q = 0
        
        # Calculate new Q-value
        new_q = current_q + self.config['learning_rate'] * (
            reward + self.config['discount_factor'] * max_future_q - current_q
        )
        
        # Update Q-table
        self.q_table[state][action] = new_q
        
        # Store experience for batch learning
        experience = {
            'state': state,
            'action': action,
            'reward': reward,
            'next_state': next_state,
            'is_terminal': is_terminal
        }
        self.memory.append(experience)
        
        # Limit memory size
        if len(self.memory) > self.config['max_memory']:
            self.memory = self.memory[-self.config['max_memory']:]
        
        # Update statistics
        self.stats['total_updates'] += 1
        self.stats['rewards_received'] += reward
        
        if reward > 0:
            self.stats['positive_rewards'] += 1
        elif reward < 0:
            self.stats['negative_rewards'] += 1
        
        print(f"📚 Learned: {state} -> {action} = {reward:.2f}")
        print(f"  Q-value: {current_q:.3f} -> {new_q:.3f}")
        
        # Periodic batch learning from memory
        if self.stats['total_updates'] % 100 == 0:
            self._batch_learn()
    
    def _batch_learn(self):
        """Learn from stored experiences (off-policy learning)"""
        if len(self.memory) < 100:
            return
        
        print(f"🧠 Batch learning from {len(self.memory)} experiences...")
        
        # Sample random experiences
        sample_size = min(100, len(self.memory))
        sample_indices = np.random.choice(len(self.memory), sample_size, replace=False)
        
        for idx in sample_indices:
            exp = self.memory[idx]
            
            # Skip if missing data
            if not all(key in exp for key in ['state', 'action', 'reward', 'next_state']):
                continue
            
            # Re-update with possibly new Q-values
            current_q = self.q_table[exp['state']][exp['action']]
            
            if exp['is_terminal']:
                max_future_q = 0
            else:
                max_future_q = max(self.q_table[exp['next_state']].values(), default=0)
            
            new_q = current_q + self.config['learning_rate'] * (
                exp['reward'] + self.config['discount_factor'] * max_future_q - current_q
            )
            
            self.q_table[exp['state']][exp['action']] = new_q
    
    def _prune_states(self):
        """Remove least used states to control memory usage"""
        if len(self.q_table) <= self.config['max_states']:
            return
        
        # Count state usage (approximate)
        state_usage = {}
        for exp in self.memory[-1000:]:  # Look at recent experiences
            state = exp.get('state')
            if state:
                state_usage[state] = state_usage.get(state, 0) + 1
        
        # Sort by usage
        sorted_states = sorted(state_usage.items(), key=lambda x: x[1])
        
        # Remove least used states
        states_to_remove = len(self.q_table) - self.config['max_states']
        for state, _ in sorted_states[:states_to_remove]:
            if state in self.q_table:
                del self.q_table[state]
        
        print(f"🧹 Pruned {states_to_remove} least used states")
    
    def get_recommendation(self, state, trade_type=None):
        """
        Get trading recommendation based on learned knowledge.
        
        Returns dict with:
        - confidence: How confident the system is (0-1)
        - action: Recommended action
        - explanation: Why this action is recommended
        """
        if state not in self.q_table or not self.q_table[state]:
            return {
                'confidence': 0.0,
                'action': 'hold',
                'explanation': 'No learned knowledge for this market condition'
            }
        
        # Get best action for this state
        action_values = self.q_table[state]
        best_action = max(action_values, key=action_values.get)
        best_value = action_values[best_action]
        
        # Calculate confidence (normalized)
        total_value = sum(abs(v) for v in action_values.values())
        if total_value > 0:
            confidence = abs(best_value) / total_value
        else:
            confidence = 0.5
        
        # Generate explanation
        if best_value > 0:
            explanation = f"Learned that '{best_action}' works well in this condition"
        else:
            explanation = f"Learned to avoid other actions in this condition"
        
        # Apply trade-type specific logic
        if trade_type == 'entry':
            if best_action in ['enter_long', 'enter_short']:
                confidence *= 1.2  # Boost confidence for entry signals
        elif trade_type == 'exit':
            if best_action in ['exit_early', 'hold']:
                confidence *= 1.1  # Boost confidence for exit decisions
        
        # Cap confidence
        confidence = min(1.0, max(0.0, confidence))
        
        return {
            'confidence': confidence,
            'action': best_action,
            'explanation': explanation,
            'q_value': best_value,
            'state_visits': len([exp for exp in self.memory if exp.get('state') == state])
        }
    
    def save(self, filename="nur_learning_state.pkl"):
        """Save learning state to file"""
        try:
            save_data = {
                'q_table': dict(self.q_table),
                'memory': self.memory,
                'stats': self.stats,
                'config': self.config
            }
            
            with open(filename, 'wb') as f:
                pickle.dump(save_data, f)
            
            print(f"💾 Saved learning state to {filename}")
            print(f"  States: {len(self.q_table)}, Memories: {len(self.memory)}")
            
        except Exception as e:
            print(f"❌ Error saving learning state: {e}")
    
    def load(self, filename="nur_learning_state.pkl"):
        """Load learning state from file"""
        try:
            if os.path.exists(filename):
                with open(filename, 'rb') as f:
                    save_data = pickle.load(f)
                
                # Convert back to defaultdict
                self.q_table = defaultdict(lambda: defaultdict(float))
                for state, actions in save_data.get('q_table', {}).items():
                    for action, value in actions.items():
                        self.q_table[state][action] = value
                
                self.memory = save_data.get('memory', [])
                self.stats = save_data.get('stats', self.stats.copy())
                self.config.update(save_data.get('config', {}))
                
                print(f"📂 Loaded learning state from {filename}")
                print(f"  States: {len(self.q_table)}, Memories: {len(self.memory)}")
                
        except Exception as e:
            print(f"⚠️  Error loading learning state: {e}")
            # Start fresh
            self.q_table = defaultdict(lambda: defaultdict(float))
            self.memory = []
    
    def print_stats(self):
        """Print learning statistics"""
        print("\n" + "="*60)
        print("🧠 NUR LEARNING STATISTICS")
        print("="*60)
        
        print(f"\n📊 Learning Performance:")
        print(f"   Total Updates: {self.stats['total_updates']}")
        print(f"   States Learned: {len(self.q_table)}")
        print(f"   Experiences Stored: {len(self.memory)}")
        
        print(f"\n⚖️  Exploration vs Exploitation:")
        total_decisions = self.stats['exploration_used'] + self.stats['exploitation_used']
        if total_decisions > 0:
            explore_pct = (self.stats['exploration_used'] / total_decisions) * 100
            exploit_pct = (self.stats['exploitation_used'] / total_decisions) * 100
            print(f"   Exploration: {self.stats['exploration_used']} ({explore_pct:.1f}%)")
            print(f"   Exploitation: {self.stats['exploitation_used']} ({exploit_pct:.1f}%)")
        
        print(f"\n💰 Reward Summary:")
        print(f"   Total Reward: {self.stats['rewards_received']:.2f}")
        print(f"   Positive Rewards: {self.stats['positive_rewards']}")
        print(f"   Negative Rewards: {self.stats['negative_rewards']}")
        
        print(f"\n⚙️  Configuration:")
        print(f"   Learning Rate: {self.config['learning_rate']}")
        print(f"   Exploration Rate: {self.config['exploration_rate']:.3f}")
        print(f"   Discount Factor: {self.config['discount_factor']}")
        
        # Show top learned states
        if self.q_table:
            print(f"\n🏆 Top Learned States:")
            
            # Calculate average Q-value per state
            state_scores = []
            for state, actions in self.q_table.items():
                if actions:
                    avg_q = sum(actions.values()) / len(actions)
                    state_scores.append((state, avg_q, len(actions)))
            
            # Sort by average Q-value
            state_scores.sort(key=lambda x: x[1], reverse=True)
            
            for i, (state, avg_q, action_count) in enumerate(state_scores[:5]):
                print(f"   {i+1}. {state}")
                print(f"      Avg Q: {avg_q:.3f}, Actions: {action_count}")
        
        print("\n" + "="*60)


# Test the learner
def test_learner():
    """Test the learning system"""
    print("🧪 Testing Nur Learning System")
    print("=" * 50)
    
    # Create learner
    learner = NurLearner()
    
    # Simulate learning scenarios
    print("\n1. Learning from scratch...")
    
    # Define some states and actions
    states = [
        "close_low_increasing_uptrend",
        "medium_medium_decreasing_downtrend", 
        "far_high_increasing_sideways"
    ]
    
    actions = ['enter_long', 'enter_short', 'hold', 'exit_early']
    
    # Simulate some learning
    for i in range(50):
        state = np.random.choice(states)
        action = np.random.choice(actions)
        reward = np.random.choice([1.0, -1.0, 0.5, -0.2])
        next_state = np.random.choice(states + [None])
        
        learner.update(state, action, reward, next_state, is_terminal=(next_state is None))
    
    print("\n2. Testing recommendations...")
    
    for state in states:
        rec = learner.get_recommendation(state)
        print(f"   State: {state}")
        print(f"   Recommendation: {rec['action']} (confidence: {rec['confidence']:.2f})")
        print(f"   Explanation: {rec['explanation']}")
    
    print("\n3. Testing action selection with exploration...")
    
    # Reset exploration for test
    learner.config['exploration_rate'] = 0.5
    
    for i in range(10):
        state = np.random.choice(states)
        action = learner.get_action(state, actions)
        print(f"   State {state}: chose {action}")
    
    # Print statistics
    learner.print_stats()
    
    # Save learning
    learner.save("test_learning.pkl")
    
    print("\n✅ Learning system test complete!")

if __name__ == "__main__":
    test_learner()
