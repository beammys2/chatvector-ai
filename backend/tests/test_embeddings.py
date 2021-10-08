import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

from services.embedding_service import get_embedding, get_embeddings
import services.providers as providers_mod
import services.embedding_cache as cache_mod
from core.config import config

pytestmark = pytest.mark.asyncio

_BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(_BACKEND_DIR / ".env", override=False)

_DEFAULT_REDIS_URL = "redis://localhost:6379/0"
_REDIS_TEST_URL = (os.environ.get("REDIS_URL") or _DEFAULT_REDIS_URL).strip() or _DEFAULT_REDIS_URL

try:
    import redis as redis_lib
    REDIS_AVAILABLE = redis_lib.Redis.from_url(_REDIS_TEST_URL).ping()
except Exception:
    REDIS_AVAILABLE = False


class _FakeEmbeddingProvider:
    """Minimal stand-in that satisfies the EmbeddingProvider contract."""

    def __init__(self, dim: int = 3072, value: float = 0.1, model: str = "fake-model"):
        self._dim = dim
        self._value = value
        self._model = model
        self.call_count = 0

    @property
    def model_name(self) -> str:
        return self._model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.call_count += 1
        return [[self._value] * self._dim for _ in texts]


@pytest.fixture(autouse=True)
def reset_provider():
    """Inject a fake provider and reset after each test."""
    providers_mod._embedding_provider = _FakeEmbeddingProvider()
    yield
    providers_mod._embedding_provider = None


async def test_get_embedding_success():
    text = "Hello world"
    embedding = await get_embedding(text)

    assert isinstance(embedding, list)
    assert len(embedding) == 3072
    assert all(isinstance(v, float) for v in embedding)


async def test_get_embeddings_batch_success():
    texts = ["Hello world", "Another sentence"]
    embeddings = await get_embeddings(texts)

    assert isinstance(embeddings, list)
    assert len(embeddings) == 2

    for emb in embeddings:
        assert isinstance(emb, list)
        assert len(emb) == 3072
        assert all(isinstance(v, float) for v in emb)


async def test_embedding_dimension_consistency():
    texts = ["short text", "longer text with more content"]
    embeddings = await get_embeddings(texts)

    dims = {len(e) for e in embeddings}
    assert dims == {3072}


async def test_get_embeddings_raises_on_failure():
    """Embedding failures must propagate; the zero-vector fallback is gone."""

    class _FailingProvider:
        async def embed(self, texts):
            raise RuntimeError("forced failure")

    providers_mod._embedding_provider = _FailingProvider()

    with pytest.raises(RuntimeError, match="forced failure"):
        await get_embeddings(["this should raise"])


# ---------------------------------------------------------------------------
# Cache-enabled behavior (ENABLE_EMBEDDING_CACHE=true)
# ---------------------------------------------------------------------------

class _FailingRedis:
    """Stand-in Redis client whose every call raises RedisError."""

    def get(self, *args, **kwargs):
        raise redis_lib.exceptions.ConnectionError("forced failure")

    def set(self, *args, **kwargs):
        raise redis_lib.exceptions.ConnectionError("forced failure")


@pytest.fixture
def cache_enabled(monkeypatch):
    monkeypatch.setattr(config, "ENABLE_EMBEDDING_CACHE", True)
    monkeypatch.setattr(config, "REDIS_URL", _REDIS_TEST_URL)
    monkeypatch.setattr(cache_mod, "_redis_client", None)
    yield
    monkeypatch.setattr(cache_mod, "_redis_client", None)


@pytest.fixture(autouse=True)
def _clean_redis_for_cache_tests():
    if not REDIS_AVAILABLE:
        yield
        return
    conn = redis_lib.Redis.from_url(_REDIS_TEST_URL)
    conn.flushdb()
    yield
    conn.flushdb()


async def test_cache_disabled_calls_provider_every_time():
    """ENABLE_EMBEDDING_CACHE=false (default): no cache get/set, provider called every time."""
    provider = _FakeEmbeddingProvider()
    providers_mod._embedding_provider = provider

    await get_embeddings(["same text"])
    await get_embeddings(["same text"])

    assert provider.call_count == 2


@pytest.mark.redis_integration
@pytest.mark.skipif(not REDIS_AVAILABLE, reason="Redis not reachable")
async def test_cache_enabled_dedupes_identical_text(cache_enabled):
    provider = _FakeEmbeddingProvider()
    providers_mod._embedding_provider = provider

    result_1 = await get_embeddings(["same text"])
    result_2 = await get_embeddings(["same text"])

    assert provider.call_count == 1
    assert result_1 == result_2


@pytest.mark.redis_integration
@pytest.mark.skipif(not REDIS_AVAILABLE, reason="Redis not reachable")
async def test_cache_enabled_model_change_bypasses_cache(cache_enabled):
    provider = _FakeEmbeddingProvider(model="model-a")
    providers_mod._embedding_provider = provider

    await get_embeddings(["same text"])
    assert provider.call_count == 1

    provider._model = "model-b"
    await get_embeddings(["same text"])
    assert provider.call_count == 2


@pytest.mark.redis_integration
@pytest.mark.skipif(not REDIS_AVAILABLE, reason="Redis not reachable")
async def test_cache_enabled_partial_batch_preserves_order(cache_enabled):
    provider = _FakeEmbeddingProvider(value=0.1)
    providers_mod._embedding_provider = provider

    await get_embeddings(["cached one"])
    assert provider.call_count == 1

    provider2 = _FakeEmbeddingProvider(value=0.2)
    providers_mod._embedding_provider = provider2

    results = await get_embeddings(["cached one", "uncached two", "cached one"])

    # Only the uncached text should have hit the (new) provider.
    assert provider2.call_count == 1
    assert results[0] == results[2]
    assert results[0] != results[1]


async def test_cache_enabled_redis_down_still_succeeds(cache_enabled, monkeypatch):
    monkeypatch.setattr(cache_mod, "_redis_client", _FailingRedis())
    provider = _FakeEmbeddingProvider()
    providers_mod._embedding_provider = provider

    result = await get_embeddings(["some text"])

    assert provider.call_count == 1
    assert len(result) == 1


async def test_cache_enabled_get_embeddings_raises_on_provider_failure(cache_enabled):
    """Cache logic must not swallow provider failures."""

    class _FailingProvider:
        _model = "fake-model"

        @property
        def model_name(self) -> str:
            return self._model

        async def embed(self, texts):
            raise RuntimeError("forced failure")

    providers_mod._embedding_provider = _FailingProvider()

    with pytest.raises(RuntimeError, match="forced failure"):
        await get_embeddings(["this should raise"])
