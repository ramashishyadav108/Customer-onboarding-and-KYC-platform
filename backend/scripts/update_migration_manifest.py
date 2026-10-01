"""Register NEW migration files in migrations/manifest.json; never rewrites existing entries."""

import sys

from onboardx.config.constants import MIGRATION_MANIFEST, MIGRATION_VERSIONS_DIR
from onboardx.config.migration_guard import MigrationGuardError, update_manifest


def main() -> int:
    try:
        added = update_manifest(MIGRATION_VERSIONS_DIR, MIGRATION_MANIFEST)
    except MigrationGuardError as error:
        sys.stderr.write(f"{error}\n")
        return 1
    sys.stdout.write("registered: " + (", ".join(added) if added else "nothing new") + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
