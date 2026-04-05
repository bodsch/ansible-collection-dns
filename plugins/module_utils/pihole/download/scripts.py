#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2026, Bodo Schulz <bodo@boone-schulz.de>

from __future__ import absolute_import, division, print_function

import io
import shutil
import tarfile
from pathlib import Path

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import fetch_url

# from typing import Optional


# Scripts aus advanced/Scripts/ → installiert nach /opt/pihole/
PIHOLE_SCRIPTS = []
#     # "gravity",
#     # "list",
#     "piholeDebug",
#     "piholeLogFlush",
#     "update",
#     "version",
#     "webpage",
# ]

# Zusätzliche Dateien aus advanced/Scripts/ oder advanced/
PIHOLE_EXTRA_FILES = [
    "COL_TABLE",
    "api.sh",
    "list.sh",
    "piholeLogFlush.sh",
    "piholeNetworkFlush.sh",
    "query.sh",
    "update.sh",
    "updatecheck.sh",
    "utils.sh",
    "version.sh",
]

# Systemd-Unit und Service-Helper aus advanced/Templates/
PIHOLE_TEMPLATES = [
    "pihole-FTL.systemd",
    "pihole-FTL-prestart.sh",
    "pihole-FTL-poststop.sh",
    "gravity.db.sql",
    "gravity_copy.sql",
]

# pihole CLI-Wrapper aus Repo-Root
PIHOLE_CLI = "pihole"

# Tarball-Pfad des database_migration-Verzeichnisses
DB_MIGRATION_SRC = "advanced/Scripts/database_migration"


class PiholeDownloadScripts:
    """
    Lädt das pi-hole Core-Repository als Tarball herunter (kein git/subprocess)
    und extrahiert die relevanten Dateien in das Cache-Verzeichnis.

    Layout:
        {cache_dir}/{core_version}/
            scripts/                    ← /opt/pihole/ Inhalte
            templates/                  ← systemd-Unit + Helper
            database_migration/         ← /etc/.pihole/advanced/Scripts/database_migration/
                gravity-db.sh
                gravity/
                    1_to_2.sql
                    2_to_3.sql
                    ...
            pihole                      ← CLI-Wrapper → /usr/local/bin/pihole
            .complete                   ← Marker: Extraktion erfolgreich

    Installationspfade:
        scripts/          → /opt/pihole/
        templates/        → je nach Datei (systemd-Unit, Helper-Scripts)
        database_migration/ → /etc/.pihole/advanced/Scripts/database_migration/
        pihole            → /usr/local/bin/pihole
    """

    TARBALL_URL = (
        "https://github.com/pi-hole/pi-hole/archive/refs/tags/{version}.tar.gz"
    )

    def __init__(self, module: AnsibleModule, cache_dir: str):
        self.module = module
        self.cache_dir = Path(cache_dir)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def download(self, core_version: str) -> dict:
        """
        Lädt und extrahiert Core-Scripts für core_version.
        Idempotent: Wird übersprungen wenn .complete-Marker existiert.
        """
        self.module.log(f"PiholeDownloadScripts::download(core_version={core_version})")

        tag = core_version if core_version.startswith("v") else f"v{core_version}"
        target_dir = self.cache_dir / "core" / tag
        complete_marker = target_dir / ".complete"

        if complete_marker.exists():
            self.module.log(f"  [cache HIT] {target_dir}")
            return self._result(target_dir, changed=False)

        # Sauberes Zielverzeichnis
        if target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True)

        # Tarball herunterladen und in-memory entpacken
        url = self.TARBALL_URL.format(version=tag)
        self.module.log(f"  fetching tarball: {url}")

        tarball_bytes = self._fetch_bytes(url)
        self._extract(tarball_bytes, tag, target_dir)

        # Marker setzen
        complete_marker.write_text(tag, encoding="utf-8")
        self.module.log(f"  [extracted] {target_dir}")

        return self._result(target_dir, changed=True)

    # ------------------------------------------------------------------
    # Private: Download
    # ------------------------------------------------------------------

    def _fetch_bytes(self, url: str) -> bytes:
        """Lädt URL komplett in Speicher. Für ~1-2 MB Tarballs vertretbar."""
        resp, info = fetch_url(self.module, url, method="GET")
        if info["status"] not in (200, 302):
            self.module.fail_json(
                msg=f"Tarball download failed: HTTP {info['status']} for {url}"
            )
        return resp.read()

    # ------------------------------------------------------------------
    # Private: Extraktion
    # ------------------------------------------------------------------

    def _extract(self, tarball_bytes: bytes, tag: str, target_dir: Path) -> None:
        """
        Öffnet den Tarball in-memory und extrahiert nur die relevanten Dateien.
        GitHub-Tarballs haben ein Root-Verzeichnis: pi-hole-{version}/
        """
        # 'v' prefix entfernen für den GitHub-internen Ordnernamen
        version_clean = tag.lstrip("v")
        repo_root = f"pi-hole-{version_clean}/"

        scripts_dir = target_dir / "scripts"
        templates_dir = target_dir / "templates"
        scripts_dir.mkdir()
        templates_dir.mkdir()

        db_migration_dir = target_dir / "database_migration"
        db_migration_dir.mkdir()

        with tarfile.open(fileobj=io.BytesIO(tarball_bytes), mode="r:gz") as tf:
            members = {m.name: m for m in tf.getmembers() if m.isfile()}

            # Scripts: advanced/Scripts/{name}.sh → scripts/{name}
            for script in PIHOLE_SCRIPTS:
                src_path = f"{repo_root}advanced/Scripts/{script}.sh"
                if src_path in members:
                    self._extract_member(
                        tf, members[src_path], scripts_dir / script, mode=0o755
                    )
                else:
                    self.module.warn(f"Script not found in tarball: {src_path}")

            # Extra-Dateien: advanced/Scripts/{name} oder advanced/{name}
            for fname in PIHOLE_EXTRA_FILES:
                for candidate in [
                    f"{repo_root}advanced/Scripts/{fname}",
                    f"{repo_root}advanced/{fname}",
                ]:
                    if candidate in members:
                        self._extract_member(
                            tf, members[candidate], scripts_dir / fname, mode=0o644
                        )
                        break
                else:
                    self.module.warn(f"Extra file not found in tarball: {fname}")

            # Templates: advanced/Templates/{name}
            for tpl in PIHOLE_TEMPLATES:
                src_path = f"{repo_root}advanced/Templates/{tpl}"
                if src_path in members:
                    mode = 0o755 if tpl.endswith(".sh") else 0o644
                    self._extract_member(
                        tf, members[src_path], templates_dir / tpl, mode=mode
                    )
                else:
                    self.module.warn(f"Template not found in tarball: {src_path}")

            # database_migration: vollständige Verzeichnisstruktur erhalten
            # Quelle: advanced/Scripts/database_migration/**
            # Ziel:   database_migration/ (→ /etc/.pihole/advanced/Scripts/database_migration/)
            db_src_prefix = f"{repo_root}{DB_MIGRATION_SRC}/"
            db_members = {
                name: m for name, m in members.items() if name.startswith(db_src_prefix)
            }
            if not db_members:
                self.module.warn(
                    f"database_migration directory not found in tarball: {db_src_prefix}"
                )
            else:
                for src_name, member in db_members.items():
                    _len_src_prefix = len(db_src_prefix)
                    # Relativen Pfad innerhalb von database_migration/ bestimmen
                    rel_path = src_name[_len_src_prefix:]
                    if not rel_path:
                        continue
                    dest = db_migration_dir / rel_path
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    mode = 0o755 if member.mode & 0o111 else 0o644
                    self._extract_member(tf, member, dest, mode=mode)

            # pihole CLI-Wrapper: pihole → pihole
            cli_path = f"{repo_root}pihole"
            if cli_path in members:
                self._extract_member(
                    tf, members[cli_path], target_dir / PIHOLE_CLI, mode=0o755
                )
            else:
                self.module.warn(f"CLI wrapper not found in tarball: {cli_path}")

    @staticmethod
    def _extract_member(
        tf: tarfile.TarFile, member: tarfile.TarInfo, dest: Path, mode: int
    ) -> None:
        """Extrahiert ein einzelnes Tarball-Member nach dest."""
        fobj = tf.extractfile(member)
        if fobj is None:
            return
        dest.write_bytes(fobj.read())
        dest.chmod(mode)

    # ------------------------------------------------------------------
    # Private: Result
    # ------------------------------------------------------------------

    @staticmethod
    def _result(target_dir: Path, changed: bool) -> dict:
        return dict(
            changed=changed,
            cache_dir=str(target_dir),
            scripts_dir=str(target_dir / "scripts"),
            templates_dir=str(target_dir / "templates"),
            database_migration_dir=str(target_dir / "database_migration"),
            cli_wrapper=str(target_dir / PIHOLE_CLI),
        )
