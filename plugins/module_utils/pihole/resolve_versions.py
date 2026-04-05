#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2026, Bodo Schulz <bodo@boone-schulz.de>

from __future__ import absolute_import, division, print_function

import json
import os
from datetime import datetime
from typing import Optional

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import fetch_url
from ansible_collections.bodsch.dns.plugins.module_utils.github_cache import GitHubCache

DOCUMENTATION = r"""
---
module: pihole_resolve_versions
short_description: Resolve matching FTL and Web UI versions for a given pi-hole Core version
description:
  - Determines which FTL and Web UI versions were current at the time a given Core version
    was released.
  - This mirrors the behaviour of basic-install.sh at that point in time.
  - GitHub API responses are cached locally to avoid rate limiting.
options:
  core_version:
    description: Core version tag from pi-hole/pi-hole, e.g. "v6.1"
    required: true
    type: str
  arch:
    description: >
      Target architecture. Auto-detected from uname if omitted.
      Valid values: amd64, 386, arm64, armhf, riscv64
    required: false
    type: str
  cache_dir:
    description: Directory for GitHub API response cache.
    required: false
    type: str
    default: ~/.cache/ansible/pihole/github
  cache_minutes:
    description: TTL for the FTL and Web release list cache (minutes).
    required: false
    type: int
    default: 60
"""

GITHUB_API = "https://api.github.com"
FTL_DOWNLOAD_BASE = "https://github.com/pi-hole/FTL/releases/download"

ARCH_MAP = {
    "x86_64":  "amd64",
    "i386":    "386",
    "i686":    "386",
    "aarch64": "arm64",
    "armv7l":  "armhf",
    "armv6l":  "armhf",
    "riscv64": "riscv64",
}


class PiholeResolveVersions:

    def __init__(
        self,
        module: AnsibleModule,
        core_version: str,
        arch: Optional[str] = None,
        cache_dir: Optional[str] = None,
        cache_minutes: int = 60,
    ):
        self.module = module
        self.core_version = core_version if core_version.startswith("v") else f"v{core_version}"
        self.arch_override = arch

        _cache_dir = cache_dir or os.path.expanduser("~/.cache/ansible/pihole/github")
        self._cache = GitHubCache(
            module=module,
            cache_dir=_cache_dir,
            cache_file="",
            cache_minutes=cache_minutes,
        )
        # Core-Release-Datum ändert sich nie → sehr langer TTL
        self._core_cache_minutes = 60 * 24 * 365
        # FTL/Web Release-Liste: Standard-TTL
        self._list_cache_minutes = cache_minutes

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def run(self) -> dict:
        self.module.log(f"PiholeResolveVersions::run(core_version={self.core_version})")

        ftl_arch    = self._resolve_arch()
        binary_name = f"pihole-FTL-{ftl_arch}"

        # 1. Release-Datum des Core-Tags
        core_date = self._get_core_release_date(self.core_version)

        # 2. FTL-Version zum Zeitpunkt des Core-Releases
        ftl_releases = self._get_releases(
            repo="pi-hole/FTL",
            cache_filename="ftl_releases.json",
        )
        ftl_release = self._find_matching_release(core_date, ftl_releases, label="FTL")
        ftl_tag = ftl_release["tag_name"]

        # 3. Web UI-Version zum Zeitpunkt des Core-Releases
        web_releases = self._get_releases(
            repo="pi-hole/web",
            cache_filename="web_releases.json",
        )
        web_release = self._find_matching_release(core_date, web_releases, label="Web")
        web_tag = web_release["tag_name"]

        urls = self._build_ftl_urls(ftl_tag, binary_name)

        return dict(
            core_version=self.core_version,
            core_release_date=core_date.isoformat(),
            # FTL
            ftl_version=ftl_tag.lstrip("v"),
            ftl_tag=ftl_tag,
            ftl_release_date=ftl_release["published_at"],
            ftl_binary_name=binary_name,
            **urls,
            # Web UI
            web_version=web_tag.lstrip("v"),
            web_tag=web_tag,
            web_release_date=web_release["published_at"],
        )

    # ------------------------------------------------------------------
    # Private: Architecture
    # ------------------------------------------------------------------

    def _resolve_arch(self) -> str:
        if self.arch_override:
            return self.arch_override
        machine = os.uname().machine
        arch = ARCH_MAP.get(machine)
        if not arch:
            self.module.fail_json(
                msg=(
                    f"Unsupported architecture '{machine}'. "
                    f"Set 'arch' explicitly. Valid values: {sorted(set(ARCH_MAP.values()))}"
                )
            )
        return arch

    # ------------------------------------------------------------------
    # Private: GitHub API (with cache)
    # ------------------------------------------------------------------

    def _gh_get(self, path: str, cache_filename: str, cache_minutes: int) -> dict | list:
        """GitHub API GET mit transparentem Datei-Cache."""
        cache_path = self._cache.cache_path(cache_filename)

        original = self._cache.cache_minutes
        self._cache.cache_minutes = cache_minutes
        cached = self._cache.cached_data(cache_path)
        self._cache.cache_minutes = original

        if cached is not None:
            self.module.log(f"  [cache HIT] {cache_filename}")
            return cached

        self.module.log(f"  [cache MISS] {cache_filename} → fetching {GITHUB_API}{path}")

        url = f"{GITHUB_API}{path}"
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        resp, info = fetch_url(self.module, url, headers=headers, method="GET")
        if info["status"] != 200:
            self.module.fail_json(
                msg=f"GitHub API error {info['status']} for {url}: {info.get('msg', '')}"
            )

        data = json.loads(resp.read().decode("utf-8"))
        self._cache.write_cache(cache_path, data)
        return data

    def _get_core_release_date(self, core_version: str) -> datetime:
        safe_name = core_version.replace("/", "_")
        data = self._gh_get(
            path=f"/repos/pi-hole/pi-hole/releases/tags/{core_version}",
            cache_filename=f"core_release_{safe_name}.json",
            cache_minutes=self._core_cache_minutes,
        )
        published = data.get("published_at")
        if not published:
            self.module.fail_json(
                msg=(
                    f"Core release {core_version} not found or missing published_at. "
                    f"See: https://github.com/pi-hole/pi-hole/releases/tag/{core_version}"
                )
            )
        return self._parse_iso(published)

    def _get_releases(self, repo: str, cache_filename: str) -> list[dict]:
        return self._gh_get(
            path=f"/repos/{repo}/releases?per_page=100",
            cache_filename=cache_filename,
            cache_minutes=self._list_cache_minutes,
        )

    # ------------------------------------------------------------------
    # Private: Version matching
    # ------------------------------------------------------------------

    def _find_matching_release(
        self,
        core_release_date: datetime,
        releases: list[dict],
        label: str,
    ) -> dict:
        """
        Neueste Release-Version die VOR oder AM SELBEN ZEITPUNKT wie das
        Core-Release veröffentlicht wurde.
        Pre-releases und Drafts werden ignoriert.
        """
        candidates = []
        for rel in releases:
            published = rel.get("published_at")
            if not published or rel.get("prerelease") or rel.get("draft"):
                continue
            rel_date = self._parse_iso(published)
            if rel_date <= core_release_date:
                candidates.append((rel_date, rel))

        if not candidates:
            self.module.fail_json(
                msg=(
                    f"No {label} release found at or before {core_release_date.isoformat()}. "
                    f"The oldest available {label} release is newer than the Core release."
                )
            )

        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    # ------------------------------------------------------------------
    # Private: Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_iso(dt_str: str) -> datetime:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))

    @staticmethod
    def _build_ftl_urls(ftl_tag: str, binary_name: str) -> dict:
        base = f"{FTL_DOWNLOAD_BASE}/{ftl_tag}"
        return {
            "ftl_binary_url": f"{base}/{binary_name}",
            "ftl_sha1_url":   f"{base}/{binary_name}.sha1",
        }
