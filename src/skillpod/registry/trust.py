"""Trust-policy enforcement for registry results.

Implements `add-skillpod-trust-and-search` §2.2 / registry-discovery spec
"Requirement: Trust policy enforcement on registry results".

`enforce` is intentionally a pure function with no side effects — Phase B
will wire it into the install pipeline. Phase A only delivers the API.
"""

from __future__ import annotations

from skillpod.manifest.models import RegistrySkillsShPolicy
from skillpod.registry.errors import RegistryError
from skillpod.registry.skills_sh import RepoInfo

__all__ = [
    "TrustError",
    "enforce",
]


class TrustError(RegistryError):
    """A registry result failed one or more trust-policy thresholds.

    ``reasons`` lists every threshold that was violated so the user can fix
    them all at once (spec: "report ALL violations in one error, not the
    first one only").
    """

    def __init__(self, reasons: list[str]) -> None:
        self.reasons: list[str] = reasons
        super().__init__("; ".join(reasons))


def enforce(policy: RegistrySkillsShPolicy, repo: RepoInfo) -> RepoInfo:
    """Validate *repo* against *policy*; return *repo* unchanged on success.

    Raises :class:`TrustError` listing every threshold that failed when the
    result does not satisfy the policy.  Three conditions are checked
    (registry-discovery spec §ADDED):

    - ``verified is False`` and ``allow_unverified is False``
    - ``installs < min_installs``
    - ``stars < min_stars``
    """
    reasons: list[str] = []

    if not repo.verified and not policy.allow_unverified:
        reasons.append(
            f"skill '{repo.name}' is not verified and allow_unverified is false"
        )
    if repo.installs < policy.min_installs:
        reasons.append(
            f"skill '{repo.name}' has {repo.installs} installs"
            f" (policy requires {policy.min_installs})"
        )
    if repo.stars < policy.min_stars:
        reasons.append(
            f"skill '{repo.name}' has {repo.stars} stars"
            f" (policy requires {policy.min_stars})"
        )

    if reasons:
        raise TrustError(reasons)

    return repo
