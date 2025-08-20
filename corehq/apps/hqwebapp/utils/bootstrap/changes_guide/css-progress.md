The markup for progress bars has been updated. We did as many find-replace changes
as possible, the rest needs more careful attention. Note changes to accessibility labels.

An EXAMPLE for how to apply this change is provided below.
Please see docs for further details.

Previously:
```
<div class="progress">
    <div class="progress-bar" role="progressbar" aria-valuenow="60" aria-valuemin="0" aria-valuemax="100" style="width: 60%;">
        <span class="sr-only">60% Complete</span>
    </div>
</div>
```

Now:
```
<div class="progress" role="progressbar" aria-label="Basic example" aria-valuenow="60" aria-valuemin="0" aria-valuemax="100">
  <div class="progress-bar" style="width: 60%"></div>
</div>
```

See: https://getbootstrap.com/docs/5.3/components/progress/
