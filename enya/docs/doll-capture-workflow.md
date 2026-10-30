# Doll Capture Workflow

This project can now store a richer local capture set for doll or character reconstruction:

- Canonical body views:
  - `front`
  - `left`
  - `back`
  - optional `right`
- Extra body references:
  - additional full-body angles from the same pose or nearby poses
- Face references:
  - close facial angles used for likeness review and future refinement

## Recommended capture plan

For the best local-first workflow with current open-source backends:

1. Pick four clean canonical body images:
   - full body visible
   - neutral background if possible
   - stable pose
   - consistent lighting
2. Add the rest of your body shots as extra body references.
3. Add the face set separately as face references.

## Why the app stores all of them

Current open-source multi-view backends such as Hunyuan3D-2mv are generally oriented around a small set of canonical body views, not a full 16-image body-plus-face bundle.

The app therefore does two things:

1. Keeps the canonical body shots ready for current multi-view shape generation.
2. Preserves the extra body and face references locally for future texture, likeness, or manual cleanup steps.

## Viewing the result

The job detail page already supports:

- GLB preview in-browser
- drag orbit
- zoom
- preset camera buttons:
  - front
  - left
  - back
  - right
  - top

## Reality check for "super realistic" dolls

The browser viewer is ready now.

The limiting factor for realism is the backend model:

- shape generation can work with fewer views
- photoreal texture and exact face likeness usually need a stronger texture stage, more VRAM, and often some manual cleanup

So the current best practical path is:

1. Generate a strong base mesh from the clean canonical body set.
2. Review it from all sides in the browser.
3. Use the stored face and extra body references for the next refinement stage when the real backend is wired in.

