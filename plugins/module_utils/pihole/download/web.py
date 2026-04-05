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


class PiholeDownloadWeb:
    """
    Lädt das pi-hole Web Interface Repository als Tarball herunter (kein git)
    und extrahiert alle Dateien in das Cache-Verzeichnis.

    Layout:
        {cache_dir}/{web_tag}/
            admin/            ← Inhalt von /var/www/html/admin/
            .complete         ← Idempotenz-Marker

    Der Inhalt von admin/ wird später via ansible.builtin.copy nach
    /var/www/html/admin/ installiert.
    """

    TARBALL_URL = "https://github.com/pi-hole/web/archive/refs/tags/{version}.tar.gz"

    def __init__(self, module: AnsibleModule, cache_dir: str):
        self.module = module
        self.cache_dir = Path(cache_dir)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def download(self, web_tag: str) -> dict:
        """
        Lädt und extrahiert den Web UI Tarball für web_tag.
        Idempotent: Wird übersprungen wenn .complete-Marker existiert.
        """
        self.module.log(f"PiholeDownloadWeb::download(web_tag={web_tag})")

        tag = web_tag if web_tag.startswith("v") else f"v{web_tag}"
        target_dir = self.cache_dir / "web" / tag
        complete_marker = target_dir / ".complete"

        if complete_marker.exists():
            self.module.log(f"  [cache HIT] {target_dir}")
            return self._result(target_dir, changed=False)

        # Sauberes Zielverzeichnis
        if target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True)

        admin_dir = target_dir / "admin"
        admin_dir.mkdir()

        # Tarball herunterladen
        url = self.TARBALL_URL.format(version=tag)
        self.module.log(f"  fetching tarball: {url}")

        tarball_bytes = self._fetch_bytes(url)
        self._extract(tarball_bytes, tag, admin_dir)

        # Marker setzen
        complete_marker.write_text(tag, encoding="utf-8")
        self.module.log(f"  [extracted] {target_dir} ({self._count_files(admin_dir)} files)")

        return self._result(target_dir, changed=True)

    # ------------------------------------------------------------------
    # Private: Download
    # ------------------------------------------------------------------

    def _fetch_bytes(self, url: str) -> bytes:
        resp, info = fetch_url(self.module, url, method="GET")
        if info["status"] not in (200, 302):
            self.module.fail_json(
                msg=f"Web UI tarball download failed: HTTP {info['status']} for {url}"
            )
        return resp.read()

    # ------------------------------------------------------------------
    # Private: Extraktion
    # ------------------------------------------------------------------

    def _extract(self, tarball_bytes: bytes, tag: str, admin_dir: Path) -> None:
        """
        Extrahiert alle Dateien aus dem Tarball nach admin_dir.
        GitHub-Tarballs haben ein Root-Verzeichnis: web-{version}/
        Dieses wird herausgeschnitten, alle Inhalte landen direkt in admin_dir.
        """
        version_clean = tag.lstrip("v")
        # GitHub Tarball Root: web-{version}/ (ohne 'v')
        tarball_root = f"web-{version_clean}/"

        with tarfile.open(fileobj=io.BytesIO(tarball_bytes), mode="r:gz") as tf:
            for member in tf.getmembers():
                # Nur Dateien, kein Root-Verzeichnis selbst
                if not member.isfile():
                    continue

                # Relativen Pfad innerhalb des Repos ermitteln
                if not member.name.startswith(tarball_root):
                    continue

                rel_path = member.name[len(tarball_root):]
                if not rel_path:
                    continue

                dest = admin_dir / rel_path

                # Zwischenverzeichnisse anlegen
                dest.parent.mkdir(parents=True, exist_ok=True)

                fobj = tf.extractfile(member)
                if fobj is None:
                    continue

                dest.write_bytes(fobj.read())

                # Ausführbare Dateien (Shell-Scripts) behalten ihr Bit
                mode = 0o755 if (member.mode & 0o111) else 0o644
                dest.chmod(mode)

    # ------------------------------------------------------------------
    # Private: Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _count_files(directory: Path) -> int:
        return sum(1 for _ in directory.rglob("*") if _.is_file())

    @staticmethod
    def _result(target_dir: Path, changed: bool) -> dict:
        return dict(
            changed=changed,
            cache_dir=str(target_dir),
            admin_dir=str(target_dir / "admin"),
        )
