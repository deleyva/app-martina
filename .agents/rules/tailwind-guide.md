---
trigger: model_decision
description: This rule should be use when working on the forntend part, touching html files and css files
---

## Tailwind CSS Conventions

### Class Organization

```html
<!-- Order: Layout → Spacing → Sizing → Typography → Colors → Effects → States -->
<button class="
    flex items-center justify-center
    px-4 py-2 gap-2
    w-full md:w-auto
    text-sm font-medium
    bg-blue-500 text-white
    rounded-lg shadow-sm
    hover:bg-blue-600 focus:ring-2 focus:ring-blue-500
    disabled:opacity-50 disabled:cursor-not-allowed
">
    Submit
</button>
```

### Component Patterns

```html
<!-- Card component -->
<div class="bg-white rounded-lg shadow-md overflow-hidden">
    <div class="p-6">
        <h3 class="text-lg font-semibold text-gray-900">Title</h3>
        <p class="mt-2 text-gray-600">Content</p>
    </div>
    <div class="px-6 py-4 bg-gray-50 border-t">
        <button class="text-blue-500 hover:text-blue-700">Action</button>
    </div>
</div>
```

### Responsive Design

```html
<!-- Mobile-first approach -->
<div class="
    grid grid-cols-1
    sm:grid-cols-2
    lg:grid-cols-3
    xl:grid-cols-4
    gap-4 md:gap-6
">
    <!-- Grid items -->
</div>
```
