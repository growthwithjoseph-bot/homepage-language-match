"""Point the global config DB at a throwaway path for the whole test session,
so API tests (which use the singleton config) never touch the real data/ DB.
Set before any backend module imports and builds the config singleton."""
import os
import tempfile

_tmp = os.path.join(tempfile.mkdtemp(prefix="tc-test-"), "test.db")
os.environ.setdefault("TC_DB_PATH", _tmp)
