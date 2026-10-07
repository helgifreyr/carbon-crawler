import argparse
import glob
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TRIPLET = os.path.join(ROOT, "vcpkg_installed", "x64-windows-v143-internal")
BIN = os.path.join(TRIPLET, "bin")
LIB = os.path.join(TRIPLET, "lib")
EXEFILE_DIR = os.path.join(TRIPLET, "tools", "carbon-exefile")
PYTHON_HOME = os.path.join(TRIPLET, "tools", "python3")
SYSTEM32 = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32")

MODULES = [os.path.join(LIB, "_destiny_internal.pyd")] + [
    p for p in glob.glob(os.path.join(BIN, "*.pyd")) if "_trinity_stub" not in p] + glob.glob(os.path.join(BIN, "Ak*.dll"))
PYTHON_PACKAGES = ["bluepycore", "scheduler", "greenlet", "destiny"]
STDLIB_SKIP = {"test", "idlelib", "tkinter", "turtledemo", "ensurepip", "venv", "lib2to3", "site-packages"}
SEARCH_DIRS = [EXEFILE_DIR, BIN, os.path.join(PYTHON_HOME, "DLLs"), PYTHON_HOME]


# The Visual C++ runtime most machines have, but a fresh Windows may not; shipped next to the exe (app-local).
VC_RUNTIME = ["msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll"]


def vs_install():
    vswhere = os.path.join(os.environ["ProgramFiles(x86)"], "Microsoft Visual Studio", "Installer", "vswhere.exe")
    return subprocess.run([vswhere, "-latest", "-products", "*", "-property", "installationPath"],
                          capture_output=True, text=True).stdout.strip()


def vc_runtime():
    crt = sorted(glob.glob(os.path.join(vs_install(), "VC", "Redist", "MSVC", "*", "x64", "Microsoft.VC14*.CRT")))
    folder = crt[-1] if crt else SYSTEM32
    return [os.path.join(folder, name) for name in VC_RUNTIME if os.path.exists(os.path.join(folder, name))]


def zip_package(out):
    import zipfile
    target = os.path.normpath(out) + ".zip"
    root = os.path.dirname(out)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for folder, dirs, names in os.walk(out):
            if folder == out:
                dirs[:] = [d for d in dirs if d not in ("logs", "cache")]
            for name in names:
                path = os.path.join(folder, name)
                z.write(path, os.path.relpath(path, root))
    print("zipped %s (%.0f MB)" % (target, os.path.getsize(target) / 1e6))


def find_dumpbin():
    install = vs_install()
    hits = sorted(glob.glob(os.path.join(install, "VC", "Tools", "MSVC", "*", "bin", "Hostx64", "x64", "dumpbin.exe")))
    if not hits:
        sys.exit("dumpbin.exe not found; install the MSVC build tools")
    return hits[-1]


def dependents(dumpbin, path):
    out = subprocess.run([dumpbin, "/nologo", "/dependents", path], capture_output=True, text=True).stdout
    names, in_list = [], False
    for line in out.splitlines():
        stripped = line.strip()
        if stripped.startswith("Image has the following dependencies"):
            in_list = True
        elif in_list and not stripped and names:
            break
        elif in_list and stripped.lower().endswith(".dll"):
            names.append(stripped)
    return names


def locate(name):
    for d in SEARCH_DIRS:
        candidate = os.path.join(d, name)
        if os.path.exists(candidate):
            return candidate
    return None


def dll_closure(dumpbin, roots):
    found, missing, stack = {}, set(), list(roots)
    while stack:
        for name in dependents(dumpbin, stack.pop()):
            key = name.lower()
            if key in found or key in missing or key.startswith(("api-ms-", "ext-ms-")):
                continue
            path = locate(name)
            if path:
                found[key] = path
                stack.append(path)
            elif not os.path.exists(os.path.join(SYSTEM32, name)):
                missing.add(key)
    return found, missing


def set_exe_icon(exe, ico):
    """Replaces the exe's main icon group (the stock exefile carries EVE's) with the images in an .ico file."""
    import ctypes
    import struct
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.LoadLibraryExW.restype = ctypes.c_void_p
    k32.LoadLibraryExW.argtypes = (ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_uint)
    k32.FreeLibrary.argtypes = (ctypes.c_void_p,)
    k32.BeginUpdateResourceW.restype = ctypes.c_void_p
    k32.BeginUpdateResourceW.argtypes = (ctypes.c_wchar_p, ctypes.c_bool)
    k32.UpdateResourceW.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ushort, ctypes.c_void_p,
                                    ctypes.c_uint)
    k32.EndUpdateResourceW.argtypes = (ctypes.c_void_p, ctypes.c_bool)
    RT_ICON, RT_GROUP_ICON = 3, 14
    found = []
    name_cb = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
    lang_cb = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ushort,
                                 ctypes.c_void_p)
    on_lang = lang_cb(lambda module, kind, name, lang, _: found.append((name, lang)) or False)
    k32.EnumResourceLanguagesW.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, lang_cb, ctypes.c_void_p)
    k32.EnumResourceNamesW.argtypes = (ctypes.c_void_p, ctypes.c_void_p, name_cb, ctypes.c_void_p)
    on_name = name_cb(lambda module, kind, name, _: k32.EnumResourceLanguagesW(module, kind, name, on_lang, None) and False)
    module = k32.LoadLibraryExW(exe, None, 2)
    k32.EnumResourceNamesW(module, RT_GROUP_ICON, on_name, None)
    if not found or not (found[0][0] or 0) < 0x10000:
        k32.FreeLibrary(module)
        print("note: %s has no numbered icon group; icon left as is" % exe)
        return
    name, lang = found[0]
    k32.FreeLibrary(module)
    data = open(ico, "rb").read()
    count = struct.unpack_from("<H", data, 4)[0]
    handle = k32.BeginUpdateResourceW(exe, False)
    k32.UpdateResourceW(handle, RT_GROUP_ICON, name, lang, None, 0)
    group = struct.pack("<HHH", 0, 1, count)
    for i in range(count):
        w, h, colors, _, planes, bpp, size, offset = struct.unpack_from("<BBBBHHII", data, 6 + 16 * i)
        image = data[offset:offset + size]
        icon_id = 7000 + i
        k32.UpdateResourceW(handle, RT_ICON, icon_id, lang, image, len(image))
        group += struct.pack("<BBBBHHIH", w, h, colors, 0, planes, bpp, size, icon_id)
    k32.UpdateResourceW(handle, RT_GROUP_ICON, name, lang, group, len(group))
    if not k32.EndUpdateResourceW(handle, False):
        print("note: could not update the icon of %s (error %d)" % (exe, ctypes.get_last_error()))


def copy_tree(src, dst, skip=()):
    shutil.copytree(src, dst, dirs_exist_ok=True,
                    ignore=lambda d, names: [n for n in names
                                             if n in skip or n == "__pycache__" or n.endswith((".pdb", ".pyc"))])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=os.path.join(ROOT, "dist", "carbon-crawler"))
    parser.add_argument("--zip", action="store_true", help="also write <out>.zip, without local logs and caches")
    args = parser.parse_args()
    out = args.out
    bin_out = os.path.join(out, "bin")
    dlls_out = os.path.join(out, "python", "DLLs")

    if os.path.isdir(out):
        # Empty it rather than removing it, so a shell sitting in the folder doesn't block a rebuild.
        for entry in os.listdir(out):
            path = os.path.join(out, entry)
            shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
    os.makedirs(bin_out, exist_ok=True)
    os.makedirs(dlls_out, exist_ok=True)

    dumpbin = find_dumpbin()
    roots = [os.path.join(EXEFILE_DIR, "exefile_Internal.exe")] + MODULES
    dlls, missing = dll_closure(dumpbin, roots)
    for path in roots + list(dlls.values()) + vc_runtime():
        shutil.copy2(path, bin_out)
    set_exe_icon(os.path.join(bin_out, "exefile_Internal.exe"), os.path.join(ROOT, "res", "arpg", "ui", "app.ico"))

    for package in PYTHON_PACKAGES:
        copy_tree(os.path.join(BIN, "python", package), os.path.join(bin_out, "python", package))
    copy_tree(os.path.join(TRIPLET, "python", "audio2"), os.path.join(bin_out, "python", "audio2"))
    copy_tree(os.path.join(PYTHON_HOME, "Lib"), os.path.join(out, "python", "Lib"), STDLIB_SKIP)
    for pyd in glob.glob(os.path.join(PYTHON_HOME, "DLLs", "*.pyd")):
        shutil.copy2(pyd, dlls_out)
    # numpy, and a plain Python for the server to generate the next act in a process of its own.
    copy_tree(os.path.join(ROOT, "vendor", "pydeps"), os.path.join(out, "python", "pydeps"), {"bin", "__pycache__"})
    for name in ("python.exe", "python312.dll"):
        shutil.copy2(os.path.join(PYTHON_HOME, name), os.path.join(out, "python"))

    copy_tree(os.path.join(ROOT, "demo"), os.path.join(out, "app"), {"_deps", "out"})
    copy_tree(os.path.join(ROOT, "res"), os.path.join(out, "res"), {"effect", "testbanks"})
    shutil.copy2(os.path.join(HERE, "run_template.cmd"), os.path.join(out, "run.cmd"))
    shutil.copy2(os.path.join(HERE, "run_template.ps1"), os.path.join(out, "run.ps1"))
    companions = ['if /i "%~1"=="companion" (', '    set COMPANIONS=%~2', '    if "%~2"=="" set COMPANIONS=1', ')',
                  'if defined COMPANIONS for /l %%i in (1,1,%COMPANIONS%) do '
                  'start "companion %%i" /min cmd /c "set COMPANION_SEED=%%i && "%~dp0arpg_companion.cmd""']
    for name in ("arpg_server", "arpg_client", "arpg_companion"):
        lines = ["@echo off"] + (companions if name == "arpg_client" else []) + ['call "%%~dp0run.cmd" %s.py' % name]
        with open(os.path.join(out, name + ".cmd"), "w", newline="") as f:
            f.write("\r\n".join(lines) + "\r\n")
    shutil.copy2(os.path.join(HERE, "package_readme.txt"), os.path.join(out, "README.txt"))
    if not os.path.isdir(os.path.join(ROOT, "res", "audio", "arpg")):
        print("note: res/audio/arpg is missing (tools/make_arpg_audio.py), so the package has no ARPG sound")

    size = sum(os.path.getsize(os.path.join(d, n)) for d, _, ns in os.walk(out) for n in ns)
    print("packaged %d DLLs into %s (%.0f MB)" % (len(dlls), out, size / 1e6))
    if missing:
        print("unresolved (not in package, not in System32):", ", ".join(sorted(missing)))
    if args.zip:
        zip_package(out)


if __name__ == "__main__":
    main()
