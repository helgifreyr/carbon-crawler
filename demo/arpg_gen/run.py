"""Generates one act in a process of its own and pickles its payload to a file: python -m arpg_gen.run caves 7 out.bin"""
import os
import pickle
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def start(template, seed, out_path):
    """Starts generating in the background with the engine's Python; poll the returned process."""
    python = os.path.join(os.environ["PYTHONHOME"], "python.exe")
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([HERE] + os.environ.get("PYTHONPATH", "").split(os.pathsep)))
    return subprocess.Popen([python, "-m", "arpg_gen.run", template, str(seed), out_path], cwd=HERE, env=env,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def load(out_path):
    with open(out_path, "rb") as f:
        return pickle.load(f)


def main(template, seed, out_path):
    from arpg_gen import generate
    level = generate.generate(template, int(seed))
    with open(out_path + ".part", "wb") as f:
        pickle.dump(level.payload(), f)
    os.replace(out_path + ".part", out_path)


if __name__ == "__main__":
    main(*sys.argv[1:4])
