# Memory Optimization for Render Deployment

## Problem

Render free tier: 512MB RAM limit
YOLO models: 50-100MB each
Loading all 4 models = Memory limit exceeded error

## Solution

### 1. Auto-Unload System (RAM Optimization)

- Only 1 model in memory at a time
- Models unload automatically after prediction
- Garbage collection after each unload
- Saves ~300MB RAM

### 2. Image Cleanup System (Disk Space Optimization)

- Previous uploaded images are deleted when user uploads new image
- Each animal type tracks its own last upload in session
- Images are NOT deleted immediately after prediction (user can see results)
- Images are deleted only when user uploads next image for same animal type
- Prevents disk space from filling up with old uploads

### Changes Made

1. model_service.py - Auto-clears other models before loading new one
2. prediction_routes.py - Unloads model after each prediction + cleans up old images
3. helpers.py - Added cleanup_previous_upload() and save_upload_to_session()
4. config.py - Added ENABLE_MODEL_UNLOAD and MODEL_CACHE_SIZE
5. .env - Set ENABLE_MODEL_UNLOAD=true

### Environment Variables

```bash
ENABLE_MODEL_UNLOAD=true
MODEL_CACHE_SIZE=1
```

## Savings

### RAM Savings

Before: 4 models = ~400MB
After: 1 model = ~100MB
Savings: ~300MB (75% reduction)

### Disk Space Savings

Before: All uploaded images stay forever
After: Only latest image per animal type per user
Example: User uploads 10 cat images → Only last one remains

## How Image Cleanup Works

1. User uploads cat image #1 → Saved as "abc123_cat.jpg" → Stored in session
2. User uploads cat image #2 → Delete "abc123_cat.jpg" → Save "def456_cat.jpg" → Update session
3. User uploads dog image #1 → Cat image stays (different animal type) → Save dog image
4. User uploads cat image #3 → Delete "def456_cat.jpg" → Save new one

Each animal type (cat, dog, cow, sheep) tracks separately per user session.

## Deployment

1. Ensure .env has ENABLE_MODEL_UNLOAD=true
2. Set same variable on Render dashboard
3. Deploy and monitor logs for:
   - "Unloading X model after prediction"
   - "Deleted previous upload: filename.jpg"

## Testing

Check logs for:

- "Clearing X model from memory to free RAM"
- "Unloading X model after prediction"
- "Memory cleared, now loading X model"
- "Deleted previous upload: abc123_cat.jpg"
- "Saved upload to session: def456_cat.jpg for cat"

All features work exactly the same, just with better memory and disk management.
