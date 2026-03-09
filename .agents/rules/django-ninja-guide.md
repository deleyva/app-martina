---
trigger: model_decision
description: This rule would be applied when working with the API part of this web app.
---

## Django Ninja API

### Router Organization

```python
# api/routers/articles.py
from ninja import Router
from typing import List

router = Router(tags=["articles"])

@router.get("/", response=List[ArticleSchema])
def list_articles(request):
    return ArticleService.get_published()

@router.post("/", response=ArticleSchema)
def create_article(request, payload: ArticleCreateSchema):
    return ArticleService.create(payload, request.user)

@router.get("/{article_id}", response=ArticleSchema)
def get_article(request, article_id: int):
    return get_object_or_404(Article, id=article_id)
```

### Schema Conventions

```python
# api/schemas/articles.py
from ninja import Schema
from datetime import datetime

class ArticleSchema(Schema):
    id: int
    title: str
    slug: str
    author_name: str  # Computed field
    created_at: datetime

    @staticmethod
    def resolve_author_name(obj):
        return obj.author.get_full_name()

class ArticleCreateSchema(Schema):
    title: str
    content: str

    class Config:
        # Validate on assignment
        validate_assignment = True
```

### Main API Setup

```python
# config/api.py
from ninja import NinjaAPI
from api.routers import articles, users

api = NinjaAPI(
    title="Project API",
    version="1.0.0",
    docs_url="/api/docs"
)

api.add_router("/articles", articles.router)
api.add_router("/users", users.router)
```
