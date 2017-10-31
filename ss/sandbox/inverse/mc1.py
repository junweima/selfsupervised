from ss.algos.main import run_parallel
from ss.algos.params import get_params
import click
from ss.algos.inverse_trainer import Trainer

def get_paramlist(render=False, sync=True, only_params=False):
    if only_params:
        Reacher7Dof = None
    else:
        from ss.envs.mountain_car_full_env import MountainCarEnv
    expname = "mc1/"

    paramlist = []
    i = 0
    actor_lr = 1e-4
    critic_lr = 1e-3
    tau = 0.8
    her = True
    for nb_train_steps in [50]:
        for horizon in [200]:
            for batch_size in [128]:
                for noise_sigma in [0.05]:
                    for seed in range(1):
                        p = get_params(nb_train_steps=nb_train_steps,
                                     actor_lr=actor_lr,
                                     critic_lr=critic_lr,
                                     her=her,
                                     horizon=horizon,
                                     expname=expname+str(i),
                                     nb_epochs=5000,
                                     render=render,
                                     tau=tau,
                                     gamma=0.98,
                                     env_type=MountainCarEnv,
                                     batch_size=batch_size,
                                     noise_sigma=noise_sigma,
                                     nb_epoch_cycles=1,
                                     buffer_size=200000,
                                     seed=seed,
                                     sync=sync,
                                     trainer=Trainer)
                        paramlist.append(p)
                        i += 1
    return paramlist

@click.command()
@click.argument("n", default=-1)
@click.argument("debug", default=0)
def run_exp_n(n, debug):
    paramlist = get_paramlist(sync=not debug)
    print("Launching experiment", n, "of", len(paramlist))
    run_parallel(paramlist[n:n+1])

if __name__ == "__main__":
    run_exp_n()