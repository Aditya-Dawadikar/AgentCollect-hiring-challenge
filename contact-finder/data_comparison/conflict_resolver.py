"""Resolves the primary identity (name + role) from registry/listing data
and flags genuine name conflicts between the two sources.

Registry is the legal-ownership record (PLAN.md "Sources & strategy"), so
it wins authority ties. A "conflict" is recorded whenever both sources name
someone and those names do NOT fuzzy-match -- registry is still used as the
best guess, but the disagreement is surfaced for human review.
"""

from data_comparison.fuzzy_matcher import FuzzyNameMatcher


class ConflictResolver:
    def resolve(self, registry: dict | None, listing: dict | None,
                 name_matcher: FuzzyNameMatcher) -> tuple[dict, list[dict]]:
        registry_name = (registry or {}).get("name")
        listing_name = (listing or {}).get("name")
        registry_role = (registry or {}).get("role")

        conflicts: list[dict] = []

        if registry_name and listing_name:
            chosen_name, name_source = registry_name, "registry"
            if not name_matcher.match(registry_name, listing_name):
                conflicts.append({
                    "field": "name",
                    "registry": registry_name,
                    "listing": listing_name,
                    "reason": (
                        f"registry name {registry_name!r} and listing name "
                        f"{listing_name!r} do not fuzzy-match "
                        f"(score={name_matcher.score(registry_name, listing_name)}, "
                        f"threshold={name_matcher.threshold})"
                    ),
                })
        elif registry_name:
            chosen_name, name_source = registry_name, "registry"
        elif listing_name:
            chosen_name, name_source = listing_name, "listing"
        else:
            chosen_name, name_source = None, None

        chosen = {
            "name": name_matcher.normalize(chosen_name) or None,
            "role": registry_role,
            "name_source": name_source,
        }
        return chosen, conflicts
