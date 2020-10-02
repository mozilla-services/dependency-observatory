import enum


class LanguageEnum(enum.Enum):
    node = 1
    rust = 2
    python = 3


class PackageManagerEnum(enum.Enum):
    npm = 1
    yarn = 2


class ScanStatusEnum(enum.Enum):
    queued = 1
    started = 2
    failed = 3
    succeeded = 4
    canceled = 5

    # transitions from queued -> started -> {succeeded, failed}
    # and queued -> canceled
