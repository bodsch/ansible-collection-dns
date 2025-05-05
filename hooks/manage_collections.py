#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2022-2024, Bodo Schulz <bodo@boone-schulz.de>

import os
import sys
import yaml
import json
import subprocess
from pathlib import Path
from packaging.version import Version, InvalidVersion
from packaging.specifiers import SpecifierSet
import site
from typing import Dict


def load_required_collections(path="collections.yml"):
    """
    Lädt die benötigten Collections aus der YAML-Datei.
    """
    with open(path, "r") as f:
        data = yaml.safe_load(f)
    return data.get("collections", [])


def is_version_compatible(installed_version: str, required_spec: str) -> bool:
    """
    Prüft, ob die installierte Version mit dem geforderten Version-String kompatibel ist.
    """
    try:
        return Version(installed_version) in SpecifierSet(required_spec)
    except InvalidVersion:
        return False


def get_ansible_collections_paths():
    """
    Ermittelt gültige Ansible-Collection-Verzeichnisse anhand von Umgebungsvariablen
    oder Standards.
    """
    paths = []
    env_paths = os.environ.get("ANSIBLE_COLLECTIONS_PATHS")

    if env_paths:
        paths.extend([os.path.join(p, "ansible_collections") for p in env_paths.split(os.pathsep)])
    else:
        # Standard: ~/.ansible/collections/ansible_collections
        paths.append(os.path.join(os.path.expanduser("~"), ".ansible", "collections", "ansible_collections"))

        # Dynamisch ermitteln: site-packages
        for sp in site.getsitepackages():
            paths.append(os.path.join(sp, "ansible_collections"))

    return paths


def get_installed_collections():
    """
        Durchsucht bekannte Collection-Pfade nach installierten Collections und ermittelt deren Versionen.
    """
    installed = {}

    for base_path in get_ansible_collections_paths():
        if not os.path.isdir(base_path):
            continue

        for namespace in os.listdir(base_path):
            ns_path = os.path.join(base_path, namespace)
            if not os.path.isdir(ns_path):
                continue

            for collection in os.listdir(ns_path):
                coll_path = os.path.join(ns_path, collection)
                manifest = os.path.join(coll_path, "MANIFEST.json")
                if os.path.isfile(manifest):
                    try:
                        with open(manifest) as f:
                            data = json.load(f)
                            name = f"{namespace}.{collection}"
                            info = data.get("collection_info", {})
                            version = info.get("version")
                            namespace = info.get("namespace")
                            name = info.get("name")

                            if namespace and name and version:
                                full_name = f"{namespace}.{name}"
                                installed[full_name] = version

                            # version = data.get("version")
                            # installed[name] = version
                    except Exception as e:
                        print(f"⚠️ Errors when reading {manifest}: {e}")

    return installed


def install_collection(name):
    """
    Installiert eine Collection über ansible-galaxy (ohne Versionsparameter).
    """
    print(f"📦 Install ansible-galaxy collection {name} ...")
    subprocess.run(["ansible-galaxy", "collection", "install", name], check=True)


def main(requirements_file="collections.yml"):
    """
    Hauptfunktion: prüft installierte vs. benötigte Collections und installiert bei Bedarf.
    """
    if not Path(requirements_file).exists():
        print(f"❌ File '{requirements_file}' not found.")
        return

    required = load_required_collections(requirements_file)
    installed = get_installed_collections()

    for item in required:
        name = item.get("name")
        required_version = item.get("version")

        current_version = installed.get(name)

        if current_version:
            if required_version:
                if not is_version_compatible(current_version, required_version):
                    print(f"🔄 '{name}' is installed in version {current_version}, {required_version} is required.")
                    install_collection(name)
                else:
                    print(f"✅ '{name}' is installed in compatible version {current_version}.")
            else:
                print(f"✅ '{name}' is installed in version {current_version}.")
        else:
            print(f"❌ '{name}' is not installed.")
            install_collection(name)

    print("")

if __name__ == "__main__":
    main()
