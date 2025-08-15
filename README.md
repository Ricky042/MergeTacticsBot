⚔️ Merge Tactics Simulator




Welcome to Merge Tactics Simulator, a strategic grid-based battle simulator where units clash with unique abilities, critical hits, and tactical movement!

🎮 Features

Dynamic Combat: Each unit has its own attack, crit chance, and special abilities.

Grid-Based Strategy: Hexagonal map system with movement, attack ranges, and dash mechanics.

Unique Units: From Archer Queens to Skeleton Kings, each unit has star levels, damage multipliers, and status effects.

Visual Simulation: Track unit positions, attack projectiles, and status effects in real-time.

Critical Hits & Special Effects: Individual crit rolls per target, invisibility triggers, splash damage, and more.

Dynamic Retargeting: Units choose closest enemies, retarget when necessary, and handle invisible or dead enemies.

🧩 How It Works

Units are placed on a hex grid.

Each round, units either move towards enemies or attack if in range.

Units have special abilities that scale with their star level:

Archer Queen can become invisible and hit multiple targets.

Valkyrie deals splash damage around her.

Executioner throws an axe that pierces and returns.

Status effects like stun or invisibility are tracked per unit.

Combat continues until one side is eliminated.

⚡ Example Output
⚔️ Princess strikes Barbarian for 163 damage
Barbarian (Owner: Greedy) takes 163 damage! HP: -24
💀 Barbarian (Owner: Greedy) has been eliminated!
🔹 Removed Barbarian as current_target from Archer Queen

🛠 Installation

Clone the repo:

git clone https://github.com/yourusername/merge-tactics-simulator.git
cd merge-tactics-simulator


Install dependencies:

pip install -r requirements.txt


Run the simulator:

python main_sim.py

📈 Roadmap

 Unit-specific abilities and attacks

 Hex grid movement & range checks

 Critical hits per target

 Splash damage & status effects

 Real-time Pygame visualization

 AI improvements for smarter retargeting

🤝 Contributing

Contributions are welcome! Please fork the repo, create a feature branch, and submit a pull request.

📜 License

This project is licensed under the MIT License – see the LICENSE file for details.
