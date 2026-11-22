import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Stub external deps so importing app.store does not require them installed.
sys.modules.setdefault("chromadb", types.SimpleNamespace(
    PersistentClient=lambda **_: types.SimpleNamespace(
        get_or_create_collection=lambda **__: None,
    ),
))
sys.modules.setdefault("chromadb.config", types.SimpleNamespace(
    Settings=lambda **_: None,
))
sys.modules.setdefault("fastembed", types.SimpleNamespace(
    TextEmbedding=lambda **_: None,
))
