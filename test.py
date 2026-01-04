from environs import Env

env = Env()
env.read_env()

MAIN_PHOTO = env("MAIN_PHOTO")
ADMIN_GROUP_ID = env("ADMIN_GROUP_ID")

print(int(-2777288165))
