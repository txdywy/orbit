"""
Orbit Wars RL Training with PPO
Run this notebook on Kaggle with GPU enabled for faster training.
"""

import math
import numpy as np
from collections import namedtuple, deque
import random

# Check for PyTorch
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.distributions import Categorical
    TORCH_AVAILABLE = True
    print(f"PyTorch available: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")
except ImportError:
    TORCH_AVAILABLE = False
    print("PyTorch not available")

# Game constants
BOARD_SIZE = 100.0
CENTER = 50.0
SUN_RADIUS = 10.0
ROTATION_RADIUS_LIMIT = 50.0
MAX_SPEED = 6.0
GAME_LENGTH = 500

Planet = namedtuple("Planet", ["id", "owner", "x", "y", "radius", "ships", "production"])
Fleet = namedtuple("Fleet", ["id", "owner", "x", "y", "angle", "from_planet_id", "ships"])

def get(obs, key, default=None):
    if isinstance(obs, dict):
        return obs.get(key, default)
    return getattr(obs, key, default)

def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])

def point_to_segment_distance(point, start, end):
    sx, sy = start
    ex, ey = end
    px, py = point
    dx = ex - sx
    dy = ey - sy
    length2 = dx * dx + dy * dy
    if length2 <= 1e-12:
        return dist(point, start)
    t = ((px - sx) * dx + (py - sy) * dy) / length2
    t = max(0.0, min(1.0, t))
    return dist(point, (sx + t * dx, sy + t * dy))

def line_crosses_sun(start, end, buffer=0.35):
    return point_to_segment_distance((CENTER, CENTER), start, end) <= SUN_RADIUS + buffer

def fleet_speed(ships):
    ships = max(1, int(ships))
    speed = 1.0 + (MAX_SPEED - 1.0) * (math.log(ships) / math.log(1000)) ** 1.5
    return min(MAX_SPEED, speed)

def is_orbiting(planet):
    return dist((planet.x, planet.y), (CENTER, CENTER)) + planet.radius < ROTATION_RADIUS_LIMIT

# Feature extraction for RL
def extract_features(obs):
    """Extract state features for RL policy"""
    player = get(obs, "player", 0)
    planets = get(obs, "planets", [])
    fleets = get(obs, "fleets", [])
    step = int(get(obs, "step", 0) or 0)
    
    my_planets = [p for p in planets if p[1] == player]
    enemy_planets = [p for p in planets if p[1] not in (-1, player)]
    neutral_planets = [p for p in planets if p[1] == -1]
    
    my_ships = sum(p[5] for p in my_planets) + sum(f[6] for f in fleets if f[1] == player)
    enemy_ships = sum(p[5] for p in enemy_planets) + sum(f[6] for f in fleets if f[1] not in (-1, player))
    my_production = sum(p[6] for p in my_planets)
    enemy_production = sum(p[6] for p in enemy_planets)
    
    # Basic features
    features = [
        len(my_planets) / 20.0,
        len(enemy_planets) / 20.0,
        len(neutral_planets) / 20.0,
        my_ships / 1000.0,
        enemy_ships / 1000.0,
        my_production / 50.0,
        enemy_production / 50.0,
        step / 500.0,
        1.0 if my_ships > enemy_ships * 1.15 else 0.0,  # ahead
        1.0 if my_ships > enemy_ships * 1.8 else 0.0,   # far_ahead
    ]
    
    # Planet position features (normalized)
    for p in my_planets[:3]:
        features.extend([p[2] / 100.0, p[3] / 100.0, p[5] / 100.0, p[6] / 5.0])
    
    # Pad to fixed size
    while len(features) < 64:
        features.append(0.0)
    
    return features[:64]

# PPO Networks
if TORCH_AVAILABLE:
    class ActorCritic(nn.Module):
        def __init__(self, state_dim=64, action_dim=32):
            super().__init__()
            
            # Shared feature extractor
            self.shared = nn.Sequential(
                nn.Linear(state_dim, 256),
                nn.ReLU(),
                nn.Linear(256, 256),
                nn.ReLU(),
            )
            
            # Actor (policy) head
            self.actor = nn.Sequential(
                nn.Linear(256, 128),
                nn.ReLU(),
                nn.Linear(128, action_dim),
            )
            
            # Critic (value) head
            self.critic = nn.Sequential(
                nn.Linear(256, 128),
                nn.ReLU(),
                nn.Linear(128, 1),
            )
        
        def forward(self, x):
            shared_features = self.shared(x)
            action_logits = self.actor(shared_features)
            value = self.critic(shared_features)
            return action_logits, value
        
        def get_action(self, state, deterministic=False):
            action_logits, value = self.forward(state)
            dist = Categorical(logits=action_logits)
            
            if deterministic:
                action = torch.argmax(action_logits, dim=-1)
            else:
                action = dist.sample()
            
            log_prob = dist.log_prob(action)
            return action, log_prob, value
        
        def evaluate_actions(self, states, actions):
            action_logits, values = self.forward(states)
            dist = Categorical(logits=action_logits)
            log_probs = dist.log_prob(actions)
            entropy = dist.entropy()
            return log_probs, values.squeeze(-1), entropy

# PPO Training
class PPOTrainer:
    def __init__(self, lr=3e-4, gamma=0.99, gae_lambda=0.95, clip_epsilon=0.2):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Using device: {self.device}")
        
        self.policy = ActorCritic().to(self.device)
        self.optimizer = optim.Adam(self.policy.parameters(), lr=lr)
        
        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.clip_epsilon = clip_epsilon
        
        self.memory = []
    
    def select_action(self, state):
        state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
        with torch.no_grad():
            action, log_prob, value = self.policy.get_action(state_tensor)
        return action.item(), log_prob.item(), value.item()
    
    def store_transition(self, state, action, log_prob, reward, value, done):
        self.memory.append((state, action, log_prob, reward, value, done))
    
    def compute_gae(self, rewards, values, dones):
        advantages = []
        gae = 0
        
        for t in reversed(range(len(rewards))):
            if t == len(rewards) - 1:
                next_value = 0
            else:
                next_value = values[t + 1]
            
            delta = rewards[t] + self.gamma * next_value * (1 - dones[t]) - values[t]
            gae = delta + self.gamma * self.gae_lambda * (1 - dones[t]) * gae
            advantages.insert(0, gae)
        
        returns = [adv + val for adv, val in zip(advantages, values)]
        return advantages, returns
    
    def update(self, batch_size=64, epochs=4):
        if len(self.memory) < batch_size:
            return
        
        # Unpack memory
        states, actions, old_log_probs, rewards, values, dones = zip(*self.memory)
        
        # Compute advantages
        advantages, returns = self.compute_gae(rewards, values, dones)
        
        # Convert to tensors
        states = torch.FloatTensor(np.array(states)).to(self.device)
        actions = torch.LongTensor(actions).to(self.device)
        old_log_probs = torch.FloatTensor(old_log_probs).to(self.device)
        advantages = torch.FloatTensor(advantages).to(self.device)
        returns = torch.FloatTensor(returns).to(self.device)
        
        # Normalize advantages
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        
        # PPO update
        for _ in range(epochs):
            # Get current policy outputs
            log_probs, values, entropy = self.policy.evaluate_actions(states, actions)
            
            # Compute ratio
            ratio = torch.exp(log_probs - old_log_probs)
            
            # Clipped surrogate loss
            surr1 = ratio * advantages
            surr2 = torch.clamp(ratio, 1 - self.clip_epsilon, 1 + self.clip_epsilon) * advantages
            actor_loss = -torch.min(surr1, surr2).mean()
            
            # Value loss
            critic_loss = nn.MSELoss()(values, returns)
            
            # Entropy bonus
            entropy_loss = -entropy.mean() * 0.01
            
            # Total loss
            loss = actor_loss + 0.5 * critic_loss + entropy_loss
            
            # Update
            self.optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(self.policy.parameters(), 0.5)
            self.optimizer.step()
        
        # Clear memory
        self.memory = []
        
        return {
            'actor_loss': actor_loss.item(),
            'critic_loss': critic_loss.item(),
            'entropy': entropy.mean().item()
        }
    
    def save(self, path):
        torch.save({
            'policy_state_dict': self.policy.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
        }, path)
        print(f"Model saved to {path}")
    
    def load(self, path):
        checkpoint = torch.load(path)
        self.policy.load_state_dict(checkpoint['policy_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        print(f"Model loaded from {path}")

# Training loop
def train_rl_agent(num_episodes=1000, save_interval=100):
    if not TORCH_AVAILABLE:
        print("PyTorch not available. Cannot train RL agent.")
        return
    
    trainer = PPOTrainer()
    
    # Training metrics
    episode_rewards = []
    best_reward = float('-inf')
    
    for episode in range(num_episodes):
        # Create environment
        from kaggle_environments import make
        env = make("orbit_wars", configuration={"seed": episode}, debug=False)
        
        # Run episode
        obs = env.reset()
        total_reward = 0
        done = False
        
        while not done:
            # Extract features
            state = extract_features(obs[0])
            
            # Select action
            action_idx, log_prob, value = trainer.select_action(state)
            
            # Use heuristic agent with RL adjustment
            # RL can adjust parameters like commit_ratio, reserve, etc.
            moves = agent(obs[0])
            
            # Store transition
            trainer.store_transition(state, action_idx, log_prob, 0, value, False)
            
            # Step environment
            obs, rewards, dones, infos = env.step([moves, []])
            total_reward += rewards[0]
            done = dones[0]
        
        # Update policy
        if len(trainer.memory) >= 64:
            losses = trainer.update()
        
        episode_rewards.append(total_reward)
        
        # Logging
        if (episode + 1) % 10 == 0:
            avg_reward = np.mean(episode_rewards[-10:])
            print(f"Episode {episode + 1}, Avg Reward: {avg_reward:.2f}")
        
        # Save best model
        if total_reward > best_reward:
            best_reward = total_reward
            trainer.save("best_model.pth")
        
        # Save checkpoint
        if (episode + 1) % save_interval == 0:
            trainer.save(f"checkpoint_{episode + 1}.pth")
    
    print("Training complete!")
    return trainer

# Main
if __name__ == "__main__":
    print("=" * 50)
    print("Orbit Wars RL Training")
    print("=" * 50)
    
    if TORCH_AVAILABLE:
        print(f"GPU Available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"GPU Name: {torch.cuda.get_device_name(0)}")
        
        print("\nTo train RL agent, run:")
        print("trainer = train_rl_agent(num_episodes=1000)")
        print("\nTo use trained model:")
        print("trainer = PPOTrainer()")
        print("trainer.load('best_model.pth')")
    else:
        print("PyTorch not available. Install torch for RL training.")
        print("Current heuristic agent is still competitive!")
