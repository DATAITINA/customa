from importlib import import_module
from pathlib import Path

from msflib.seed.utils import get_yml_config


def test_app_seeders_use_class_factory_paths():
    seeders_path = Path(__file__).resolve().parents[2] / "seed" / "seeders.yml"
    config = get_yml_config(str(seeders_path))

    accounts_factory = config["seeders"]["accounts"]["action"]["class_factory"]
    profiles_factory = config["seeders"]["profiles"]["action"]["class_factory"]

    assert accounts_factory == "app.seed.factories.account_action_factory"
    assert profiles_factory == "app.seed.factories.profile_action_factory"

    acc_mod, acc_func = accounts_factory.rsplit(".", 1)
    prof_mod, prof_func = profiles_factory.rsplit(".", 1)

    assert callable(getattr(import_module(acc_mod), acc_func))
    assert callable(getattr(import_module(prof_mod), prof_func))
