from ss.algos.main import run_parallel
from ss.algos.params import get_params
import click
from ss.algos.inverse_trainer import Trainer

def get_paramlist(render=False, sync=True, only_params=False):
    if only_params:
        Reacher7Dof = None
    else:
        from ss.envs.reacher_env import Reacher7Dof
    expname = "inverse/reacher1/"

    paramlist = []
    i = 0
    critic_lr = 1e-3
    tau = 0.8
    her = True
    for actor_lr in [1e-3, 1e-4]:
        for nb_train_steps in [5, 50]:
            for horizon in [50, 100]:
                for batch_size in [128]:
                    for noise_sigma in [0.1, 0.5]:
                        for seed in range(4):
                            p = get_params(nb_train_steps=nb_train_steps,
                                         actor_lr=actor_lr,
                                         critic_lr=critic_lr,
                                         her=her,
                                         horizon=horizon,
                                         expname=expname+str(i),
                                         nb_epochs=1000,
                                         render=render,
                                         tau=tau,
                                         gamma=0.98,
                                         env_type=Reacher7Dof,
                                         batch_size=batch_size,
                                         noise_sigma=noise_sigma,
                                         nb_epoch_cycles=1,
                                         buffer_size=1000000,
                                         seed=seed,
                                         sync=sync,
                                         trainer=Trainer)
                            paramlist.append(p)
                            i += 1
    return paramlist

@click.command()
@click.argument("n", default=-1)
@click.argument("debug", default=0)
@click.argument("render", default=0)
def run_exp_n(n, debug, render):
    paramlist = get_paramlist(render=render, sync=not debug)
    print("Launching experiment", n, "of", len(paramlist))
    run_parallel(paramlist[n:n+1])

if __name__ == "__main__":
    run_exp_n()