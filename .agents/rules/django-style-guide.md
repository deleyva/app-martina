---
trigger: always_on
---

## Django Conventions

### Project Structure

```
project/
├── apps/
│   ├── core/              # Shared models, utils, base classes
│   ├── users/             # User management
│   └── [feature]/         # Feature-specific apps
├── config/
│   ├── settings/
│   │   ├── base.py
│   │   ├── local.py
│   │   └── production.py
│   ├── urls.py
│   └── wsgi.py
├── static/
├── templates/
│   ├── base.html
│   ├── partials/          # HTMX partial templates
│   └── components/        # Reusable template components
├── justfile
├── Dockerfile
└── docker-compose.yml
```

### Models

```python
# Always use explicit related_name
class Article(models.Model):
    author = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="articles"  # Always explicit
    )

    # Use TextChoices for status fields
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT
    )

    # Always add timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
```

### Views (Keep Thin)

```python
# views.py - Keep minimal, delegate to services
from django.shortcuts import render, get_object_or_404
from .services import ArticleService

def article_list(request):
    articles = ArticleService.get_published()
    return render(request, "articles/list.html", {"articles": articles})

# For HTMX partials, return partial templates
def article_list_partial(request):
    articles = ArticleService.get_published()
    return render(request, "articles/partials/list.html", {"articles": articles})
```

### Services (Business Logic Here)

```python
# services.py - All business logic lives here
class ArticleService:
    @staticmethod
    def get_published():
        return Article.objects.filter(
            status=Article.Status.PUBLISHED
        ).select_related("author")

    @staticmethod
    def publish(article: Article, user: User) -> Article:
        if not user.has_perm("articles.publish"):
            raise PermissionError("Cannot publish")
        article.status = Article.Status.PUBLISHED
        article.published_at = timezone.now()
        article.save(update_fields=["status", "published_at", "updated_at"])
        return article
```
