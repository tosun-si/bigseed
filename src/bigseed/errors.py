class BigSeedError(Exception):
    """An error shown as a message by the CLI, with the exit code 2."""


class PackError(BigSeedError):
    """An invalid or incomplete pack."""


class SeedError(BigSeedError):
    """A seed refused: unknown or protected environment, unmapped dataset..."""
