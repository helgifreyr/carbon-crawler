"""Generates one act in a process of its own and pickles its payload to a file: python -m arpg_gen.run caves 7 out.bin

With a fourth argument "debug" the file holds {"payload", "debug"}, the debug part being the fields the editor draws."""
import os
import pickle
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def start(template, seed, out_path, debug=False):
    """Starts generating in the background with the engine's Python; poll the returned process."""
    python = os.path.join(os.environ["PYTHONHOME"], "python.exe")
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([HERE] + os.environ.get("PYTHONPATH", "").split(os.pathsep)))
    args = [python, "-m", "arpg_gen.run", template, str(seed), out_path] + (["debug"] if debug else [])
    return subprocess.Popen(args, cwd=HERE, env=env,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def load(out_path):
    with open(out_path, "rb") as f:
        return pickle.load(f)


def main(template, seed, out_path, debug=None):
    from arpg_gen import generate
    level = generate.generate(template, int(seed), debug=bool(debug))
    with open(out_path + ".part", "wb") as f:
        pickle.dump({"payload": level.payload(), "debug": level.debug} if debug else level.payload(), f)
    os.replace(out_path + ".part", out_path)


if __name__ == "__main__":
    main(*sys.argv[1:5])
