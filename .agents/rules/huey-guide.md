---
trigger: model_decision
description: This rule should be use when working on background tasks, editing tasks.py, views.py, services.py, base.py, and other config files.
---

## django-huey Background Tasks

### Task Definition

```python
# tasks.py
from huey.contrib.djhuey import task, periodic_task, db_task
from huey import crontab

# Simple background task
@task()
def send_welcome_email(user_id: int):
    user = User.objects.get(id=user_id)
    send_email(user.email, "Welcome!", "welcome.html")

# Database task (auto-closes connections)
@db_task()
def process_upload(upload_id: int):
    upload = Upload.objects.get(id=upload_id)
    # Heavy processing...
    upload.status = "completed"
    upload.save()

# Periodic task
@periodic_task(crontab(minute="0", hour="*/6"))
def cleanup_old_sessions():
    Session.objects.filter(
        expire_date__lt=timezone.now()
    ).delete()

# Task with retry
@task(retries=3, retry_delay=60)
def sync_external_api(resource_id: int):
    # Will retry 3 times with 60s delay on failure
    pass
```

### Calling Tasks

```python
# In views or services
from .tasks import send_welcome_email, process_upload

def register_user(request):
    user = UserService.create(request.POST)
    # Fire and forget - returns immediately
    send_welcome_email(user.id)
    return redirect("home")

# Get result (if needed)
def process_file(request):
    upload = Upload.objects.create(file=request.FILES["file"])
    result = process_upload(upload.id)
    # result is a TaskResultWrapper
    # result.get(blocking=True) to wait for result
    return JsonResponse({"task_id": result.id})
```

### Configuration

```python
# settings/base.py
HUEY = {
    "huey_class": "huey.RedisHuey",
    "name": "project-tasks",
    "connection": {
        "host": env("REDIS_HOST", default="localhost"),
        "port": 6379,
        "db": 1,
    },
    "immediate": env.bool("HUEY_IMMEDIATE", default=False),  # True for testing
    "consumer": {
        "workers": 4,
        "worker_type": "thread",
    },
}
```