#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2026, Bodo Schulz <bodo@boone-schulz.de>

from __future__ import absolute_import, division, print_function

import hashlib
# import os
import shutil
from pathlib import Path
from typing import Optional

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import fetch_url


class PiholeDownloadFTL:
    """
    Lädt das pihole-FTL Binary und dessen SHA1-Prüfsumme in ein Cache-Verzeichnis.

    Layout:
        {cache_dir}/{ftl_tag}/pihole-FTL-{arch}
        {cache_dir}/{ftl_tag}/pihole-FTL-{arch}.sha1

    Idempotent: Bereits gecachte und verifizierte Dateien werden nicht erneut heruntergeladen.
    """

    def __init__(self, module: AnsibleModule, cache_dir: str):
        """ """
        self.module = module
        self.module.log(f"PiholeDownloadFTL::__init(module, cache_dir: {cache_dir})")

        self.cache_dir = Path(cache_dir)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def download(
        self,
        ftl_tag: str,
        binary_name: str,
        binary_url: str,
        sha1_url: str,
    ) -> dict:
        """
        Lädt Binary + SHA1 in {cache_dir}/{ftl_tag}/ herunter.
        Gibt Pfade und Prüfstatus zurück.
        Überspringt den Download wenn die Datei bereits vorhanden und gültig ist.
        """
        self.module.log(
            f"PiholeDownloadFTL::download(ftl_tag={ftl_tag}, binary_name={binary_name})"
        )

        target_dir = self.cache_dir / "ftl" / ftl_tag
        target_dir.mkdir(parents=True, exist_ok=True)

        binary_path = target_dir / binary_name
        sha1_path = target_dir / f"{binary_name}.sha1"

        # SHA1 zuerst holen (klein, immer aktuell)
        expected_sha1 = self._fetch_sha1(sha1_url, sha1_path)

        # Binary nur herunterladen wenn nötig
        if binary_path.exists() and expected_sha1:
            if self._verify_sha1(binary_path, expected_sha1):
                # self.module.log(f"  [cache HIT] {binary_path} – checksum OK")
                return self._result(
                    binary_path, sha1_path, expected_sha1, changed=False
                )
            else:
                # self.module.log(f"  [cache STALE] {binary_path} – checksum mismatch, re-downloading")
                binary_path.unlink()

        # Download
        self._fetch_binary(binary_url, binary_path)

        # Verifizieren
        if expected_sha1 and not self._verify_sha1(binary_path, expected_sha1):
            binary_path.unlink()
            self.module.fail_json(
                msg=f"SHA1 mismatch for {binary_name} after download. "
                f"Expected: {expected_sha1}"
            )

        binary_path.chmod(0o755)
        self.module.log(f"  [downloaded] {binary_path}")

        return self._result(binary_path, sha1_path, expected_sha1, changed=True)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _fetch_sha1(self, sha1_url: str, sha1_path: Path) -> Optional[str]:
        """Holt SHA1-Prüfsumme. Gibt Hash-String zurück oder None."""
        self.module.log(
            f"PiholeDownloadFTL::_fetch_sha1(sha1_url: {sha1_url}, sha1_path: {sha1_path})"
        )

        resp, info = fetch_url(self.module, sha1_url, method="GET")
        if info["status"] != 200:
            self.module.warn(
                f"Could not fetch SHA1 from {sha1_url} (HTTP {info['status']})"
            )
            return None

        content = resp.read().decode("utf-8").strip()
        # Format: "<hash>  filename" oder "<hash>"
        sha1_hash = content.split()[0]

        sha1_path.write_text(f"{sha1_hash}  {sha1_path.stem}\n", encoding="utf-8")
        return sha1_hash

    def _fetch_binary(self, url: str, dest: Path) -> None:
        """Streamt Binary direkt in die Zieldatei."""
        self.module.log(f"PiholeDownloadFTL::_fetch_binary(url: {url}, dest: {dest})")

        resp, info = fetch_url(self.module, url, method="GET")
        if info["status"] != 200:
            self.module.fail_json(
                msg=f"Binary download failed: HTTP {info['status']} for {url}"
            )

        with dest.open("wb") as f:
            shutil.copyfileobj(resp, f)

    @staticmethod
    def _verify_sha1(file_path: Path, expected: str) -> bool:
        """ """
        h = hashlib.sha1()
        with file_path.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest() == expected

    @staticmethod
    def _result(
        binary_path: Path, sha1_path: Path, sha1: Optional[str], changed: bool
    ) -> dict:
        """ """
        return dict(
            changed=changed,
            binary_path=str(binary_path),
            sha1_path=str(sha1_path),
            sha1=sha1,
            sha1_verified=(sha1 is not None),
        )
