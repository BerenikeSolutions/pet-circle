---
name: python-patterns
description: Comprehensive Python skill covering Pythonic idioms, type hints, async/await, dataclasses, pytest, Django ORM, security, TDD workflow, and verification gates.
---

# Python Development Patterns

Idiomatic Python and production-grade Django practices — from clean code patterns to TDD and pre-deploy verification.

---

## 1. Pythonic Idioms and Code Style

Use `use v5.36`-equivalent defaults: type hints everywhere, `with` for resources, EAFP over LBYL, f-strings, `pathlib.Path`, `enumerate`, and list/generator comprehensions.

```python
# Good: Readable, explicit, typed
def get_active_users(users: list[User]) -> list[User]:
    return [u for u in users if u.is_active]

# Good: EAFP
def get_value(d: dict, key: str) -> Any:
    try:
        return d[key]
    except KeyError:
        return default_value
```

**Rule:** Never use mutable default arguments (`def f(items=[])`). Use `isinstance` not `type()`. Compare `None` with `is`, not `==`. Never use `from module import *`.

---

## 2. Type Hints

Use built-in generic types (Python 3.9+). Use `Protocol` for duck typing. Use `TypeVar` for generics.

```python
from typing import Protocol, TypeVar

T = TypeVar('T')

def first(items: list[T]) -> T | None:
    return items[0] if items else None

class Renderable(Protocol):
    def render(self) -> str: ...

def render_all(items: list[Renderable]) -> str:
    return "\n".join(item.render() for item in items)
```

Run `mypy .` with `disallow_untyped_defs = true` in `pyproject.toml`.

---

## 3. Dataclasses and Named Tuples

Use `@dataclass` for data containers; use `NamedTuple` for immutable records:

```python
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class User:
    id: str
    name: str
    email: str
    created_at: datetime = field(default_factory=datetime.now)
    is_active: bool = True

    def __post_init__(self):
        if "@" not in self.email:
            raise ValueError(f"Invalid email: {self.email}")
```

---

## 4. Async/Await

Use `asyncio.gather` for concurrent I/O. Use `async with` for async context managers.

```python
import asyncio
import aiohttp

async def fetch_all(urls: list[str]) -> dict[str, str]:
    async def fetch(url: str) -> str:
        async with aiohttp.ClientSession() as s:
            async with s.get(url) as r:
                return await r.text()
    results = await asyncio.gather(*[fetch(u) for u in urls], return_exceptions=True)
    return dict(zip(urls, results))
```

---

## 5. pytest: Fixtures, Parametrize, Mocking

Write tests first (RED-GREEN-REFACTOR). Use fixtures for shared setup, `parametrize` for multiple inputs, `patch` for mocks.

```python
import pytest
from unittest.mock import patch

@pytest.fixture
def db_session():
    session = Session(bind=engine)
    session.begin_nested()
    yield session
    session.rollback()
    session.close()

@pytest.mark.parametrize("a,b,expected", [(2,3,5),(0,0,0),(-1,1,0)])
def test_add(a, b, expected):
    assert add(a, b) == expected

@patch("myapp.external_api_call")
def test_with_mock(api_mock):
    api_mock.return_value = {"status": "ok"}
    result = my_function()
    api_mock.assert_called_once()
    assert result["status"] == "ok"
```

Use `tmp_path` for temp files. Use `pytest.raises` — never catch exceptions in tests directly.

**Rule:** Target 80%+ overall coverage; 100% on critical business logic. Run `pytest --cov=mypackage`.

---

## 6. Django ORM Patterns

Use custom `QuerySet` classes for reusable query logic. Use `select_related` for FK, `prefetch_related` for M2M:

```python
class ProductQuerySet(models.QuerySet):
    def active(self):      return self.filter(is_active=True)
    def with_category(self): return self.select_related('category')
    def in_stock(self):    return self.filter(stock__gt=0)
    def search(self, q):
        return self.filter(
            models.Q(name__icontains=q) | models.Q(description__icontains=q)
        )

class Product(models.Model):
    objects = ProductQuerySet.as_manager()
```

Use `@transaction.atomic` for multi-step writes. Use `bulk_create`/`bulk_update` for large operations. Add `Meta.indexes` for frequently filtered fields.

**Rule:** Never use N+1 queries. Always check with Django Debug Toolbar before shipping.

---

## 7. Django Security

Production settings — mandatory:

```python
DEBUG = False
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_PRELOAD = True
X_FRAME_OPTIONS = 'DENY'
SECRET_KEY = os.environ['DJANGO_SECRET_KEY']
```

SQL injection: always use ORM or parameterized `raw()` — never interpolate user input into queries.

XSS: Django auto-escapes template vars. Never use `mark_safe(user_input)`. Use `format_html` for HTML with variables.

CSRF: enabled by default. Use `{% csrf_token %}` in forms. Set `CSRF_TRUSTED_ORIGINS` for API consumers.

DRF auth/throttle:

```python
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework_simplejwt.authentication.JWTAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_THROTTLE_RATES': {'anon': '100/day', 'user': '1000/day'},
}
```

**Rule:** Never commit `SECRET_KEY`. Use `python-decouple` or `django-environ` for all secrets.

---

## 8. Django TDD Workflow

Use `pytest-django` with `--reuse-db --nomigrations` for speed. Use `factory_boy` instead of manual object creation.

```python
# tests/factories.py
class UserFactory(factory.django.DjangoModelFactory):
    class Meta: model = User
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    password = factory.PostGenerationMethodCall('set_password', 'testpass123')

# tests/conftest.py
@pytest.fixture
def api_client(): return APIClient()

@pytest.fixture
def authenticated_api_client(api_client, db):
    user = UserFactory()
    api_client.force_authenticate(user=user)
    return api_client
```

Test DRF endpoints against status codes and response shape:

```python
def test_create_product_authorized(authenticated_api_client, db):
    url = reverse('api:product-list')
    response = authenticated_api_client.post(url, {'name': 'X', 'price': '9.99', 'stock': 5})
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data['name'] == 'X'
```

Coverage targets: Models 90%+, Serializers 85%+, Views 80%+, Services 90%+.

---

## 9. Django Verification Gates

Run this pipeline before every PR and deployment:

```bash
# 1. Code quality
mypy . && ruff check . --fix && black . && isort .
python manage.py check --deploy

# 2. Migrations
python manage.py makemigrations --check
python manage.py migrate --plan

# 3. Tests + coverage
pytest --cov=apps --cov-report=term-missing --reuse-db

# 4. Security
bandit -r . && pip-audit && safety check
python manage.py check --deploy

# 5. Static assets
python manage.py collectstatic --noinput
```

Pre-deploy checklist: `DEBUG=False`, `SECRET_KEY` set, `ALLOWED_HOSTS` set, HTTPS enabled, migrations applied, coverage ≥ 80%, no vulnerable dependencies, no hardcoded secrets in diff.

**Rule:** Block merges on failing tests, security issues, or `DEBUG=True` in production settings.
