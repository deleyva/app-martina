---
trigger: model_decision
description: This rule should be use when working on the forntend part, touching html files and reading views.py files
---

## HTMX Patterns

### Base Template Setup

```html
<!-- templates/base.html -->
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}App{% endblock %}</title>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <script defer src="https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js"></script>
    <link href="{% static 'css/output.css' %}" rel="stylesheet">
</head>
<body hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>
    {% block content %}{% endblock %}
</body>
</html>
```

### Partial Updates

```html
<!-- templates/articles/list.html -->
<div id="article-list" hx-get="{% url 'article_list_partial' %}" hx-trigger="load">
    <!-- Loading state shown first -->
    <div class="animate-pulse">Loading...</div>
</div>

<!-- templates/articles/partials/list.html -->
{% for article in articles %}
<article class="border-b py-4">
    <h2>{{ article.title }}</h2>
    <button
        hx-delete="{% url 'article_delete' article.id %}"
        hx-target="closest article"
        hx-swap="outerHTML"
        hx-confirm="Delete this article?"
        class="text-red-500">
        Delete
    </button>
</article>
{% endfor %}
```

### Form Submission

```html
<!-- Inline form with HTMX -->
<form
    hx-post="{% url 'article_create' %}"
    hx-target="#article-list"
    hx-swap="afterbegin"
    hx-on::after-request="this.reset()">

    <input type="text" name="title" required
           class="border rounded px-3 py-2 w-full">
    <button type="submit"
            class="bg-blue-500 text-white px-4 py-2 rounded">
        Add Article
    </button>
</form>
```

### Search with Debounce

```html
<input type="search" name="q"
       hx-get="{% url 'article_search' %}"
       hx-trigger="input changed delay:300ms"
       hx-target="#search-results"
       placeholder="Search articles...">

<div id="search-results"></div>
```

## Common Patterns

### Flash Messages with HTMX

```html
<!-- In base.html -->
<div id="messages" class="fixed top-4 right-4 space-y-2">
    {% include "partials/messages.html" %}
</div>

<!-- partials/messages.html -->
{% for message in messages %}
<div x-data="{ show: true }"
     x-show="show"
     x-init="setTimeout(() => show = false, 5000)"
     x-transition
     class="px-4 py-3 rounded-lg shadow-lg
            {% if message.tags == 'success' %}bg-green-500{% endif %}
            {% if message.tags == 'error' %}bg-red-500{% endif %}
            text-white">
    {{ message }}
</div>
{% endfor %}
```

### Infinite Scroll

```html
<div id="item-list">
    {% include "items/partials/list.html" %}
</div>

<!-- items/partials/list.html -->
{% for item in items %}
    <div class="item">{{ item.name }}</div>
{% endfor %}

{% if has_next %}
<div hx-get="{% url 'items_list' %}?page={{ next_page }}"
     hx-trigger="revealed"
     hx-swap="outerHTML"
     class="loading">
    Loading more...
</div>
{% endif %}
```

### Optimistic UI Updates

```html
<button hx-post="{% url 'like_item' item.id %}"
        hx-swap="outerHTML"
        hx-indicator="#like-spinner"
        @click="liked = true"
        x-data="{ liked: {{ item.is_liked|yesno:'true,false' }} }"
        :class="liked ? 'text-red-500' : 'text-gray-400'">
    <span x-text="liked ? '❤️' : '🤍'"></span>
    <span id="like-spinner" class="htmx-indicator">...</span>
</button>
```

