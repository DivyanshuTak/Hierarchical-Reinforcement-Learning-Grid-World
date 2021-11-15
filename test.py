from envs.grid_world import GridWorld


env = GridWorld()

for i in range(10):
	print(env.step(0))