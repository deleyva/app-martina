---
trigger: model_decision
description: This rule should be use when working on the forntend part, touching html files.
---

## Alpine.js Patterns

### Component Structure

```html
<!-- Dropdown component -->
<div x-data="{ open: false }" class="relative">
    <button @click="open = !open" class="px-4 py-2 bg-gray-100 rounded">
        Menu
    </button>

    <div x-show="open"
         x-transition
         @click.outside="open = false"
         class="absolute mt-2 bg-white shadow-lg rounded">
        <a href="#" class="block px-4 py-2 hover:bg-gray-100">Option 1</a>
        <a href="#" class="block px-4 py-2 hover:bg-gray-100">Option 2</a>
    </div>
</div>
```

### HTMX + Alpine Integration

```html
<!-- Modal with Alpine state, content loaded via HTMX -->
<div x-data="{ showModal: false }">
    <button @click="showModal = true"
            hx-get="{% url 'article_form' %}"
            hx-target="#modal-content">
        New Article
    </button>

    <div x-show="showModal"
         x-transition
         class="fixed inset-0 bg-black/50 flex items-center justify-center">
        <div class="bg-white p-6 rounded-lg max-w-lg w-full"
             @click.outside="showModal = false">
            <div id="modal-content">
                <!-- HTMX loads content here -->
            </div>
        </div>
    </div>
</div>
```

### Form Validation

```html
<form x-data="{
    title: '',
    isValid: false,
    validate() {
        this.isValid = this.title.length >= 3
    }
}">
    <input type="text"
           x-model="title"
           @input="validate()"
           class="border rounded px-3 py-2">

    <button type="submit"
            :disabled="!isValid"
            :class="isValid ? 'bg-blue-500' : 'bg-gray-300'"
            class="px-4 py-2 rounded text-white">
        Submit
    </button>
</form>
```